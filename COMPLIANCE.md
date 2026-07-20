# EagleEye コンプライアンス確認表

最終技術レビュー: 2026-07-20

結論は **条件付きPASS** です。公開ソース版の既定構成は、データ最小化、明示同意、local-first保存、安全管理、削除、秘密情報の非保存を実装しています。ただし、特定組織の法令準拠を認証するものではなく、対象サイト、利用地域、データ主体、契約、AIプロバイダー、リモート保存を決める運用者の責任が残ります。

## 対応表

| 観点 | 実装・文書 | 判定 | 運用者に残る事項 |
|---|---|---|---|
| 利用目的の明示 | popup内の目立つ説明、[PRIVACY.md](PRIVACY.md) | PASS | 対象サイト側の通知・社内規程 |
| 明示同意 | 記録内容と対象サイトの許可を確認するcheckboxが必須 | PASS | 同意以外の法的根拠が必要な場面の判断 |
| データ最小化 | 本文/HTML/入力値/Cookieを取得せず件数制限付きDOM要約 | PASS | 機密画面で開始しない運用 |
| screenshot | 初期OFF、別checkbox、可視領域のみ、AI送信なし | PASS | 画像内PIIの目視確認・mask |
| 保存・削除 | local保存、session-only extension state、1-click削除API/UI | PASS | backup・外部共有先の削除 |
| 安全管理 | Host/CORS/Origin/CSP、no-store、path confinement、redirect guard | PASS | remote公開時のTLS・認証・rate limit |
| 第三者提供 | AI生成時だけ最小化promptを選択providerへ送信 | PASS | provider契約、国外移転、DPA/DPIA |
| 本人の権利 | localデータの閲覧・export・セッション単位削除 | PASS | 組織運用での請求受付・本人確認・期限管理 |
| 漏えい対応 | private security reportingと事故連絡方針 | PARTIAL | 組織の報告手順・監督機関/本人通知 |
| 子ども・高感度データ | 使用禁止/回避を明記 | POLICY | 必要なら年齢確認・追加同意・DPIA |
| Chrome Web Store Limited Use | QAという単一目的、最小permission、local-first、目立つ説明 | PASS | Store掲載時のPrivacyタブ・Data use申告 |
| OpenAI利用 | API経路とCodex/ChatGPT経路を区別しtoken非保存 | PASS | 選択製品の最新契約・data controls確認 |

## 参照した公式原則

- 個人情報保護委員会「個人情報の保護に関する法律についてのガイドライン」: 利用目的、安全管理、第三者提供、開示等、漏えい等対応。
  <https://www.ppc.go.jp/personalinfo/legal/guidelines_tsusoku/>
- GDPR本文: data minimisation、privacy by design and by default、controller/processorの責任。
  <https://eur-lex.europa.eu/eli/reg/2016/679/oj>
- Chrome Web Store User Data FAQ / Limited Use: website content、browsing activity、screenshotもuser dataに含まれ、目立つ説明、同意、最小permission、privacy policyが必要。
  <https://developer.chrome.com/docs/webstore/program-policies/user-data-faq>
- OpenAI API data controls: APIと各consumer/product経路では適用される保持・学習方針が異なるため、実際の経路を区別する。
  <https://developers.openai.com/api/docs/guides/your-data>

## 公開・導入前に運用者が決める項目

1. controller / processorその他の役割と問い合わせ窓口
2. 対象サイトをテストする権限、従業員・顧客への通知、法的根拠
3. 保存期間、backup、削除、access control、incident response
4. AI/Report Hub/GitHub等の提供先、DPA、国外移転、subprocessor
5. 高リスク処理に対するDPIAまたは同等評価
6. Chrome Web Storeへ提出する場合のData use申告とpolicy URL

法的判断が必要な運用では、適用法域の専門家による確認を行ってください。
