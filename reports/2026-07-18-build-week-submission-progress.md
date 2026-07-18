# EagleEye OpenAI Build Week submission progress

更新日: 2026-07-18 (JST)

総合ステータス: **PARTIAL**

EagleEye本体、提出用privateリポジトリ、英語音声・字幕付きデモ動画、Devpost本文は提出可能な状態まで完成しています。最終提出は、公開YouTube URLとDevpostの居住国入力を待っているため未実施です。

## 完了した成果

| 項目 | 状態 | 証跡 |
|---|---:|---|
| GitHubアカウント | PASS | `nullx2-x` がGitHub CLIのactive account |
| privateリポジトリ | PASS | <https://github.com/nullx2-x/eagleeye-qa-agent>、default branch `main` |
| Git履歴分離 | PASS | 旧開発履歴を含まない監査済みrelease snapshotから開始 |
| GitHub審査アクセス | PASS_WITH_CONFIRMATION | 2件の読取専用招待を作成。`devposttesting` はAPIで確認済み。メール招待はGitHub API上で宛先非表示のためManage access画面で最終確認する |
| 秘密・個人情報監査 | PASS | Gitleaks 0、個人名・個人email・実絶対path・秘密鍵・主要token pattern 0 |
| Python QA | PASS | `142 passed`、Ruff lint/format PASS |
| Chrome拡張 QA | PASS | Manifest V3、最小権限、同意、redaction、削除導線、ESLint PASS |
| Python依存監査 | PASS | 固定version 57依存、公式PyPI既知脆弱性0 |
| 動画用Node依存 | PASS | `adm-zip 0.6.0`へoverrideし、`npm audit`既知脆弱性0。HyperFrames check PASS |
| 提出動画 | PASS | 2:55、英語音声、72字幕cue、GPT-5.6 / Codex App Serverを明示、全編decode PASS |
| Devpost下書き | PASS | <https://devpost.com/software/eagleeye-browser-native-ai-qa-agent>、説明・技術・画像・private repo URLを設定済み |
| YouTube初回アップロード | REPLACE_REQUIRED | 公開・2:55・1080pだが、字幕なしmaster版であることをremote frame比較で確認 |
| Devpost最終送信 | BLOCKED | 字幕付きYouTube URLと居住国の入力待ち |

## 提出動画

- ローカル成果物: `videos/eagleeye-build-week/output/eagleeye-build-week-submission-en-captioned.mp4`
- 映像: 1920x1080、30fps、H.264
- 音声: AAC、48kHz stereo、ローカル音声エンジン
- 長さ: 175.018667秒（3分未満）
- SHA-256: `68DEC5780B95F20CD9F0E97DC51B18693B48AF8D152F1419480FF270A66EF6F1`
- 要件反映: `GPT-5.6 through Codex App Server` を音声と焼込み字幕の両方で確認
- 映像ソース検証: Runtime / Layout / Motion error 0、Contrast warning 2、総合check PASS

## YouTubeアップロード確認

- 確認URL: <https://youtu.be/bYC5OidwvJM>
- YouTubeメタデータ: public、2:55、1920x1080、age limit 0
- YouTube上の60秒フレームには焼込み字幕がない
- ローカル最終版の同時刻には `GPT-5.6 through Codex App Server expands the recorded` の焼込み字幕がある
- 判定: **REPLACE_REQUIRED**。`eagleeye-build-week-master-en.mp4`ではなく、`eagleeye-build-week-submission-en-captioned.mp4`を新規アップロードする
- 誤登録防止のため、当該URLはDevpostのvideo URLへ設定していない

## セキュリティ・プライバシー判定

技術監査は**条件付きPASS**です。EagleEyeはlocal-first、明示同意、入力値・Cookie・認証header・OTP・決済情報の非保持、URL redaction、任意スクリーンショット、端末内削除を実装しています。

商用・共有・remote運用では、運用者が保存期限、自動削除、controller/processor、法的根拠、DPA/DPIA、越境移転、incident response、強い認証、TLS、rate limit、暗号化backupを別途確定する必要があります。これは技術的適合性レビューであり、法的認証ではありません。

詳細: `reports/2026-07-18-nullx2-private-release-security-privacy.md`

## 残作業

1. 字幕付き最終MP4をYouTubeへ**Public**で新規アップロードし、公開URLをDevpostへ設定する。
2. GitHubのManage access画面で、2件目が `build-week-event@openai.com` 宛の読取専用招待であることを確認する。
3. Devpost必須項目のCountry of Residenceを本人回答で設定する。
4. Devpostの最終Submitを実行し、提出状態とURLを再確認する。

締切: 2026-07-22 09:00 JST。現在は締切前で、提出物本体は完成済みです。
