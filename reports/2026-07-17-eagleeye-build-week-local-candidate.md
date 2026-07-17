# EagleEye OpenAI Build Week ローカル提出候補レポート

## 判定

**PARTIAL** — 審査員が5分で価値を理解できるローカル提出候補は完成した。実WordPressで主要導線を最後まで実行し、コード・安全性・提出素材を検証済み。private backupとWindows/Linux pre-release CIも完了した。最終MP4 render、公開GitHubへのpushと未認証確認、Devpost最終送信は外部変更の承認待ちである。

## 5分で伝える価値

EagleEyeは「AIテスト生成ツール」ではなく、ブラウザに常駐するローカルAI QAエージェントである。

1. Chrome拡張をONにする。
2. ユーザーは普段どおりWebサイトを操作する。
3. 入力値を保存せず、DOM要約・可視画面・操作履歴を同一セッションで観測する。
4. Codex App Server経由のOpenAIが、実操作に基づく追加テストを構造化生成する。
5. 決定論的品質チェッカーを通し、Playwrightが記録導線をReplayする。
6. 結果、画像・動画・SHA-256、修正提案をHTML/Markdownレポートへまとめ、人間が明示共有する。

AIが停止しても記録ケースを失わず、fallbackを隠さない。AIは候補を出し、Replayと証跡とrelease判断は決定論的コードと人間が所有する。

## 実装した範囲

- ログイン不要の同梱デモと、既存ローカルWordPressへの自動接続。
- 最小権限のManifest V3 Chrome拡張、ON/OFF、session-only状態、bounded capture。
- browser session、DOM/画面/履歴、AIテスト生成、Replay、report、screenshot、bug-report API。
- Codex App Serverのread-only・approval拒否・JSON Schema出力、timeout/error/fallback表示。
- URL/title/heading assertion、PNG/WebM証跡とSHA-256、修正提案、人間承認境界。
- Dashboard、Test一覧、実行中、Report、ダークUI、日本語表示。
- README、MIT LICENSE、`.env.example`、Quick Start、Architecture、Windows/Linux CI。
- 実画面6枚、Architecture画像、12秒GIF、2:55 HyperFramesプレビュー、デモ台本、Devpost草稿。

## 実WordPress E2E証跡

2026-07-17にfresh unpacked Chromiumと、以前から検証に使っているローカルWordPressで実行した。

| 項目 | 結果 |
|---|---:|
| 拡張OFF時のsession増分 | 0 |
| 明示ON後の観測 | 4 |
| Codex生成ケース | 5 |
| provider / model | codex-agent / gpt-5.6-terra |
| fallback | false |
| ケース品質 | PASS / 100 |
| Replay | PASS / 1,745 ms |
| PNG証跡 | 103,299 bytes / SHA-256一致 |
| WebM証跡 | 112,935 bytes / SHA-256一致 |

3回連続の再現性確認ではReplay 3/3、品質100が3/3でPASSした。live AIは1/3、明示fallbackは2/3だった。外部AIの揺らぎと、決定論的に継続できる製品価値を分けて記録している。

## 品質・セキュリティゲート

- `pytest`: **138 passed**、failed/error 0。既知のupstream deprecation warning 1件。
- Ruff lint: PASS。Ruff format: PASS（64 files）。
- Python dependency audit: known vulnerabilities 0、broken requirements 0。
- Chrome拡張: static verifierとESLint PASS。
- HyperFrames preview: runtime/layout/motion/contrast PASS、10 frameを目視確認。
- Private pre-release CI: Windows/Linuxとも、locked sync、138 tests、Ruff lint/format、clean tree checkをPASS。
- Secret scan: **gitleaks 8.30.1 / 公開候補160ファイル / 提出commitを含む全12 commit / finding 0**。
- 入力値非保存、secret query除去、same-origin、固定拡張origin、screenshot上限、path confinement、HTML escapeを負例テスト済み。
- session/run/video IDとprivate pathを公開証跡からmaskし、token、password、API key、chat IDを記録していない。

## 提出素材

- `README.md`
- `docs/build-week/architecture.md`
- `docs/build-week/screenshots/architecture-flow.png`
- `docs/build-week/screenshots/eagleeye-demo-flow.gif`
- `docs/build-week/demo-script.md`
- `docs/build-week/devpost-draft.md`
- `docs/build-week/submission-checklist.md`
- `docs/build-week/evidence/extension-wordpress-e2e.json`
- `docs/build-week/evidence/three-run-reproducibility.json`

## 今後の方針・指針

1. **提出まではwinning pathを凍結する。** 新規機能より、3分動画、公開再現性、説明の一貫性を優先する。
2. **AI成功を捏造しない。** provider、model、fallback、品質判定を常に別項目で表示する。
3. **記録ケースを主経路にする。** AI生成ケースは補完候補であり、実行前品質検査と安全範囲を越えない。
4. **公開はclean candidateから行う。** secret/history/license/link scanを通したファイルだけを公開し、private originやruntime artifactを持ち込まない。
5. **修正適用とreleaseは人間承認を守る。** 自動提案は行うが、公開・本番書込み・最終送信を代行しない。
6. **審査基準へ直結させる。** 技術実装は実E2E証跡、Designは5分導線、ImpactはQA時間短縮、Ideaは実操作とAI coverageの統合で説明する。
7. **提出後は履歴差分・controlled failure・public report sharingを拡張する。** 現在の安全なlocal-first境界を崩さず、認証・保持期限・監査を先に設計する。

## 残作業と承認ゲート

- 2:55 HyperFramesの最終MP4 renderと公開先へのupload。
- sanitized public GitHub repositoryの作成/push、公開commitのWindows/Linux CI、未認証閲覧確認。
- DevpostのGitHub、動画、スクリーンショット設定と最終submit。
- 任意加点: controlled regression fixture、独立reviewer、3-browser remote gate。

外部ゲートが1件でも未完了の間は提出完了をPASSとせず、PARTIALとして報告する。
