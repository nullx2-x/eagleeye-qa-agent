# EagleEye private release security and privacy review

実施日: 2026-07-18 (JST)

対象: `nullx2-x/eagleeye-qa-agent` へ提出する単一スナップショット

判定: **条件付きPASS**

本判定はソース、既定構成、提出資料に対する技術監査です。特定組織のAPPI、GDPR、契約、越境移転、DPIA、保存期間、事故報告を法的に認証するものではありません。

## 結果要約

| 項目 | 結果 | 根拠 |
|---|---:|---|
| Pythonテスト | PASS | `142 passed` |
| Ruff lint / format | PASS | lint 0、64 files formatted |
| Chrome拡張 invariant / ESLint | PASS | Manifest V3、最小permission、入力値非保持、明示同意、削除UIを検証 |
| Bandit | PASS_WITH_NOTE | High/Medium 0、Low 17。固定argvの`subprocess`とOAuth endpoint文字列のみ |
| Python依存 | PASS | 公式PyPIの固定version APIで57依存、既知脆弱性0、取得失敗0 |
| 動画用Node依存 | PASS_WITH_WARNING | High 3。HyperFramesの開発専用`adm-zip` / `onnxruntime-node`経路、修正版なし、EagleEye実行環境には非同梱 |
| 秘密・個人情報・固有path | PASS | 追跡対象から旧owner名、実ユーザーpath、実Workspace path、個人email、秘密鍵形式0件 |
| Gitleaks | PASS | release snapshotを`.gitleaks.toml`付きで検査。Chrome manifestの公開SPKI鍵だけを狭くallowlist |
| 動画 | PASS | 2:55、1920x1080、30fps、H.264/AAC、全編decode成功、英語音声と72字幕cue |

## 公開履歴と識別情報

- 旧開発リポジトリの履歴は提出先へpushしない。過去commit author、旧owner URL、過去のテスト用疑似secretを新しい履歴へ継承しない。
- 提出先は監査済みファイルだけを含む単一commitから開始する。
- READMEと既存レポートのowner URLを`nullx2-x`へ更新した。
- 実在したWorkspace絶対path 2件を、相対pathと`<your-project-root>` placeholderへ置換した。
- テスト内のJWT/AWS疑似値は実秘密ではないが、秘密検出器が一行のcredentialと誤認しない構成へ分割した。
- `output/`、`.runtime/`、`.workflow/`、`.env`はGit対象外。提出動画、監査生データ、ローカルmodel、認証状態をリポジトリへ含めない。

## プライバシー・コンプライアンス照合

### Chrome Web Store

Chromeは、website content、閲覧活動、スクリーンショットをuser dataとして扱い、端末内だけの処理でも開示を要求しています。EagleEyeは次を満たします。

- `activeTab`、`scripting`、`storage`と2つのloopback hostだけを要求し、incognitoを無効化。
- 記録内容、対象サイトの権限、任意スクリーンショットを開始前に表示し、明示checkboxが揃うまで開始不可。
- フォーム値、Cookie、認証header、`FormData`、password、OTP、決済情報を保持しない。
- URLのcredential、fragment、secret-like queryを除去し、入力イベントは型だけを`redacted=true`で記録。
- 端末内セッション削除UIと`DELETE` APIを提供。

参照: [Chrome Web Store User Data FAQ](https://developer.chrome.com/docs/webstore/program-policies/user-data-faq)

### APPI / GDPR

利用目的、データ最小化、privacy by default、アクセス制限、安全管理、削除手段は実装済みです。GDPR Article 5の透明性、data minimisation、storage limitation、integrity/confidentialityに対応する設計要素があります。ただし、次は導入者が決める必要があります。

- controller / processor、法的根拠、通知対象、本人請求窓口
- 自動削除期限。既定は利用者管理であり、共有・商用運用では無期限保持のままにしない
- DPA、DPIA、越境移転、再委託先、処理記録、incident response
- 高感度情報、児童、医療、金融、雇用画面を対象外にするか、追加統制を設ける

参照: [個人情報保護委員会 法令・ガイドライン](https://www.ppc.go.jp/en/legal/)、[GDPR本文](https://eur-lex.europa.eu/eli/reg/2016/679/oj)

### OpenAI / Codex

- AIへ送るのは目的、sanitized URL、action種別、accessible label、安全なDOM要約に限定する。
- スクリーンショット、フォーム入力値、provider tokenはAI promptへ含めない。
- Codex App Server経路ではCodex管理のChatGPT loginを利用し、EagleEyeはOAuth tokenを読取・保存しない。
- OpenAI APIを直接選ぶ場合、API dataは明示opt-inがない限りtrainingへ使われず、標準のabuse monitoring logは原則最大30日です。Codex/ChatGPT経路とは契約とdata controlsが異なるため、運用前に選択製品の最新条件を確認する。

参照: [OpenAI API data controls](https://developers.openai.com/api/docs/guides/your-data)

## セキュリティ境界

- 既定APIはloopback、CORS/Hostを限定し、Replayもloopback HTTP(S)だけを許可する。
- provider credentialはレスポンスへ返さず、対応環境ではOS keyringへ保存する。
- Codex turnはread-only、ephemeral、approval拒否、JSON Schema固定。
- subprocessはshellを使わず、固定binary、固定registry、allowlist、timeout、最小環境で実行する。
- 自動修正はlocal・非本番・clean Git・one-use attestation・変更上限・固定検証が揃わなければfail closed。

## 残余リスクと必須運用

1. loopback用の認証なしAPIを直接LAN/VPN/Internetへbindしない。
2. remote Report HubにはTLS、強い認証、期限付きsession、rate limit、監査log、backup暗号化、削除手順を追加する。
3. 記録前に対象サイトの所有または明示許可を確認し、production書込み、決済、本人確認、法的同意、公開操作は人間承認に残す。
4. 共有・商用運用では保存期限を定め、自動削除jobと外部複製先の削除手順を実装する。
5. HyperFramesの開発依存3件は修正版公開後に更新する。未信頼ZIPを動画制作環境へ入力しない。

## 結論

監査済み単一履歴をprivateで共有する提出形態は**条件付きPASS**です。EagleEyeの既定local-first構成はデータ最小化と明示同意を実装していますが、remote化・複数利用者化・商用化は別の認証、保持、契約、事故対応ゲートを必要とします。
