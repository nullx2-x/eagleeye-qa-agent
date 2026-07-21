# EagleEye AI-first QA Agent

[English](README.md) | **日本語**

**普段どおりブラウザを操作するだけで、AIが回帰テストと証跡レポートに変える、ローカル常駐型QAエージェントです。**

Chrome拡張をONにすると、EagleEyeは入力値を保存せずにDOM要約、可視画面、操作履歴を観測します。Codex App Server経由のOpenAIが追加テストを生成し、決定論的な品質検査を通したうえで、Playwrightが記録導線をReplayします。結果、画像・動画のSHA-256、改善案を一つのHTML/Markdownレポートにまとめます。

AIは候補を提案しますが、記録されたcritical path、実行結果、リリース判断、修正適用を上書きできません。

> **利用条件:** 所有または明示的な許可を得たサイトだけをテストしてください。収集項目、AI送信、保存・削除は [Privacy](PRIVACY.ja.md)、安全境界は [Security](SECURITY.ja.md)、法令・Store方針との対応範囲は [Compliance](COMPLIANCE.ja.md) を確認してください。

![EagleEye end-to-end demo flow](docs/build-week/screenshots/eagleeye-demo-flow.gif)

▶ [英語音声・焼込み字幕付き2分55秒デモ](https://youtu.be/O70IfVOqZvA)

12秒のプレビューはブラウザー観察フローを示します。正式な運用経路は、認可済みリポジトリのテストを検出・実行して証跡付き品質ゲートへ集約する Project QA です。

## 5分で分かる勝ち筋

1. Chrome拡張をONにする。
2. ユーザーは対象サイトを普段どおり操作する。
3. EagleEyeが安全なDOM要約、画面、操作履歴を同一セッションで観測する。
4. OpenAIが実操作に基づく追加テストを生成し、品質チェッカーが曖昧さや危険なケースを除く。
5. Playwrightが記録導線をReplayし、画像・動画・SHA-256を残す。
6. 修正案付きレポートを確認し、明示操作でMarkdownバグレポートを開発チームへ渡す。

Project QA は Node.js、Python、Go、Rust、.NET、Gradle、Maven を検出します。`.eagleeye/qa.json` で許可済みコマンド配列を追加でき、明示認可、ルート制限、タイムアウト、秘密情報マスキング、ログ上限、SHA-256証跡を必須にします。

URLだけを受け取った場合は、観察専用のURL Auditを入口にできます。HTTPS、security header、安全なCORS preflight、robots.txt、sitemap.xml、security.txt、固定3候補のOpenAPI、favicon、login導線、technology hintを確認し、JSON/Markdown証跡、品質検査済み初期テストケース、Browser Agent開始URLを持つQA project seedを生成します。

SQL Injection、XSS、総当たり、port scan、directory brute-force、資格情報送信、破壊的writeは実行しません。1監査を10 request、4 MiB、30秒、同時2件に制限します。標準はpublic HTTP(S)だけで、localhostは`allowLocalhost=true`と`EAGLEEYE_URL_AUDIT_ALLOW_LOCALHOST=1`の二重opt-inが必要です。LAN、link-local、metadata、multicast、unspecified、reserved addressは常に拒否します。

## Quick Start

必要環境はPython 3.12、[uv](https://docs.astral.sh/uv/)、Chromiumです。任意のハッカソン用fixtureはproduction runtimeから分離して`demos/hackathon`に置いています。

```powershell
git clone https://github.com/nullx2-x/eagleeye-qa-agent.git
cd eagleeye-qa-agent
Copy-Item .env.example .env
uv sync --locked --dev
uv run playwright install chromium
.\scripts\start-eagleeye.ps1
```

起動後、認可済みプロジェクトを次のように検証します。

```powershell
.\scripts\start-eagleeye.ps1
.\scripts\start-mcp.ps1
.\scripts\run-project-qa.ps1 -ProjectRoot <authorized-project-path> -Mode development
```

認可済みpublic URLから始める場合:

```powershell
.\scripts\run-url-audit.ps1 -Url https://example.com
```

### Chrome拡張

1. `chrome://extensions` でデベロッパーモードをONにする。
2. 「パッケージ化されていない拡張機能を読み込む」で`chrome-extension`を選ぶ。
3. 対象ページで拡張アイコン、または`Ctrl+Shift+Y`を押す。
4. popupの記録内容を読み、対象サイトの許可とプライバシー同意を確認する。
5. **開始 → 通常操作 → 停止 → AI生成 → Replay → レポート表示**の順で進める。
6. 不要になったら **このセッションを端末から削除** でDOM要約・画像・動画・生成物を消去する。

拡張権限は`activeTab`、`scripting`、session-only storageとloopback API通信だけです。AI未接続やタイムアウト時も記録ケースは残り、画面にfallback理由を表示します。Codexへ接続済みならCodex App Serverをエージェントとして利用し、EagleEyeが存在しないエンドユーザーOAuthやChatGPT tokenを仮装・保存することはありません。

Webフォーム入力値、Cookie、認証header、`FormData`は取得しません。表示中のタイトル・見出し・control名には個人情報が含まれ得るため、機密画面では開始しないでください。スクリーンショットは初期OFFで、AIプロンプトへは送りません。EagleEye本体に開発者向け製品telemetryや自動公開処理はありません。

## Build Week提出資料

- [Architecture](docs/build-week/architecture.md)
- [Architecture図](docs/build-week/screenshots/architecture-flow.png)
- [2:55デモ台本](docs/build-week/demo-script.md)
- [Devpost提出内容](docs/build-week/devpost-draft.md)
- [Release公開監査](docs/release/1.0.0-publication-audit.md)
- [Phase 1-9チェックリスト](docs/build-week/submission-checklist.md)
- [公開前セキュリティ手順](docs/build-week/publication-security.md)
- [提出スクリーンショット](docs/build-week/screenshots/)
- [Privacy](PRIVACY.ja.md) / [Security](SECURITY.ja.md) / [Compliance](COMPLIANCE.ja.md)

License: [MIT](LICENSE)

## 主な機能

- 開発段階: prototype / development / stabilization / release / maintenance
- サービス種別: web / ecommerce / business / api / batch / ai_agent / legacy_desktop / emulator
- エミュレータ互換性: functional / system / cycle / physical の累積プロファイル
- リスク加重: 事業影響30%、データ機密性25%、変更複雑度15%、利用者影響20%、復旧困難度10%
- モード: LIGHT / DEVELOPMENT / STANDARD / STRICT / RELEASE_GATE
- 差分影響分析、認証・決済・DB等の高影響変更でフル回帰を強制
- flakyを通常失敗と分離した品質ゲート
- 差分件数、対象範囲、サンプル数、独立オラクル、証跡SHA-256を検証する互換性ゲート
- テストケースの曖昧さ、assertion不足、固定wait、不安定selector、秘密値、重複、retry依存、種別不足を実行前に自動検査
- Codex App Serverが管理するChatGPT OAuth。EagleEyeはtokenやAPIキーを受領・保存せず、接続状態と構造化turnだけを利用
- `recording=true`のPlaywright実行で、スクリーンショットとWebM動画をSHA-256・byte数・MIME・取得時刻・取得元付き証跡として保存
- 固定レジストリに登録したdesktop targetだけを起動するadapter。任意command/pathを受け付けず、外部QA証跡をEagleEye配下へ再hashして取り込み
- exact allowlistの高能力モデルだけに限定したbounded self-repair。local・非本番・clean Git・fresh eval attestationを要求し、失敗時はcheckpointから復旧
- Ollamaを既定とするローカルAI助言。OpenAI互換エンドポイントも選択可能
- release assurance / balanced / high volume / local private別のAIモデル推薦カタログと公式ソースリンク
- Orbit Assistの受領時にテストプロファイルを自動生成し、モードとリスクを拡張へ返却
- Streamable HTTP MCPとインストール済みCodex Skill
- 自動テストとは分離されたAI誘導型ユーザーテスト（manual / hybrid / telemetry）
- exact/maxイベント回数とsettle windowによる、後発イベントを含む誤操作監視
- runner固有human-attestationによる承認・実施不能・人間判定のREST/MCP代行防止
- OAuth/APIキー/WIF資格情報はOSキーチェーンに保存し、API応答へ秘密値を返さない

## セットアップと起動

```powershell
cd <project-root>
uv sync
uv run playwright install chromium
.\scripts\start-eagleeye.ps1
```

別のPowerShellでMCPを起動します。

```powershell
.\scripts\start-mcp.ps1

# API/MCPの片方だけ落ちた場合は、欠けたサービスだけを復旧・確認
.\scripts\ensure-eagleeye.ps1
```

- ダッシュボード/API: `http://127.0.0.1:8766`
- MCP: `http://127.0.0.1:8768/mcp`
- 任意のハッカソン用fixture: `demos\hackathon\start.ps1` で `http://127.0.0.1:8767`

この環境の起動スクリプトは、未指定時に`EAGLEEYE_AI_PROVIDER=codex-agent`、`EAGLEEYE_CODEX_TRANSPORT=app-server`、`EAGLEEYE_SELF_REPAIR_ENABLED=1`を設定します。自己修復のfeature flagだけでは書込みを許可しません。モデル・環境・Git状態・fresh attestation・変更上限・固定検証の全条件を満たさない場合はfail closedします。Ollamaへ戻す場合は起動前に`EAGLEEYE_AI_PROVIDER=ollama`を設定してください。

## AIプロバイダー認証

`.env.example` を参照し、公開してよいOAuthクライアントIDだけを環境変数へ設定します。トークンとAPIキーはAPI本文へ再表示せず、Windows Credential Manager等のOSキーチェーンへ保存します。

| プロバイダー | 実装方式 | 外部準備 |
|---|---|---|
| OpenAI API | APIキー | APIキー発行 |
| Codex Agent | Codex App Server管理のChatGPT OAuth | ローカル`codex app-server`を起動できること |
| Anthropic | APIキー / OIDC WIF token exchange | 組織のissuer・rule・service accountとIdP JWT |
| Google Gemini | Authorization Code + PKCE S256 / APIキー | OAuth desktop client IDと同意 |
| Azure OpenAI | Microsoft Entra PKCE / Azure Identity / APIキー | Entra app registrationとAzure RBAC |
| GitHub Models | OAuth Device Flow / token | OAuth App client IDと利用者同意 |
| Ollama | ローカル・認証なし | Ollama起動 |
| LM Studio | ローカル・任意APIキー | Local Server起動 |

OpenAI APIそのものにはEagleEye独自のエンドユーザーOAuthを仮装しません。OpenAI APIを直接使う場合はAPIキー認証です。一方、`EAGLEEYE_AI_PROVIDER=codex-agent`では、ローカルCodex App ServerへJSONLで接続し、App Serverが管理するChatGPT OAuthを使います。接続状態の取得、ログイン開始・取消、ログアウトはApp Serverへ委譲し、EagleEyeはログイントークンを読み取りません。AI turnはephemeral・read-only・approval拒否・構造化JSON Schemaに固定します。Anthropic WIFは対話ログインではなくワークロード認証なので、設定後に `POST /api/v1/auth/providers/anthropic/refresh` で短期トークンを交換します。

## REST API

- `POST /api/v1/url-audits`: 認可済みURLを非侵襲で観察し、QA project seedと証跡を生成
- `GET /api/v1/url-audits/{id}`: 保存済みURL Auditを取得
- `GET /api/v1/url-audits/{id}/report`: Markdownレポートを取得
- `DELETE /api/v1/url-audits/{id}`: 保存済みJSON/Markdown証跡を削除
- `POST /api/v1/test-profiles/generate`: リスク適応プロファイル生成
- `GET /api/v1/test-profiles/{id}`: 保存済みプロファイル
- `POST /api/v1/quality-gates/evaluate`: PASS / WARNING / REVIEW / FAIL / BLOCKED判定
- `POST /api/v1/test-cases/check`: ケース別スコア、健全性判定、修正案、カバレッジ不足
- `GET /api/v1/ai/providers`: 機密値を除いた接続状態
- `GET /api/v1/ai/model-recommendations?workload=balanced`: 用途別モデル推薦と検証日、公式ソース
- `POST /api/v1/auth/providers/{id}/start`: PKCEまたはDevice Flow開始
- `POST /api/v1/auth/providers/{id}/cancel/{flowId}`: Codex App Serverの未完了ChatGPTログインを取消
- `DELETE /api/v1/auth/providers/{id}`: 接続解除。CodexはApp Server管理アカウントからログアウト
- `POST /api/v1/auth/providers/{id}/refresh`: Anthropic WIF交換
- `POST /api/v1/auth/providers/{id}/api-key`: APIキーをOSキーチェーンへ格納
- `GET /api/v1/desktop-targets`: 固定desktop targetレジストリの公開ID一覧
- `POST /api/v1/desktop-runs`: 登録済みtargetを隔離起動し、画像・動画・log証跡を取り込み
- `GET /api/v1/self-repair/status`: feature flag、能力allowlist、適用上限を機密値なしで取得
- `POST /api/v1/self-repair/evaluate`: 独立した高能力モデルevalで修復可否を判定
- `POST /api/v1/self-repair/execute`: fresh one-use attestation付きのbounded修復、固定検証、rollback
- `POST /api/v1/sessions`: Orbitバンドルの検証・保存・プロファイル生成
- `POST /api/v1/sessions/{id}/run`: localhost限定Playwright実行
- `DELETE /api/v1/browser-agent/sessions/{id}`: browser sessionと派生するローカル証跡を削除
- `POST /api/v1/sessions/{id}/self-repair`: 失敗runをfingerprintし、評価後にproposalまたは限定自動修復
- `GET /api/v1/sessions/{id}/codex-handoff`: 失敗証跡と承認必須の修正指示
- `POST /api/v1/guided/scenarios`: AIまたは人が作成した汎用シナリオJSONを検証・保存
- `POST /api/v1/guided/sessions`: 承認前の `PREPARED` ユーザーテストを準備
- `GET /api/v1/guided/sessions/{id}/next`: 次のテキスト・画像・画面マーカー指示
- `POST /api/v1/guided/sessions/{id}/control`: approve / activate / pause / resume / next 等。人間操作はrunner固有attestation必須
- `POST /api/v1/guided/sessions/{id}/feedback`: runnerからユーザー自己申告または観察者判定を記録
- `POST /api/v1/guided/sessions/{id}/observations:batch`: 任意の構造化telemetryを冪等受領

## AI誘導型ユーザーテスト

`http://127.0.0.1:8766/guided` は、自動テストとは別のhuman-in-the-loop runnerです。AIはシナリオ作成、セッション準備、次stepの読み上げ、進行補助を行えます。ユーザーはテキスト、参考画像、正規化座標の `rect / circle / arrow / point` マーカーに従って操作し、本人または任意の観察者が結果を入力します。

状態は `PREPARED → (ユーザー承認) → READY → activate` の順です。承認・activate・resume・block・abort・人間feedbackはrunnerだけへ渡すattestationが必須で、構造化REST応答やMCPから代行できません。承認前のtelemetryは保存しません。実施中は休憩・再開でき、失敗またはBLOCKED終了時は該当stepだけを含む `PREPARED` 再テストが自動作成されます。

汎用サンプルを登録する例です。

```powershell
$body = Get-Content -Raw .\examples\guided-user-scenario.json
Invoke-RestMethod http://127.0.0.1:8766/api/v1/guided/scenarios `
  -Method Post -ContentType 'application/json' -Body $body
Start-Process http://127.0.0.1:8766/guided
```

`manual` は人の結果、`telemetry` は汎用predicate/eventオラクル、`hybrid` は両方を要求します。`requiredEvents` に加えて `exactEventCounts` / `maxEventCounts` / `settleWindowMs` を使うと、条件成立直後に完了せず、静穏期間中の多重発火や禁止イベントまで監視できます。製品固有のフィールドはシナリオまたは外部adapterの `values` / `payload` に置き、EagleEye本体へ埋め込みません。local assetは `data\guided\assets` 配下だけを相対パスで参照できます。観測、監査ログ、step証跡、session reportにはSHA-256を付与します。

guided user QAはtelemetry-onlyを含め常に `humanApprovalRequired=true`、`releaseRecommended=false` です。人の合格証拠を含む場合は `MANUAL_REVIEW`、telemetry-onlyのオラクル判定自体は `PASS` になり得ますが、どちらも自動テストやリリースゲートの代替にはしません。

FastAPIの`/docs`と`/openapi.json`は標準で無効です。loopback開発時に限り、`EAGLEEYE_ENABLE_API_DOCS=1`で明示的に有効化できます。

## Circuit Forge Studio / GBダンパー拡張adapter QA

`scenarios/circuit-forge-studio/test-cases.json`には、配布版Electronの固定desktop adapter実行、動画証跡、ChatGPT OAuthの正負、自己修復の拒否・rollback、GBダンパー拡張adapterのhardware gateを収録しています。`guided-scenario.json`は誘導員がユーザーを支援・監視し、問題発生時に修正と再テストへ戻す手順です。人間承認前のセッションは`PREPARED`で止まり、EagleEyeが承認や実機判定を代行しません。

GBダンパー拡張adapterはN64ダンパーの実機型番、基板rev、firmware、コネクタ向き、電圧・波形が未確認の間は`BLOCKED_FOR_HARDWARE_IDENTIFICATION`です。回路案をfabrication-readyとは扱わず、給電、3.3 V/5 V変換、bus競合、N64 12 V非接続、first power、カートリッジwriteを手動gateに残します。

## MCP / Codex Skill

MCPは従来toolに加え、`guided_list_scenarios`、`guided_register_scenario`、`guided_prepare_session`、`guided_session_status`、`guided_next_step`、`guided_control_session`、`guided_record_human_result`、`guided_get_retest` を提供します。`guided_prepare_session` は `PREPARED` を作るだけです。MCPの自己申告フラグは人間証明として扱わず、承認や人間判定はattestationを持つrunnerからしか確定できません。AIは案内と読み取り、再テスト準備の補助に限定されます。

Codex Skillは次の3系統を配置済みです。

- `%USERPROFILE%\.codex\skills\eagleeye-ai-qa`: リスク適応戦略、品質ゲート、証跡検査
- `%USERPROFILE%\.codex\skills\eagleeye-author-tests`: 要件・差分・不具合からAIテストケースとユーザーシナリオを作成し、自動品質検査してPREPAREDへ登録
- `%USERPROFILE%\.codex\skills\eagleeye-guided-support`: 承認済みユーザーテストの誘導、telemetry監視、要件判定、ログ、修正案、失敗項目だけの再テスト準備

AIはセッション作成と案内を行えますが、ユーザーの承認や人間の使用感判定は代行しません。

## セキュリティ

- 既定は `127.0.0.1` のみ。外部URL実行は `EAGLEEYE_ALLOW_REMOTE=1` がない限り拒否
- ブラウザーの書込み要求はsame-originだけを許可。Orbit/Chrome拡張は`EAGLEEYE_ALLOWED_EXTENSION_ORIGINS`へ完全一致Originを明示した場合だけCORS許可し、wildcardを拒否
- Host headerを`127.0.0.1`/`localhost`へ限定し、nosniff・frame拒否・referrer/permission制限headerを全応答へ付与
- 未マスク入力、password/token/secret型、危険なセッションIDを受信時に拒否
- PKCE S256、state照合、OAuthフロー期限、HTTPS認可/トークンURLを強制
- Codex App Serverのauth URLはHTTPSかつ固定host・標準portだけを許可し、credential・fragment・紛らわしいsuffix hostを拒否
- URL AuditはIPを検証後に固定接続し、same-host redirect、semantic headerだけの保存、query value秘匿、10 request / 4 MiB / 30秒 / 同時2件を強制
- desktop adapterは固定target ID、`shell=False`、最小環境変数、project root confinement、timeout時process tree終了を強制
- desktop logはBearer/API keyに加え、JWT、GitHub token、AWS access key、URL queryの認証値を保存前にマスク
- self-repairは`codex-agent/gpt-5.6-sol`のexact allowlist、local・非本番、clean exact Git root、one-use fresh attestationを要求
- self-repairは最大2試行・5 files・200 changed lines・256 KiBで、secret/binary/lockfile/delete/rename・policy自己改変を拒否
- 本番プロファイルはread-only、AIは必須テストを削除不可
- AI助言の有効化とAI製品向け試験を分離し、非AI対象へLLM試験を混入させない
- Codex修正案の適用、破壊的操作、リリース判断は明示承認が必要

EagleEyeは単一ユーザーのローカルQAサービスです。同一Windowsユーザーで動くprocessは同じrepositoryへ直接書き込めるため信頼境界内とし、LAN公開や共有ホスト運用は対象外です。別ユーザー・別端末へ公開する場合は、loopback bindの解除前に認証付きgatewayを追加してください。

## 検証

```powershell
uv run ruff check .
uv run pytest -q
```

現行のPythonテストスイート、ruff check、PowerShell構文検査を変更時に実行します。件数は機能追加で変動するため、直近の実行結果をリリース報告とReport Hubに記録します。

運用品質ゲートは、API/MCP/実Chromium/Report Hub、3ブラウザ互換、bounded performance、固定AI安全eval、runtimeバックアップ復元ドリルまで一括実行します。

```powershell
.\scripts\quality-gate.ps1
```

ログオン時の自己復旧・health確認を登録する場合:

```powershell
.\scripts\install-startup-health-task.ps1
```

実ブラウザ検証のスクリーンショット、WebM、`result.json` は `artifacts\runs\<session-id>` に保存されます。desktop adapterが取り込む証跡は `artifacts\runs\<run-id>\desktop`、self-repairのcheckpoint・監査JSONは `.runtime\self-repair` 配下です。

## カテゴリ

03_AI-Agents（AI・エージェント）
