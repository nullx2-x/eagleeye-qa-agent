# EagleEye セキュリティポリシー

[English](SECURITY.md) | [日本語](SECURITY.ja.md)

> 英語版を正本とし、日本語版は参考訳として提供します。

## 対応バージョン

セキュリティ修正は最新の`1.x`系列を対象とします。公開Releaseの最新版で再現を確認してください。

## 脆弱性の報告

個人情報、秘密情報、exploit、未公開の脆弱性を公開Issueへ投稿しないでください。GitHubリポジトリの **Security → Report a vulnerability** からPrivate Vulnerability Reportingを利用してください。

報告には次を含め、実データの代わりに合成値を使ってください。

- 影響するversionまたはcommit
- 再現条件と最小の手順
- 期待結果と実際の結果
- 影響範囲
- 秘密情報を除いたlog、動画、proof of concept

保守者は受領確認、triage、修正、公開時期を同じprivate advisory内で調整します。本プロジェクトはbug bountyを約束するものではありません。

## 既定の安全境界

- API、MCP、Report機能はloopback優先で、Hostとbrowser Originを制限します。
- Replayは標準でloopback HTTP(S)だけを許可し、redirectとsubresourceにも同じ制限を適用します。
- URL Auditは対象の明示認可を要求し、DNS検証済みIPへ固定接続し、same-hostの安全なredirectと固定観察requestだけを使います。上限は10 request、4 MiB、30秒、同時2件です。
- URL Auditの標準対象はglobal addressです。localhostはrequest flagと環境変数の二重opt-inが必要で、LAN、link-local、metadata、multicast、unspecified、reserved addressは常に拒否します。
- Chrome拡張は`activeTab`、`scripting`、session-only storage、2つのloopback host permissionだけを要求します。
- フォーム値、Cookie、認証ヘッダー、`FormData`は記録しません。
- スクリーンショットはopt-inで、AIプロンプトへは含めません。
- provider tokenとAPIキーはレスポンスへ返さず、対応環境ではOSキーチェーンへ保存します。
- Codex turnはread-only、ephemeral、approval拒否、JSON Schema固定です。
- 自動修正はlocal・非本番・clean Git・fresh one-use attestation・変更上限・固定検証を全て要求し、失敗時はrollbackします。
- 外部commandや任意pathをAPI入力から実行せず、固定registryとallowlistを使用します。

## 運用上の制限

EagleEyeは認証・認可製品、DLP、WAF、EDR、法令認証の代替ではありません。loopback上の別プロセス、OS管理者、悪意あるブラウザー拡張からの完全な隔離は保証しません。共有端末ではOSアカウント分離、ディスク暗号化、短い保存期間を使用してください。

`EAGLEEYE_ALLOW_REMOTE=1`、外部bind、reverse proxy、クラウドAI、リモートReport Hubを有効にする場合は、TLS、強い認証、最小権限、network allowlist、rate limit、監査log、backup暗号化、削除手順を運用者が追加してください。標準のloopback用APIを認証なしでインターネットへ公開してはいけません。

## 許可されたテストだけを行う

所有または明示的な許可を得た対象だけをテストしてください。資格情報の窃取、rate-limit回避、破壊的payload、可用性攻撃、第三者データの取得を禁止します。productionでの書込み、決済、本人確認、法的同意、公開・送信の最終操作は人間の承認境界に残してください。

URL Auditはpenetration testではありません。固定requestへexploit payload、port scan、directory brute-force、資格情報試行、状態変更requestを追加してはいけません。

## Release security gate

公開Releaseは最低限、全pytest、Ruff、extension verifier、ESLint、dependency audit、Gitleaks、公開候補の個人情報・絶対パスscan、CIを通し、結果をレポートへ残します。
