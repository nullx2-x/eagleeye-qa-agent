# EagleEye 不足機能改修・運用強化レポート

- 実施日: 2026-07-16
- 対象: EagleEye AI-first QA Agent
- 更新前: 0.4.0 / 内部実運用ベータ
- 更新後: **0.6.0 / レベル4候補**
- EagleEye profile: `<redacted-profile-id>`
- strict full gate: **PASS / 17 of 17 / 100%**

## 結論

現状評価で不足していたP0運用基盤と、機械的に解消可能なP1/P2項目を実装した。API/MCP/ブラウザ/Report Hubの運用スモーク、証跡バックアップ復元、ログオン自己復旧、Git/タグ/CI定義、3ブラウザ互換、bounded performance、固定AI安全eval、コードrollback drillまで実測PASSとなった。

技術機能はレベル4候補へ到達した。ただし、レベル4正式昇格に必要な「3対象・合計30回」「実ユーザーguided QA 5回」「長時間soak」「外部AI実接続」は継続運用実績であり、未達として残す。

## 実装内容

### 1. 単一品質ゲート

`scripts/quality-gate.ps1`で以下を一括実行する。

- pytest
- ruff check / format check
- API、MCP、実Chromium、Report Hubスモーク
- Chromium / Firefox / WebKit互換スモーク
- bounded performance benchmark
- 固定AI安全eval
- runtimeバックアップ作成とsandbox復元

### 2. 正規MCPスモーク

Streamable HTTP MCP clientでinitialize、tool list、`eagleeye_status`呼出しを実行する。単純なGET/port確認ではなく、15ツールの存在と実tool callを検証する。

### 3. バックアップ・復元

- allowlist対象のみ保存
- token / secret / credential名を除外
- active SQLiteはbackup APIで一貫したsnapshotを取得
- manifestにファイル別SHA-256とsizeを保存
- ZIP path traversalを拒否
- live領域を上書きせずsandboxへ復元

最新実測は48エントリ、archive SHA-256 `55705166253dc3f0690116014422e2e0e9ea71a9d7620bb97ceceb4456971036`、復元PASS。

### 4. Windowsログオン自己復旧

Scheduled Task `EagleEye_StartupHealth`を登録した。ログオン時にAPI/MCPを必要時のみ復旧し、API、MCP、Report Hubを検査して`.runtime/startup-health/latest.json`へ保存する。

実行結果: `LastTaskResult=0`、attempt 1、EagleEye 0.6.0、MCP 15 tools、Report Hub 200。

### 5. Git・バージョン・CI基盤

- local Git repositoryを`main`で初期化
- `v0.5.0`と`v0.6.0`のannotated tag
- VERSION / CHANGELOG / pyproject / API versionを同期
- GitHub Actions用offline deterministic quality定義を追加
- `.env`、runtime、Playwright一時ログ、生成プロファイル、バックアップZIPを除外
- commit候補の秘密情報scanはCLEAN

GitHubへのpush・外部公開は行っていない。

### 6. AI安全eval

固定8ケースで次を検査する。

- required test削除指示
- safety restriction弱体化指示
- production自動承認指示
- token/API key露出指示
- infinite/unbounded loop指示
- 不正なtest名
- 重複test
- 正常なtest追加

AI追加はslug形式・重複なし・最大30件に制限し、required testsとrestrictionsのpost-condition違反時は元へ戻す。

### 7. 互換性・性能・rollback

- Chromium / Firefox / WebKit: 3/3 PASS、HTTP 200
- benchmark: 200 samples、concurrency 10、failure 0、145.27 req/s、p95 199.5ms（基準250ms以下）
- rollback: `v0.5.0`をsandboxへ復元、VERSION 0.5.0、Python compile PASS

## 検証結果

| 項目 | 結果 |
|---|---|
| pytest | 62 PASS / 0 FAIL |
| ruff check | PASS |
| ruff format | 42 files PASS |
| API | healthy / 0.6.0 |
| MCP | initialize PASS / 15 tools / status call PASS |
| 実Chromium | PASS |
| Firefox | PASS |
| WebKit | PASS |
| Report Hub | HTTP 200 / healthy |
| AI safety eval | 8/8 PASS |
| benchmark | 200/200成功、p95 199.5ms |
| runtime restore | 48 entries PASS |
| code rollback | v0.5.0 sandbox restore PASS |
| startup task | LastTaskResult 0 |
| EagleEye P0 scoped gate | 5/5 PASS |
| EagleEye strict full gate | **17/17 PASS** |

## 残存課題

1. 3種類以上の実対象で各10回、合計30回以上の継続実績
2. 実ユーザーguided QA 5セッション
3. 数時間単位のsoak、障害注入、ネットワーク劣化試験
4. Ollama以外の外部AIプロバイダー実接続
5. GitHubへpush後の実CI実行20回
6. Starlette依存の`python_multipart` PendingDeprecationWarning解消

これらは外部資格情報、人間操作、長期実行、公開先を必要とするため、今回のローカル実装だけで達成済みとは扱わない。

## 主要成果物

- `scripts/quality-gate.ps1`
- `scripts/operational_smoke.py`
- `scripts/browser_matrix.py`
- `scripts/operational_benchmark.py`
- `scripts/run_ai_safety_evals.py`
- `scripts/runtime_backup.py`
- `scripts/rollback_drill.py`
- `scripts/startup-health.ps1`
- `app/ai_safety_eval.py`
- `evals/ai-safety-cases.json`
- `.runtime/quality-gate/latest.json`
- `.runtime/full-readiness-gate.json`

## 次の指針

- 直近は新機能追加より、実対象3種類での反復運用を優先する。
- strict gate 17項目を今後も削減しない。
- performance-soak、cross-browser-extended、red-team evaluationは通常ゲートと分離し、夜間・定期実行へ移す。
- 外部AIは必要性が確定したproviderから1つずつ接続し、秘密値をAPI・ログ・Report Hubへ出さない。
- レベル4正式昇格は運用回数と事故0件の基準達成後に判断する。
