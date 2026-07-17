# EagleEye Build Week 英語音声・字幕付き提出動画レポート

- 実施日: 2026-07-17 (JST)
- 対象: EagleEye Build Week 2分55秒デモ
- 判定: `PASS`
- 未実施の外部操作: 公開動画アップロード、公開URL設定、Devpost送信

## 結果

ローカル音声エンジンKokoro-82Mの`af_nova`で英語AIナレーションを生成し、10シーンの既存HyperFrames動画へ統合した。ローカルFaster-Whisperの単語時刻から72個の英語字幕cueを作成し、提出用MP4へ焼き込んだ。SRT/VTT sidecarも保持している。BGMは使用していない。

## 最終提出候補

- ファイル: `videos/eagleeye-build-week/output/eagleeye-build-week-submission-en-captioned.mp4`
- 映像: H.264 / 1920x1080 / 30fps / yuv420p
- 音声: AAC / 48kHz / stereo
- 長さ: 175.018667秒（2分55秒、3分未満）
- サイズ: 22,285,370 bytes
- SHA-256: `B4E9B44131C666AF8C2E1EECBD9BEB900FCD2CBB062AAB3CBD1B9C083D1534B4`
- 最終音声: -16.2 LUFS / True Peak -4.4 dBTP / LRA 4.8 LU

## 生成物

- ナレーション原稿: `videos/eagleeye-build-week/audio_request.json`
- シーン別音声と文字起こし証跡: `videos/eagleeye-build-week/assets/voice/`, `audio_meta.json`
- タイムライン統合音声: `videos/eagleeye-build-week/assets/audio/narration-en.m4a`
- 字幕データ: `videos/eagleeye-build-week/captions-en.json`
- 字幕sidecar: `videos/eagleeye-build-week/assets/captions/eagleeye-build-week.en.srt`, `.vtt`
- 音声トラック統合: `videos/eagleeye-build-week/index.html`

## 検証

- HyperFrames CLI: `0.7.60`（latestと一致）
- HyperFrames lint: error 0 / warning 267 / info 15
- HyperFrames check: `PASS`
  - runtime finding 0
  - motion finding 0
  - contrast finding 0
  - layoutは既存演出由来のinfo 4件のみ
- 高品質render: `PASS`、5,250 frames、175秒
- 最終MP4全編デコード: `PASS`
- 音声クリップ: 10/10生成成功、合計132.203秒
- 音声原稿との文字起こし一致率: 最小0.8993、最大1.0000
- 字幕: JSON/SRT/VTT各72 cue、時刻逆転・cue重複0
- 最終接触シート: 全10シーンで字幕の表示、位置、コントラストを目視確認
- `git diff --check`: `PASS`
- Gitleaks 8.30.1 staged scan: leak 0
- 個人名、個人ディレクトリパス、API key、password、token、private key形状: 新規提出素材で0件

## 修復履歴

1. 初回Kokoro実行は`kokoro-onnx`未導入で失敗したため、`.runtime`配下の分離Python環境へ依存を導入した。
2. HyperFrames内蔵文字起こしはWindows上で`whisper_unavailable`だったため、Faster-Whisper `small.en` CPU int8へ切り替えた。音声を外部APIへ送信していない。
3. 初回FFmpegミックスのPowerShellラベル解釈エラーを修正した。
4. `amix`既定正規化によるLRA 17.6 LUを検出し、`normalize=0`と二段階loudnormでLRA 4.9 LUへ改善した。

## 残存事項

- 公開アップロードとDevpost設定は本作業の範囲外として未実施。ローカル提出候補の完成判定には影響しない。
- レンダー済みMP4はリポジトリの`output/`除外規則に従いGit管理対象外。音声素材、字幕、原稿、HyperFrames統合sourceはprivate repositoryへ保存する。
- 既存HyperFrames warning 267件は主に数字始まりIDと大きいsub-composition fileで、今回追加した音声トラック由来の新規warningはない。

## AI音声開示

英語ナレーションはKokoro-82Mでローカル生成したAI音声である。この開示は`THIRD_PARTY_NOTICES.md`、デモ台本、Devpost draftにも反映した。
