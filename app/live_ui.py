"""Dependency-free assets for the EagleEye browser-agent live console."""


def live_html() -> str:
    """Return the semantic shell for the browser-agent live console."""
    return r"""<!doctype html>
<html lang="ja" data-theme="dark">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="dark light">
  <meta name="description" content="EagleEye Live Browser QA operations console">
  <link rel="icon" href="data:,">
  <link rel="stylesheet" href="/assets/live.css">
  <script src="/assets/live.js" defer></script>
  <title>EagleEye Live QA</title>
</head>
<body>
  <a class="skip-link" href="#main-content">メインコンテンツへ移動</a>
  <div class="app-shell">
    <header class="topbar">
      <a class="brand" href="#dashboard" aria-label="EagleEye Live QA ホーム">
        <span class="brand-mark" aria-hidden="true">E</span>
        <span>
          <strong>EagleEye</strong>
          <small>LIVE QA</small>
        </span>
      </a>
      <div class="topbar-actions">
        <div id="service-indicator" class="service-indicator" data-state="loading"
             role="status" aria-live="polite">
          <span class="service-dot" aria-hidden="true"></span>
          <span id="service-label">接続確認中</span>
        </div>
        <button id="theme-toggle" class="icon-button theme-toggle" type="button"
                aria-pressed="false" aria-label="ライト表示に切り替える">
          <span class="theme-icon" aria-hidden="true">◐</span>
          <span>ダーク / ライト</span>
        </button>
      </div>
    </header>

    <nav class="peer-tabs" aria-label="Live QA ワークスペース">
      <div class="tab-list" role="tablist" aria-label="運用ビュー">
        <button id="tab-dashboard" class="tab-button" type="button" role="tab"
                aria-selected="true" aria-controls="panel-dashboard" tabindex="0"
                data-tab="dashboard">Dashboard</button>
        <button id="tab-tests" class="tab-button" type="button" role="tab"
                aria-selected="false" aria-controls="panel-tests" tabindex="-1"
                data-tab="tests">Test一覧</button>
        <button id="tab-running" class="tab-button" type="button" role="tab"
                aria-selected="false" aria-controls="panel-running" tabindex="-1"
                data-tab="running">
          実行中 <span id="running-tab-count" class="tab-count">0</span>
        </button>
        <button id="tab-reports" class="tab-button" type="button" role="tab"
                aria-selected="false" aria-controls="panel-reports" tabindex="-1"
                data-tab="reports">レポート</button>
      </div>
    </nav>

    <main id="main-content" class="main-content" tabindex="-1">
      <section id="panel-dashboard" class="tab-panel" role="tabpanel"
               aria-labelledby="tab-dashboard" data-panel="dashboard">
        <div class="hero-grid">
          <section class="hero-copy" aria-labelledby="live-title">
            <p class="eyebrow">LIVE BROWSER QA</p>
            <h1 id="live-title">
              <span>普段どおり操作するだけ。</span>
              <span>AIがテストに変える</span>
            </h1>
            <p class="hero-lead">
              操作の観察から再現、説明、共有までを一つの証跡にまとめます。
              入力値や秘密情報は記録せず、実行判断は人間に残します。
            </p>

            <ol class="workflow" aria-label="EagleEye の5段階">
              <li>
                <span class="workflow-index">01</span>
                <strong>Observe</strong>
                <small>操作を安全に観察</small>
              </li>
              <li>
                <span class="workflow-index">02</span>
                <strong>Generate</strong>
                <small>テストへ構造化</small>
              </li>
              <li>
                <span class="workflow-index">03</span>
                <strong>Replay</strong>
                <small>同じ導線を再実行</small>
              </li>
              <li>
                <span class="workflow-index">04</span>
                <strong>Explain</strong>
                <small>原因と修正案を説明</small>
              </li>
              <li>
                <span class="workflow-index">05</span>
                <strong>Share</strong>
                <small>証跡レポートを共有</small>
              </li>
            </ol>

            <div class="hero-actions">
              <button id="local-sample" class="button button-primary" type="button"
                      aria-describedby="demo-help" disabled>
                <span id="local-sample-label">ローカルサンプルを作成</span>
              </button>
              <a class="button button-secondary" href="#extension-setup">拡張導入ガイド</a>
            </div>
            <p id="demo-help" class="action-help">接続状態を確認しています。</p>
          </section>

          <aside class="readiness-card" aria-labelledby="readiness-title">
            <div class="card-heading">
              <div>
                <p class="section-kicker">READINESS</p>
                <h2 id="readiness-title">今すぐ動かせる状態</h2>
              </div>
              <span id="readiness-badge" class="badge badge-loading">確認中</span>
            </div>
            <dl class="readiness-list">
              <div>
                <dt>Codex / provider</dt>
                <dd id="provider-state">読み込み中</dd>
              </div>
              <div>
                <dt>Authorized sample target</dt>
                <dd id="target-state">読み込み中</dd>
              </div>
              <div>
                <dt>Browser extension</dt>
                <dd id="extension-state">読み込み中</dd>
              </div>
            </dl>
            <p id="provider-guidance" class="readiness-guidance">
              provider 状態を取得しています。
            </p>
          </aside>
        </div>

        <div id="dashboard-alert" class="state-host" aria-live="polite">
          <div class="state-box" data-state="loading" role="status">
            <span class="state-symbol" aria-hidden="true"></span>
            <div>
              <strong>運用データを読み込み中</strong>
              <p>Browser Agent とセッション履歴を確認しています。</p>
            </div>
          </div>
        </div>

        <section class="metrics" aria-label="Live QA サマリー">
          <article class="metric-card">
            <span>Tests</span>
            <strong id="metric-tests">—</strong>
            <small>生成済みケース</small>
          </article>
          <article class="metric-card">
            <span>Running</span>
            <strong id="metric-running">—</strong>
            <small>現在の Replay</small>
          </article>
          <article class="metric-card">
            <span>Passed</span>
            <strong id="metric-passed">—</strong>
            <small>成功セッション</small>
          </article>
          <article class="metric-card">
            <span>Reports</span>
            <strong id="metric-reports">—</strong>
            <small>共有可能な証跡</small>
          </article>
        </section>

        <div class="dashboard-grid">
          <section class="panel" aria-labelledby="recent-title">
            <div class="panel-heading">
              <div>
                <p class="section-kicker">RECENT ACTIVITY</p>
                <h2 id="recent-title">最近のテスト</h2>
              </div>
              <button class="text-button" type="button" data-open-tab="tests">すべて表示</button>
            </div>
            <div id="dashboard-recent" class="panel-body state-host" aria-live="polite">
              <div class="state-box state-box-compact" data-state="loading" role="status">
                <span class="state-symbol" aria-hidden="true"></span>
                <div><strong>セッションを読み込み中</strong></div>
              </div>
            </div>
          </section>

          <section id="extension-setup" class="panel" aria-labelledby="extension-title">
            <div class="panel-heading">
              <div>
                <p class="section-kicker">ONE-TIME SETUP</p>
                <h2 id="extension-title">ブラウザー拡張を導入</h2>
              </div>
              <span class="badge badge-neutral">約1分</span>
            </div>
            <div class="panel-body extension-guide">
              <ol>
                <li>Chrome の拡張機能管理を開く</li>
                <li>デベロッパーモードを有効にする</li>
                <li>EagleEye 拡張を「パッケージ化されていない拡張機能」として読み込む</li>
              </ol>
              <a id="extension-install-link" class="inline-link" href="chrome://extensions/"
                 target="_blank" rel="noopener noreferrer">Chrome 拡張機能を開く</a>
              <dl class="setup-meta">
                <div>
                  <dt>許可済み origin</dt>
                  <dd id="extension-origin">取得中</dd>
                </div>
                <div>
                  <dt>Privacy</dt>
                  <dd>入力値・password・token は保存しません</dd>
                </div>
              </dl>
            </div>
          </section>
        </div>
      </section>

      <section id="panel-tests" class="tab-panel" role="tabpanel"
               aria-labelledby="tab-tests" data-panel="tests" hidden>
        <div class="page-heading">
          <div>
            <p class="section-kicker">TEST LIBRARY</p>
            <h1>Test一覧</h1>
            <p>観察から生成されたケースを確認し、承認したセッションだけ Replay します。</p>
          </div>
          <button id="refresh-sessions" class="button button-secondary" type="button">
            更新
          </button>
        </div>
        <div id="tests-state" class="state-host" aria-live="polite"></div>
        <div id="tests-table-wrap" class="table-panel" hidden>
          <table>
            <caption class="sr-only">Browser Agent のテストセッション一覧</caption>
            <thead>
              <tr>
                <th scope="col">テスト</th>
                <th scope="col">状態</th>
                <th scope="col">更新</th>
                <th scope="col">Cases / Events</th>
                <th scope="col"><span class="sr-only">操作</span></th>
              </tr>
            </thead>
            <tbody id="tests-body"></tbody>
          </table>
        </div>
      </section>

      <section id="panel-running" class="tab-panel" role="tabpanel"
               aria-labelledby="tab-running" data-panel="running" hidden>
        <div class="page-heading">
          <div>
            <p class="section-kicker">ACTIVE REPLAY</p>
            <h1>実行中</h1>
            <p>進行中の Replay と、完了後に判定へ渡る流れを監視します。</p>
          </div>
        </div>
        <div id="running-state" class="state-host" aria-live="polite"></div>
        <div id="running-list" class="session-grid" aria-live="polite"></div>
      </section>

      <section id="panel-reports" class="tab-panel" role="tabpanel"
               aria-labelledby="tab-reports" data-panel="reports" hidden>
        <div class="page-heading">
          <div>
            <p class="section-kicker">EVIDENCE &amp; EXPLANATION</p>
            <h1>レポート</h1>
            <p>PASS / FAIL を根拠、再現回数、修正提案と一緒に共有します。</p>
          </div>
        </div>
        <div id="reports-state" class="state-host" aria-live="polite"></div>
        <div id="reports-list" class="report-list" aria-live="polite"></div>
      </section>
    </main>

    <footer class="footer">
      <span>Local-first · secret-safe · human-approved</span>
      <span>Observe → Generate → Replay → Explain → Share</span>
    </footer>
  </div>
  <div id="toast" class="toast" role="status" aria-live="polite" hidden></div>
</body>
</html>
"""


def live_css() -> str:
    """Return the self-contained responsive stylesheet for the live console."""
    return r""":root {
  color-scheme: dark;
  --bg: #0a0d12;
  --surface: #10151d;
  --surface-raised: #151b24;
  --surface-muted: #0d1118;
  --line: #27303d;
  --line-strong: #384455;
  --text: #edf2f7;
  --text-soft: #c7d0dc;
  --muted: #8e9aaa;
  --accent: #3dd6ba;
  --accent-strong: #22ad98;
  --accent-soft: #123b36;
  --blue: #6ea8fe;
  --green: #56d69b;
  --amber: #efbd67;
  --red: #ff7d83;
  --shadow: 0 18px 48px rgb(0 0 0 / 24%);
  --radius: 10px;
  --radius-small: 7px;
  --content: 1380px;
  font-family:
    Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI",
    sans-serif;
}

:root[data-theme="light"] {
  color-scheme: light;
  --bg: #f2f5f8;
  --surface: #ffffff;
  --surface-raised: #f8fafc;
  --surface-muted: #eef2f6;
  --line: #d9e0e8;
  --line-strong: #b8c3d0;
  --text: #18212d;
  --text-soft: #354254;
  --muted: #647286;
  --accent: #087e70;
  --accent-strong: #06685d;
  --accent-soft: #d9f2ed;
  --blue: #2563a9;
  --green: #187d52;
  --amber: #9a6411;
  --red: #b6323a;
  --shadow: 0 18px 48px rgb(26 39 57 / 10%);
}

*,
*::before,
*::after {
  box-sizing: border-box;
}

html {
  scroll-behavior: smooth;
}

body {
  min-width: 300px;
  min-height: 100vh;
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-size: 14px;
  line-height: 1.5;
  text-rendering: optimizeLegibility;
}

button,
a {
  -webkit-tap-highlight-color: transparent;
}

button {
  font: inherit;
}

a {
  color: inherit;
}

[hidden] {
  display: none !important;
}

:focus-visible {
  outline: 2px solid var(--blue);
  outline-offset: 3px;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.skip-link {
  position: fixed;
  top: 8px;
  left: 8px;
  z-index: 100;
  padding: 8px 12px;
  border-radius: var(--radius-small);
  background: var(--text);
  color: var(--bg);
  font-weight: 700;
  transform: translateY(-160%);
}

.skip-link:focus {
  transform: translateY(0);
}

.app-shell {
  min-height: 100vh;
  display: grid;
  grid-template-rows: 58px 48px 1fr auto;
}

.topbar {
  position: sticky;
  top: 0;
  z-index: 40;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 0 max(20px, calc((100vw - var(--content)) / 2));
  border-bottom: 1px solid var(--line);
  background: color-mix(in srgb, var(--bg) 91%, transparent);
  backdrop-filter: blur(16px);
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: var(--text);
  text-decoration: none;
}

.brand-mark {
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  border: 1px solid color-mix(in srgb, var(--accent) 55%, var(--line));
  border-radius: 50%;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 13px;
  font-weight: 900;
}

.brand strong,
.brand small {
  display: block;
}

.brand strong {
  font-size: 14px;
  line-height: 1.1;
  letter-spacing: 0.01em;
}

.brand small {
  margin-top: 2px;
  color: var(--muted);
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.18em;
}

.topbar-actions,
.service-indicator,
.icon-button {
  display: flex;
  align-items: center;
}

.topbar-actions {
  gap: 10px;
}

.service-indicator {
  gap: 7px;
  min-height: 30px;
  padding: 0 10px;
  border: 1px solid var(--line);
  border-radius: 999px;
  color: var(--muted);
  font-size: 11px;
  font-weight: 700;
}

.service-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--amber);
}

.service-indicator[data-state="success"] .service-dot {
  background: var(--green);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--green) 16%, transparent);
}

.service-indicator[data-state="error"] .service-dot {
  background: var(--red);
}

.icon-button {
  min-height: 32px;
  gap: 7px;
  padding: 0 10px;
  border: 1px solid var(--line);
  border-radius: var(--radius-small);
  background: transparent;
  color: var(--text-soft);
  cursor: pointer;
  font-size: 11px;
}

.icon-button:hover {
  border-color: var(--line-strong);
  background: var(--surface-raised);
}

.theme-icon {
  color: var(--accent);
  font-size: 15px;
}

.peer-tabs {
  position: sticky;
  top: 58px;
  z-index: 30;
  border-bottom: 1px solid var(--line);
  background: var(--bg);
}

.tab-list {
  width: min(100%, var(--content));
  height: 100%;
  display: flex;
  align-items: stretch;
  gap: 22px;
  margin: 0 auto;
  padding: 0 20px;
  overflow-x: auto;
  scrollbar-width: none;
}

.tab-list::-webkit-scrollbar {
  display: none;
}

.tab-button {
  position: relative;
  min-width: max-content;
  padding: 0 2px;
  border: 0;
  background: transparent;
  color: var(--muted);
  cursor: pointer;
  font-size: 12px;
  font-weight: 700;
}

.tab-button::after {
  position: absolute;
  right: 0;
  bottom: -1px;
  left: 0;
  height: 2px;
  background: var(--accent);
  content: "";
  opacity: 0;
  transform: scaleX(0.6);
  transition: opacity 140ms ease, transform 140ms ease;
}

.tab-button:hover,
.tab-button[aria-selected="true"] {
  color: var(--text);
}

.tab-button[aria-selected="true"]::after {
  opacity: 1;
  transform: scaleX(1);
}

.tab-count {
  display: inline-grid;
  min-width: 18px;
  min-height: 18px;
  place-items: center;
  margin-left: 4px;
  padding: 0 5px;
  border-radius: 999px;
  background: var(--surface-raised);
  color: var(--text-soft);
  font-size: 9px;
}

.main-content {
  width: min(100%, var(--content));
  margin: 0 auto;
  padding: 26px 20px 48px;
}

.tab-panel {
  animation: panel-in 160ms ease-out;
}

@keyframes panel-in {
  from {
    opacity: 0;
    transform: translateY(3px);
  }

  to {
    opacity: 1;
    transform: none;
  }
}

.hero-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(320px, 0.7fr);
  gap: 20px;
}

.hero-copy,
.readiness-card,
.panel,
.table-panel,
.session-card,
.report-card {
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--surface);
}

.hero-copy {
  padding: clamp(22px, 4vw, 42px);
  background:
    linear-gradient(135deg, color-mix(in srgb, var(--accent-soft) 62%, transparent), transparent 48%),
    var(--surface);
}

.eyebrow,
.section-kicker {
  margin: 0;
  color: var(--accent);
  font-size: 10px;
  font-weight: 900;
  letter-spacing: 0.16em;
}

.hero-copy h1 {
  max-width: 760px;
  margin: 12px 0 12px;
  font-size: clamp(28px, 4vw, 46px);
  line-height: 1.15;
  letter-spacing: -0.035em;
}

.hero-copy h1 span {
  display: block;
}

.hero-lead {
  max-width: 720px;
  margin: 0;
  color: var(--text-soft);
  font-size: 14px;
}

.workflow {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  margin: 30px 0 26px;
  padding: 0;
  list-style: none;
}

.workflow li {
  position: relative;
  min-width: 0;
  padding: 0 12px;
  border-left: 1px solid var(--line);
}

.workflow li:first-child {
  padding-left: 0;
  border-left: 0;
}

.workflow-index,
.workflow strong,
.workflow small {
  display: block;
}

.workflow-index {
  margin-bottom: 8px;
  color: var(--accent);
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 9px;
}

.workflow strong {
  font-size: 12px;
}

.workflow small {
  margin-top: 3px;
  color: var(--muted);
  font-size: 10px;
  line-height: 1.4;
}

.hero-actions,
.row-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.button,
.text-button,
.inline-link {
  font-weight: 750;
  text-decoration: none;
}

.button {
  min-height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 0 13px;
  border: 1px solid transparent;
  border-radius: var(--radius-small);
  cursor: pointer;
  font-size: 12px;
}

.button-primary {
  background: var(--accent-strong);
  color: #ffffff;
}

.button-primary:hover:not(:disabled) {
  background: var(--accent);
  color: #071411;
}

.button-secondary {
  border-color: var(--line-strong);
  background: var(--surface-raised);
  color: var(--text);
}

.button-secondary:hover:not(:disabled) {
  border-color: var(--accent);
}

.button-small {
  min-height: 30px;
  padding: 0 10px;
  font-size: 11px;
}

.button:disabled {
  border-color: var(--line);
  background: var(--surface-muted);
  color: var(--muted);
  cursor: not-allowed;
  opacity: 0.72;
}

.action-help {
  min-height: 18px;
  margin: 8px 0 0;
  color: var(--muted);
  font-size: 10px;
}

.readiness-card {
  padding: 20px;
}

.card-heading,
.panel-heading,
.page-heading,
.session-card-heading,
.report-card-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.card-heading h2,
.panel-heading h2,
.page-heading h1 {
  margin: 4px 0 0;
}

.card-heading h2,
.panel-heading h2 {
  font-size: 15px;
}

.badge {
  display: inline-flex;
  min-height: 22px;
  align-items: center;
  justify-content: center;
  padding: 0 8px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: var(--surface-muted);
  color: var(--text-soft);
  font-size: 9px;
  font-weight: 900;
  letter-spacing: 0.05em;
  white-space: nowrap;
}

.badge-success,
.badge-passed {
  border-color: color-mix(in srgb, var(--green) 38%, var(--line));
  background: color-mix(in srgb, var(--green) 13%, var(--surface));
  color: var(--green);
}

.badge-warning,
.badge-recording,
.badge-generated,
.badge-running,
.badge-loading {
  border-color: color-mix(in srgb, var(--amber) 32%, var(--line));
  background: color-mix(in srgb, var(--amber) 10%, var(--surface));
  color: var(--amber);
}

.badge-error,
.badge-failed {
  border-color: color-mix(in srgb, var(--red) 38%, var(--line));
  background: color-mix(in srgb, var(--red) 12%, var(--surface));
  color: var(--red);
}

.badge-neutral {
  color: var(--muted);
}

.readiness-list {
  margin: 18px 0 0;
}

.readiness-list div,
.setup-meta div {
  display: grid;
  grid-template-columns: minmax(120px, 0.8fr) minmax(0, 1.2fr);
  gap: 12px;
  padding: 11px 0;
  border-top: 1px solid var(--line);
}

.readiness-list dt,
.setup-meta dt {
  color: var(--muted);
  font-size: 10px;
}

.readiness-list dd,
.setup-meta dd {
  min-width: 0;
  margin: 0;
  color: var(--text-soft);
  font-size: 11px;
  overflow-wrap: anywhere;
}

.readiness-guidance {
  margin: 12px 0 0;
  padding: 10px;
  border-radius: var(--radius-small);
  background: var(--surface-muted);
  color: var(--muted);
  font-size: 10px;
}

.state-host {
  margin-top: 14px;
}

.state-box {
  display: flex;
  align-items: flex-start;
  gap: 11px;
  min-height: 56px;
  padding: 12px 14px;
  border: 1px solid var(--line);
  border-radius: var(--radius-small);
  background: var(--surface-muted);
  color: var(--text-soft);
}

.state-box-compact {
  min-height: 44px;
  padding: 9px 10px;
}

.state-box[data-state="success"] {
  border-color: color-mix(in srgb, var(--green) 30%, var(--line));
}

.state-box[data-state="warning"] {
  border-color: color-mix(in srgb, var(--amber) 34%, var(--line));
}

.state-box[data-state="error"] {
  border-color: color-mix(in srgb, var(--red) 36%, var(--line));
}

.state-symbol {
  width: 8px;
  height: 8px;
  flex: 0 0 auto;
  margin-top: 6px;
  border-radius: 50%;
  background: var(--amber);
}

.state-box[data-state="success"] .state-symbol {
  background: var(--green);
}

.state-box[data-state="error"] .state-symbol {
  background: var(--red);
}

.state-box strong,
.state-box p {
  display: block;
}

.state-box strong {
  font-size: 11px;
}

.state-box p {
  margin: 2px 0 0;
  color: var(--muted);
  font-size: 10px;
}

.state-box .button {
  margin-left: auto;
}

.metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin: 14px 0;
}

.metric-card {
  min-width: 0;
  padding: 14px;
  border: 1px solid var(--line);
  border-radius: var(--radius-small);
  background: var(--surface);
}

.metric-card span,
.metric-card small {
  color: var(--muted);
}

.metric-card span {
  display: block;
  font-size: 9px;
  font-weight: 850;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.metric-card strong {
  display: block;
  margin: 5px 0 1px;
  font-size: 24px;
  line-height: 1.1;
}

.metric-card small {
  font-size: 9px;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(320px, 0.75fr);
  gap: 14px;
}

.panel-heading {
  padding: 14px 16px;
  border-bottom: 1px solid var(--line);
}

.panel-body {
  margin-top: 0;
  padding: 14px 16px;
}

.text-button {
  padding: 2px;
  border: 0;
  background: transparent;
  color: var(--accent);
  cursor: pointer;
  font-size: 10px;
}

.text-button:hover,
.inline-link:hover {
  text-decoration: underline;
  text-underline-offset: 3px;
}

.activity-list,
.extension-guide ol {
  margin: 0;
  padding: 0;
  list-style: none;
}

.activity-item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 12px;
  padding: 10px 0;
  border-top: 1px solid var(--line);
}

.activity-item:first-child {
  padding-top: 0;
  border-top: 0;
}

.activity-copy,
.session-copy,
.report-copy {
  min-width: 0;
}

.activity-copy strong,
.activity-copy small,
.session-copy strong,
.session-copy small,
.report-copy strong,
.report-copy small {
  display: block;
}

.activity-copy strong,
.session-copy strong,
.report-copy strong {
  overflow: hidden;
  color: var(--text-soft);
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.activity-copy small,
.session-copy small,
.report-copy small {
  margin-top: 2px;
  overflow: hidden;
  color: var(--muted);
  font-size: 9px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.activity-time,
.table-meta {
  color: var(--muted);
  font-size: 9px;
  white-space: nowrap;
}

.extension-guide ol {
  counter-reset: setup;
}

.extension-guide li {
  position: relative;
  min-height: 30px;
  padding: 5px 0 5px 34px;
  color: var(--text-soft);
  counter-increment: setup;
  font-size: 11px;
}

.extension-guide li::before {
  position: absolute;
  top: 3px;
  left: 0;
  width: 24px;
  height: 24px;
  display: grid;
  place-items: center;
  border: 1px solid var(--line);
  border-radius: 50%;
  color: var(--accent);
  content: counter(setup);
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 9px;
}

.inline-link {
  display: inline-block;
  margin: 10px 0 14px;
  color: var(--accent);
  font-size: 11px;
}

.setup-meta {
  margin: 0;
}

.page-heading {
  margin-bottom: 18px;
}

.page-heading h1 {
  font-size: 24px;
  letter-spacing: -0.02em;
}

.page-heading p:last-child {
  margin: 5px 0 0;
  color: var(--muted);
  font-size: 11px;
}

.table-panel {
  overflow: hidden;
}

.table-panel table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}

.table-panel th,
.table-panel td {
  padding: 11px 14px;
  border-bottom: 1px solid var(--line);
  text-align: left;
  vertical-align: middle;
}

.table-panel th {
  background: var(--surface-muted);
  color: var(--muted);
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.table-panel td {
  color: var(--text-soft);
  font-size: 11px;
}

.table-panel tbody tr:last-child td {
  border-bottom: 0;
}

.table-panel tbody tr:hover td {
  background: var(--surface-raised);
}

.table-panel th:nth-child(1) {
  width: 38%;
}

.table-panel th:nth-child(2) {
  width: 12%;
}

.table-panel th:nth-child(3) {
  width: 16%;
}

.table-panel th:nth-child(4) {
  width: 14%;
}

.table-panel th:nth-child(5) {
  width: 20%;
}

.row-actions {
  justify-content: flex-end;
}

.session-grid,
.report-list {
  display: grid;
  gap: 10px;
}

.session-card,
.report-card {
  padding: 15px 16px;
}

.session-card {
  border-left: 3px solid var(--amber);
}

.session-progress {
  height: 3px;
  margin-top: 14px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--surface-muted);
}

.session-progress::after {
  width: 34%;
  height: 100%;
  display: block;
  border-radius: inherit;
  background: var(--accent);
  content: "";
  animation: progress 1.6s ease-in-out infinite;
}

@keyframes progress {
  0% {
    transform: translateX(-110%);
  }

  100% {
    transform: translateX(310%);
  }
}

.session-detail,
.report-detail {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  margin-top: 10px;
  color: var(--muted);
  font-size: 9px;
}

.report-card-heading {
  align-items: center;
}

.report-card[data-result="passed"] {
  border-left: 3px solid var(--green);
}

.report-card[data-result="failed"] {
  border-left: 3px solid var(--red);
}

.footer {
  width: min(100%, var(--content));
  display: flex;
  justify-content: space-between;
  gap: 20px;
  margin: 0 auto;
  padding: 18px 20px 26px;
  color: var(--muted);
  font-size: 9px;
  letter-spacing: 0.04em;
}

.toast {
  position: fixed;
  right: 18px;
  bottom: 18px;
  z-index: 80;
  max-width: min(420px, calc(100vw - 36px));
  padding: 10px 13px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-small);
  background: var(--surface-raised);
  box-shadow: var(--shadow);
  color: var(--text);
  font-size: 11px;
}

.toast[data-state="error"] {
  border-color: var(--red);
}

@media (max-width: 940px) {
  .hero-grid,
  .dashboard-grid {
    grid-template-columns: 1fr;
  }

  .workflow {
    overflow-x: auto;
  }

  .workflow li {
    min-width: 128px;
  }

  .table-panel {
    overflow-x: auto;
  }

  .table-panel table {
    min-width: 820px;
  }
}

@media (max-width: 640px) {
  .app-shell {
    grid-template-rows: 54px 46px 1fr auto;
  }

  .topbar {
    padding: 0 12px;
  }

  .service-indicator {
    padding: 0 8px;
  }

  .service-indicator span:last-child {
    max-width: 106px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .theme-toggle span:last-child {
    display: none;
  }

  .peer-tabs {
    top: 54px;
  }

  .tab-list {
    gap: 18px;
    padding: 0 12px;
  }

  .main-content {
    padding: 16px 12px 34px;
  }

  .hero-copy,
  .readiness-card {
    padding: 18px;
  }

  .hero-copy h1 {
    font-size: 29px;
  }

  .workflow {
    margin: 24px -18px 22px;
    padding: 0 18px 5px;
  }

  .workflow li:first-child {
    padding-left: 0;
  }

  .hero-actions .button {
    width: 100%;
  }

  .metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .activity-item {
    grid-template-columns: minmax(0, 1fr) auto;
  }

  .activity-time {
    display: none;
  }

  .page-heading {
    align-items: flex-end;
  }

  .state-box {
    flex-wrap: wrap;
  }

  .state-box .button {
    width: 100%;
    margin: 2px 0 0;
  }

  .report-card-heading {
    align-items: flex-start;
  }

  .report-card-heading .button {
    flex: 0 0 auto;
  }

  .footer {
    display: grid;
    padding: 14px 12px 22px;
  }
}

@media (prefers-reduced-motion: reduce) {
  html {
    scroll-behavior: auto;
  }

  *,
  *::before,
  *::after {
    scroll-behavior: auto !important;
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
"""


def live_js() -> str:
    """Return safe DOM-only behavior for the live console."""
    return r"""(() => {
  "use strict";

  const ENDPOINTS = Object.freeze({
    status: "/api/v1/browser-agent/status",
    sessions: "/api/v1/browser-agent/sessions",
    localSample: "/api/v1/browser-agent/sample/local",
    run: (sessionId) =>
      `/api/v1/browser-agent/sessions/${encodeURIComponent(sessionId)}/run`,
    report: (sessionId) =>
      `/api/v1/browser-agent/sessions/${encodeURIComponent(sessionId)}/report`,
  });

  const STATUS_META = Object.freeze({
    recording: Object.freeze({ label: "OBSERVE", badge: "recording" }),
    generated: Object.freeze({ label: "GENERATED", badge: "generated" }),
    running: Object.freeze({ label: "REPLAY中", badge: "running" }),
    passed: Object.freeze({ label: "PASS", badge: "passed" }),
    failed: Object.freeze({ label: "FAIL", badge: "failed" }),
  });

  const state = {
    agent: null,
    sessions: [],
    statusLoading: true,
    sessionsLoading: true,
    refreshing: false,
    statusError: "",
    sessionsError: "",
    demoBusy: false,
    busyRuns: new Set(),
    actionNotice: null,
    toastTimer: null,
  };

  const nodes = {};

  document.addEventListener("DOMContentLoaded", init);

  function init() {
    cacheNodes();
    setupTheme();
    setupTabs();
    nodes.demo.addEventListener("click", startLocalSample);
    nodes.refresh.addEventListener("click", () => refreshSessions(true));
    document.querySelectorAll("[data-open-tab]").forEach((button) => {
      button.addEventListener("click", () => activateTab(button.dataset.openTab, true));
    });
    renderAll();
    loadAll();
    window.setInterval(refreshWhileRunning, 6000);
  }

  function cacheNodes() {
    nodes.service = byId("service-indicator");
    nodes.serviceLabel = byId("service-label");
    nodes.theme = byId("theme-toggle");
    nodes.demo = byId("local-sample");
    nodes.demoLabel = byId("local-sample-label");
    nodes.demoHelp = byId("demo-help");
    nodes.readinessBadge = byId("readiness-badge");
    nodes.providerState = byId("provider-state");
    nodes.targetState = byId("target-state");
    nodes.extensionState = byId("extension-state");
    nodes.providerGuidance = byId("provider-guidance");
    nodes.extensionOrigin = byId("extension-origin");
    nodes.dashboardAlert = byId("dashboard-alert");
    nodes.metricTests = byId("metric-tests");
    nodes.metricRunning = byId("metric-running");
    nodes.metricPassed = byId("metric-passed");
    nodes.metricReports = byId("metric-reports");
    nodes.dashboardRecent = byId("dashboard-recent");
    nodes.refresh = byId("refresh-sessions");
    nodes.testsState = byId("tests-state");
    nodes.testsTable = byId("tests-table-wrap");
    nodes.testsBody = byId("tests-body");
    nodes.runningState = byId("running-state");
    nodes.runningList = byId("running-list");
    nodes.runningCount = byId("running-tab-count");
    nodes.reportsState = byId("reports-state");
    nodes.reportsList = byId("reports-list");
    nodes.toast = byId("toast");
  }

  function byId(id) {
    const node = document.getElementById(id);
    if (!node) {
      throw new Error(`Live UI element is missing: ${id}`);
    }
    return node;
  }

  function setupTheme() {
    let saved = "";
    try {
      saved = window.localStorage.getItem("eagleeye-live-theme") || "";
    } catch {
      saved = "";
    }
    const preferred = window.matchMedia("(prefers-color-scheme: light)").matches
      ? "light"
      : "dark";
    applyTheme(saved === "light" || saved === "dark" ? saved : preferred);
    nodes.theme.addEventListener("click", () => {
      const next = document.documentElement.dataset.theme === "light" ? "dark" : "light";
      applyTheme(next);
      try {
        window.localStorage.setItem("eagleeye-live-theme", next);
      } catch {
        showToast("表示設定はこのページ内だけで有効です。", "warning");
      }
    });
  }

  function applyTheme(theme) {
    const light = theme === "light";
    document.documentElement.dataset.theme = light ? "light" : "dark";
    nodes.theme.setAttribute("aria-pressed", String(light));
    nodes.theme.setAttribute(
      "aria-label",
      light ? "ダーク表示に切り替える" : "ライト表示に切り替える",
    );
  }

  function setupTabs() {
    const tabs = Array.from(document.querySelectorAll('[role="tab"][data-tab]'));
    tabs.forEach((tab) => {
      tab.addEventListener("click", () => activateTab(tab.dataset.tab, false));
      tab.addEventListener("keydown", (event) => handleTabKey(event, tabs));
    });
    const requested = window.location.hash.replace("#", "");
    const initial = tabs.some((tab) => tab.dataset.tab === requested) ? requested : "dashboard";
    activateTab(initial, false);
  }

  function handleTabKey(event, tabs) {
    const keys = ["ArrowLeft", "ArrowRight", "Home", "End"];
    if (!keys.includes(event.key)) {
      return;
    }
    event.preventDefault();
    const current = tabs.indexOf(event.currentTarget);
    let next = current;
    if (event.key === "ArrowLeft") {
      next = (current - 1 + tabs.length) % tabs.length;
    } else if (event.key === "ArrowRight") {
      next = (current + 1) % tabs.length;
    } else if (event.key === "Home") {
      next = 0;
    } else if (event.key === "End") {
      next = tabs.length - 1;
    }
    activateTab(tabs[next].dataset.tab, true);
  }

  function activateTab(name, moveFocus) {
    const safeName = ["dashboard", "tests", "running", "reports"].includes(name)
      ? name
      : "dashboard";
    document.querySelectorAll('[role="tab"][data-tab]').forEach((tab) => {
      const active = tab.dataset.tab === safeName;
      tab.setAttribute("aria-selected", String(active));
      tab.tabIndex = active ? 0 : -1;
      if (active && moveFocus) {
        tab.focus();
      }
    });
    document.querySelectorAll("[data-panel]").forEach((panel) => {
      panel.hidden = panel.dataset.panel !== safeName;
    });
    if (window.location.hash !== `#${safeName}`) {
      window.history.replaceState(null, "", `#${safeName}`);
    }
  }

  async function loadAll() {
    state.statusLoading = true;
    state.sessionsLoading = true;
    state.statusError = "";
    state.sessionsError = "";
    renderAll();

    const results = await Promise.allSettled([
      requestJson(ENDPOINTS.status),
      requestJson(ENDPOINTS.sessions),
    ]);

    if (results[0].status === "fulfilled") {
      state.agent = normalizeAgent(results[0].value);
    } else {
      state.statusError = messageFromError(results[0].reason);
    }
    if (results[1].status === "fulfilled") {
      state.sessions = normalizeSessionList(results[1].value);
    } else {
      state.sessionsError = messageFromError(results[1].reason);
    }
    state.statusLoading = false;
    state.sessionsLoading = false;
    renderAll();
  }

  async function refreshSessions(announce) {
    if (state.refreshing) {
      return;
    }
    state.refreshing = true;
    state.sessionsError = "";
    renderSessionViews();
    try {
      const payload = await requestJson(ENDPOINTS.sessions);
      state.sessions = normalizeSessionList(payload);
      if (announce) {
        showToast("セッション一覧を更新しました。", "success");
      }
    } catch (error) {
      state.sessionsError = messageFromError(error);
      if (announce) {
        showToast("一覧を更新できませんでした。", "error");
      }
    } finally {
      state.refreshing = false;
      renderAll();
    }
  }

  async function refreshWhileRunning() {
    if (document.hidden || state.refreshing || state.busyRuns.size > 0) {
      return;
    }
    if (state.sessions.some((session) => session.status === "running")) {
      await refreshSessions(false);
    }
  }

  async function startLocalSample() {
    if (nodes.demo.disabled || state.demoBusy) {
      return;
    }
    state.demoBusy = true;
    state.actionNotice = {
      kind: "loading",
      title: "ローカルサンプルを準備中",
      detail: "公開導線を観察し、安全なテストケースへ変換しています。",
    };
    renderAll();
    try {
      const session = normalizeSession(await requestJson(ENDPOINTS.localSample, { method: "POST" }));
      upsertSession(session);
      state.actionNotice = {
        kind: "success",
        title: "ローカルサンプルを生成しました",
        detail: "Test一覧から Replay を実行すると、判定とレポートまで確認できます。",
      };
      activateTab("tests", true);
      showToast("ローカルサンプルを Test一覧へ追加しました。", "success");
    } catch (error) {
      const message = messageFromError(error);
      state.actionNotice = {
        kind: "error",
        title: "ローカルサンプルを開始できませんでした",
        detail: message,
      };
      showToast(message, "error");
    } finally {
      state.demoBusy = false;
      renderAll();
    }
  }

  async function runSession(sessionId) {
    if (state.busyRuns.has(sessionId)) {
      return;
    }
    state.busyRuns.add(sessionId);
    state.actionNotice = {
      kind: "loading",
      title: "Replay を実行中",
      detail: "操作を再現し、品質ゲートと証跡レポートを生成しています。",
    };
    activateTab("running", true);
    renderAll();
    try {
      const session = normalizeSession(
        await requestJson(ENDPOINTS.run(sessionId), { method: "POST" }),
      );
      upsertSession(session);
      const passed = session.status === "passed";
      state.actionNotice = {
        kind: passed ? "success" : "warning",
        title: passed ? "Replay が PASS しました" : "Replay の確認が必要です",
        detail: "レポートで根拠、再現回数、修正提案を確認してください。",
      };
      showToast(passed ? "Replay PASS" : "Replay 完了: 要確認", passed ? "success" : "warning");
      activateTab("reports", true);
    } catch (error) {
      const message = messageFromError(error);
      state.actionNotice = {
        kind: "error",
        title: "Replay を完了できませんでした",
        detail: message,
      };
      showToast(message, "error");
      activateTab("tests", true);
    } finally {
      state.busyRuns.delete(sessionId);
      renderAll();
    }
  }

  async function requestJson(url, options = {}) {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 15000);
    const headers = new Headers(options.headers || {});
    headers.set("Accept", "application/json");
    try {
      const response = await fetch(url, {
        ...options,
        credentials: "same-origin",
        headers,
        signal: controller.signal,
      });
      let payload = null;
      try {
        payload = await response.json();
      } catch {
        payload = null;
      }
      if (!response.ok) {
        throw new Error(errorDetail(payload, response.status));
      }
      return payload;
    } catch (error) {
      if (error && error.name === "AbortError") {
        throw new Error("API応答がタイムアウトしました。サービス状態を確認してください。");
      }
      throw error;
    } finally {
      window.clearTimeout(timeout);
    }
  }

  function errorDetail(payload, statusCode) {
    if (payload && typeof payload.detail === "string") {
      return payload.detail;
    }
    if (payload && Array.isArray(payload.detail)) {
      const details = payload.detail
        .map((item) => (item && typeof item.msg === "string" ? item.msg : ""))
        .filter(Boolean);
      if (details.length) {
        return details.join(" / ");
      }
    }
    return `API request failed (HTTP ${statusCode})`;
  }

  function messageFromError(error) {
    if (error instanceof Error && error.message) {
      return error.message;
    }
    return "予期しない通信エラーが発生しました。";
  }

  function normalizeAgent(value) {
    const source = value && typeof value === "object" ? value : {};
    return {
      status: textValue(source.status, "unknown"),
      extensionOrigin: textValue(source.extensionOrigin, "未登録"),
      selectedProvider: textValue(source.selectedProvider, "未選択"),
      providerConnected: source.providerConnected === true,
      setupGuidance: textValue(source.setupGuidance, "接続案内を取得できません。"),
      demoTarget: textValue(source.demoTarget, "未設定"),
      demoTargetReachable: source.demoTargetReachable === true,
    };
  }

  function normalizeSessionList(value) {
    const items = value && Array.isArray(value.sessions) ? value.sessions : [];
    return items.map(normalizeSession).sort((left, right) => right.updatedAt.localeCompare(left.updatedAt));
  }

  function normalizeSession(value) {
    const source = value && typeof value === "object" ? value : {};
    const generatedCases = Array.isArray(source.generatedCases) ? source.generatedCases : [];
    const observations = Array.isArray(source.observations) ? source.observations : [];
    return {
      id: textValue(source.id, "unknown"),
      name: textValue(source.name, "名称未設定のテスト"),
      goal: textValue(source.goal, "目的は未登録です。"),
      startUrl: textValue(source.startUrl, ""),
      status: STATUS_META[source.status] ? source.status : "recording",
      updatedAt: textValue(source.updatedAt, ""),
      caseCount: numberValue(source.caseCount, generatedCases.length),
      observationCount: numberValue(source.observationCount, observations.length),
      screenshotAvailable: source.screenshotAvailable === true,
      replayCount: numberValue(source.replayCount, 0),
    };
  }

  function textValue(value, fallback) {
    return typeof value === "string" && value.trim() ? value.trim() : fallback;
  }

  function numberValue(value, fallback) {
    return Number.isFinite(value) && value >= 0 ? value : fallback;
  }

  function upsertSession(session) {
    const others = state.sessions.filter((item) => item.id !== session.id);
    state.sessions = [session, ...others].sort((left, right) =>
      right.updatedAt.localeCompare(left.updatedAt),
    );
  }

  function renderAll() {
    renderReadiness();
    renderDashboardNotice();
    renderMetrics();
    renderRecent();
    renderSessionViews();
  }

  function renderReadiness() {
    if (state.statusLoading) {
      nodes.service.dataset.state = "loading";
      nodes.serviceLabel.textContent = "接続確認中";
      nodes.readinessBadge.className = "badge badge-loading";
      nodes.readinessBadge.textContent = "確認中";
      nodes.providerState.textContent = "読み込み中";
      nodes.targetState.textContent = "読み込み中";
      nodes.extensionState.textContent = "読み込み中";
      nodes.providerGuidance.textContent = "provider 状態を取得しています。";
      nodes.extensionOrigin.textContent = "取得中";
    } else if (state.statusError) {
      nodes.service.dataset.state = "error";
      nodes.serviceLabel.textContent = "API接続エラー";
      nodes.readinessBadge.className = "badge badge-error";
      nodes.readinessBadge.textContent = "OFFLINE";
      nodes.providerState.textContent = "確認できません";
      nodes.targetState.textContent = "確認できません";
      nodes.extensionState.textContent = "確認できません";
      nodes.providerGuidance.textContent = state.statusError;
      nodes.extensionOrigin.textContent = "API接続後に表示します";
    } else {
      const agent = state.agent;
      const fullyReady = agent.providerConnected && agent.demoTargetReachable;
      nodes.service.dataset.state = "success";
      nodes.serviceLabel.textContent = "Browser Agent ready";
      nodes.readinessBadge.className = `badge ${fullyReady ? "badge-success" : "badge-warning"}`;
      nodes.readinessBadge.textContent = fullyReady ? "READY" : "DEGRADED";
      nodes.providerState.textContent = agent.providerConnected
        ? `${agent.selectedProvider} · 接続済み`
        : `${agent.selectedProvider} · fallback`;
      nodes.targetState.textContent = agent.demoTargetReachable
        ? `${agent.demoTarget} · 到達可`
        : `${agent.demoTarget} · 停止中`;
      nodes.extensionState.textContent = agent.extensionOrigin === "未登録" ? "未登録" : "origin 登録済み";
      nodes.providerGuidance.textContent = agent.setupGuidance;
      nodes.extensionOrigin.textContent = agent.extensionOrigin;
    }

    const targetUnavailable = !state.agent || !state.agent.demoTargetReachable;
    nodes.demo.disabled =
      state.statusLoading || Boolean(state.statusError) || state.demoBusy || targetUnavailable;
    nodes.demoLabel.textContent = state.demoBusy ? "サンプル準備中…" : "ローカルサンプルを作成";
    if (state.demoBusy) {
      nodes.demoHelp.textContent = "観察データとテストケースを生成しています。";
    } else if (state.statusLoading) {
      nodes.demoHelp.textContent = "接続状態を確認しています。";
    } else if (state.statusError) {
      nodes.demoHelp.textContent = "APIへの接続後に利用できます。";
    } else if (targetUnavailable) {
      nodes.demoHelp.textContent = "認可済みローカルサンプルの起動後に利用できます。";
    } else {
      nodes.demoHelp.textContent = "公開ページだけを使い、約30秒で生成します。";
    }
  }

  function renderDashboardNotice() {
    if (state.actionNotice) {
      renderStateBox(
        nodes.dashboardAlert,
        state.actionNotice.kind,
        state.actionNotice.title,
        state.actionNotice.detail,
      );
      return;
    }
    if (state.statusLoading || state.sessionsLoading) {
      renderStateBox(
        nodes.dashboardAlert,
        "loading",
        "運用データを読み込み中",
        "Browser Agent とセッション履歴を確認しています。",
      );
      return;
    }
    if (state.statusError && state.sessionsError) {
      renderStateBox(
        nodes.dashboardAlert,
        "error",
        "Live QA に接続できません",
        `${state.statusError} / ${state.sessionsError}`,
        { label: "再試行", action: loadAll },
      );
      return;
    }
    if (state.statusError || state.sessionsError) {
      renderStateBox(
        nodes.dashboardAlert,
        "warning",
        "一部の運用データを確認できません",
        state.statusError || state.sessionsError,
        { label: "再試行", action: loadAll },
      );
      return;
    }
    const providerNote = state.agent && state.agent.providerConnected
      ? "Codex/provider 接続済み。Replay と説明生成を利用できます。"
      : "決定論的 fallback で生成できます。AI説明には provider 接続が必要です。";
    renderStateBox(nodes.dashboardAlert, "success", "Live QA は運用可能です", providerNote);
  }

  function renderMetrics() {
    if (state.sessionsLoading && state.sessions.length === 0) {
      [
        nodes.metricTests,
        nodes.metricRunning,
        nodes.metricPassed,
        nodes.metricReports,
      ].forEach((node) => {
        node.textContent = "—";
      });
      return;
    }
    const running = effectiveRunningSessions();
    const completed = state.sessions.filter((session) => isCompleted(session.status));
    const tests = state.sessions.reduce((total, session) => total + session.caseCount, 0);
    nodes.metricTests.textContent = String(tests);
    nodes.metricRunning.textContent = String(running.length);
    nodes.metricPassed.textContent = String(
      state.sessions.filter((session) => session.status === "passed").length,
    );
    nodes.metricReports.textContent = String(completed.length);
    nodes.runningCount.textContent = String(running.length);
  }

  function renderRecent() {
    if (state.sessionsLoading && state.sessions.length === 0) {
      renderStateBox(
        nodes.dashboardRecent,
        "loading",
        "セッションを読み込み中",
        "",
        null,
        true,
      );
      return;
    }
    if (state.sessionsError && state.sessions.length === 0) {
      renderStateBox(
        nodes.dashboardRecent,
        "error",
        "履歴を取得できません",
        state.sessionsError,
        { label: "再試行", action: () => refreshSessions(false) },
        true,
      );
      return;
    }
    if (state.sessions.length === 0) {
      renderStateBox(
        nodes.dashboardRecent,
        "empty",
        "まだテストはありません",
        "ローカルサンプルまたはブラウザー拡張から最初の操作を記録してください。",
        null,
        true,
      );
      return;
    }
    const list = makeElement("ol", "activity-list");
    state.sessions.slice(0, 5).forEach((session) => {
      const item = makeElement("li", "activity-item");
      const copy = makeElement("div", "activity-copy");
      copy.append(
        textElement("strong", session.name),
        textElement("small", `${session.caseCount} cases · ${session.observationCount} events`),
      );
      item.append(
        copy,
        statusBadge(effectiveStatus(session)),
        textElement("time", formatTime(session.updatedAt)),
      );
      item.lastElementChild.className = "activity-time";
      list.append(item);
    });
    nodes.dashboardRecent.replaceChildren(list);
  }

  function renderSessionViews() {
    renderTests();
    renderRunning();
    renderReports();
    nodes.refresh.disabled = state.sessionsLoading || state.refreshing;
    nodes.refresh.textContent = state.refreshing ? "更新中…" : "更新";
  }

  function renderTests() {
    nodes.testsBody.replaceChildren();
    const noStoredData = state.sessions.length === 0;
    if ((state.sessionsLoading || state.refreshing) && noStoredData) {
      nodes.testsTable.hidden = true;
      renderStateBox(
        nodes.testsState,
        "loading",
        "Test一覧を読み込み中",
        "保存済みセッションを取得しています。",
      );
      return;
    }
    if (state.sessionsError && noStoredData) {
      nodes.testsTable.hidden = true;
      renderStateBox(
        nodes.testsState,
        "error",
        "Test一覧を取得できません",
        state.sessionsError,
        { label: "再試行", action: () => refreshSessions(false) },
      );
      return;
    }
    if (noStoredData) {
      nodes.testsTable.hidden = true;
      renderStateBox(
        nodes.testsState,
        "empty",
        "テストはまだありません",
        "Dashboard のローカルサンプル、またはブラウザー拡張から作成できます。",
      );
      return;
    }

    nodes.testsTable.hidden = false;
    if (state.sessionsError) {
      renderStateBox(
        nodes.testsState,
        "warning",
        "前回取得した一覧を表示しています",
        state.sessionsError,
        { label: "再試行", action: () => refreshSessions(false) },
      );
    } else if (state.refreshing) {
      renderStateBox(nodes.testsState, "loading", "一覧を更新中", "現在の表示は維持されます。");
    } else {
      nodes.testsState.replaceChildren();
    }

    state.sessions.forEach((session) => {
      nodes.testsBody.append(testRow(session));
    });
  }

  function testRow(session) {
    const row = document.createElement("tr");
    const testCell = document.createElement("td");
    const copy = makeElement("div", "session-copy");
    copy.append(textElement("strong", session.name), textElement("small", session.goal));
    testCell.append(copy);

    const statusCell = document.createElement("td");
    statusCell.append(statusBadge(effectiveStatus(session)));

    const timeCell = textElement("td", formatTime(session.updatedAt));
    timeCell.className = "table-meta";
    const countCell = textElement("td", `${session.caseCount} / ${session.observationCount}`);
    countCell.className = "table-meta";

    const actionCell = document.createElement("td");
    const actions = makeElement("div", "row-actions");
    const running = effectiveStatus(session) === "running";
    const runButton = textElement("button", running ? "実行中…" : "Replay");
    runButton.type = "button";
    runButton.className = "button button-primary button-small";
    runButton.disabled = running || Boolean(state.statusError) || state.statusLoading;
    runButton.setAttribute("aria-label", `${session.name} を Replay`);
    runButton.addEventListener("click", () => runSession(session.id));
    actions.append(runButton, reportLink(session, "Report"));
    actionCell.append(actions);
    row.append(testCell, statusCell, timeCell, countCell, actionCell);
    return row;
  }

  function renderRunning() {
    nodes.runningList.replaceChildren();
    const running = effectiveRunningSessions();
    if ((state.sessionsLoading || state.refreshing) && state.sessions.length === 0) {
      renderStateBox(
        nodes.runningState,
        "loading",
        "実行状態を確認中",
        "Replay セッションを取得しています。",
      );
      return;
    }
    if (state.sessionsError && state.sessions.length === 0) {
      renderStateBox(
        nodes.runningState,
        "error",
        "実行状態を取得できません",
        state.sessionsError,
        { label: "再試行", action: () => refreshSessions(false) },
      );
      return;
    }
    if (running.length === 0) {
      renderStateBox(
        nodes.runningState,
        "empty",
        "現在実行中の Replay はありません",
        "Test一覧で対象を確認し、Replay を選択してください。",
      );
      return;
    }
    nodes.runningState.replaceChildren();
    running.forEach((session) => nodes.runningList.append(runningCard(session)));
  }

  function runningCard(session) {
    const card = makeElement("article", "session-card");
    const heading = makeElement("div", "session-card-heading");
    const copy = makeElement("div", "session-copy");
    copy.append(textElement("strong", session.name), textElement("small", session.goal));
    heading.append(copy, statusBadge("running"));
    const detail = makeElement("div", "session-detail");
    detail.append(
      textElement("span", `${session.caseCount} cases`),
      textElement("span", `Replay ${session.replayCount + 1}`),
      textElement("span", `開始基準 ${formatTime(session.updatedAt)}`),
    );
    card.append(heading, detail, makeElement("div", "session-progress"));
    return card;
  }

  function renderReports() {
    nodes.reportsList.replaceChildren();
    const reports = state.sessions.filter((session) => isCompleted(session.status));
    if ((state.sessionsLoading || state.refreshing) && state.sessions.length === 0) {
      renderStateBox(
        nodes.reportsState,
        "loading",
        "レポートを読み込み中",
        "完了済みセッションを取得しています。",
      );
      return;
    }
    if (state.sessionsError && state.sessions.length === 0) {
      renderStateBox(
        nodes.reportsState,
        "error",
        "レポートを取得できません",
        state.sessionsError,
        { label: "再試行", action: () => refreshSessions(false) },
      );
      return;
    }
    if (reports.length === 0) {
      renderStateBox(
        nodes.reportsState,
        "empty",
        "共有できるレポートはまだありません",
        "Replay が完了すると PASS / FAIL の証跡がここに並びます。",
      );
      return;
    }
    nodes.reportsState.replaceChildren();
    reports.forEach((session) => nodes.reportsList.append(reportCard(session)));
  }

  function reportCard(session) {
    const card = makeElement("article", "report-card");
    card.dataset.result = session.status;
    const heading = makeElement("div", "report-card-heading");
    const copy = makeElement("div", "report-copy");
    copy.append(textElement("strong", session.name), textElement("small", session.goal));
    heading.append(copy, reportLink(session, "レポートを開く"));
    const detail = makeElement("div", "report-detail");
    detail.append(
      statusBadge(session.status),
      textElement("span", `Replay ${session.replayCount}回`),
      textElement("span", `${session.caseCount} cases`),
      textElement("span", formatTime(session.updatedAt)),
    );
    card.append(heading, detail);
    return card;
  }

  function effectiveRunningSessions() {
    return state.sessions.filter(
      (session) => session.status === "running" || state.busyRuns.has(session.id),
    );
  }

  function effectiveStatus(session) {
    return state.busyRuns.has(session.id) ? "running" : session.status;
  }

  function isCompleted(status) {
    return status === "passed" || status === "failed";
  }

  function statusBadge(status) {
    const meta = STATUS_META[status] || STATUS_META.recording;
    const badge = textElement("span", meta.label);
    badge.className = `badge badge-${meta.badge}`;
    return badge;
  }

  function reportLink(session, label) {
    const link = textElement("a", label);
    link.className = "button button-secondary button-small";
    link.href = ENDPOINTS.report(session.id);
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.setAttribute("aria-label", `${session.name} のレポートを開く`);
    return link;
  }

  function renderStateBox(host, kind, title, detail, action = null, compact = false) {
    const box = makeElement("div", `state-box${compact ? " state-box-compact" : ""}`);
    box.dataset.state = kind;
    box.setAttribute("role", kind === "error" ? "alert" : "status");
    const symbol = makeElement("span", "state-symbol");
    symbol.setAttribute("aria-hidden", "true");
    const copy = document.createElement("div");
    copy.append(textElement("strong", title));
    if (detail) {
      copy.append(textElement("p", detail));
    }
    box.append(symbol, copy);
    if (action) {
      const button = textElement("button", action.label);
      button.type = "button";
      button.className = "button button-secondary button-small";
      button.addEventListener("click", action.action);
      box.append(button);
    }
    host.replaceChildren(box);
  }

  function makeElement(tagName, className) {
    const element = document.createElement(tagName);
    if (className) {
      element.className = className;
    }
    return element;
  }

  function textElement(tagName, text) {
    const element = document.createElement(tagName);
    element.textContent = String(text);
    return element;
  }

  function formatTime(value) {
    if (!value) {
      return "時刻不明";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return "時刻不明";
    }
    return new Intl.DateTimeFormat("ja-JP", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    }).format(date);
  }

  function showToast(message, kind) {
    if (state.toastTimer) {
      window.clearTimeout(state.toastTimer);
    }
    nodes.toast.textContent = message;
    nodes.toast.dataset.state = kind;
    nodes.toast.hidden = false;
    state.toastTimer = window.setTimeout(() => {
      nodes.toast.hidden = true;
      state.toastTimer = null;
    }, 3200);
  }
})();
"""
