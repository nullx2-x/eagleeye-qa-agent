"use strict";

const elements = {
  name: document.querySelector("#session-name"),
  goal: document.querySelector("#session-goal"),
  capture: document.querySelector("#capture-screenshot"),
  consent: document.querySelector("#privacy-consent"),
  start: document.querySelector("#start-button"),
  stop: document.querySelector("#stop-button"),
  generate: document.querySelector("#generate-button"),
  replay: document.querySelector("#replay-button"),
  report: document.querySelector("#report-button"),
  delete: document.querySelector("#delete-button"),
  badge: document.querySelector("#status-badge"),
  operation: document.querySelector("#operation-status"),
  errorPanel: document.querySelector("#error-panel"),
  errorMessage: document.querySelector("#error-message"),
  sessionId: document.querySelector("#session-id"),
  metrics: document.querySelector("#metrics"),
  cases: document.querySelector("#case-list"),
};

let currentState = null;
let busy = false;

elements.start.addEventListener("click", () => {
  if (!elements.consent.checked) {
    showError("記録内容を確認し、対象サイトの許可とプライバシー同意をチェックしてください。");
    return;
  }
  void perform("記録を開始しています…", "記録を開始しました。", () =>
    sendCommand("START_RECORDING", {
      name: elements.name.value.trim(),
      goal: elements.goal.value.trim(),
      captureScreenshot: elements.capture.checked,
      privacyConsent: elements.consent.checked,
    }),
  );
});

elements.stop.addEventListener("click", () => {
  void perform("記録を停止しています…", "記録を停止しました。", () =>
    sendCommand("STOP_RECORDING"),
  );
});

elements.generate.addEventListener("click", () => {
  void perform("AIケースを生成しています。最大2分ほどかかります…", "AI生成が完了しました。", () =>
    sendCommand("GENERATE_CASES"),
  );
});

elements.replay.addEventListener("click", () => {
  void perform("Replayを実行しています…", "Replayが完了しました。", () =>
    sendCommand("REPLAY_SESSION"),
  );
});

elements.report.addEventListener("click", () => {
  void perform("レポートを確認しています…", "レポートを新しいタブで開きました。", () =>
    sendCommand("OPEN_REPORT"),
  );
});

elements.delete.addEventListener("click", () => {
  if (!globalThis.confirm("このセッション、DOM要約、スクリーンショット、Replay証跡を端末から削除しますか？")) {
    return;
  }
  void perform("ローカルデータを削除しています…", "ローカルデータを削除しました。", () =>
    sendCommand("DELETE_SESSION"),
  );
});

elements.consent.addEventListener("change", renderControls);

void initialize();

async function initialize() {
  try {
    const response = await sendCommand("GET_STATE");
    currentState = response.state;
    if (!currentState) {
      await applyPageDefaults();
    }
    render();
  } catch (error) {
    showError(error.message);
    render();
  }
}

async function applyPageDefaults() {
  elements.goal.value = "主要なユーザー導線が期待どおりに動作することを確認する";
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const title = typeof tab?.title === "string" ? tab.title.trim().slice(0, 130) : "";
    elements.name.value = title ? `${title} QA` : "現在のページ QA";
  } catch {
    elements.name.value = "現在のページ QA";
  }
}

async function perform(startMessage, successMessage, action) {
  if (busy) {
    return;
  }
  busy = true;
  hideError();
  setOperation(startMessage);
  renderControls();
  try {
    const response = await action();
    if (Object.hasOwn(response, "state")) {
      currentState = response.state;
    }
    setOperation(successMessage);
  } catch (error) {
    showError(error.message);
    setOperation("");
    try {
      const response = await sendCommand("GET_STATE");
      currentState = response.state;
    } catch {
      // The original, more useful error remains visible.
    }
  } finally {
    busy = false;
    render();
  }
}

async function sendCommand(type, payload) {
  const response = await chrome.runtime.sendMessage({ type, payload });
  if (!response || response.ok !== true) {
    const message =
      typeof response?.error?.message === "string"
        ? response.error.message.slice(0, 500)
        : "拡張のバックグラウンド処理が応答しませんでした。";
    throw new Error(message);
  }
  return response;
}

function render() {
  renderStatus();
  renderMetrics();
  renderCases();
  renderControls();
  if (currentState?.lastError) {
    showError(currentState.lastError);
  }
}

function renderStatus() {
  const status = currentState?.view?.status ?? null;
  const labels = {
    recording: currentState?.recording ? "記録中" : "記録停止",
    generated: "生成済み",
    running: "実行中",
    passed: "PASS",
    failed: "FAIL",
  };
  elements.badge.textContent = status ? labels[status] ?? status : "未開始";
  elements.badge.classList.toggle("live", currentState?.recording === true);
  elements.sessionId.textContent = currentState?.sessionId ? "ID非表示" : "—";
}

function renderMetrics() {
  elements.metrics.replaceChildren();
  const view = currentState?.view;
  if (!view) {
    addMetric("観測", "0");
    addMetric("ケース", "0");
    addMetric("Replay", "0");
    addMetric("品質判定", "—");
    return;
  }
  addMetric("観測", String(view.observationCount));
  addMetric("ケース", String(view.caseCount));
  addMetric("Replay", String(view.replayCount));
  addMetric("品質判定", view.qualityDecision ?? view.status.toUpperCase());
  if (view.aiMessage) {
    addMetric("AI", view.aiMessage);
  }
  addMetric("画像証跡", view.screenshotAvailable ? "あり" : "なし");
}

function addMetric(label, value) {
  const wrapper = document.createElement("div");
  wrapper.className = "metric";
  const term = document.createElement("dt");
  term.textContent = label;
  const description = document.createElement("dd");
  description.textContent = value;
  wrapper.append(term, description);
  elements.metrics.append(wrapper);
}

function renderCases() {
  elements.cases.replaceChildren();
  const cases = currentState?.view?.cases ?? [];
  if (cases.length === 0) {
    const empty = document.createElement("li");
    empty.className = "muted";
    empty.textContent = "まだ生成されていません。";
    elements.cases.append(empty);
    return;
  }
  for (const item of cases) {
    const row = document.createElement("li");
    const title = document.createElement("strong");
    title.textContent = item.title;
    const meta = document.createElement("span");
    meta.className = "case-meta";
    meta.textContent = `${item.source.toUpperCase()} · ${item.priority.toUpperCase()} · ${
      item.runnable ? "REPLAY可" : "設計ケース"
    }`;
    row.append(title, meta);
    elements.cases.append(row);
  }
}

function renderControls() {
  const hasSession = currentState !== null;
  const recording = currentState?.recording === true;
  elements.start.disabled = busy || recording || !elements.consent.checked;
  elements.stop.disabled = busy || !recording;
  elements.generate.disabled = busy || !hasSession;
  elements.replay.disabled = busy || !hasSession;
  elements.report.disabled = busy || !hasSession;
  elements.delete.disabled = busy || !hasSession;
  elements.name.disabled = busy || recording;
  elements.goal.disabled = busy || recording;
  elements.capture.disabled = busy || recording;
  elements.consent.disabled = busy || recording;
}

function setOperation(message) {
  elements.operation.textContent = message;
}

function showError(message) {
  elements.errorMessage.textContent = typeof message === "string" ? message.slice(0, 500) : "不明なエラーです。";
  elements.errorPanel.hidden = false;
}

function hideError() {
  elements.errorMessage.textContent = "";
  elements.errorPanel.hidden = true;
}
