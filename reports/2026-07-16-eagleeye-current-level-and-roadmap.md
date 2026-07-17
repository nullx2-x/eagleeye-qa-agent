# EagleEye 現状到達レベル・次期方針レポート

- 作成日: 2026-07-16
- 対象: EagleEye AI-first QA Agent
- 現行バージョン: `0.4.0`
- 評価基準日: 2026-07-16 06:40 JST
- 対象範囲: EagleEye本体、REST API、MCP、ローカルPlaywright実行、AI誘導型ユーザーテスト、WordPress実運用検証
- 除外: 未接続の外部AIプロバイダーの本番認証、第三者環境での大規模負荷試験、商用SLA保証

## 1. エグゼクティブサマリー

EagleEyeは、単なるテストケース生成ツールではなく、**リスクに応じたテスト戦略生成から、実行前品質検査、ブラウザ実行、証跡保存、品質ゲート、失敗分析、人間承認付きユーザーテストまでを一連で扱えるQAオーケストレーター**に到達している。

総合評価は、5段階中 **レベル3「内部実運用ベータ」**、一部の中核機能はレベル4相当である。

| 評価軸 | 到達度 | 判定 |
|---|---:|---|
| QA戦略・リスク適応 | 4/5 | 実運用可能 |
| テストケース品質検査 | 4/5 | 実運用可能 |
| ローカルWeb自動実行 | 4/5 | 実運用可能 |
| 品質ゲート・証跡 | 4/5 | 実運用可能 |
| AI誘導型ユーザーテスト | 3/5 | 内部ベータ |
| MCP・他エージェント連携 | 3/5 | 内部ベータ |
| 外部AIプロバイダー連携 | 2/5 | 実装済み・実接続限定 |
| CI/CD・継続運用 | 2/5 | 未整備部分あり |
| 複数製品・大規模運用実績 | 2/5 | 実績不足 |
| 総合 | **3/5** | **内部実運用ベータ** |

結論として、EagleEyeはローカルまたは管理下環境でのQA運用に投入できる。ただし、現段階で「汎用の商用QA基盤」「自律的なリリース承認システム」と表現するのは早い。人間承認を保持したまま対象アダプターと運用実績を増やす段階である。

## 2. レベル定義

| レベル | 定義 |
|---|---|
| 1 | 構想。仕様や画面だけで、反復可能な実行がない |
| 2 | 技術試作。主要機能は動くが、統合・安全境界・証跡が不足 |
| 3 | 内部実運用ベータ。管理下の対象で一連の運用ができ、失敗も記録できる |
| 4 | 本番候補。複数対象、CI、監視、回帰、復旧手順、継続実績が揃う |
| 5 | 組織標準。SLA、権限分離、監査、スケール、長期実績が確立 |

EagleEyeをレベル3とする理由は、成功デモだけでなく、失敗実行、品質ゲートFAIL、証跡、再テスト方針まで実測できている一方、対象と運用期間がまだ限定されるためである。

## 3. 実装済み能力

### 3.1 リスク適応型QA戦略

- 開発段階、サービス種別、環境、変更ファイル、5つのリスク因子からテストプロファイルを生成する。
- 事業影響30%、データ機密性25%、変更複雑度15%、利用者影響20%、復旧困難度10%でリスクを評価する。
- 認証、権限、スキーマ、決済などの高影響変更ではstrict/full regressionを強制する。
- productionは常に`production_safe`へ固定し、書き込み・高負荷操作を禁止する。
- エミュレーターはfunctional / system / cycle / physicalの累積互換性プロファイルを持つ。

主要実装: `app/strategy.py`、`app/compatibility.py`、`profiles/default.yaml`

### 3.2 テストケース品質検査

- 曖昧な手順、assertion不足、固定wait、不安定selector、秘密値、重複、retry依存、必須種別不足を実行前に検出する。
- WordPressセキュリティ検査では、追加した5ケースを100点・問題0件として検査してから実行した。

主要実装: `app/test_case_checker.py`、`app/test_case_models.py`

### 3.3 自動実行・失敗分析・証跡

- Orbit Assist形式の操作記録を受け付け、localhost限定でPlaywrightを実行する。
- スクリーンショットと`result.json`をセッション単位で保存する。
- 未マスク入力、危険なセッションID、既定外の外部URL実行を拒否する。
- 失敗時はselector、timeout等を分類し、Codex向け修正ハンドオフを生成する。

主要実装: `app/runner.py`、`app/analyzer.py`、`app/security.py`、`app/storage.py`

### 3.4 品質ゲート

- PASS / PASS_WITH_WARNING / MANUAL_REVIEW / FAIL / BLOCKEDを判定する。
- Critical/High失敗、主要フロー失敗、必須テスト不足、互換性不一致、証跡不足、INFRA_ERROR、低成功率、strict時のFLAKYをリリース阻止要因として扱う。
- retry後の成功を通常PASSへ混ぜず、FLAKYとして分離する。

主要実装: `app/quality.py`

### 3.5 AI誘導型ユーザーテスト

- manual / telemetry / hybridシナリオを扱う。
- PREPARED → READY → ACTIVEの承認境界を持つ。
- runner固有attestationなしでは承認、再開、中断、人間判定を確定できない。
- exact/maxイベント回数、settle window、後発禁止イベントを監視できる。
- FAIL/BLOCKED時は失敗項目だけの再テストを準備する。
- 人間テストは自動リリース判断の代替にしない。

主要実装: `app/guided_service.py`、`app/guided_api.py`、`app/guided_ui.py`

### 3.6 API・MCP・AIプロバイダー

- RESTルートは本体21、guided router 16で、合計37ルートを実装している。
- MCP toolは15件を実装している。
- OpenAI、Anthropic、Gemini、Azure OpenAI、GitHub Models、Ollama、LM Studioの設定モデルを持つ。
- 秘密値はAPI応答へ返さず、OS資格情報保管を利用する設計である。
- 2026-07-16時点で実接続確認済みはOllamaのみ。その他は未設定である。

主要実装: `app/main.py`、`app/mcp_server.py`、`app/providers.py`、`app/ai_advisor.py`

## 4. 再検証結果

### 4.1 本体品質

| 検証 | 実測結果 |
|---|---|
| API health | `status=ok`、version `0.4.0` |
| pytest | **55件PASS**、0 FAIL、1件の依存ライブラリ非推奨警告 |
| ruff check | PASS |
| ruff format check | 32 files formatted / PASS |
| Python実装ファイル | 25件 |
| テストファイル | 7件 |
| RESTルート | 37件 |
| MCP tool | 15件 |
| 保存済みブラウザ実行証跡 | 7セッション |

唯一の警告はStarlette依存内の`python_multipart`移行に関するPendingDeprecationWarningで、EagleEye自身のテスト失敗ではない。ただし依存更新時の回帰候補として追跡する。

### 4.2 ブラウザ実行実績

`artifacts/runs/*/result.json`を再集計した結果は次のとおり。

| 結果 | 件数 | 注記 |
|---|---:|---|
| PASSED | 4 | 通常フロー、Orbit、WordPress運用E2Eを含む |
| FAILED | 3 | 意図的失敗証跡2件、WordPress初回timeout失敗1件 |
| 合計 | 7 | 全件にセッション別結果ファイルあり |

失敗が存在すること自体は成熟度低下ではない。失敗を成功扱いせず、errorと証跡を保存し、次の実行で修正結果を確認できている点を評価する。

### 4.3 WordPressでの実運用検証

運用E2Eでは、導入、ログイン、カテゴリ作成、公開トップ確認を10,032msで完了し、ケース品質100点、品質ゲートPASSとなった。

別のproduction_safeセキュリティ・運用検査では、リスク73/100、5ケース中2 PASS・3 FAIL、成功率40%、品質ゲートFAILを正しく返した。未認証ユーザー列挙、古いWordPress、セキュリティヘッダー欠落等を検出し、DB非公開、コアチェックサム、WP_DEBUG、コンテナ健全性等の合格事項と分離できた。

この実績により、EagleEyeは「正常系を通すだけのデモ」ではなく、実対象の脆弱な運用状態をリリース非推奨として止められる段階にある。

## 5. 現時点でできること・できないこと

### できること

- 対象の段階・変更・リスクから安全側のテスト計画を生成する。
- テストケースを実行前に品質検査し、危険・曖昧・不足を止める。
- localhostのWeb操作をPlaywrightで実行し、結果と画像を保存する。
- 正常、失敗、FLAKY、BLOCKED、INFRA_ERRORを分離して品質判定する。
- production対象を読み取り専用へ強制する。
- WordPressの運用フローと非破壊セキュリティ検査を一連で管理する。
- 人間承認付きのguided QAを準備・誘導・記録し、失敗項目だけ再テストする。
- REST、MCP、Codex Skillから計画・検査・証跡参照を利用する。

### まだ限定的なこと

- Playwright実行アダプターは主に記録済みWeb操作向けで、API、モバイル、デスクトップ、バッチの実行器は共通化途上である。
- Chromium以外の継続的な実ブラウザ互換試験実績がない。
- 外部AIプロバイダーは認証実装と単体試験が中心で、現行環境の実接続はOllamaのみである。
- guided QAは契約・状態機械・安全境界のテストが厚い一方、複数の実ユーザーによる継続運用実績が不足する。
- CI/CDで全変更を自動評価するパイプライン、長期履歴ダッシュボード、SLA、バックアップ・復旧演習が未整備である。
- 大規模並列、長時間soak、障害注入、ネットワーク劣化条件での実測がない。
- コードカバレッジ率は今回計測していないため、55 PASSを網羅性100%とは解釈しない。
- EagleEye本体ディレクトリはGitリポジトリとして初期化されておらず、変更履歴・レビュー・リリースタグの統制が弱い。

## 6. 次の方針

### 方針A: 「機能追加」より先に運用基盤を固める

次段階の最優先は、機能数を増やすことではなく、再現性、履歴、回帰、復旧性を上げることである。

受入基準:

- Git管理、バージョンタグ、CHANGELOG、レビュー手順を導入する。
- Windows起動後にAPI/MCPのhealthと主要smokeを自動確認する。
- pytest、ruff、format、主要E2EをCI相当の単一コマンドで再現可能にする。
- データ、証跡、guided sessionのバックアップと復元試験を1回以上成功させる。
- 依存ライブラリ警告をゼロまたは追跡チケット付きにする。

### 方針B: 対象別アダプターを明示的に分離する

EagleEyeコアへ製品固有処理を埋め込まず、Web、API、WordPress、デスクトップ、エミュレーター等をアダプターとして分離する。

受入基準:

- 共通のnormalized result schemaを全アダプターで使用する。
- 各アダプターが対応操作、禁止操作、証跡形式、timeout、cleanupを宣言する。
- production_safe時は各アダプターが書き込みを技術的に拒否する。
- WordPress検査を再利用可能アダプター化し、同一ケースで修正前FAIL・修正後PASSを再現する。

### 方針C: 品質ゲートを運用判断の中心に置く

AIの文章評価ではなく、決定論的な品質ゲートを最終判断の中心に維持する。AIは候補追加、要約、異常兆候、修正案に限定する。

指針:

- AIは必須テストを削除しない。
- retry-passはFLAKYのまま扱う。
- 証跡不備はPASSにしない。
- Critical/High失敗、主要フロー失敗、INFRA_ERRORは自動リリースを止める。
- guided QAの人間判定をAIやMCPが代行しない。

### 方針D: 実運用対象を3種類へ増やす

WordPressだけで成熟度を判断せず、性質の異なる3対象で継続運用する。

推奨対象:

1. Web/CMS: WordPressの修正・再検査
2. API/業務: 認証、権限、schema、障害系を含むサービス
3. AI/agentまたはemulator: 決定論的oracle、replay、mismatch、証跡SHA-256を要求する対象

受入基準:

- 各対象で最低10回の継続実行を行う。
- PASS、FAIL、BLOCKED、FLAKY、INFRA_ERRORの分類が意図どおりである。
- 誤検知・見逃し・再現不能を記録し、改善前後を比較する。
- Report Hubへ全結果を提出し、時系列で追跡できる。

### 方針E: レベル4昇格条件を数値化する

次の全条件を満たした時点で「本番候補 レベル4」へ昇格する。

- 3種類以上の対象で各10回以上、合計30回以上の運用実績
- CI相当の品質チェックが連続20回成功
- Criticalな安全境界テスト100% PASS
- production_safeの書き込み事故0件
- 証跡欠損0件、秘密値漏えい0件
- 既知FLAKYを全件追跡し、strict/release gateへ混入0件
- バックアップ復元試験PASS
- Windows再起動後のAPI/MCP自動復旧・health確認PASS
- 実ユーザーguided QAを最低5セッション実施し、人間承認境界違反0件

## 7. 直近の実行計画

### 優先度P0

1. EagleEye本体をGit管理し、現行`0.4.0`を基準タグ化する。
2. WordPressの検出事項を修正し、同じproduction_safeケースで再検査する。
3. API/MCP/主要E2E/Report Hub提出をまとめた運用smokeを作る。
4. 証跡・guided dataのバックアップと復元手順を作り、実際に復元する。

### 優先度P1

1. WordPress検査を汎用アダプターへ分離する。
2. Firefox/WebKitを含むブラウザ互換マトリクスを追加する。
3. APIサービス向けadapterとschema/permission regressionを追加する。
4. 実ユーザーによるguided QAを5セッション実施する。

### 優先度P2

1. 外部AIプロバイダーを必要性順に実接続検証する。
2. 長時間soak、並列、ネットワーク劣化、サービス再起動時の回復性を測定する。
3. Report Hubで対象別・状態別・期間別の品質推移を可視化する。

## 8. 失敗と修正の履歴から得た指針

- WordPress初回実行は102,381msでtimeout失敗したが、timeout条件を調整した次の実行は10,032msでPASSした。再試行で成功した事実と初回失敗は分離して保存されている。
- セキュリティ検査では、運用E2EがPASSでも安全性ゲートはFAILになった。機能正常とセキュリティ適合を別ゲートにする方針は維持すべきである。
- MCPの単純GETはHTTP 406であり、これはStreamable HTTP MCPの要求形式と異なるアクセスである。APIプロセスの稼働だけでMCP tool全件の実呼出し成功を意味しないため、今後はMCP smokeを明示的に追加する。

## 9. 証拠台帳

| 主張 | 一次証拠 | 種別 | 注意点 |
|---|---|---|---|
| 本体55テストPASS | 2026-07-16実行の`pytest -q` | measured | coverage率は未計測 |
| lint/format PASS | 2026-07-16実行のruff check/format | measured | 静的品質のみ |
| API version 0.4.0稼働 | `GET http://127.0.0.1:8766/health` | measured | ローカル環境 |
| REST 37ルート | `app/main.py`、`app/guided_api.py` | implementation | UI routeを含む |
| MCP tool 15件 | `app/mcp_server.py` | implementation | 全toolのlive smokeは未実施 |
| guided承認境界 | `app/guided_service.py`、`tests/test_guided_qa.py` | implementation/measured | 実ユーザー実績は限定的 |
| ブラウザ実行4 PASS/3 FAIL | `artifacts/runs/*/result.json` | measured | 7セッションの小標本 |
| WordPress運用E2E PASS | WordPress検証レポート（ローカル管理下） | measured | ローカルDocker対象 |
| WordPress安全性ゲートFAIL | WordPress安全性検証レポート（ローカル管理下） | measured | 非破壊検査 |
| 外部AIはOllamaのみ接続 | `GET /api/v1/ai/providers` | measured | 2026-07-16時点 |

## 10. 再現コマンド

```powershell
cd <project-root>
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
Invoke-RestMethod http://127.0.0.1:8766/health
Invoke-RestMethod http://127.0.0.1:8766/api/v1/ai/providers
```

## 11. 最終判断

EagleEyeは、**管理下の対象で実際に使えるQAオーケストレーター**であり、現状は内部実運用ベータである。次に必要なのは派手な機能追加ではなく、対象アダプターの標準化、CI、復旧、継続実績、実ユーザー検証である。

次期開発では、品質ゲートと人間承認境界を絶対に弱めず、30回以上の複数対象運用実績を積んだうえでレベル4への昇格を判断する。
