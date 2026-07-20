# Changelog

## 1.0.0 - 2026-07-17

- Chrome拡張を明示的にONにし、通常操作から安全なDOM要約、可視スクリーンショット、操作履歴を同一セッションへ記録するBuild Week導線を追加。
- Codex App Serverと`gpt-5.6-terra`によるschema準拠のAIテスト生成、固定wait除去、決定論的品質検査、OpenAI停止時fallbackを統合。
- 記録ケースをPlaywrightでReplayし、期待URL・title・headingを検証して、画像・動画・SHA-256を持つHTMLレポートとMarkdownバグレポートを生成。
- Dashboard、Test一覧、実行中、レポート、ダーク/ライトテーマを備えた日本語Live UIと、ログイン不要の同梱デモサイトを追加。
- ブラウザAPIからローカル絶対パスを除去し、秘密query・入力値・危険なOrigin・cross-origin記録・oversize画像をfail closedで拒否。
- Windows/Linux GitHub Actions、MIT License、Build Week architecture、2:55デモ台本、Devpost原稿、公開前セキュリティ手順を追加。
- 記録前の目立つprivacy disclosureと明示同意、セッション単位の完全削除、AI用URL/PII秘匿化を追加。
- Replayのredirect/subresourceを含むnetwork境界、既定API docs無効化、CSP/no-store headerを追加。
- Privacy、Security、Compliance、third-party notice、CodeQL、Dependabot、extension CIを公開Release gateへ追加。
- Guided assetを安全なcatalog lookupへ変更し、SVGを拒否。route IDのHTML埋め込みとReDoS対象regexを除去し、patched MCPだけへ解決されるPython範囲を固定。

## 0.8.0 - 2026-07-16

- `codex app-server`を介したChatGPT管理OAuthを追加し、EagleEyeがtokenやAPIキーを受領せずに接続状態、ログイン開始・取消、ログアウト、構造化turnを扱えるように変更。
- Playwright記録時のスクリーンショットとWebM動画に、SHA-256、byte数、MIME、取得時刻、取得元を付ける動画証跡を追加。
- 固定レジストリに登録したdesktop targetだけを起動できるadapterを追加し、Circuit Forge Studioの配布版QAと動画証跡取り込みを実装。
- exact allowlistの高能力モデル、local・非本番、clean Git、fresh eval attestationをすべて要求するbounded self-repairを追加。変更量・試行回数を制限し、検証失敗時はcheckpointから復旧。
- self-repair attestationを評価requestへ束縛して原子的に一度だけ消費し、認証・実行・policy・test・script・profile・CI/依存設定を自己改変対象から除外。
- Chrome拡張Originを明示allowlist化し、Host/unsafe-method Origin検証とsecurity header、desktop logのJWT/PAT/AWS/query-secret追加マスキングを実装。
- Circuit Forge Studio、ChatGPT OAuth、自己修復の負系・rollback、GBダンパー拡張adapterのhardware gateを含む自動・guided QAシナリオを追加。guided sessionは人間の承認前に`PREPARED`で停止。

## 0.7.0 - 2026-07-16

- ChatGPTログイン済みのローカルCodex CLIを、APIキー不要の`codex-agent`プロバイダーとして追加。
- Codex呼出しをephemeral、read-only、承認なし、構造化JSON Schema、最小環境変数に制限。
- API/MCP起動スクリプトの未指定時プロバイダーを`codex-agent`へ変更。
- Codexログイン検出と安全な子プロセス境界の単体試験を追加。

## 0.6.0 - 2026-07-16

- Chromium、Firefox、WebKitの互換スモークを追加。
- bounded performance benchmarkとp95基準を追加。
- prompt injection、secret exfiltration、unbounded loopを含む固定AI安全evalを追加。
- AI提案による必須テスト・制約の弱体化を検出するpost-conditionを追加。
- Gitタグからsandboxへ復元するコードrollback drillを追加。

## 0.5.0 - 2026-07-16

- API、MCP、Chromium、Report Hubを検証する運用スモークを追加。
- allowlist、SQLite snapshot、manifest SHA-256を備えたruntimeバックアップと復元ドリルを追加。
- pytest、ruff、運用スモーク、復元ドリルを統合する単一品質ゲートを追加。
- Windowsログオン時のAPI/MCP自己復旧とhealth証跡を追加。
- ローカルGit、CI定義、VERSION、変更履歴の運用基盤を追加。

## 0.4.0 - 2026-07-15

- リスク適応QA、品質ゲート、MCP、AIプロバイダー、guided user QAを統合。
