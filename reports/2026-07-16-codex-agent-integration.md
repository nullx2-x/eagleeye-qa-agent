# EagleEye Codex Agent統合レポート

- 実施日: 2026-07-16
- バージョン: 0.7.0
- 判定: PASS

## 結論

EagleEyeから、ChatGPTログイン済みのローカルCodex CLIを独立したQA助言エージェントとして利用可能にした。OpenAI APIキーやCodexの認証トークンをEagleEyeへ保存・転送しない。

## 安全境界

- `codex exec`の非対話実行を使用
- 一時ディレクトリで実行し、セッションを保存しない
- read-only sandbox、approval policy `never`
- ユーザー設定を読み込まず、認証キャッシュだけをCodex側で利用
- 子プロセスへ渡す環境変数をOS・Codex認証に必要な名前へ限定
- QA助言の出力をJSON Schemaで固定
- Codexの提案は既存のAI安全evalと決定論的post-conditionを通し、必須テスト削除や制約緩和を拒否

## 検証

- pytest: 64 PASS
- ruff check / format check: PASS
- `codex login status`: ChatGPTログインを認識
- Codex単体実接続: JSON Schema準拠、追加テスト1件を取得
- EagleEye API実接続: `provider=codex-agent`、`available=true`、安全性検出0件
- API/MCP再起動: healthy

## App Server方針

現行のQA助言は単発の構造化要求であるため、安定した`codex exec`を採用した。将来、長寿命スレッド、途中イベント、承認UI、キャンセル、ターン再開が必要になった時点で、同じプロバイダー境界の実装をCodex App Serverへ差し替える。
