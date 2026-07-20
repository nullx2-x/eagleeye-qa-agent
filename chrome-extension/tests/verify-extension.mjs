import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const read = (name) => readFile(join(root, name), "utf8");
const manifest = JSON.parse(await read("manifest.json"));
const sources = Object.fromEntries(
  await Promise.all(
    ["background.js", "content.js", "popup.js"].map(async (name) => [name, await read(name)]),
  ),
);
const popupHtml = await read("popup.html");
const privacyHtml = await read("privacy.html");

const extensionId = createHash("sha256")
  .update(Buffer.from(manifest.key, "base64"))
  .digest()
  .subarray(0, 16)
  .toString("hex")
  .replace(/[0-9a-f]/g, (character) =>
    String.fromCharCode("a".charCodeAt(0) + Number.parseInt(character, 16)),
  );

assert.equal(manifest.manifest_version, 3);
assert.match(extensionId, /^[a-p]{32}$/u);
assert.deepEqual(manifest.permissions, ["activeTab", "scripting", "storage"]);
assert.deepEqual(manifest.host_permissions, [
  "http://127.0.0.1:8766/*",
  "http://localhost:8766/*",
]);
assert.equal(manifest.background.service_worker, "background.js");
assert.equal(manifest.action.default_popup, "popup.html");
assert.equal(manifest.content_scripts, undefined);

const combined = Object.values(sources).join("\n");
for (const forbidden of [
  /\.innerHTML\b/u,
  /\.outerHTML\b/u,
  /insertAdjacentHTML/u,
  /document\.write/u,
  /\beval\s*\(/u,
  /new\s+Function\b/u,
]) {
  assert.doesNotMatch(combined, forbidden);
}

assert.doesNotMatch(combined, /chrome\.storage\.(?:local|sync|managed)\b/u);
assert.match(sources["background.js"], /chrome\.storage\.session/u);
assert.match(sources["background.js"], /captureVisibleTab/u);
assert.doesNotMatch(sources["content.js"], /\.value\b/u);
assert.doesNotMatch(sources["content.js"], /\bFormData\b/u);
assert.doesNotMatch(
  sources["popup.js"],
  /sessionId\.textContent\s*=\s*currentState\?\.sessionId\s*(?:\?\?|;)/u,
);
assert.match(sources["popup.js"], /sessionId\.textContent.*ID非表示/u);

for (const endpoint of [
  "/api/v1/browser-agent/sessions",
  "/observations",
  "/generate",
  "/run",
  "/report",
]) {
  assert.match(sources["background.js"], new RegExp(endpoint.replaceAll("/", "\\/"), "u"));
}

for (const label of [
  "開始",
  "停止",
  "AI生成",
  "Replay",
  "レポート表示",
  "このセッションを端末から削除",
]) {
  assert.match(popupHtml, new RegExp(`>${label}<`, "u"));
}
assert.match(popupHtml, /id="privacy-consent"/u);
assert.match(popupHtml, /href="privacy\.html"/u);
assert.match(sources["popup.js"], /privacyConsent: elements\.consent\.checked/u);
assert.match(sources["background.js"], /payload\.privacyConsent !== true/u);
assert.match(sources["background.js"], /method: "DELETE"/u);
assert.match(privacyHtml, /フォーム入力値とスクリーンショットは送りません/u);
assert.doesNotMatch(privacyHtml, /<script\b/iu);
assert.doesNotMatch(popupHtml, /\son[a-z]+\s*=/iu);
assert.equal((popupHtml.match(/<script\b/gu) ?? []).length, 1);
assert.match(popupHtml, /<script src="popup\.js" defer><\/script>/u);

for (const [name, maximum] of [
  ["MAX_HEADINGS", 40],
  ["MAX_LANDMARKS", 30],
  ["MAX_CONTROLS", 150],
]) {
  const match = sources["content.js"].match(new RegExp(`const ${name} = (\\d+);`, "u"));
  assert.ok(match, `${name} is declared`);
  assert.ok(Number(match[1]) <= maximum, `${name} stays within the API limit`);
}

assert.match(sources["content.js"], /redacted: true/u);
assert.match(sources["content.js"], /valueType/u);
assert.match(sources["content.js"], /pageTitle/u);
assert.match(sources["content.js"], /headings/u);
assert.match(sources["content.js"], /landmarks/u);
assert.match(sources["content.js"], /controls/u);

console.log("PASS manifest v3 / deterministic public extension identity (value withheld)");
console.log("PASS minimal permissions / session-only storage / bounded accessible summary");
console.log("PASS no input values / no innerHTML / no eval / optional visible screenshot path");
console.log("PASS prominent privacy disclosure / explicit consent / local session deletion");
