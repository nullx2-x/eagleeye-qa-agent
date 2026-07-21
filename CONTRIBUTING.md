# Contributing to EagleEye

Issue、Pull Request、fixture、screenshot、動画、logへ、実在する個人情報、顧客情報、秘密鍵、API key、token、password、private hostname、端末固有の絶対pathを含めないでください。例には`example.invalid`、loopback、合成IDを使用します。

## 開発手順

```powershell
uv sync --locked --dev
uv run playwright install chromium
uv run pytest -q
uv run ruff check app tests scripts
node .\chrome-extension\tests\verify-extension.mjs
Push-Location .\chrome-extension
npx --yes eslint@9 background.js content.js popup.js tests/verify-extension.mjs
Pop-Location
```

コード変更には関連テストを追加し、権限追加、収集データ追加、外部送信先追加、保存期間変更、remote access変更では英語正本の `PRIVACY.md`、`SECURITY.md`、`COMPLIANCE.md` と日本語訳も更新してください。

セキュリティ問題は公開Issueではなく [SECURITY.ja.md](SECURITY.ja.md) のprivate reporting手順を使ってください。
