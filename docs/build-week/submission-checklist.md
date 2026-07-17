# OpenAI Build Week 提出チェックリスト - Phase 1-9

## 運用ルール

これはEagleEye内部の提出準備Phaseであり、公式審査基準を推測して置き換えるものではない。1項目でも証跡がなければ完了扱いにしない。

機械判定用ステータスは次の6種類に固定する。

- `PASS`: 現在の成果物と実行証跡で合格
- `FAIL`: 実行したが受入条件を満たさない
- `IN_PROGRESS`: 実装または統合中
- `BLOCKED`: 前提成果物がなく実行不能
- `NOT_RUN`: 実装はあるが現在スナップショットで未実行
- `TBD`: 外部URL・媒体・担当などが未確定

チェックボックスは `PASS` のときだけ `[x]` にする。コードが存在するだけ、過去版で通っただけ、画面案があるだけでは `[x]` にしない。

## 現在スナップショット

- 基準日: `2026-07-17`
- 基準バージョン: `1.0.0`
- 基準コミット: `cc1617e` 上の並行作業ツリー
- 全体判定: `PARTIAL`（ローカル提出候補は完成。外部公開・最終送信は承認待ち）
- 公開GitHub: `TBD`（ユーザー承認後にpublic化）
- 公開URL: `TBD`（local-firstを採用し、公開URLを実装済みとは主張しない）
- 動画URL: `TBD`（2:55ローカル最終候補は完成。公開uploadだけ未実施）
- スクリーンショット: `PASS`（実画面6枚 + Architecture図1枚）

| Phase | 判定 | 主な未達 |
|---|---|---|
| 1. Story | PASS | なし |
| 2. Legal and repository | IN_PROGRESS | 公開予定履歴の最終監査とpublic化承認 |
| 3. Reproducible quality | PASS | local全ゲートとprivate pre-release Windows/Linux CIがPASS |
| 4. Chrome extension | PASS | なし |
| 5. Safe observation | PASS | なし |
| 6. OpenAI generation | PASS | なし |
| 7. Replay and evidence | PASS | controlled failure fixtureは任意の将来項目 |
| 8. Fix and sharing | PASS | local HTML/Markdownのみ。公開ホスティングは主張しない |
| 9. Submission release | IN_PROGRESS | 動画の公開upload、公開URL、Devpost送信の承認ゲート |

## Phase 1 - 問題、価値、勝ち筋

- [x] `P1-01 | PASS` 一文の価値提案がArchitectureとDevpostで一致している。
  証跡: `docs/build-week/architecture.md`, `docs/build-week/devpost-draft.md`
- [x] `P1-02 | PASS` 勝ち筋が次の順で固定されている。
  `Chrome拡張ON -> 通常操作 -> DOM/画面/履歴解析 -> AIテスト生成 -> Replay -> 修正提案 -> 共有`
- [x] `P1-03 | PASS` 2:30-3:00の時間制約を満たす2:55の台本があり、各区間も指定上限以下である。
  証跡: `docs/build-week/demo-script.md`
- [x] `P1-04 | PASS` 実装済み、統合中、未実装、TBDを文書内で分離している。

## Phase 2 - LICENSE、リポジトリ、公開可能性

- [x] `P2-01 | PASS` MIT Licenseが存在し、`2026 EagleEye contributors` と記載されている。
  検査: `Get-Content -Raw LICENSE`
- [x] `P2-02 | PASS` Windows/LinuxのCI定義が存在し、`pytest`、`ruff check`、`ruff format --check` を実行する。
  検査: `Get-Content -Raw .github/workflows/ci.yml`
- [x] `P2-03 | PASS` Python依存はApache/BSD/ISC/MIT/MPL/PSF系で禁止・不明ライセンス0件。3つのGitHub ActionsはMITを確認し、mutable major tagではなく確認済みcommit SHAへpinした。
  証跡: `pip-licenses`、`pip-audit`、`.github/workflows/ci.yml`
- [ ] `P2-04 | TBD` 公開GitHub URLを確定する。
  合格条件: 未認証ブラウザでURLが閲覧でき、default branchに提出commitが存在
- [x] `P2-05 | PASS` gitleaks `8.30.1`で公開候補160ファイルと提出commitを含む全12 commitを`--redact`検査し、未解決finding 0件。synthetic redaction fixtureは静的連結を避け、過去commitの3 fingerprintだけを限定allowlistした。
  手順: `docs/build-week/publication-security.md`

## Phase 3 - 再現可能なセットアップと品質ゲート

- [x] `P3-01 | PASS` Python要件、`pyproject.toml`、`uv.lock`、READMEセットアップ手順が存在する。
- [x] `P3-02 | PASS` locked dependency syncが成功した。
  実行: `uv sync --locked --dev`
  証跡: exit code `0`、`Resolved 59 packages`、lockfile変更なし
- [x] `P3-03 | PASS` 全pytestが成功した。
  実行: `uv run pytest -q`
  証跡: `138 passed, 1 warning`、failed/error `0`
- [x] `P3-04 | PASS` Ruff lintが成功した。
  実行: `uv run ruff check .`
  証跡: `All checks passed!`
- [x] `P3-05 | PASS` Ruff format checkが成功した。
  実行: `uv run ruff format --check .`
  証跡: exit code `0`、`64 files already formatted`
- [x] `P3-06 | PASS` private pre-release GitHub Actionsで同一commitのWindows/Linux両jobがgreen。private URLは公開資料へ記載しない。
- [x] `P3-07 | PASS` 両jobの最終stepが`git status --porcelain`を検査し、CIコマンド実行後もcleanで成功した。

## Phase 4 - Chrome拡張 ON/OFF と最小権限

- [x] `P4-01 | PASS` Chrome拡張source、`manifest.json`、install手順、version `1.0.0` が存在し、static verifierが成功した。
- [x] `P4-02 | PASS` fresh unpacked Chromiumで、明示ON前のsession deltaは`0`、実ショートカットON後だけobservationが`4`へ増加した。
- [x] `P4-03 | PASS` popupにON/OFF、session識別子、観測数を表示し、実画面スクリーンショットへ記録した。
  証跡: `docs/build-week/screenshots/02-extension-recording.png`
- [x] `P4-04 | PASS` permissionsとhost permissionsのstatic検査が必要最小限で成功した。
  証跡: Manifest V3、`activeTab/scripting/storage`、loopback hostのみ、remote code/`eval`なし
- [x] `P4-05 | PASS` 拡張Originは固定IDの完全一致allowlistで、wildcardを拒否する。
  証跡: extension verifierとPython test PASS。公開レポートでは拡張IDの値を非表示
- [x] `P4-06 | PASS` 拡張JavaScriptのESLintが成功した。
  実行: `npx --yes eslint@9 .\background.js .\content.js .\popup.js .\tests\verify-extension.mjs`

## Phase 5 - DOM、画面、操作履歴の安全な解析

- [x] `P5-01 | PASS` browser-agent routerがFastAPIへmountされ、全10 routeを列挙できる。
  証跡: route introspection PASS、API unit test PASS
- [x] `P5-02 | PASS` 同一sessionでsafe DOM summary、visible screenshot、action historyを実Chromium上で取得した。
  証跡: 公開run IDはマスク済み、observations `4`
- [x] `P5-03 | PASS` raw入力値をイベントschemaへ持たず、保存前sanitizerと負例testが成功した。
- [x] `P5-04 | PASS` password/OTP/card/secret型、secret query、fragment、cross-origin遷移を拒否または除去するunit + integrated API testが成功した。
  コード根拠: `app/browser_agent.py`, `app/security.py`
- [x] `P5-05 | PASS` screenshotの型・3 MiB上限、保存先confinement、HTML escapeについて正常系とoversize/path/XSS負例testが成功した。

## Phase 6 - OpenAIによるテスト生成

- [x] `P6-01 | PASS` Codex App Server providerのcore実装とunit testが存在する。
  コード根拠: `app/codex_app_server.py`, `app/codex_agent.py`, provider tests
- [x] `P6-02 | PASS` browser sessionからschema-validなAIケースを生成するrouteがmountされ、mocked structured outputのunit testが成功した。
  注意: live OpenAI証跡は`P6-03`で別判定
- [x] `P6-03 | PASS` live WordPress demoでprovider `codex-agent`、model `gpt-5.6-terra`、available `true`、fallbackUsed `false`を画面とJSONへ記録した。
- [x] `P6-04 | PASS` AIケースを実行前checkerへ通し、critical/highケースを候補から除外するunit test経路が成功した。
- [x] `P6-05 | PASS` OpenAI停止・timeout時もrecorded caseを失わない。
  証跡: `REC-001` runnable、fallback明示のunit test PASS
- [x] `P6-06 | PASS` prompt builder testでraw入力、secret query、credential、不要な全文DOMを含まず、safe summaryだけを渡すことを確認した。

## Phase 7 - Replayと証跡

- [x] `P7-01 | PASS` localhost既定のPlaywright runnerが存在する。
  コード根拠: `app/runner.py`, `app/security.py`
- [x] `P7-02 | PASS` browser sessionからReplay endpointを呼び、`passed`、`1,745 ms`、現在runの結果を取得した。
- [x] `P7-03 | PASS` core runnerがスクリーンショット/動画のSHA-256、byte数、MIME、時刻、取得元を扱う。
- [x] `P7-04 | PASS` extension起点のfresh Replayでscreenshot `103,299` bytesとWebM `112,935` bytesを保存し、表示SHA-256とartifact metadataが一致した。
  証跡: `docs/build-week/evidence/extension-wordpress-e2e.json`
- [ ] `P7-05 | NOT_RUN` 制御されたlocal regression fixtureを用意し、失敗を再現できる。
  合格条件: fixture手順、期待failure、reset手順が追跡済み
- [x] `P7-06 | PASS` Replayはrecorded runnable caseだけを実行し、AI生成ケースは候補として表示する。critical/highの不適切候補をdropするtestが成功した。

## Phase 8 - 修正提案、レポート、共有

- [x] `P8-01 | PASS` coreにfailure analysisとCodex handoffがあり、適用に承認を要求する。
- [x] `P8-02 | PASS` bounded self-repair policyがlocal/non-production、clean Git、fresh attestation、model allowlist、変更上限でfail closedする。
- [x] `P8-03 | PASS` browser reportにrecorded/AIケース、provider/model、quality、Replay、evidence、fix suggestionを同一sessionで表示した。
- [x] `P8-04 | PASS` report内のuntrusted文字列をescapeし、秘密値と絶対ローカルpathを再表示しないXSS/secret負例testが成功した。
- [x] `P8-05 | PASS` 共有は明示的な`Markdown bug report`取得だけで発生し、自動uploadしない。
  境界: 認証・期限・失効・削除を要するpublic hostingは未実装として明示し、local exportと混同しない。
- [ ] `P8-06 | NOT_RUN` public product URLは採用していない。Devpostにはlocal-first Quick Startを正確に記載し、公開GitHubから再現する。

## Phase 9 - 提出release

- [x] `P9-01 | PASS` Architecture、2:55 demo script、Devpost draft、Phase checklist、publication security procedureが存在する。
- [x] `P9-01V | PASS` 2:55のローカル最終動画を英語AIナレーション、焼き込み英語字幕72 cue、SRT/VTT sidecar付きでrenderし、1920x1080、30fps、H.264/AAC、175.018667秒を検証した。
  証跡: `videos/eagleeye-build-week/output/eagleeye-build-week-submission-en-captioned.mp4`、SHA-256 `B4E9B44131C666AF8C2E1EECBD9BEB900FCD2CBB062AAB3CBD1B9C083D1534B4`
- [ ] `P9-02 | NOT_RUN` 公開前セキュリティ手順を提出commitと全履歴へ実行する。
- [ ] `P9-03 | TBD` 公開GitHub URLをDevpostへ設定する。
- [ ] `P9-04 | IN_PROGRESS` 2:30-3:00の最終動画とchecksumはローカル確定。公開uploadとURL記録は未実施。
- [x] `P9-05 | PASS` 6枚の最終UIスクリーンショットとArchitecture図を取得し、SHA-256とbyte数をmachine-readable evidenceへ記録した。
- [x] `P9-06 | PASS` 公開SaaSを装わず、READMEとDevpost draftへ「local-first Quick Start」を正確に記載した。
- [ ] `P9-07 | NOT_RUN` 未認証ブラウザでGitHub、video、public URL、画像をすべて開く。
- [ ] `P9-08 | NOT_RUN` Devpost本文から`TBD`、`IN_PROGRESS`、内部パス、private URL、過去版の件数を最終検索する。
  実行: `rg -n "TBD|IN_PROGRESS|C:\\\\|private|123 passed|17/17" docs/build-week`
- [ ] `P9-09 | NOT_RUN` 提出直前commitでWindows/Linux CIがgreenである。

## 加点要素

- [x] `B-01 | PASS` AI停止時のdeterministic fallback設計がある。
- [x] `B-02 | PASS` 生成前のtest-case quality checkerがある。
- [x] `B-03 | PASS` 証跡にSHA-256と取得metadataを付与するcoreがある。
- [x] `B-04 | PASS` 修正適用とrelease判断を人間承認境界に残す。
- [x] `B-05 | PASS` MCP経由で他エージェントと連携できるcoreがある。
- [x] `B-06 | PASS` AI safety evalとbounded repairの拒否testがある。
- [x] `B-07 | PASS` 実Chromiumで`Ctrl+Shift+Y`によるkeyboard-only extension ONを実行し、同一E2Eを完了した。
- [ ] `B-08 | NOT_RUN` Chromium/Firefox/WebKit互換ゲートを提出commitで実行する。
- [x] `B-09 | PASS` 同じ実WordPress demoを3回連続実行し、Replayは3/3 PASS、品質100、証跡2件/回を記録した。live AIは1/3、明示fallbackは2/3であり、外部AIの揺らぎと決定論的継続を分けて記録した。
  証跡: `docs/build-week/evidence/three-run-reproducibility.json`
- [x] `B-10 | PASS` 1枚で全flowとtrust boundaryを説明する提出用Architecture画像を作成した。
  証跡: `docs/build-week/screenshots/architecture-flow.png`

## 最終一括ゲート

以下をclean cloneで順番に実行し、全exit codeとcommit SHAを保存する。

```powershell
uv sync --locked --dev
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
git diff --check
git status --short
```

合格条件:

- すべてexit code `0`
- `git status --short`は空
- Windows/Linux CI green
- Phase 1-9の必須項目がすべて`PASS`
- Devpostの外部項目に`TBD`が0件
- 未実装を実装済みとする記述が0件

未達が1件でもあれば提出判定は`IN_PROGRESS`または`BLOCKED`であり、PASSにはしない。
