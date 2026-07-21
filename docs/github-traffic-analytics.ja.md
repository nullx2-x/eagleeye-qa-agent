# GitHubリポジトリトラフィック収集

GitHubがClone数・View数の日別明細を保持する期間は限定されているため、EagleEyeではGitHub Actionsから定期取得して履歴をリポジトリ内へ保存します。同じ日付のデータは加算せず置換するため、再実行しても二重計上しません。

## 収集項目

- Clone数とユニークClone実行者数
- View数とユニーク訪問者数
- Stars、Forks、Watchers、未解決Issue数
- Releaseアセットの累計ダウンロード数
- 主な流入元と閲覧パス

## 実行周期

Workflowは毎日00:17 UTC（日本時間09:17）に起動します。`scripts/collect_github_traffic.py`が`analytics/github-traffic/latest.json`を確認し、前回収集から47時間未満の場合は処理をスキップします。手動実行では`force`入力により周期判定を無視できます。

## 認証境界

`TRAFFIC_TOKEN`はGitHub ActionsのRepository Secretとして保存します。Fine-grained personal access tokenは`eagleeye-qa-agent`だけを対象にし、権限は **Repository permissions → Administration: Read-only** に限定します。生成ファイルのCommitには別系統の組込み`GITHUB_TOKEN`を利用します。

## 失敗時の挙動

Secret未設定、期限切れ、権限不足の場合はFail closedし、既存の履歴ファイルを更新しません。トークン文字列はコード、README、Issue、Actionsログへ出力しないでください。
