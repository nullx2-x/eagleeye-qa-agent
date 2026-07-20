# solo-map.app の EagleEye 非破壊動作検証（2026-07-20 JST）

## 判定

**PARTIAL** — 公開トップページのEagleEye再生はPASSした。一方で、同一ページ内アンカー（`#profile`）の再生は、EagleEye Browser AgentがURLフラグメントを記録時に除去するため、最終URLアサーションを正しく保持できずFAILした。これは今回確認した範囲ではサイト本体ではなくテストハーネスの機能制限である。

## 実施範囲と安全境界

- 対象: `https://solo-map.app/`
- 実施: 初期表示、Primary navigationの `Profile` / `Skills` / `Links` / `Contact` アンカー遷移、EagleEyeのAIケース生成、Playwright replay。
- 非実施: フォーム入力、メール送信、アカウント操作、外部カードリンクへの遷移、データ変更。
- リモート再生はこのローカルEagleEyeプロセスだけに `EAGLEEYE_ALLOW_REMOTE=1` を明示して許可した。永続設定は変更していない。
- AI: `codex-agent` / `gpt-5.6-terra`。両セッションでCodex App Serverが接続済み、fallbackなしでスキーマ検証済みケースを返した。

## 結果

| 検証 | 結果 | 根拠 |
| --- | --- | --- |
| 実ブラウザでの初期表示 | PASS | タイトル `jack-low | solo-map.app`、main/landmark/見出しを確認。 |
| Primary navigationのアンカー遷移 | PASS | `Profile` → `#profile`、`Skills` → `#skills`、`Links` → `#projects`、`Contact` → `#contact` を実ブラウザで確認。 |
| EagleEye AIケース生成（初期表示） | PASS | `gpt-5.6-terra` が5ケース生成、deterministic case quality: 100/100、PASS。 |
| EagleEye Playwright replay（初期表示） | PASS | 5,760 ms、quality gate PASS、100%、画像・WebMのハッシュ証跡あり。 |
| EagleEye Playwright replay（Profileアンカー） | FAIL / ハーネス制限 | 2回目の再生ではクリック自体は成功したが、記録済み期待URLが `/` に正規化され、実測 `/#profile` と不一致。 |

## PASS証跡

- EagleEye browser session: `e1ce6ef28f6345928ffaff8ef7fbb6af`
- Screenshot: `artifacts/runs/e1ce6ef28f6345928ffaff8ef7fbb6af/final.png`
  - SHA-256: `065655fc18d7c560524510e3e85951da54cae0dcff4f84011a030b3ba6294f33`
- Video: `artifacts/runs/e1ce6ef28f6345928ffaff8ef7fbb6af/video/page@7b6e748aa2a730c9e89916057c68c371.webm`
  - SHA-256: `3eb194518730aff06e2863da85737d03e131529703a45e5ea7618d11c9538d82`
- 実ブラウザの発見時スクリーンショット: `artifacts/browser-agent/solo-map-app-validation-2026-07-20-discovery.png`

## 検出事項: アンカーURLを再生できない

**分類:** EagleEye Browser Agentの再生精度上の不具合 / 制限。サイト不具合としては未判定。

`app/browser_agent.py` の `_sanitize_url()` は `urlunsplit()` のfragmentに常に空文字を渡す。そのため、観測した `https://solo-map.app/#profile` は保存時に `https://solo-map.app/` へ変換される。EagleEyeのreplayは `Profile` をクリックして実際に `/#profile` へ到達するが、保存された期待URL `/` と比較して `Final URL mismatch` になる。

再現手順:

1. Browser Agent sessionを `https://solo-map.app/` で開始する。
2. `Profile` リンク（role=`link`, name=`Profile`）のクリックと、最終URL `https://solo-map.app/#profile` を観測として送る。
3. sessionを生成して再生する。
4. `data/browser-agent/<session>.json` とbundleのURLが `/` になり、クリック成功後の実測 `/#profile` との不一致でFAILする。

失敗セッション `1b04e56725e54b6ca3ff6ca3def11e54` には、失敗時スクリーンショットと2回分のWebM証跡が残る。後者はクリック成功後のURLアサーション不一致を示す。フォーム値・認証値・外部送信は含まない。

## 推奨対応

EagleEye側で、URLフラグメントを資格情報・クエリ値とは別に扱い、許可リストまたは安全な正規化を導入する。アンカーを除外する設計を維持する場合は、`expectedFinalUrl` のフラグメントを比較対象から除外するか、最終セクションの見出し/フォーカスを決定論的な到達オラクルとして保存する。

## 残存範囲

外部サイトへのカードリンクと `mailto:` は、非破壊スコープのため未実行。モバイル表示、キーボードフォーカス、スクリーンリーダーの読み上げは今回の対象外。

## 運用報告の配送

- Report Hub: 既定の安全な提出経路（`rspi-codex`）で提出を試みたが、この端末ではホスト名を解決できず未達。受付IDは発行されていない。
- Telegram: ワークスペース内に既存の安全な通知スクリプトまたは設定を検出できなかったため、秘密値を探索・推測せず未送信。`message_id` はない。
