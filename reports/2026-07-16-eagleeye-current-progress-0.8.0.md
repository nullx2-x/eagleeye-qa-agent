# EagleEye 現在進捗レポート — 0.8.0

- 確認日: 2026-07-16
- 対象: EagleEye AI-first QA Agent
- 現行ローカルバージョン: 0.8.0
- 総合状態: **PARTIAL / 技術レベル4候補を維持**
- 評価方法: 稼働API、MCP実呼出し、実ブラウザ、pytest、ruff、Git、プロバイダー状態、既存証跡を再確認

## 1. エグゼクティブサマリー

EagleEyeは、リスク適応テスト戦略、品質ゲート、ブラウザ実行、証跡管理、AI誘導型ユーザーテスト、MCPに加え、Codex App Server管理のChatGPT OAuth、構造化Codex turn、動画証跡、固定desktop adapter、限定自己修復まで実装済みである。

現在稼働中のAPIは0.8.0でhealthy、MCP 15ツールと実ChromiumはPASS、Codex AgentはApp Server経由でconnected、pytestは123件PASSである。一方、0.8.0に対する統合full-readiness gateの再実行証跡がなく、ruff format checkでは16ファイルが未整形、ローカルGitはリモートより1コミット先行している。このため、実装完了ではなく**リリース整備中のPARTIAL**と判定する。

## 2. 現在確認できた状態

| 評価項目 | 現在値 | 判定 | 証拠種別 |
|---|---|---|---|
| API | healthy / version 0.8.0 | PASS | 2026-07-16 live |
| MCP | initialize・status call成功 / 15 tools / 欠損0 | PASS | 2026-07-16 live |
| ダッシュボード | Chromium HTTP 200 / EagleEye表示 | PASS | 2026-07-16 live |
| Codex Agent | connected / configured / App Server ChatGPT認証 | PASS | 2026-07-16 live |
| Ollama | connected / configured | PASS | 2026-07-16 live |
| OpenAI APIほか外部provider | 未接続 | NOT CONFIGURED | 2026-07-16 live |
| pytest | 123 PASS / 0 FAIL / 1依存警告 | PASS | 2026-07-16 live |
| ruff check | 問題0 | PASS | 2026-07-16 live |
| ruff format check | 16 files would be reformatted | **未達** | 2026-07-16 live |
| Git作業ツリー | tracked変更なし | PASS | 2026-07-16 live |
| Git同期 | local `cc1617e`、origin/mainは`4a42755` | **ahead 1** | 2026-07-16 live |
| GitHub | private / default branch main | PASS | GitHub live |
| 旧full readiness | 17/17 PASS | 参考のみ | 0.6系時点の既存証跡 |

## 3. 0.8.0で進んだ機能

### 3.1 Codex App Server統合

- Codex App ServerへJSONL接続し、ChatGPT管理OAuthの状態確認、ログイン開始・取消、ログアウトを委譲する。
- EagleEyeはアクセストークンやAPIキーを受領・保存しない。
- Codex turnは構造化schema、read-only、approval拒否を基本境界とする。
- 現在のprovider状態は`codex-agent / connected=true / credentialKind=app_server_chatgpt`。

### 3.2 動画・画像証跡

- Playwright実行でスクリーンショットとWebMを保存できる。
- SHA-256、byte数、MIME、取得時刻、取得元を証跡へ付与する。
- Circuit Forge Studio実測ではdesktop run PASS、画像4件、WebM 1件を取得済み。

### 3.3 固定desktop adapter

- 呼出側が任意commandやpathを渡せず、固定レジストリのtarget IDだけを起動する。
- 現在登録済みのdesktop targetは`circuit-forge-studio`の1件。
- `shell=False`、最小環境、root confinement、timeout時process tree終了、ログの秘密値マスクを実装した。

### 3.4 限定自己修復

- 現在enabledだが、local・非productionだけに限定される。
- 許可能力は`codex-agent`のexact allowlistモデルのみ。
- clean Git、fresh one-use attestation、request binding、固定検証、checkpoint rollbackを要求する。
- 上限は2 attempts、5 files、200 changed lines、256 KiB。
- secrets、認証、依存関係、binary、hardware net、policy自己改変を対象外とする。

### 3.5 セキュリティ強化

- Chrome拡張Originの明示allowlist、Host・unsafe-method Origin検証、security headerを追加した。
- desktop logでJWT、GitHub token、AWS access key、URL query認証値を保存前にマスクする。
- 自己修復attestationの偽造、再利用、別requestへの転用を拒否する試験を追加した。

## 4. 実績と成熟度

現段階は、単一のWeb QAデモを超え、Web、MCP、Codex Agent、desktop対象、動画証跡、限定修復まで統合された状態である。技術機能は引き続きレベル4候補に相当する。

ただし正式なレベル4判定には、0.8.0での統合ゲート再認定に加え、複数対象の継続実行、実ユーザーguided QA、長時間soak、障害注入、証跡保持方針、共有環境向け認証境界が必要である。現在のローカルREST APIは同一Windowsユーザー配下を信頼境界としており、LAN・共有ホストへ直接公開できる完成度ではない。

## 5. 未完了事項・リスク

### P0 — リリース前に必要

1. 16ファイルをruff formatし、pytest・ruff・運用smoke・3ブラウザ・性能・AI safety・backup restoreを再実行する。
2. 0.8.0用のfull-readiness gateを新規実行し、過去0.6の17/17証跡を置き換える。
3. 秘密情報・ローカルパスを再監査後、先行コミット`cc1617e`をprivate originへpushし、0.8.0 tagを作成する。

### P1 — 運用投入前に必要

1. LAN・共有ホスト・Raspberry Pi経由で利用する前に、認証付きgatewayと利用者別監査を追加する。
2. 動画に映り得るPIIの保存期間、閲覧権限、削除、暗号化方針を決める。
3. 実対象3種類で各10回、合計30回の継続実行と、guided QA 5セッションを完了する。
4. 数時間単位のsoak、プロセス再起動、ネットワーク劣化、障害注入を実施する。

### 外部ブロッカー

- GB-N64ダンパー拡張adapterは設計・validator・ERCまで進んだが、実機同定情報不足のため製造・通電を停止中。
- 必要情報は本体・PCBの鮮明な表裏写真、型番・revision、controller、firmware hash、挿入方向、接点面、pitch、基板厚、無負荷電圧、logic analyzer trace。

## 6. 次の実行順序

1. format修正と0.8.0統合品質ゲート
2. current commitの安全監査、private remote push、v0.8.0 tag
3. 認証gatewayと動画保持ポリシー
4. 30回運用・guided QA 5回・soak/障害試験
5. 実機情報取得後にGB adapter設計を再開

## 7. 証拠索引

- live operational smoke: API 0.8.0、MCP 15 tools、Chromium PASS
- live pytest: 123 PASS、1 dependency warning
- live ruff: check PASS、format 16 files未達
- live provider status: Codex App Server ChatGPT connected、Ollama connected
- Git: local `cc1617e`、origin/main `4a42755`、private remote
- `.runtime/full-readiness-gate.json`: 旧17/17 PASS証跡。0.8.0再認定には未使用
- `reports/2026-07-16-eagleeye-oauth-video-self-repair-circuit-forge-gb-adapter.md`: 0.8.0追加機能と実対象証跡

## 8. 最終判断

EagleEye 0.8.0は主要機能が実装・稼働しており、Codex App Serverを含むAI-first QA基盤として大きく前進した。現在の阻害要因は中核機能不足ではなく、最新版の品質ゲート再認定、整形・リモート同期、共有利用時の認証、運用回数と長時間実績である。次の判断点は、0.8.0の統合品質ゲートを全てPASSさせた時点とする。
