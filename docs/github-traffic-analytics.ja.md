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
