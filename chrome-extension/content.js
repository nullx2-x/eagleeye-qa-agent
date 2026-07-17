(() => {
  "use strict";

  if (globalThis.__EAGLEEYE_RECORDER_V1__) {
    return;
  }
  globalThis.__EAGLEEYE_RECORDER_V1__ = true;

  const MAX_HEADINGS = 24;
  const MAX_LANDMARKS = 20;
  const MAX_CONTROLS = 60;
  const MAX_NAME_LENGTH = 240;
  const SECRET_QUERY_KEY = /(token|secret|password|passwd|api[_-]?key|auth|code|session)/iu;
  const CONTROL_SELECTOR = [
    "a[href]",
    "button",
    "input",
    "select",
    "textarea",
    "summary",
    "[contenteditable='true']",
    "[role='button']",
    "[role='link']",
    "[role='textbox']",
    "[role='combobox']",
    "[role='checkbox']",
    "[role='radio']",
    "[role='switch']",
    "[role='tab']",
    "[role='menuitem']",
  ].join(",");
  const LANDMARK_SELECTOR = [
    "header",
    "nav",
    "main",
    "aside",
    "footer",
    "form",
    "[role='banner']",
    "[role='navigation']",
    "[role='main']",
    "[role='complementary']",
    "[role='contentinfo']",
    "[role='form']",
    "[role='region']",
    "[role='search']",
  ].join(",");

  let recording = false;
  let fillTimers = new WeakMap();
  const pendingTimers = new Set();

  document.addEventListener("click", onClick, true);
  document.addEventListener("input", onInput, true);
  document.addEventListener("change", onChange, true);

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (!isPlainObject(message)) {
      return false;
    }
    if (message.type === "EAGLEEYE_CONTENT_START") {
      recording = true;
      sendResponse({ ok: true, snapshot: buildDomSnapshot() });
      return false;
    }
    if (message.type === "EAGLEEYE_CONTENT_STOP") {
      recording = false;
      clearFillTimers();
      sendResponse({ ok: true, snapshot: buildDomSnapshot() });
      return false;
    }
    if (message.type === "EAGLEEYE_CONTENT_SNAPSHOT") {
      sendResponse({ ok: true, snapshot: buildDomSnapshot() });
      return false;
    }
    return false;
  });

  function onClick(event) {
    if (!recording || !event.isTrusted) {
      return;
    }
    const element = eventElement(event);
    if (!element) {
      return;
    }
    const control = element.closest(CONTROL_SELECTOR);
    if (!control) {
      return;
    }

    const tagName = control.tagName.toLowerCase();
    const explicitRole = compact(control.getAttribute("role"), 80).toLowerCase();
    if (tagName === "select" || tagName === "textarea" || control.isContentEditable) {
      return;
    }
    if (tagName === "input") {
      const inputType = compact(control.getAttribute("type") || "text", 40).toLowerCase();
      if (["checkbox", "radio"].includes(inputType)) {
        return;
      }
      if (!["button", "submit", "reset", "image"].includes(inputType)) {
        return;
      }
    }
    if (["checkbox", "radio", "switch"].includes(explicitRole)) {
      sendEvent("check", control, explicitRole === "switch" ? "checkbox" : explicitRole);
      return;
    }
    sendEvent("click", control, "none");
  }

  function onInput(event) {
    if (!recording || !event.isTrusted) {
      return;
    }
    const element = eventElement(event);
    if (!element || !isFillControl(element)) {
      return;
    }
    scheduleFill(element);
  }

  function onChange(event) {
    if (!recording || !event.isTrusted) {
      return;
    }
    const element = eventElement(event);
    if (!element) {
      return;
    }
    cancelFill(element);
    if (element instanceof HTMLSelectElement) {
      sendEvent("select", element, element.multiple ? "select-multiple" : "select-one");
      return;
    }
    if (element instanceof HTMLInputElement) {
      const inputType = compact(element.getAttribute("type") || "text", 40).toLowerCase();
      if (["checkbox", "radio"].includes(inputType)) {
        sendEvent("check", element, inputType);
        return;
      }
    }
    if (isFillControl(element)) {
      sendEvent("fill", element, valueTypeFor(element));
    }
  }

  function scheduleFill(element) {
    cancelFill(element);
    const timer = setTimeout(() => {
      pendingTimers.delete(timer);
      fillTimers.delete(element);
      if (recording && element.isConnected) {
        sendEvent("fill", element, valueTypeFor(element));
      }
    }, 500);
    fillTimers.set(element, timer);
    pendingTimers.add(timer);
  }

  function cancelFill(element) {
    const timer = fillTimers.get(element);
    if (timer !== undefined) {
      clearTimeout(timer);
      pendingTimers.delete(timer);
      fillTimers.delete(element);
    }
  }

  function clearFillTimers() {
    for (const timer of pendingTimers) {
      clearTimeout(timer);
    }
    pendingTimers.clear();
    fillTimers = new WeakMap();
  }

  function sendEvent(action, element, valueType) {
    if (!recording) {
      return;
    }
    const event = {
      action,
      url: safePageUrl(),
      target: targetSnapshot(element),
      valueType,
      redacted: true,
    };
    void chrome.runtime.sendMessage({ type: "EAGLEEYE_EVENT", event }).catch(() => undefined);
  }

  function targetSnapshot(element) {
    return {
      role: roleFor(element),
      name: accessibleName(element),
      selector: selectorFor(element),
      tagName: element.tagName.toLowerCase(),
    };
  }

  function buildDomSnapshot() {
    const headings = [];
    for (const element of document.querySelectorAll("h1,h2,h3,h4,h5,h6,[role='heading']")) {
      if (headings.length >= MAX_HEADINGS) {
        break;
      }
      const name = accessibleName(element);
      if (name) {
        headings.push(name);
      }
    }

    const landmarks = [];
    const seenLandmarks = new Set();
    for (const element of document.querySelectorAll(LANDMARK_SELECTOR)) {
      if (landmarks.length >= MAX_LANDMARKS) {
        break;
      }
      const role = landmarkRole(element);
      const name = accessibleName(element);
      const summary = compact(name ? `${role}: ${name}` : role, MAX_NAME_LENGTH);
      if (summary && !seenLandmarks.has(summary)) {
        seenLandmarks.add(summary);
        landmarks.push(summary);
      }
    }

    const controls = [];
    for (const element of document.querySelectorAll(CONTROL_SELECTOR)) {
      if (controls.length >= MAX_CONTROLS) {
        break;
      }
      const testId = safeTestId(element.getAttribute("data-testid"));
      controls.push({
        role: roleFor(element),
        name: accessibleName(element),
        tagName: element.tagName.toLowerCase(),
        selector: selectorFor(element),
        testId,
        disabled:
          element.matches(":disabled") ||
          compact(element.getAttribute("aria-disabled"), 10).toLowerCase() === "true",
      });
    }

    return {
      pageTitle: compact(document.title, 300),
      headings,
      landmarks,
      controls,
    };
  }

  function accessibleName(element) {
    const ariaLabel = compact(element.getAttribute("aria-label"), MAX_NAME_LENGTH);
    if (ariaLabel) {
      return ariaLabel;
    }

    const labelledBy = compact(element.getAttribute("aria-labelledby"), 300);
    if (labelledBy) {
      const parts = [];
      for (const id of labelledBy.split(/\s+/u).slice(0, 4)) {
        const node = document.getElementById(id);
        const text = node ? compact(node.textContent, MAX_NAME_LENGTH) : "";
        if (text) {
          parts.push(text);
        }
      }
      const joined = compact(parts.join(" "), MAX_NAME_LENGTH);
      if (joined) {
        return joined;
      }
    }

    if (
      element instanceof HTMLInputElement ||
      element instanceof HTMLSelectElement ||
      element instanceof HTMLTextAreaElement
    ) {
      const firstLabel = element.labels?.[0];
      const labelText = firstLabel ? compact(firstLabel.textContent, MAX_NAME_LENGTH) : "";
      if (labelText) {
        return labelText;
      }
    }

    const explicitRole = compact(element.getAttribute("role"), 80).toLowerCase();
    const tagName = element.tagName.toLowerCase();
    if (
      ["a", "button", "summary", "h1", "h2", "h3", "h4", "h5", "h6"].includes(tagName) ||
      ["button", "link", "tab", "menuitem", "checkbox", "radio", "switch", "heading"].includes(
        explicitRole,
      )
    ) {
      const visibleText = compact(element.textContent, MAX_NAME_LENGTH);
      if (visibleText) {
        return visibleText;
      }
    }

    for (const attribute of ["alt", "title", "placeholder"]) {
      const candidate = compact(element.getAttribute(attribute), MAX_NAME_LENGTH);
      if (candidate) {
        return candidate;
      }
    }
    return null;
  }

  function roleFor(element) {
    const explicitRole = compact(element.getAttribute("role"), 80).split(/\s+/u)[0];
    if (explicitRole) {
      return explicitRole.toLowerCase();
    }
    const tagName = element.tagName.toLowerCase();
    if (tagName === "a" && element.hasAttribute("href")) {
      return "link";
    }
    if (["button", "summary"].includes(tagName)) {
      return "button";
    }
    if (tagName === "textarea") {
      return "textbox";
    }
    if (tagName === "select") {
      return element.multiple ? "listbox" : "combobox";
    }
    if (tagName === "input") {
      const inputType = compact(element.getAttribute("type") || "text", 40).toLowerCase();
      const roles = {
        button: "button",
        submit: "button",
        reset: "button",
        checkbox: "checkbox",
        radio: "radio",
        range: "slider",
        number: "spinbutton",
        search: "searchbox",
      };
      return roles[inputType] ?? "textbox";
    }
    if (element.isContentEditable) {
      return "textbox";
    }
    return tagName;
  }

  function landmarkRole(element) {
    const explicitRole = compact(element.getAttribute("role"), 80).split(/\s+/u)[0];
    if (explicitRole) {
      return explicitRole.toLowerCase();
    }
    const roles = {
      header: "banner",
      nav: "navigation",
      main: "main",
      aside: "complementary",
      footer: "contentinfo",
      form: "form",
    };
    return roles[element.tagName.toLowerCase()] ?? "region";
  }

  function selectorFor(element) {
    const testId = safeTestId(element.getAttribute("data-testid"));
    if (testId) {
      return `[data-testid="${testId}"]`;
    }
    const id = compact(element.getAttribute("id"), 180);
    if (id) {
      return `#${CSS.escape(id)}`;
    }

    const parts = [];
    let current = element;
    while (current && parts.length < 4) {
      const tagName = current.tagName.toLowerCase();
      let part = tagName;
      const parent = current.parentElement;
      if (parent) {
        const siblings = [...parent.children].filter(
          (sibling) => sibling.tagName.toLowerCase() === tagName,
        );
        if (siblings.length > 1) {
          part += `:nth-of-type(${siblings.indexOf(current) + 1})`;
        }
      }
      parts.unshift(part);
      current = parent;
      if (current?.tagName.toLowerCase() === "body") {
        break;
      }
    }
    return compact(parts.join(" > "), 500) || null;
  }

  function valueTypeFor(element) {
    if (element.isContentEditable) {
      return "contenteditable";
    }
    if (element instanceof HTMLTextAreaElement) {
      return "text";
    }
    if (!(element instanceof HTMLInputElement)) {
      return "unknown";
    }
    const inputType = compact(element.getAttribute("type") || "text", 40).toLowerCase();
    const autocomplete = compact(element.getAttribute("autocomplete"), 120).toLowerCase();
    if (
      inputType === "password" ||
      autocomplete.includes("one-time-code") ||
      autocomplete.includes("cc-") ||
      autocomplete.includes("current-password") ||
      autocomplete.includes("new-password")
    ) {
      return "sensitive";
    }
    const allowed = new Set([
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
    ]);
    return allowed.has(inputType) ? inputType : "unknown";
  }

  function isFillControl(element) {
    if (element instanceof HTMLTextAreaElement || element.isContentEditable) {
      return true;
    }
    if (!(element instanceof HTMLInputElement)) {
      return false;
    }
    const inputType = compact(element.getAttribute("type") || "text", 40).toLowerCase();
    return ![
      "button",
      "submit",
      "reset",
      "image",
      "checkbox",
      "radio",
      "file",
      "hidden",
    ].includes(inputType);
  }

  function eventElement(event) {
    for (const node of event.composedPath()) {
      if (node instanceof Element) {
        return node;
      }
    }
    return null;
  }

  function safePageUrl() {
    const pageUrl = new URL(location.href);
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

  function safeTestId(value) {
    const candidate = compact(value, 120);
    return /^[A-Za-z0-9_-]+$/u.test(candidate) ? candidate : null;
  }

  function compact(value, maximumLength) {
    if (typeof value !== "string") {
      return "";
    }
    return value
      .replace(/[\u0000-\u001f\u007f]/gu, " ")
      .replace(/\s+/gu, " ")
      .trim()
      .slice(0, maximumLength);
  }

  function isPlainObject(value) {
    return value !== null && typeof value === "object" && !Array.isArray(value);
  }
})();
