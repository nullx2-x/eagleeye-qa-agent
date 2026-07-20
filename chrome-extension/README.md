# EagleEye Browser QA Chrome拡張 — 入力値を保存せず、現在のタブの操作から安全なQAセッションを作成します。

Manifest V3 の unpacked 拡張です。ユーザーがツールバーから明示的に開始した現在のタブだけへ recorder を注入し、ローカルの EagleEye API へ観測を送ります。

## 導入

1. EagleEye API を起動します。

   ```powershell
   cd <repository>
   .\scripts\start-eagleeye.ps1
   ```

2. `http://127.0.0.1:8766/health` が応答することを確認します。
3. Chrome で `chrome://extensions` を開き、「デベロッパー モード」を有効にします。
4. 「パッケージ化されていない拡張機能を読み込む」から次を選びます。

   ```text
   <repository>\chrome-extension
   ```

5. 拡張IDが表示され、EagleEyeの起動設定に登録済みであることを確認します。公開資料やレポートへ値を転記する必要はありません。

## 使い方

1. QA対象の HTTP(S) ページを現在のタブで開きます。
2. ツールバーのEagleEyeアイコン、または `Ctrl+Shift+Y` で拡張のpopupを開き、セッション名と確認目的を入力します。
3. 目立つプライバシー説明を読み、対象サイトの許可と記録内容への同意を確認します。
4. 必要な場合だけ「可視画面のスクリーンショットも送る」を選び、「開始」を押します。
5. ページ上で click / fill / select / check 操作を行い、「停止」を押します。
6. 「AI生成」でケースを生成し、「Replay」で EagleEye の承認済みローカル実行経路を呼び出します。
7. 「レポート表示」で `GET /api/v1/browser-agent/sessions/{id}/report` を新しいタブに開きます。
8. 不要になったら「このセッションを端末から削除」で、DOM要約、画像、動画、生成物を削除します。

同一オリジン内の遷移では recorder を再注入します。別オリジンへ移動した場合は記録を停止します。Replay の対象範囲は EagleEye サーバー側の安全ポリシーにも従い、標準設定では loopback URL に限定されます。

## プライバシー境界

- フォーム入力値、選択値、チェック値、`FormData` は読み取りも送信もしません。操作には安全な `valueType` 分類と `redacted=true` だけを付与します。
- DOM は本文や HTML を送らず、ページタイトル、見出し最大24件、ランドマーク最大20件、コントロール最大60件のアクセシブル要約だけを送ります。
- コントロール名や見出し自体に個人情報が表示されている場合は要約へ含まれ得ます。機密画面では記録を開始しないでください。
- スクリーンショットは初期状態で無効です。有効にした場合も `chrome.tabs.captureVisibleTab` による現在の可視領域だけで、開始時と停止時に送ります。画面内の機密情報も画像化されるため、必要な場合だけ同意して有効にしてください。
- 拡張状態は `chrome.storage.session` だけに保存します。Chrome の再起動、拡張の再読み込み・無効化・更新で消去され、content script からはアクセスできません。
- API 通信先はコードでも `http://127.0.0.1:8766` と `http://localhost:8766` に固定しています。認証情報や Cookie は送信しません。
- API 応答は未信頼データとして扱い、popup では `textContent` と `createElement` だけで描画します。`innerHTML`、`eval`、リモートコードは使用しません。
- 「AI生成」で外部AIを使う場合も、秘匿化URL、操作種別、限定DOM要約だけを送り、フォーム入力値とスクリーンショットは送りません。
- 完全な方針はリポジトリ直下の `PRIVACY.md`、`SECURITY.md`、`COMPLIANCE.md` を参照してください。

## エラー案内

- 「APIに接続できません」: `scripts\start-eagleeye.ps1` を実行し、`/health` を確認してください。
- 「タイムアウト」: APIログと AI provider の接続状態を確認してから再実行してください。AI生成と Replay には通常のAPI呼び出しより長い上限を設定しています。
- 「このページでは開始できません」: `chrome://`、拡張ページ、PDF viewer などには注入できません。HTTP(S) ページを現在のタブにして再度開いてください。

## 自己検証

```powershell
cd <repository>
node .\chrome-extension\tests\verify-extension.mjs
npx --yes eslint@9 .\chrome-extension\background.js .\chrome-extension\content.js `
  .\chrome-extension\popup.js .\chrome-extension\tests\verify-extension.mjs
npx --yes --package @playwright/cli playwright-cli -s=eagleeye-extension `
  open chrome-extension://<表示された拡張ID>/popup.html `
  --config .\chrome-extension\tests\playwright-extension.config.json --persistent
```

検証スクリプトは固定 manifest public key から期待 ID を再計算し、権限、API endpoint、session-only storage、DOM 件数、値非取得、危険な描画 API の不使用、目立つ説明、明示同意、削除導線を検査します。このpublic keyは拡張のdemo identityを固定する公開鍵で、署名用秘密鍵、API key、認証資格情報ではありません。
