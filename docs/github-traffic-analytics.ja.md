# GitHubリポジトリトラフィック収集

GitHubがClone数・View数の日別明細を保持する期間は限定されているため、EagleEyeではGitHub Actionsから定期取得して履歴を保存します。同じ日付のデータは加算せず置換するため、再実行しても二重計上しません。

## 収集項目

- Clone数とユニークClone実行者数
- View数とユニーク訪問者数
- Stars、Forks、Watchers、未解決Issue数
- Releaseアセットの累計ダウンロード数
- 主な流入元と閲覧パス

## 実行周期

Workflowは毎日00:17 UTC（日本時間09:17）に起動します。`scripts/collect_github_traffic.py`が`analytics-data`ブランチ上の`analytics/github-traffic/latest.json`を確認し、前回収集から47時間未満の場合は処理をスキップします。手動実行では`force`入力により周期判定を無視できます。

## 保存境界

Workflow定義と収集スクリプトは、保護された`main`ブランチから読み込みます。生成された集計ファイルは専用の`analytics-data`ブランチだけへCommitします。これにより、`main`のPull Request必須・ステータスチェック必須という保護設定を回避せずに自動収集できます。

## 認証境界

`TRAFFIC_TOKEN`はGitHub ActionsのRepository Secretとして保存します。Fine-grained personal access tokenは`eagleeye-qa-agent`だけを対象にし、権限は **Repository permissions → Administration: Read-only** に限定します。生成ファイルのCommitには別系統の組込み`GITHUB_TOKEN`を利用し、更新先は`analytics-data`ブランチに限定します。

## 失敗時の挙動

Secret未設定、期限切れ、権限不足の場合はFail closedし、既存の履歴ファイルを更新しません。`analytics-data`へのPushが拒否された場合もWorkflowを失敗させ、`main`の保護設定は変更しません。トークン文字列はコード、README、Issue、Actionsログへ出力しないでください。

## 認証エラーからの復旧

2026-10-13以降の定期実行では、収集ステップが `TRAFFIC_TOKEN was rejected` と表示して失敗しています。Secretの存在確認は成功しているため、未設定ではなくAPI側の拒否です。旧実装はHTTP 401/403をまとめて扱うため、失効・権限不足・レート制限のどれかは旧ログから確定できません。

1. GitHubの Settings → Developer settings → Personal access tokens → Fine-grained tokens で既存トークンの期限、状態、アクセス先を確認します。
2. 必要なら新しいFine-grained PATを作成します。Resource ownerを `nullx2-x`、Repository accessを `Only select repositories` → `eagleeye-qa-agent`、Repository permissionsを `Administration: Read-only` に設定します。必要な承認があれば完了させます。
3. リポジトリの Settings → Secrets and variables → Actions → Repository secrets → `TRAFFIC_TOKEN` を更新します。トークンの文字列をIssue、PR、ログ、チャットに貼らないでください。
4. Actions → Collect repository traffic → Run workflow を選択し、`main` と `force=true` で実行します。修正PRをマージする前は旧エラーメッセージのままです。
5. 収集と `analytics-data` へのコミットが成功したことを確認します。データが変化しない場合、Commitステップがスキップ相当になるのは正常です。

401はトークンの失効・無効化を、403は権限・ポリシー・二次レート制限を、403かつ残り回数0または429はレート制限を優先して確認してください。新しい診断メッセージはHTTPコードと失敗したAPIパスだけを出し、認証情報は出しません。

GitHubのトラフィックAPIは過去データの取得期間が限定されます。復旧後に取得できない過去の日別データを推測で補完せず、履歴に欠測期間が残ることを許容してください。
