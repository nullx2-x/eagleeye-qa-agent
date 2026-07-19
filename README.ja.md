# EagleEye — 運用型AI QAエージェント

[English](README.md) | **日本語**

**実プロジェクトのQAを検出・実行し、ブラウザーReplay、境界付き自己修復、証跡付き品質ゲートまで一つにまとめるローカル常駐型QAシステムです。**

EagleEyeは、明示的に認可されたプロジェクトからテスト、lint、型検査、セキュリティ、integration、E2E、buildを検出します。承認済みルート内でshellを使わず実行し、結果を正規化して、上限付きログとSHA-256証跡を含むJSON／Markdownレポートを生成します。

ブラウザーエージェントは任意の証跡入力として利用できます。入力値を保持せず、限定されたDOM要約と操作履歴を記録し、Codex App Server経由のGPT-5.6が追加ケースを提案します。生成ケースは決定論的に検査され、記録されたcritical pathはPlaywrightでReplayされます。

AIはテストや境界付き修正を提案できますが、合否判定の根拠、リリース承認、本番変更、安全ゲートを上書きできません。

> **認可済みテストのみ。** 所有している、または明示的な許可を得たシステムだけを対象にしてください。実システムから証跡を取得する前に [Privacy](PRIVACY.md)、[Security](SECURITY.md)、[Compliance](COMPLIANCE.md) を確認してください。

## Operational Project QA

自動検出する主要エコシステムは次のとおりです。

- Node.js
- Python
- Go
- Rust
- .NET
- Gradle
- Maven

リポジトリ管理者は`.eagleeye/qa.json`に、承認済みcommand配列を追加できます。

Project QAの各実行では、次を必須にします。

- `authorized=true`
- `EAGLEEYE_PROJECT_ROOTS`配下のプロジェクト
- 実行ファイルのallowlist
- `shell=False`
- 上限付き・秘密情報マスキング済みログ
- timeoutとprocess tree終了処理
- SHA-256証跡
- 決定論的なquality gate

CPU固有検証、端末ベンチマーク、Web診断probeは必須項目ではありません。必要な場合だけ、リポジトリ管理者が`.eagleeye/qa.json`へ明示的に追加します。
エミュレータ互換性レベルは`serviceType=emulator`の場合だけ受け付け、Webなど他サービスへの混在は拒否します。

## Quick Start

必要環境はPython 3.12、[uv](https://docs.astral.sh/uv/)、PowerShell、Chromiumです。

```powershell
git clone https://github.com/nullx2-x/eagleeye-qa-agent.git
cd eagleeye-qa-agent
Copy-Item .env.example .env
uv sync --locked --dev
uv run playwright install chromium
.\scripts\start-eagleeye.ps1
```

EagleEyeが検査してよいプロジェクトの親ディレクトリを認可します。

```powershell
$env:EAGLEEYE_PROJECT_ROOTS = "C:\WorkSpace\01_Apps"
```

検出または実行します。

```powershell
uv run python scripts/run_project_qa.py C:\WorkSpace\01_Apps\your-project --discover
.\scripts\run-project-qa.ps1 -ProjectRoot C:\WorkSpace\01_Apps\your-project -Mode development
```

## ブラウザーエージェント

1. `chrome://extensions`でデベロッパーモードをONにします。
2. **パッケージ化されていない拡張機能を読み込む**から`chrome-extension`を選びます。
3. 認可済みのHTTP(S)ページを開きます。
4. EagleEyeアイコン、または`Ctrl+Shift+Y`を押します。
5. 対象サイトの認可とプライバシー同意を確認します。
6. **開始 → 通常操作 → 停止 → AI生成 → Replay → レポート**の順で進めます。
7. 証跡が不要になったらローカルセッションを削除します。

拡張権限は`activeTab`、`scripting`、session storage、loopback API通信だけです。スクリーンショットは初期OFFで、AIプロンプトへ含めません。

### 機密性の高い管理画面

機密性の高い管理・認証パスでは、次の制限を適用します。

- AIケース生成を停止
- Replayを拒否
- 決定論的なローカル記録だけを手動レビュー可能
- nonce系query parameterを削除
- URLのusername、password、fragment、秘密値らしいquery parameterを保存前に削除

管理操作のテストには、破棄可能なローカルfixture、または非破壊性を確認済みのstaging環境を使用してください。

## プライバシー契約

EagleEyeは次を収集・保持しません。

- フォーム入力値
- パスワード、ワンタイムコード
- Cookie
- 認証header
- `FormData` payload
- 決済情報
- URL userinfo、fragment
- token、auth、session、code、nonce、API keyに類するquery parameter

ただし、画面タイトル、見出し、accessible name、control labelには機密情報が含まれる可能性があります。追加の組織的統制なしに機密画面で記録を開始しないでください。

## 境界付き自己修復

自己修復はfail closedです。次を含む全条件を満たした場合だけ進みます。

- localかつ非本番
- cleanなGit状態
- 許可済みモデルと操作
- freshな一回限りのhuman attestation
- 厳格なファイル数・変更行数上限
- 固定された検証command
- checkpointとrollback

条件を満たさない場合はレポートを残して停止し、安全条件を緩めたり変更を黙って適用したりしません。

## サービスとAPI

| サービス | URL |
|---|---|
| Dashboard／API | `http://127.0.0.1:8766` |
| MCP | `http://127.0.0.1:8768/mcp` |
| ローカルsample | `http://127.0.0.1:8766/demo-site/` |

Project QA:

- `POST /api/v1/project-qa/discover`
- `POST /api/v1/project-qa/runs`
- `GET /api/v1/project-qa/runs/{runId}`

Browser Agent:

- `POST /api/v1/browser-agent/sessions`
- `POST /api/v1/browser-agent/sessions/{sessionId}/generate`
- `POST /api/v1/browser-agent/sessions/{sessionId}/run`
- `GET /api/v1/browser-agent/sessions/{sessionId}/report`
- `DELETE /api/v1/browser-agent/sessions/{sessionId}`

FastAPIの`/docs`と`/openapi.json`は既定で無効です。loopback開発時だけ`EAGLEEYE_ENABLE_API_DOCS=1`で有効化してください。

## 検証

```powershell
uv run ruff format --check app scripts tests
uv run ruff check app scripts tests
uv run pytest -q
```

CIでは、生成済みレポート、提出用動画、廃止済みデモroute、旧CMS固有証跡が現在の製品ツリーへ混入していないことも確認します。

## 人間の責任範囲

EagleEyeは観測、テスト設計、決定論的実行、証跡、境界付き修正提案を支援します。認可、機密情報の取扱い、本番変更、法的同意、リリース承認、公開判断は人間が担当します。

## License

[MIT](LICENSE)
