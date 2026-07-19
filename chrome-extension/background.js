"use strict";

const API_BASES = Object.freeze([
  "http://127.0.0.1:8766",
  "http://localhost:8766",
]);
const STORAGE_KEY = "eagleeyeBrowserStateV1";
const STATE_VERSION = 1;
const SESSION_ID_PATTERN = /^[a-f0-9]{32}$/u;
const SAFE_ACTIONS = new Set(["click", "fill", "select", "check"]);
const SAFE_VALUE_TYPES = new Set([
  "none",
  "text",
  "email",
  "search",
  "tel",
  "url",
  "number",
  "date",
  "time",
  "datetime-local",
  "month",
  "week",
  "color",
  "range",
  "select-one",
  "select-multiple",
  "checkbox",
  "radio",
  "contenteditable",
  "sensitive",
  "unknown",
  "navigation",
  "snapshot",
]);
const SESSION_STATUSES = new Set(["recording", "generated", "running", "passed", "failed"]);
const CASE_SOURCES = new Set(["recording", "ai", "deterministic"]);
const CASE_PRIORITIES = new Set(["critical", "high", "medium", "low"]);
const QUALITY_DECISIONS = new Set([
  "PASS",
  "PASS_WITH_WARNING",
  "MANUAL_REVIEW",
  "FAIL",
  "BLOCKED",
]);
const SECRET_QUERY_KEY = /(token|secret|password|passwd|api[_-]?key|auth|code|session|nonce|wpnonce|rest[_-]?nonce)/iu;
const MAX_JSON_RESPONSE = 5_000_000;
const MAX_REPORT_RESPONSE = 2_000_000;
const MAX_SCREENSHOT_DATA_URL = 4_000_000;
const API_START_GUIDANCE =
  "EagleEye APIに接続できません。リポジトリで .\\scripts\\start-eagleeye.ps1 を実行し、http://127.0.0.1:8766/health を確認してください。";

class ExtensionError extends Error {
  constructor(kind, message, status = null) {
    super(message);
    this.name = "ExtensionError";
    this.kind = kind;
    this.status = status;
  }
}

let operationQueue = Promise.resolve();

void chrome.storage.session
  .setAccessLevel({ accessLevel: "TRUSTED_CONTEXTS" })
  .catch(() => undefined);

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!isPlainObject(message) || sender.id !== chrome.runtime.id) {
    return false;
  }

  const task = routeMessage(message, sender);
  if (!task) {
    return false;
  }

  task
    .then((result) => sendResponse({ ok: true, ...result }))
    .catch((error) => sendResponse({ ok: false, error: publicError(error) }));
  return true;
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status !== "complete") {
    return;
  }
  void enqueueOperation(() => resumeAfterNavigation(tabId, tab)).catch(() => undefined);
});

chrome.tabs.onRemoved.addListener((tabId) => {
  void enqueueOperation(async () => {
    const state = await readState();
    if (!state || !state.recording || state.tabId !== tabId) {
      return;
    }
    await writeState({
      ...state,
      tabId: null,
      windowId: null,
      recording: false,
      updatedAt: Date.now(),
      lastError: "記録中のタブが閉じられたため停止しました。",
    });
  }).catch(() => undefined);
});

function routeMessage(message, sender) {
  if (message.type === "EAGLEEYE_EVENT" && sender.tab) {
    return enqueueOperation(() => recordContentEvent(message, sender));
  }

  if (!isPopupSender(sender)) {
    return null;
  }

  if (message.type === "GET_STATE") {
    return readState().then((state) => ({ state }));
  }
  if (message.type === "START_RECORDING") {
    return enqueueOperation(() => startRecording(message.payload));
  }
  if (message.type === "STOP_RECORDING") {
    return enqueueOperation(async () => ({ state: await stopCurrentRecording() }));
  }
  if (message.type === "GENERATE_CASES") {
    return enqueueOperation(async () => ({ state: await generateCases() }));
  }
  if (message.type === "REPLAY_SESSION") {
    return enqueueOperation(async () => ({ state: await replaySession() }));
  }
  if (message.type === "OPEN_REPORT") {
    return enqueueOperation(async () => ({ state: await openReport() }));
  }
  if (message.type === "DELETE_SESSION") {
    return enqueueOperation(async () => ({ state: await deleteCurrentSession() }));
  }
  return Promise.reject(new ExtensionError("input", "不明な拡張操作です。"));
}

function isPopupSender(sender) {
  // Chrome action popups have no tab, while the same signed popup opened in a
  // dedicated tab is useful for accessibility and automated release checks.
  // Both are the same extension principal and must still match the exact URL.
  return sender.url === chrome.runtime.getURL("popup.html");
}

function enqueueOperation(task) {
  const current = operationQueue.then(task, task);
  operationQueue = current.catch(() => undefined);
  return current;
}

async function startRecording(payload) {
  const input = validateStartInput(payload);
  const previous = await readState();
  if (previous?.recording) {
    throw new ExtensionError("state", "すでに記録中です。先に停止してください。");
  }

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !Number.isInteger(tab.id) || !Number.isInteger(tab.windowId)) {
    throw new ExtensionError("tab", "現在のタブを取得できませんでした。");
  }
  const startUrl = sanitizePageUrl(tab.url);
  const startOrigin = new URL(startUrl).origin;
  const apiBase = await resolveApiBase();
  const session = await requestJson(
    apiBase,
    "/api/v1/browser-agent/sessions",
    {
      method: "POST",
      body: {
        name: input.name,
        goal: input.goal,
        startUrl,
        locale: "ja",
      },
      timeoutMs: 10_000,
    },
  );
  const view = sessionToView(session);
  let state = {
    version: STATE_VERSION,
    apiBase,
    sessionId: view.id,
    tabId: tab.id,
    windowId: tab.windowId,
    startOrigin,
    recording: true,
    captureScreenshot: input.captureScreenshot,
    updatedAt: Date.now(),
    view,
    lastError: null,
  };
  await writeState(state);

  let contentResponse;
  try {
    contentResponse = await injectRecorder(tab.id, "EAGLEEYE_CONTENT_START");
  } catch (error) {
    state = await stopWithError(
      state,
      new ExtensionError(
        "tab",
        "このページでは記録を開始できません。HTTP(S)ページを現在のタブで開いてください。",
      ),
    );
    throw new ExtensionError("tab", state.lastError ?? publicError(error).message);
  }

  const dom = validateContentSnapshot(contentResponse);
  const screenshotDataUrl = input.captureScreenshot
    ? await captureVisibleScreenshot(tab.id, tab.windowId)
    : null;
  const observation = {
    id: observationId("goto"),
    timestamp: Date.now(),
    action: "goto",
    url: startUrl,
    valueType: "navigation",
    redacted: true,
    dom,
  };
  if (screenshotDataUrl) {
    observation.screenshotDataUrl = screenshotDataUrl;
  }

  try {
    const appended = await postObservation(state, observation);
    state = {
      ...state,
      view: sessionToView(appended),
      updatedAt: Date.now(),
    };
    await writeState(state);
    return { state };
  } catch (error) {
    await sendContentCommand(tab.id, "EAGLEEYE_CONTENT_STOP").catch(() => undefined);
    await stopWithError(state, error);
    throw error;
  }
}

async function stopCurrentRecording() {
  const state = requireState(await readState());
  if (!state.recording) {
    return state;
  }
  return stopRecording(state, true);
}

async function stopRecording(state, includeSnapshot) {
  let dom = null;
  if (Number.isInteger(state.tabId)) {
    try {
      const response = await sendContentCommand(state.tabId, "EAGLEEYE_CONTENT_STOP");
      dom = validateContentSnapshot(response);
    } catch {
      dom = null;
    }
  }

  const screenshotDataUrl =
    includeSnapshot && state.captureScreenshot && Number.isInteger(state.tabId) && Number.isInteger(state.windowId)
      ? await captureVisibleScreenshot(state.tabId, state.windowId)
      : null;

  let next = state;
  try {
    if (includeSnapshot && (dom || screenshotDataUrl)) {
      const observation = {
        id: observationId("snapshot"),
        timestamp: Date.now(),
        action: "snapshot",
        url: await currentSafeUrl(state),
        valueType: "snapshot",
        redacted: true,
      };
      if (dom) {
        observation.dom = dom;
      }
      if (screenshotDataUrl) {
        observation.screenshotDataUrl = screenshotDataUrl;
      }
      const appended = await postObservation(state, observation);
      next = { ...state, view: sessionToView(appended) };
    }
  } catch (error) {
    next = await stopWithError(state, error);
    throw error;
  }

  next = {
    ...next,
    tabId: null,
    windowId: null,
    recording: false,
    updatedAt: Date.now(),
  };
  await writeState(next);
  return next;
}

async function generateCases() {
  let state = requireState(await readState());
  if (state.recording) {
    state = await stopRecording(state, true);
  }
  const session = await requestJson(
    state.apiBase,
    `/api/v1/browser-agent/sessions/${state.sessionId}/generate`,
    { method: "POST", timeoutMs: 135_000 },
  );
  state = {
    ...state,
    view: sessionToView(session),
    updatedAt: Date.now(),
    lastError: null,
  };
  await writeState(state);
  return state;
}

async function replaySession() {
  let state = requireState(await readState());
  if (state.recording) {
    state = await stopRecording(state, true);
  }
  const session = await requestJson(
    state.apiBase,
    `/api/v1/browser-agent/sessions/${state.sessionId}/run`,
    { method: "POST", timeoutMs: 195_000 },
  );
  state = {
    ...state,
    view: sessionToView(session),
    updatedAt: Date.now(),
    lastError: null,
  };
  await writeState(state);
  return state;
}

async function openReport() {
  const state = requireState(await readState());
  const path = `/api/v1/browser-agent/sessions/${state.sessionId}/report`;
  await requestText(state.apiBase, path, 10_000);
  await chrome.tabs.create({ url: `${state.apiBase}${path}` });
  return state;
}

async function deleteCurrentSession() {
  let state = requireState(await readState());
  if (state.recording) {
    state = await stopRecording(state, false);
  }
  await requestJson(
    state.apiBase,
    `/api/v1/browser-agent/sessions/${state.sessionId}`,
    { method: "DELETE", timeoutMs: 10_000, emptyResponse: true },
  );
  await chrome.storage.session.remove(STORAGE_KEY);
  return null;
}

async function recordContentEvent(message, sender) {
  const state = await readState();
  if (!state || !state.recording || sender.tab?.id !== state.tabId) {
    return { accepted: false };
  }

  try {
    const observation = validateContentEvent(message.event, state);
    const session = await postObservation(state, observation);
    await writeState({
      ...state,
      view: sessionToView(session),
      updatedAt: Date.now(),
      lastError: null,
    });
    return { accepted: true };
  } catch (error) {
    if (Number.isInteger(state.tabId)) {
      await sendContentCommand(state.tabId, "EAGLEEYE_CONTENT_STOP").catch(() => undefined);
    }
    await stopWithError(state, error);
    throw error;
  }
}

async function resumeAfterNavigation(tabId, tab) {
  const state = await readState();
  if (!state || !state.recording || state.tabId !== tabId) {
    return;
  }

  let pageUrl;
  try {
    pageUrl = sanitizePageUrl(tab.url);
  } catch {
    await stopWithError(
      state,
      new ExtensionError("origin", "記録権限が失われたため停止しました。"),
    );
    return;
  }

  if (new URL(pageUrl).origin !== state.startOrigin) {
    await stopWithError(
      state,
      new ExtensionError("origin", "開始元と異なるオリジンへ移動したため記録を停止しました。"),
    );
    return;
  }

  try {
    const response = await injectRecorder(tabId, "EAGLEEYE_CONTENT_START");
    const dom = validateContentSnapshot(response);
    const screenshotDataUrl =
      state.captureScreenshot && Number.isInteger(state.windowId)
        ? await captureVisibleScreenshot(tabId, state.windowId)
        : null;
    const observation = {
      id: observationId("goto"),
      timestamp: Date.now(),
      action: "goto",
      url: pageUrl,
      valueType: "navigation",
      redacted: true,
      dom,
    };
    if (screenshotDataUrl) {
      observation.screenshotDataUrl = screenshotDataUrl;
    }
    const session = await postObservation(state, observation);
    await writeState({
      ...state,
      view: sessionToView(session),
      updatedAt: Date.now(),
      lastError: null,
    });
  } catch (error) {
    await stopWithError(state, error);
  }
}

async function injectRecorder(tabId, command) {
  await chrome.scripting.executeScript({
    target: { tabId },
    files: ["content.js"],
  });
  return sendContentCommand(tabId, command);
}

async function sendContentCommand(tabId, type) {
  const response = await chrome.tabs.sendMessage(tabId, { type });
  if (!isPlainObject(response) || response.ok !== true) {
    throw new ExtensionError("content", "ページ観測コンポーネントが応答しませんでした。" );
  }
  return response;
}

async function captureVisibleScreenshot(tabId, windowId) {
  try {
    const [activeTab] = await chrome.tabs.query({ active: true, windowId });
    if (!activeTab || activeTab.id !== tabId) {
      return null;
    }
    const dataUrl = await chrome.tabs.captureVisibleTab(windowId, {
      format: "jpeg",
      quality: 55,
    });
    if (
      typeof dataUrl !== "string" ||
      !dataUrl.startsWith("data:image/jpeg;base64,") ||
      dataUrl.length > MAX_SCREENSHOT_DATA_URL
    ) {
      return null;
    }
    return dataUrl;
  } catch {
    return null;
  }
}

async function currentSafeUrl(state) {
  if (!Number.isInteger(state.tabId)) {
    return `${state.startOrigin}/`;
  }
  try {
    const tab = await chrome.tabs.get(state.tabId);
    const pageUrl = sanitizePageUrl(tab.url);
    return new URL(pageUrl).origin === state.startOrigin ? pageUrl : `${state.startOrigin}/`;
  } catch {
    return `${state.startOrigin}/`;
  }
}

async function postObservation(state, observation) {
  return requestJson(
    state.apiBase,
    `/api/v1/browser-agent/sessions/${state.sessionId}/observations`,
    { method: "POST", body: observation, timeoutMs: 12_000 },
  );
}

async function resolveApiBase() {
  for (const base of API_BASES) {
    try {
      const health = await requestJson(base, "/health", { timeoutMs: 4_000 });
      if (isPlainObject(health) && health.status === "ok") {
        return base;
      }
    } catch {
      // Try the other exact loopback name before surfacing startup guidance.
    }
  }
  throw new ExtensionError("unavailable", API_START_GUIDANCE);
}

async function requestJson(base, path, options = {}) {
  const response = await request(base, path, options);
  const text = await response.text();
  if (options.emptyResponse === true && response.ok && text.length === 0) {
    return {};
  }
  if (text.length > MAX_JSON_RESPONSE) {
    throw new ExtensionError("api", "API応答が大きすぎるため破棄しました。", response.status);
  }

  let payload;
  try {
    payload = JSON.parse(text);
  } catch {
    throw new ExtensionError("api", "APIがJSON以外の応答を返しました。", response.status);
  }
  if (!response.ok) {
    const detail = isPlainObject(payload) && typeof payload.detail === "string"
      ? boundedText(payload.detail, 300)
      : `HTTP ${response.status}`;
    throw new ExtensionError("http", detail, response.status);
  }
  return payload;
}

async function requestText(base, path, timeoutMs) {
  const response = await request(base, path, { timeoutMs });
  const text = await response.text();
  if (!response.ok) {
    throw new ExtensionError("http", `HTTP ${response.status}`, response.status);
  }
  if (text.length > MAX_REPORT_RESPONSE) {
    throw new ExtensionError("api", "レポートが大きすぎるため開けませんでした。", response.status);
  }
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.toLowerCase().includes("text/html")) {
    throw new ExtensionError("api", "レポートAPIがHTML以外を返しました。", response.status);
  }
  return text;
}

async function request(base, path, options) {
  if (!API_BASES.includes(base) || !path.startsWith("/")) {
    throw new ExtensionError("input", "許可されていないAPI宛先です。" );
  }
  const method = options.method ?? "GET";
  const timeoutMs = options.timeoutMs ?? 10_000;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  const headers = {};
  let body;
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }
  try {
    return await fetch(`${base}${path}`, {
      method,
      headers,
      body,
      cache: "no-store",
      credentials: "omit",
      redirect: "error",
      referrerPolicy: "no-referrer",
      signal: controller.signal,
    });
  } catch (error) {
    if (error?.name === "AbortError") {
      throw new ExtensionError(
        "timeout",
        `API応答が${Math.ceil(timeoutMs / 1000)}秒でタイムアウトしました。`,
      );
    }
    throw new ExtensionError("unavailable", API_START_GUIDANCE);
  } finally {
    clearTimeout(timeout);
  }
}

function validateStartInput(payload) {
  if (!isPlainObject(payload)) {
    throw new ExtensionError("input", "記録設定が不正です。" );
  }
  const name = requiredText(payload.name, 160, "セッション名");
  const goal = requiredText(payload.goal, 800, "確認したいこと");
  if (typeof payload.captureScreenshot !== "boolean") {
    throw new ExtensionError("input", "スクリーンショット設定が不正です。" );
  }
  if (payload.privacyConsent !== true) {
    throw new ExtensionError("input", "プライバシー確認への同意が必要です。" );
  }
  return { name, goal, captureScreenshot: payload.captureScreenshot };
}

function validateContentEvent(event, state) {
  if (!isPlainObject(event) || !SAFE_ACTIONS.has(event.action)) {
    throw new ExtensionError("content", "許可されていないページ操作を破棄しました。" );
  }
  const pageUrl = sanitizePageUrl(event.url);
  if (new URL(pageUrl).origin !== state.startOrigin) {
    throw new ExtensionError("origin", "開始元と異なるオリジンの操作を拒否しました。" );
  }
  const valueType = SAFE_VALUE_TYPES.has(event.valueType) ? event.valueType : "unknown";
  return {
    id: observationId(event.action),
    timestamp: Date.now(),
    action: event.action,
    url: pageUrl,
    target: validateTarget(event.target),
    valueType,
    redacted: true,
  };
}

function validateTarget(target) {
  if (!isPlainObject(target)) {
    return null;
  }
  const clean = {
    role: optionalText(target.role, 80),
    name: optionalText(target.name, 240),
    selector: optionalText(target.selector, 500),
    tagName: optionalText(target.tagName, 40),
  };
  if (!Object.values(clean).some((value) => value !== null)) {
    return null;
  }
  return clean;
}

function validateContentSnapshot(response) {
  if (!isPlainObject(response) || response.ok !== true) {
    throw new ExtensionError("content", "DOM要約を取得できませんでした。" );
  }
  return validateDomSnapshot(response.snapshot);
}

function validateDomSnapshot(snapshot) {
  if (!isPlainObject(snapshot)) {
    throw new ExtensionError("content", "DOM要約の形式が不正です。" );
  }
  const headings = boundedStringList(snapshot.headings, 24, 240);
  const landmarks = boundedStringList(snapshot.landmarks, 20, 240);
  if (!Array.isArray(snapshot.controls) || snapshot.controls.length > 60) {
    throw new ExtensionError("content", "コントロール要約が上限を超えました。" );
  }
  const controls = snapshot.controls.map((control) => validateControl(control));
  return {
    pageTitle: boundedText(snapshot.pageTitle, 300),
    headings,
    landmarks,
    controls,
  };
}

function validateControl(control) {
  if (!isPlainObject(control)) {
    throw new ExtensionError("content", "コントロール要約の形式が不正です。" );
  }
  const tagName = requiredText(control.tagName, 40, "tagName").toLowerCase();
  return {
    role: optionalText(control.role, 80),
    name: optionalText(control.name, 240),
    tagName,
    selector: optionalText(control.selector, 500),
    testId: optionalText(control.testId, 200),
    disabled: control.disabled === true,
  };
}

function boundedStringList(value, maximumItems, maximumLength) {
  if (!Array.isArray(value) || value.length > maximumItems) {
    throw new ExtensionError("content", "DOM要約の件数が上限を超えました。" );
  }
  return value.map((item) => boundedText(item, maximumLength));
}

function sessionToView(session) {
  if (!isPlainObject(session) || !SESSION_ID_PATTERN.test(session.id)) {
    throw new ExtensionError("api", "APIセッションIDが不正です。" );
  }
  if (!SESSION_STATUSES.has(session.status)) {
    throw new ExtensionError("api", "APIセッション状態が不正です。" );
  }
  if (!Array.isArray(session.observations) || session.observations.length > 500) {
    throw new ExtensionError("api", "API観測件数が不正です。" );
  }
  if (!Array.isArray(session.generatedCases) || session.generatedCases.length > 20) {
    throw new ExtensionError("api", "API生成ケース件数が不正です。" );
  }
  const cases = session.generatedCases.map((item) => {
    if (!isPlainObject(item) || !CASE_SOURCES.has(item.source) || !CASE_PRIORITIES.has(item.priority)) {
      throw new ExtensionError("api", "API生成ケースの形式が不正です。" );
    }
    return {
      title: requiredText(item.title, 300, "case title"),
      source: item.source,
      priority: item.priority,
      runnable: item.runnable === true,
    };
  });
  let qualityDecision = null;
  if (session.qualityGate !== null && session.qualityGate !== undefined) {
    if (!isPlainObject(session.qualityGate) || !QUALITY_DECISIONS.has(session.qualityGate.decision)) {
      throw new ExtensionError("api", "品質ゲート結果の形式が不正です。" );
    }
    qualityDecision = session.qualityGate.decision;
  }
  let aiMessage = null;
  if (session.ai !== null && session.ai !== undefined) {
    if (!isPlainObject(session.ai)) {
      throw new ExtensionError("api", "AI結果の形式が不正です。" );
    }
    aiMessage = optionalText(session.ai.message, 500);
  }
  if (!Number.isInteger(session.replayCount) || session.replayCount < 0) {
    throw new ExtensionError("api", "Replay件数が不正です。" );
  }
  return {
    id: session.id,
    name: requiredText(session.name, 160, "session name"),
    goal: requiredText(session.goal, 800, "session goal"),
    status: session.status,
    observationCount: session.observations.length,
    caseCount: cases.length,
    replayCount: session.replayCount,
    screenshotAvailable: session.screenshotAvailable === true,
    qualityDecision,
    aiMessage,
    updatedAt: requiredText(session.updatedAt, 80, "updatedAt"),
    cases,
  };
}

async function readState() {
  const stored = await chrome.storage.session.get(STORAGE_KEY);
  if (!(STORAGE_KEY in stored)) {
    return null;
  }
  if (!isValidState(stored[STORAGE_KEY])) {
    await chrome.storage.session.remove(STORAGE_KEY);
    return null;
  }
  return stored[STORAGE_KEY];
}

async function writeState(state) {
  if (!isValidState(state)) {
    throw new ExtensionError("state", "保存しようとしたセッション状態が不正です。" );
  }
  await chrome.storage.session.set({ [STORAGE_KEY]: state });
}

function isValidState(state) {
  if (
    !hasOnlyKeys(state, [
      "version",
      "apiBase",
      "sessionId",
      "tabId",
      "windowId",
      "startOrigin",
      "recording",
      "captureScreenshot",
      "updatedAt",
      "view",
      "lastError",
    ]) ||
    state.version !== STATE_VERSION ||
    !API_BASES.includes(state.apiBase) ||
    !SESSION_ID_PATTERN.test(state.sessionId) ||
    !(state.tabId === null || Number.isInteger(state.tabId)) ||
    !(state.windowId === null || Number.isInteger(state.windowId)) ||
    typeof state.recording !== "boolean" ||
    typeof state.captureScreenshot !== "boolean" ||
    !Number.isInteger(state.updatedAt) ||
    !(state.lastError === null || (typeof state.lastError === "string" && state.lastError.length <= 500)) ||
    !isValidView(state.view) ||
    state.view.id !== state.sessionId
  ) {
    return false;
  }
  if (state.recording && (!Number.isInteger(state.tabId) || !Number.isInteger(state.windowId))) {
    return false;
  }
  try {
    const origin = new URL(state.startOrigin);
    return (
      ["http:", "https:"].includes(origin.protocol) &&
      origin.origin === state.startOrigin &&
      origin.username === "" &&
      origin.password === ""
    );
  } catch {
    return false;
  }
}

function isValidView(view) {
  if (
    !hasOnlyKeys(view, [
      "id",
      "name",
      "goal",
      "status",
      "observationCount",
      "caseCount",
      "replayCount",
      "screenshotAvailable",
      "qualityDecision",
      "aiMessage",
      "updatedAt",
      "cases",
    ]) ||
    !SESSION_ID_PATTERN.test(view.id) ||
    typeof view.name !== "string" ||
    view.name.length === 0 ||
    view.name.length > 160 ||
    typeof view.goal !== "string" ||
    view.goal.length === 0 ||
    view.goal.length > 800 ||
    !SESSION_STATUSES.has(view.status) ||
    !Number.isInteger(view.observationCount) ||
    view.observationCount < 0 ||
    view.observationCount > 500 ||
    !Number.isInteger(view.caseCount) ||
    view.caseCount < 0 ||
    view.caseCount > 20 ||
    !Number.isInteger(view.replayCount) ||
    view.replayCount < 0 ||
    typeof view.screenshotAvailable !== "boolean" ||
    !(view.qualityDecision === null || QUALITY_DECISIONS.has(view.qualityDecision)) ||
    !(view.aiMessage === null || (typeof view.aiMessage === "string" && view.aiMessage.length <= 500)) ||
    typeof view.updatedAt !== "string" ||
    view.updatedAt.length > 80 ||
    !Array.isArray(view.cases) ||
    view.cases.length !== view.caseCount
  ) {
    return false;
  }
  return view.cases.every(
    (item) =>
      hasOnlyKeys(item, ["title", "source", "priority", "runnable"]) &&
      typeof item.title === "string" &&
      item.title.length > 0 &&
      item.title.length <= 300 &&
      CASE_SOURCES.has(item.source) &&
      CASE_PRIORITIES.has(item.priority) &&
      typeof item.runnable === "boolean",
  );
}

async function stopWithError(state, error) {
  const message = publicError(error).message;
  const next = {
    ...state,
    tabId: null,
    windowId: null,
    recording: false,
    updatedAt: Date.now(),
    lastError: boundedText(message, 500),
  };
  await writeState(next);
  return next;
}

function requireState(state) {
  if (!state) {
    throw new ExtensionError("state", "先にセッションを開始してください。" );
  }
  return state;
}

function sanitizePageUrl(raw) {
  if (typeof raw !== "string" || raw.length > 8_000) {
    throw new ExtensionError("tab", "現在のページURLを利用できません。" );
  }
  let pageUrl;
  try {
    pageUrl = new URL(raw);
  } catch {
    throw new ExtensionError("tab", "現在のページURLが不正です。" );
  }
  if (!['http:', 'https:'].includes(pageUrl.protocol) || !pageUrl.hostname) {
    throw new ExtensionError(
      "tab",
      "このページでは開始できません。HTTP(S)ページを現在のタブで開いてください。",
    );
  }
  pageUrl.username = "";
  pageUrl.password = "";
  pageUrl.hash = "";
  for (const key of [...pageUrl.searchParams.keys()]) {
    if (SECRET_QUERY_KEY.test(key)) {
      pageUrl.searchParams.delete(key);
    }
  }
  return pageUrl.href;
}

function observationId(action) {
  const random = crypto.randomUUID().replaceAll("-", "").slice(0, 16);
  return `${action}-${Date.now()}-${random}`;
}

function requiredText(value, maximumLength, label) {
  const text = boundedText(value, maximumLength).trim();
  if (!text) {
    throw new ExtensionError("input", `${label}を入力してください。`);
  }
  return text;
}

function optionalText(value, maximumLength) {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  return boundedText(value, maximumLength).trim() || null;
}

function boundedText(value, maximumLength) {
  if (typeof value !== "string") {
    throw new ExtensionError("input", "文字列データの形式が不正です。" );
  }
  return value.replace(/[\u0000-\u001f\u007f]/gu, " ").replace(/\s+/gu, " ").slice(0, maximumLength);
}

function isPlainObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function hasOnlyKeys(value, allowedKeys) {
  if (!isPlainObject(value)) {
    return false;
  }
  const allowed = new Set(allowedKeys);
  return Object.keys(value).every((key) => allowed.has(key));
}

function publicError(error) {
  if (error instanceof ExtensionError) {
    if (error.kind === "timeout") {
      return {
        kind: error.kind,
        message: `${boundedText(error.message, 300)} APIログとAI providerの接続状態を確認してください。`,
      };
    }
    if (error.kind === "unavailable") {
      return { kind: error.kind, message: API_START_GUIDANCE };
    }
    if (error.kind === "http" && error.status === 403) {
      return {
        kind: error.kind,
        message: `ReplayはEagleEyeの安全ポリシーで拒否されました。標準設定ではloopback対象だけ実行できます。${boundedText(error.message, 180)}`,
      };
    }
    return { kind: error.kind, message: boundedText(error.message, 500) };
  }
  return {
    kind: "unexpected",
    message: "予期しない拡張エラーが発生しました。拡張を再読み込みして再試行してください。",
  };
}
