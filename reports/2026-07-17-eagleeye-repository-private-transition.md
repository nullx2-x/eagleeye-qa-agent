# EagleEye リポジトリprivate化レポート

実施日: 2026-07-17 (JST)  
判定: **PASS**

## 実施内容

- Build Week公開候補リポジトリのvisibilityを`public`から`private`へ変更。
- ソース、branch、CI履歴は削除せず保持。
- private開発用リポジトリには変更なし。

## 検証

- GitHub API上のvisibility: `private`
- 未認証リポジトリページ: HTTP 404
- 未認証Raw README: HTTP 404
- credentialなしGit read: 拒否
- 認証済みGit read: PASS
- 公開fork: 0件
- Actions履歴: 認証済みで閲覧可能
- Branch Protection API: private化後は現在のGitHub契約条件で利用不可
- Secret Scanning / Push Protection: private化後はAPI上で有効状態が返らず、継続有効とは判定しない

## 影響

- リポジトリURLは、明示的にアクセスを許可されたGitHubアカウントだけが閲覧できる。
- README、Privacy、Security、Compliance、Actions、CodeQLも外部の未認証利用者からは閲覧できない。
- Build Week / Devpostへ公開リンクとして提出する前に、利用者の明示指示で再度public化し、Branch Protection、Secret Scanning、Push Protectionの再有効化、未認証閲覧、秘密情報scanを再確認する必要がある。
