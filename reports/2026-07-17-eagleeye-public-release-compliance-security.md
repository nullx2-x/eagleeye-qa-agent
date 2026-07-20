# EagleEye 公開・コンプライアンス・セキュリティ監査レポート

実施日: 2026-07-17 (JST)
総合判定: **PARTIAL**（項目1は音声方式の選択待ち、項目2はPASS）

## 1. デモ動画の最終公開

判定: **PARTIAL**

- 2分55秒の日本語画面構成、台本、実Authorized targetの最新画面素材は完成。
- HyperFrames checkは0 error、runtime/motion/contrast gateはPASS。
- OpenAI Build Weekの公開動画要件に合わせ、音声付きで最終renderする必要がある。
- AI音声の生成方式（HeyGenログインまたはローカル音声エンジン）が未選択のため、無断でproviderを決めず停止中。
- 音声生成、最終render、音声stream・尺・全frame確認、公開Releaseは未実施。

## 2. 公開GitHub、コンプライアンス、セキュリティ、プライバシー

判定: **PASS**

公開先: <https://github.com/nullx2-x/eagleeye-qa-agent>

### 公開履歴と秘密情報

- private開発履歴を継承せず、公開専用の新規履歴を作成。
- 内部運用レポート、runtime DB、実session、browser profile、認証cache、`.env`実体を公開対象から除外。
- Gitleaks 8.30.1で公開全3コミットを検査し、finding 0件。
- API key、OAuth token、password、cookie、private key、接続文字列の検出0件。
- 個人メール、氏名、住所、端末固有の絶対path、private IP、tailnet hostnameの検出0件。
- メール文字列は`example.com`、`example.invalid`とOpenAIの合成テスト用service domainだけ。
- 固定Chrome拡張IDの直書きは0件。値はmanifestの公開SPKIから実行時導出し、画面・レポートでは非表示。
- manifestのSPKIは秘密鍵やcredentialではなく、拡張同一性を固定する公開情報として限定allowlist化。
- 画像/GIFなど20媒体の埋め込み文字列を確認し、個人path・handle・private network・secret形状0件。提出画面も目視確認済み。

### 実装したプライバシー対策

- 記録前の目立つ説明と明示同意。未同意では開始不可。
- input値、Cookie、認証header、FormData、password、OTP、決済情報を収集しない。
- screenshotは初期OFFのopt-inで、AI promptへ送信しない。
- AI用URLはquery valueとIDらしいpath segmentを秘匿化。
- email、電話番号、UUID、ユーザーhome pathをレポート・prompt前に秘匿化。
- popupとREST APIからsession、DOM要約、画像、動画、生成spec、run証跡を一括削除可能。
- 製品telemetryなし。外部AI送信は利用者がAI生成を実行したときだけ。

### 実装したセキュリティ対策

- API docs/OpenAPIを既定無効化し、CSP、no-store、nosniff、frame deny、referrer/permissions policyを付与。
- Host、unsafe method Origin、CORSをexact allowlistで制限。
- Replayのredirectとsubresourceを含め、許可境界外networkを遮断。
- Guided assetは利用者入力からpathを構築せず、root内の安全な画像catalogから参照。
- 能動コンテンツになり得るSVGをGuided assetで拒否。
- route IDをHTMLへ埋め込まず、script文脈のtokenも`<`と`&`をescape。
- ReDoS対象regexを除去し、資産pathは長さ上限と有限の文字検査へ変更。
- patched MCPだけへ解決されるようPython対応範囲を固定し、古い重複requirementsを削除。

### 検証結果

- ローカル全回帰: **142 passed**（既知の非失敗deprecation warning 1件）。
- Ruff lint / format: PASS。
- Chrome extension privacy/security verifier: PASS。
- ESLint: PASS。
- Bandit medium/high: 0件。
- pip-audit: known vulnerability 0件。
- 公開CI: Windows、Linux、Chrome extensionの全job PASS。
- CodeQL: Python / JavaScriptともPASS。初回5件と追加1件を修正し、open alert **0件**。
- GitHub Secret Scanning: open alert **0件**。
- Dependabot: 初回2件を修正し、open alert **0件**。
- 公開README、Privacy、Security、Complianceは未認証HTTP 200。認証なしGit readもPASS。
- main branchは5 required checks、strict、linear history、force push/deletion禁止、conversation resolution必須で保護。
- Secret Scanning、Push Protection、Dependabot security updates、Private Vulnerability Reporting、Actions既定read-onlyを有効化。

### 実Authorized target E2E

- 拡張OFF時のsession増加0件。
- 明示同意後、実Chrome拡張から4 observationsを記録し、Codex App Serverで5ケース生成。
- case quality 100、Replay PASS、screenshot/WebM/SHA-256付きreport生成を確認。
- 初回はChrome `activeTab`権限待ちで失敗。実ショートカット操作後の再実行でPASS。失敗経過も隠さず証跡化。

## 3. コンプライアンス判定

技術実装は **条件付きPASS**。APPI/GDPRの原則、Chrome Web Store Limited Use、OpenAI data controlの観点で、目的明示、最小化、明示同意、privacy by default、削除、安全管理、提供先区別を反映した。

ただし、これは法的認証ではない。実運用者には、対象サイトをテストする権限、法的根拠、通知、保存期間、DPA/DPIA、国外移転、本人権利対応、incident response、remote公開時のTLS・認証・rate limitが残る。標準loopback APIを認証なしでインターネットへ公開してはならない。

参照:

- <https://www.ppc.go.jp/personalinfo/legal/guidelines_tsusoku/>
- <https://eur-lex.europa.eu/eli/reg/2016/679/oj>
- <https://developer.chrome.com/docs/webstore/program-policies/user-data-faq>
- <https://developers.openai.com/api/docs/guides/your-data>

## 4. 次の方針

1. 利用者が音声方式を選択する。
2. AI音声であることを明記して最終renderする。
3. 3分未満、音声stream、1920x1080、全frame、字幕・主張一致を再検査する。
4. 合格したMP4だけを公開Releaseへ添付し、未認証再生を確認する。
5. Devpostの最終送信は、別途明示承認があるまで実行しない。
