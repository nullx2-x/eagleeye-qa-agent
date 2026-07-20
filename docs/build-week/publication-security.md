# EagleEye 公開前セキュリティ手順

## 目的

この手順は、EagleEyeをprivate開発環境からpublic GitHub、動画、Devpost、公開URLへ移す直前に毎回実施する。既存の内部監査、`.gitignore`、privateリポジトリでの削除は、公開予定履歴が安全である証明の代わりにならない。

実行結果はこの手順書へ上書きせず、日付付きの公開監査レポートまたはGitHub Releaseへ記録する。ソース公開、動画公開、Devpost送信は別々のgateとして判定する。

## 絶対停止条件

次のどれかが見つかったら公開操作を停止する。

- API key、OAuth token、cookie、password、private key、接続文字列、実credential
- 個人メール、氏名、住所、アカウントavatar、ブラウザprofile情報など不要なPII
- 実ユーザー入力、スクリーンショット、動画、DOM dump、操作履歴、SQLite、runtime backup
- private/LAN/tailnet URL、社内host、不要な実IP、ローカルusernameや絶対path
- 配布権限が不明なコード、画像、ロゴ、フォント、音声、動画、データ
- wildcard extension origin、不要なChrome permission、remote code、secretの永続化
- Windows/Linux quality gateの失敗
- `TBD`のGitHub、動画、公開URLを完成済みとする説明

## 役割分離

可能なら2名で行う。

1. **Release operator:** 固定commitを準備し、scannerとtestを実行する。
2. **Reviewer:** scannerの設定、公開予定tree、GitHub設定、動画全フレームを独立確認する。

同一人物で行う場合も、最初の確認後にclean cloneを作り、別セッションで再確認する。

## Step 0 - 公開候補を固定する

1. 並行作業を止め、公開候補commit SHAを記録する。
2. `git status --short --branch`、`git remote -v`、`git submodule status`を保存する。
3. 公開対象branchとtagを決める。可変な作業treeを直接公開しない。
4. tracked、untracked、ignoredを別々に列挙する。

```powershell
git status --short --branch
git ls-files
git ls-files --others --exclude-standard
git status --short --ignored
```

合格条件: 公開対象ファイルが説明でき、runtime/credential/artifactが追跡対象にない。

## Step 1 - 秘密情報をworking treeと全履歴で検査する

使用するsecret scannerのversionとrule setを固定し、値そのものを共有ログへ出さない。例としてgitleaksを使う場合:

```powershell
gitleaks detect --source . --redact --exit-code 1
gitleaks detect --source . --log-opts="--all" --redact --exit-code 1
```

補助検索は内容ではなくファイル名を先に出し、誤検知を手動分類する。

```powershell
rg -l -i --hidden --glob '!**/.git/**' "api[_-]?key|client[_-]?secret|access[_-]?token|refresh[_-]?token|authorization:|bearer |BEGIN [A-Z ]*PRIVATE KEY|password\s*[:=]|connection[_-]?string"
rg -l -i --hidden --glob '!**/.git/**' "C:\\\\Users\\\\|/home/[^/]+|192\.168\.|10\.[0-9]+\.|\.ts\.net|localhost:[0-9]+/reports"
```

合格条件:

- scanner finding 0件、またはすべて誤検知としてファイル・行・理由を記録
- `.env`実体、keychain export、auth cache、browser profile、runtime DBが全履歴に0件
- secretらしき値を単に削除したcommitが過去履歴に残っていない

## Step 2 - 生成物、証跡、PIIを検査する

次をtracked treeと全履歴で確認する。

- `.env`、`.runtime/`、`.workflow/`、`data/`の実session、`artifacts/`の実run
- PNG/JPEG/WebM/trace/ZIP/SQLite/log/backup
- 実URLを含むJSON、YAML、HTML report
- スクリーンショット内の通知、avatar、bookmark、path、email、token、browser extension一覧
- 動画の全フレームと音声に含まれる氏名、通知音、会話、credential

公開用画像は新しいsynthetic demoから再取得する。既存artifactの「見た目が安全そう」は根拠にしない。

合格条件: 公開媒体にsynthetic data以外の識別可能情報0件。

## Step 3 - Chrome拡張を専用監査する

`manifest.json`、background/service worker、content script、popup、storage、network呼出しを確認する。

- permissionとhost permissionは最小限
- `<all_urls>`を原則不使用。必要なら審査資料で理由と制限を説明
- remote JavaScript、`eval`、`new Function`、外部CDN scriptなし
- Content Security Policyを緩和しない
- captureは明示ON後のみ、停止が可視、session境界が明確
- raw input、password、OTP、card、secret fieldを保存・送信しない
- screenshot取得範囲と保存期間をユーザーへ表示
- localhost APIはexact origin、Host、CORS、methodを検証
- extension IDとallowlistが配布packageで一致
- update URL、analytics、telemetryがある場合は明記し、不要なら削除

合格条件: 権限差分レビューとfresh profileのOFF/ON負例試験がPASS。

## Step 4 - ローカルAPIとAI境界を監査する

- 既定bindが`127.0.0.1`
- remote URL実行は既定拒否
- unsafe methodは許可Originだけ
- wildcard CORSなし
- browser/DOM文字列をprompt instructionとして扱わない
- OpenAIへ送るpayloadをtestで捕捉し、raw value、credential、不要な全文DOMがない
- Codex turnはread-only、approval拒否、schema output
- OpenAI停止時はfallbackを明示し、AI生成済みと表示しない
- reportはHTML escapeし、secretを再表示しない
- self-repairは明示承認と全fail-closed gateを保持

合格条件: 正常系だけでなくorigin、cross-origin、secret、oversize、prompt injection、provider停止の負例がPASS。

## Step 5 - 依存関係、ライセンス、供給網を確認する

1. `uv.lock`からのみ環境を再現する。
2. Python依存の既知脆弱性を監査する。
3. Python、GitHub Actions、Chrome拡張assetのlicenseを確認する。
4. GitHub Actionsをcommit SHAへpinするか、major tag採用のリスクを明示承認する。
5. 不要なpackage、binary、vendored codeを除外する。

例:

```powershell
uv sync --locked --dev
uv run python -m pip check
uv run pip-audit
```

`pip-audit`等をdev依存へ追加しない運用の場合は、隔離した監査環境で実行し、scanner versionと結果だけを保存する。

合格条件: 未評価のcritical/high finding 0件、配布条件不明asset 0件。

## Step 6 - clean cloneで品質を再現する

公開候補commitだけを新しいdirectoryへcloneし、ローカルcacheや未追跡ファイルに依存しないことを確認する。

```powershell
uv sync --locked --dev
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
git diff --check
git status --short
```

さらに、WindowsとLinuxのGitHub Actions matrixを同一commitで成功させる。

合格条件: 全command exit code 0、tree clean、両OS green。

## Step 7 - 公開GitHub設定を確認する

公開切替または新規public repository作成の直前に確認する。

- repository名、owner、default branch、visibility
- branch protectionとrequired CI
- Actionsのdefault permissionはread-only
- secret scanning、push protection、Dependabot alerts/updates
- issue/PRで秘密情報を貼らないtemplateまたは運用ルール
- release artifactにruntime dataがない
- public fork、Pages、Actions artifactの公開範囲
- README、LICENSE、セットアップ、security contact

公開後はログアウト状態またはprivate browsingからtree、commit history、release、Actions logs、artifactを確認する。private remote URLやlocal pathをDevpostへ貼らない。

## Step 8 - Devpost、動画、画像を独立監査する

1. `docs/build-week/devpost-draft.md`から`TBD`、`IN_PROGRESS`、内部path、private URL、古いtest件数を検索する。
2. 実装状態と文章を1 claimずつ照合する。
3. 動画を0.25倍速で確認し、全frameの通知・path・account情報を見る。
4. 字幕が画面と異なる成功主張をしていないか確認する。
5. GitHub、video、public URL、各画像を未認証環境から開く。

合格条件: broken link 0件、TBD 0件、未実装の成功主張0件、PII/secret 0件。

## Step 9 - 公開判定と証跡

次を1つのrelease recordへ残す。

- commit SHA、tag、scanner version/rules、finding数
- pytest結果、Ruff結果、Windows/Linux CI URL
- extension identityの導出確認（値は非表示）、version、permission review結果
- GitHub、video、public URL、画像URL
- reviewer、実施時刻、残存リスク、判定

判定は`PASS / FAIL / BLOCKED / PARTIAL / INCOMPLETE`のいずれかを使用する。すべての必須gateがPASSになるまで公開判定はPASSにしない。

## 漏えいを発見した場合

1. 公開・push・動画uploadを直ちに止める。
2. 秘密値を先にrevoke/rotateし、sessionやtokenを無効化する。
3. 影響範囲、最初の露出時刻、clone/fork/artifact/logを確認する。
4. owner承認のもと、使い捨てmirror cloneで`git filter-repo`等を使用して履歴を修復する。作業中repositoryへ衝動的なforce pushをしない。
5. collaboratorへ旧clone破棄と再cloneを依頼する。
6. 全履歴と公開surfaceを再scanする。
7. 秘密値を含めずincident recordを残す。

ファイル削除、`.gitignore`追加、後続commitでのマスクだけでは、既に公開された秘密値は安全にならない。
