---
format: 1920x1080
message: "普段どおり操作するだけ。AIがテストに変える。"
arc: "Demo Loop — Problem → Observe → Generate → Replay → Explain → Share"
audience: "OpenAI Build Week judges and developer-tool teams"
mode: autonomous
language: en
duration: 175s
music: none
captions: burned-in English subtitles plus SRT/VTT sidecars
---

## Video direction

- palette system: `frame.md`を単一の正とし、cream `#eff8f8`を床、ink `#081019`を主情報、tile `#E2E7EB`を面、coral `#34d6b4`を各フレーム一度だけの電圧として使う。warm navyは実UIや技術面の背景に限定する。表示はYu Gothic UI、技術ラベルと実測値の単位はJetBrains Monoの役割で扱う。
- motion grammar: 全フレームをpaused GSAP timelineで決定論的に構成し、入口は`fromTo`、標準は滑らかなlong-tail `power3`。画面上の日本語コピーを黙読する順に要素を後半約50%まで逐次表示し、冒頭25%へ全要素を詰め込まない。フレーム間の退出はstoryの`transition_in`を使い、内部の切替は速度を合わせたcut-the-curveかzoom-throughにする。
- reveal model: 各Sceneの最初にはその時点で伝える一要素だけを置き、次の語句・実画面・実測値は意味が到達した時刻で出す。最終表示後は止めて読ませ、hold中は必要な場合だけ低振幅の有限jitterを許す。無音版でも画面内コピーだけで意味が完結する。
- rhythm / held frames: Frame 4（安全境界）とFrame 8（人間承認）を意図的なbreather、Frame 7（1,745ms）とFrame 10（価値提案）を長いheld readにする。それ以外は操作やデータの逐次表示で進行する。
- composition: 主役は常にキャンバスの40%以上、背景・面・前景の3層を基本とし、重要情報は上83%へ収める。実画面は装飾的なブラウザ外枠を足さず、取得済みスクリーンショットそのものを使う。
- negative list: 純白・純黒・紫青のAIグラデーション・重い影・複数coral・架空数値・架空顧客・実ブラウザchrome・実カーソル・常時浮遊・無限repeat・`Math.random`・`Date.now`を使わない。slideshow（前半で全表示して停止）とscreensaver（各要素が独立して漂う）の両方を禁止し、lazy breathing、後半の遅いpan/push、bounce/elasticの常用を行わない。
- audio: ローカルKokoro-82Mの`af_nova`で生成した英語AIナレーション。BGMなし。字幕はローカルFaster-Whisperの単語時刻から72 cueを作成し、提出MP4へ焼き込む。SRT/VTTも保持し、AI生成音声であることを提出文書へ明記する。

## Frame 1 — テスト作成の時間 (0:00–0:12)

- scene: テスト設計・実装・証跡作成が積み上がる問題を大きな日本語で提示する
- voiceover: "Webテストには、設計、実装、実行、報告。その全部に時間が掛かる。"
- duration: 12s
- transition_in: cut
- status: animated
- src: compositions/frames/01-testing-takes-time.html
- type: hook
- persuasion: Pain validation
- beat: frustration
- blueprint: kinetic-type-beats (Adapt)
- asset_candidates: assets/screenshots/dashboard.png — EagleEye Live QAの全体画面
- focal: assets/screenshots/dashboard.png
- roles: dashboard = background（最終beatでdim 42%）
- sfx: none

Adapt: multi-beat statement buildの中央固定とhard-cut置換を維持し、痛みを四工程へ分解した後、実Dashboardを薄く見せて「全部に時間」を現実の画面へ接続する。署名動作は中央アンカー上の語句置換。
Scene 1 (0.0–2.8s): creamの空面に「Webテストには」だけを中央上寄りへper-word staggered reveal（`dynamic-content-sequencing`）で入れる。Centered、主役約55%、背景・文字・coralの短いsection-ruleの3層。
Scene 2 (2.8–7.8s): 同じ中央アンカーで「設計」→「実装」→「実行」→「報告」を順にhard-cut / flash word-swap（`discrete-text-sequence`）。各語の下に工程番号だけがmonoで遅れて着地し、前の語は残さない。
Scene 3 (7.8–10.2s): 4語を一行の小さな工程列へ縮約し、背後へdashboardを下から短くscale-swap（`scale-swap-transition`）で置く。Asymmetric 70/30、dashboardはdim 42%、文字を上83%へ保持。
Scene 4 (10.2–12.0s): 「その全部に、時間が掛かる。」を大きく着地させ、coralの1px ruleだけを左から描いて静止。動かさずheld readにする。

narrativeRole: 開発者が既に知っている痛みを12秒で言語化する。
keyMessage: Webテストは一連の作業全体が重い。

## Frame 2 — 操作をテストへ (0:12–0:25)

- scene: 散らばったQA工程がEagleEyeの五段階へ収束し、製品名と約束が着地する
- voiceover: "EagleEyeは、その入口を変える。普段どおり操作するだけ。AIがテストに変える。"
- duration: 13s
- transition_in: zoom-through
- status: animated
- src: compositions/frames/02-introducing-eagleeye.html
- type: product_intro
- persuasion: Friction reduction
- beat: relief + curiosity
- blueprint: logo-assemble-lockup (Adapt)
- asset_candidates: assets/screenshots/dashboard.png — ObserveからShareまでを示すヒーロー画面
- focal: assets/screenshots/dashboard.png
- roles: dashboard = cutout（最終lockupの製品面）
- sfx: none

Adapt: logo assemble→lockupの「部品が中央の製品へ収束する」署名動作を、Observe / Generate / Replay / Explain / Shareの五工程で再現する。抽象ロゴではなく実Dashboardをlockupにする。
Scene 1 (0.0–3.2s): 「入口を変える。」だけをcream上の左上三分割点へ表示し、5本のhairlineが中央へSVG self-draw（`svg-path-draw`）。画面はまだ製品名を見せない。
Scene 2 (3.2–8.2s): Observe、Generate、Replay、Explain、Shareの5 pillが一つずつ中央へcluster→outward expansionの逆向きassemble（`center-outward-expansion`）で集まり、EagleEyeの文字lockupをsegment-by-segment build（`discrete-text-sequence`）。Layered-depth、3層、coralはObserve pillだけ。
Scene 3 (8.2–10.8s): assembled lockupを同じ中心のdashboardカードへcard morph-anchor（`card-morph-anchor`）で受け渡し、実UIをキャンバスの68%まで表示する。コピー「普段どおり操作するだけ。」を上側へ逐次表示。
Scene 4 (10.8–13.0s): dashboardの上に「AIがテストに変える。」だけを大きく重ね、EagleEye lockupとともに静止。余計なcamera driftなし。

narrativeRole: 解決策と一文の価値を25秒以内に確定する。
keyMessage: EagleEyeは通常操作をQAの起点にする。

## Frame 3 — Chrome拡張をON (0:25–0:43)

- scene: 実拡張の記録中画面と実WordPress操作を並べ、明示ONから通常操作まで見せる
- voiceover: "Chrome拡張をON。ユーザーはWordPressをいつもどおり操作する。OFFの間は何も記録しない。"
- duration: 18s
- transition_in: push-slide LEFT
- status: animated
- src: compositions/frames/03-extension-on.html
- type: feature_showcase
- persuasion: Show-don't-tell proof
- beat: control
- blueprint: device-surface-showcase (Adapt)
- asset_candidates: assets/screenshots/extension-recording.png — 明示的な記録中状態; assets/screenshots/wordpress-observed.png — 実WordPress Sample Page
- focal: assets/screenshots/wordpress-observed.png
- roles: extension-recording = supporting（制御面） · wordpress-observed = cutout（操作対象）
- sfx: none

Adapt: 一つの製品surfaceが操作に応じて状態を進める署名構造を、左の拡張状態と右のWordPress実画面の同期で置き換える。surfaceは全編で保持し、画面だけを段階的に読ませる。
Scene 1 (0.0–4.2s): extension-recordingを左42%、wordpress-observedを右58%のsplitへedge slide-in + settle。最初は拡張の「記録中」だけをcoral hairlineで囲み、「明示的にON」をmonoラベルで表示する。3 depth layers、bottom 17%は空ける。
Scene 2 (4.2–9.8s): WordPress側へ短いcoordinate zoom（`coordinate-target-zoom`）を行い、Sample Pageの見出しと本文を順にhairline markerで示す。実画面はscale-swapせずpersistent、視線だけを移す。
Scene 3 (9.8–14.2s): 画面上部に「いつもどおり操作」を逐次表示し、extension側へ「DOM / screenshot / action」の小さな状態行を1行ずつ`dynamic-content-sequencing`で追加する。
Scene 4 (14.2–18.0s): 左下へ「OFF = 0 observations」を実測ルールとして着地させ、両surfaceを静止保持。「OFFの間は何も記録しない」を最後に読む。

narrativeRole: ブラウザ常駐エージェントの差別化を実画面で証明する。
keyMessage: 捕捉はユーザーの明示操作でだけ始まる。

## Frame 4 — 安全な三つの文脈 (0:43–0:59)

- scene: DOM要約、可視スクリーンショット、操作履歴の三要素が一つのセッションへ集まる
- voiceover: "EagleEyeが見るのは、安全なDOM要約、可視画面、操作履歴。入力値と秘密情報は保存しない。"
- duration: 16s
- transition_in: crossfade
- status: animated
- src: compositions/frames/04-safe-context.html
- type: feature_showcase
- persuasion: Risk reversal
- beat: trust
- blueprint: grid-card-assemble (Adapt)
- asset_candidates: assets/screenshots/wordpress-observed.png — 観測対象画面; assets/screenshots/dashboard.png — 同一セッションの運用画面
- focal: assets/screenshots/wordpress-observed.png
- roles: wordpress-observed = background（dim 38%） · dashboard = supporting（同一セッション）
- sfx: none

Adapt: N itemsが短い距離から各slotへassembleする署名動作を、安全な三文脈の3-card gridへ適用する。共通中心から爆発させず、各カードが自分の位置へ入る。
Scene 1 (0.0–3.6s): wordpress-observedをfull-bleed dim 38%で置き、「EagleEyeが見るもの」だけを上三分割へ表示。中央のgrid領域は空のまま。
Scene 2 (3.6–9.6s): 「DOM要約」「可視スクリーンショット」「操作履歴」の3カードを左→右へitem stagger-assemble（`center-outward-expansion`のshort-path variant）。各カードは名称の後に「safe summary」「visible only」「event trail」をmonoで遅れて表示する。
Scene 3 (9.6–12.4s): 3カードから一本のhairlineが同一セッションカードへ収束し、dashboardの小さなsupporting cutoutを右上へscale-swap（`scale-swap-transition`）。
Scene 4 (12.4–16.0s): coralの唯一のcalloutとして「入力値・秘密情報は保存しない」を下ではなく上83%内へ横長に着地。カードと背景は止め、breatherとして保持する。

narrativeRole: AIに渡す情報量とプライバシー境界を同時に説明する。
keyMessage: 文脈は豊富だが、秘密値は入らない。

## Frame 5 — 実操作からOpenAIが追加生成 (0:59–1:15)

- scene: 記録ケースを中心にAIケースが展開し、provider、model、fallback、100点品質を数値で示す
- voiceover: "Codex App Server経由のOpenAIが、実操作を根に追加ケースを生成。記録ケースは消せず、品質検査は100点。"
- duration: 16s
- transition_in: squeeze
- status: animated
- src: compositions/frames/05-openai-generation.html
- type: feature_showcase
- persuasion: Feature-to-benefit translation
- beat: confidence
- blueprint: dataviz-countup (Adapt)
- asset_candidates: assets/screenshots/test-list.png — 生成済みケース一覧; assets/screenshots/replay-result.png — AI利用と5ケースを示す拡張結果
- focal: assets/screenshots/test-list.png
- roles: test-list = cutout（生成結果） · replay-result = supporting（provider/model証跡）
- sfx: none

Adapt: count-up→次のinstrument→hero metricへ着地する署名動作を、記録ケース1件から全5件、品質100点への実測導線へ適用する。数値は検証済み証跡だけを使う。
Scene 1 (0.0–4.6s): warm navyの技術面に「Recorded 1」をcenter statとしてcount-up 0→1（`counting-dynamic-scale`）。周囲へtest-listの先頭ケースだけをcutoutで見せ、coral ringを0→1へsweep（`stat-bars-and-fills`）。
Scene 2 (4.6–9.4s): cameraを右のprovider instrumentへ短くpan / focus-lock（`viewport-change`）。`codex-agent`、`gpt-5.6-terra`、`fallback false`をreplay-resultから順に表示し、「OpenAIが追加生成」を最後に着地。
Scene 3 (9.4–13.2s): test-list全体へzoom-to-target（`coordinate-target-zoom`）し、case countを1→5へcount-up。Recorded caseを固定したままAI generated rowsが後半で一件ずつassembleする。
Scene 4 (13.2–16.0s): `QUALITY 100 / PASS`を中央hero metricへscale-swapし、周囲のUIはdim。最終値を静止して読み切る。

narrativeRole: OpenAIが空想ではなく現実の操作へ追加価値を載せることを示す。
keyMessage: OpenAIは補完し、決定論的な記録と検査が土台になる。

## Frame 6 — Replay開始 (1:15–1:35)

- scene: ReplayボタンからWordPress導線が再生され、モデルではなくPlaywrightが判定する
- voiceover: "Replayを押す。Playwrightが同じ導線を実行し、URL、タイトル、見出しまで検証する。AIは判定者ではない。"
- duration: 20s
- transition_in: zoom-through
- status: animated
- src: compositions/frames/06-replay-run.html
- type: feature_showcase
- persuasion: Show-don't-tell proof
- beat: anticipation
- blueprint: cursor-ui-demo (Adapt)
- asset_candidates: assets/screenshots/replay-result.png — Replay操作と結果; assets/screenshots/wordpress-observed.png — 再現された最終画面
- focal: assets/screenshots/replay-result.png
- roles: replay-result = cutout（操作面） · wordpress-observed = supporting（再現結果）
- sfx: none

Adapt: custom cursorが実UIを一操作し、cameraが結果へ追従してpayoff stateで止まる署名動作をReplay一連の証明へ適用する。カーソルはCSSで作るcoral pointerで、OSカーソルやブラウザchromeは見せない。
Scene 1 (0.0–4.8s): replay-resultをキャンバス中央68%のpersistent surfaceとして入れ、CSS pointerがReplayボタンへ移動。ボタンとpointerを同時にpress-compressしripple（`cursor-click-ripple` + `physics-press-reaction`）。
Scene 2 (4.8–10.0s): UI上へ「Playwright」のrunner railを表示し、`goto`→`click`→`assert URL`→`assert title`→`assert heading`を一行ずつ`dynamic-content-sequencing`。cameraは対象行へ短いpan/focus-lock（`viewport-change`）で追う。
Scene 3 (10.0–15.6s): wordpress-observedを右側へcard morph-anchor（`card-morph-anchor`）で展開し、Sample Page見出しをhairline markerで示す。左にrunner、右に最終画面のasymmetric 45/55。
Scene 4 (15.6–20.0s): `PASS`を中央上へ着地し、「AIは判定者ではない。Playwrightが検証する。」を2行で順に表示。cameraを止めて結果を保持する。

narrativeRole: 生成と実証を分離し、QAとしての信頼性を示す。
keyMessage: テスト結果は決定論的なランナーが作る。

## Frame 7 — 1,745msの実証 (1:35–1:53)

- scene: PASS、1,745ms、スクリーンショット、WebM、SHA-256が順にロックされる
- voiceover: "今回の実WordPress Replayは1,745ミリ秒でPASS。画像と動画にbyte数、時刻、SHA-256を残す。"
- duration: 18s
- transition_in: crossfade
- status: animated
- src: compositions/frames/07-evidence-proof.html
- type: social_proof
- persuasion: Statistical proof
- beat: trust + confidence
- blueprint: dataviz-countup (Adapt)
- asset_candidates: assets/screenshots/report.png — 実行証跡を含むHTMLレポート; assets/screenshots/wordpress-observed.png — Replay最終画面
- focal: assets/screenshots/report.png
- roles: report = cutout（実測レポート） · wordpress-observed = supporting（最終画面証跡）
- sfx: none

Adapt: hero number→evidence instruments→最終proof cardへcameraが移る署名動作を、1,745msとハッシュ付き証跡に適用する。coralはPASS statusの一度だけ。
Scene 1 (0.0–4.8s): navy面の中央で0→1,745をvalue-scaled counter（`counting-dynamic-scale`）、単位`ms`をmonoで固定。周囲のprogress ringが同じeaseで満ち、`PASS`が最後にcoralで着地する。
Scene 2 (4.8–10.6s): report cutoutへzoom-through seam（`cut-catalog.md`）で入り、`screenshot 103,299 bytes`、`video 112,935 bytes`を二つのinstrument cardとして順に表示。各値は実証済み。
Scene 3 (10.6–14.4s): wordpress-observedを左supportingへ置き、report内のtimestampとSHA-256を右側へmono railで一行ずつreveal。hashは先頭12文字＋末尾8文字だけを表示し、全文はレポートに残す。
Scene 4 (14.4–18.0s): `PASS = result + evidence + integrity`のproof cardを中央へ置き、他要素を静かにdim。長めのheld read、camera driftなし。

narrativeRole: デモの主張を測定済みの結果へ変える。
keyMessage: PASSは物語ではなく、ハッシュ付き証跡である。

## Frame 8 — 修正案、人間の承認 (1:53–2:05)

- scene: AI提案と人間承認の境界を左右に分け、適用とリリースは人に残す
- voiceover: "EagleEyeは改善案まで示す。ただし修正適用、本番操作、リリース承認は人間に残す。"
- duration: 12s
- transition_in: squeeze
- status: animated
- src: compositions/frames/08-human-boundary.html
- type: benefit_highlight
- persuasion: Risk reversal
- beat: control + trust
- blueprint: comparison-split (Adapt)
- asset_candidates: assets/screenshots/report.png — 改善提案と証跡が同居するレポート
- focal: assets/screenshots/report.png
- roles: report = background（dim 44%、根拠面）
- sfx: none

Adapt: mirrored opposite-wing cardsとinner-edge badgeの署名動作を、AIができること／人間に残すことの権限境界へ適用する。左右は同じ重さだが、結論は共同作業。
Scene 1 (0.0–2.4s): reportをdim 44%の背景に置き、「自動化の境界」を中央上へslide-down settle。下のsplit領域は空ける。
Scene 2 (2.4–6.8s): 左から「AI — 分析・テスト生成・修正提案」、右から「Human — 修正適用・本番操作・リリース承認」の等幅カードがmirrored opposite-wing entry（`split-tilt-cards`）。tiltは入口だけで収束し、最終面は読みやすく正対する。
Scene 3 (6.8–9.2s): 左inner edgeへ「提案」、右inner edgeへ「決定」のpill badgeを順にspring-pop（`spring-pop-entrance`、この場面唯一の軽いovershoot）。
Scene 4 (9.2–12.0s): 二つのカード間へ一本のhairlineを描き、「AIは提案し、人間が決める。」を上83%内に着地。breatherとして完全静止する。

narrativeRole: 自動化の強さと安全な権限境界を同時に着地させる。
keyMessage: AIは提案し、人間が決める。

## Frame 9 — 一つの共有レポート (2:05–2:30)

- scene: HTMLレポートを縦に巡り、ケース、改善案、証跡、Markdown出力を一枚にまとめる
- voiceover: "最後に、意図、記録ケース、AI追加ケース、Replay結果、改善案を一つのレポートへ。Markdownで開発チームへ渡せる。"
- duration: 25s
- transition_in: push-slide UP
- status: animated
- src: compositions/frames/09-shareable-report.html
- type: benefit_highlight
- persuasion: Friction reduction
- beat: clarity + completion
- blueprint: device-surface-showcase (Adapt)
- asset_candidates: assets/screenshots/report.png — テスト、提案、実行証跡を含む最終レポート
- focal: assets/screenshots/report.png
- roles: report = cutout（persistent report surface）
- sfx: none

Adapt: persistent product surfaceを内部scrollで巡り、最後のscreenで保持する署名構造をHTMLレポート一枚へ適用する。架空ブラウザ外枠は足さない。
Scene 1 (0.0–5.0s): reportを中央76%のlarge surfaceとしてedge slide-in。上部のprovider/model/live-stateと「Intent」をhairline markerで示し、「一つの共有レポート」を上に置く。
Scene 2 (5.0–11.0s): report内部だけをscroll（`3d-page-scroll`、surfaceは`overflow:hidden`）し、Recorded caseとAI generated casesへ順にfocus。左のmono indexが`01 Intent`→`02 Cases`へstate swap（`discrete-text-sequence`）。
Scene 3 (11.0–16.8s): 同じsurfaceをさらにscrollし、Replay結果とfix suggestionsを順に読む。重要なPASSと提案見出しだけをcoralではなくink hairlineでマーキングし、coralの使用は共有ボタンまで温存。
Scene 4 (16.8–21.6s): Evidenceのbytes・timestamp・SHAへscrollし、cameraを短くzoom-to-target（`coordinate-target-zoom`）。mono indexを`03 Evidence`へ更新。
Scene 5 (21.6–25.0s): surface全体へzoom back outし、右上へcoral callout「Markdown bug report」を一度だけ着地。`そのまま開発チームへ`を表示して静止保持。

narrativeRole: 観測から共有までが一つの成果物で終わることを示す。
keyMessage: QAの結果はそのままチームへ渡せる。

## Frame 10 — Observe reality. Replay proof. (2:30–2:55)

- scene: Extension、OpenAI、Replay、ReportがEagleEyeロックアップへ収束し、最終コピーを保持する
- voiceover: "Observe reality. Generate coverage. Replay proof. EagleEyeは、ブラウザに常駐するAI QAエージェント。"
- duration: 25s
- transition_in: zoom-through
- status: animated
- src: compositions/frames/10-outro.html
- type: branding
- persuasion: Rule of three
- beat: inevitability + motivation
- blueprint: logo-assemble-lockup (Adapt)
- asset_candidates: assets/screenshots/dashboard.png — 五段階と製品価値を一枚で示すDashboard; assets/screenshots/extension-recording.png — Observe; assets/screenshots/replay-result.png — GenerateとReplay; assets/screenshots/report.png — ExplainとShare
- focal: assets/screenshots/dashboard.png
- roles: dashboard = cutout（最終lockup） · extension-recording = supporting（Observe） · replay-result = supporting（Generate / Replay） · report = supporting（Explain / Share）
- sfx: none

Adapt: 複数の実surfaceが段階的にassembleし、EagleEyeの製品lockupへ収束する署名動作を最終CTAへ適用する。最後のフレームなのでlockup後のterminal fadeだけを許す。
Scene 1 (0.0–5.0s): extension-recording、replay-result、reportを3枚のhairline cardとして各slotへshort-path assemble。各カードの下に`OBSERVE`、`GENERATE / REPLAY`、`EXPLAIN / SHARE`をmonoで一つずつ表示する。
Scene 2 (5.0–10.8s): 3カードから中央へhairline connectorがSVG self-draw（`svg-path-draw`）。`Observe reality.`→`Generate coverage.`→`Replay proof.`をhard-cutではなく一行ずつper-word reveal（`dynamic-content-sequencing`）。
Scene 3 (10.8–16.8s): supporting cardsを同じ中心のdashboardへcard morph-anchor（`card-morph-anchor`）で収束し、五段階が一画面に揃う。EagleEye wordmarkをsegment-by-segment build（`discrete-text-sequence`）。
Scene 4 (16.8–22.0s): 「ブラウザに常駐するAI QAエージェント。」をdisplayで着地し、coralの✱一つだけをspike-markとしてfade + scale 0.92→1。全要素を静止保持する。
Scene 5 (22.0–25.0s): `EagleEye`と三語の価値提案だけを残し、他のsurfaceをゆっくりopacity fade。最終1.5秒は完全静止し、外部URLや未公開GitHubを表示しない。

narrativeRole: 5分後にも残る三語と製品カテゴリで締める。
keyMessage: EagleEyeは現実を観測し、カバレッジを生成し、証拠を再生する。

## Approval record

The user supplied and approved the five-part Build Week sequence, the 2:55 target, and the winning path, then selected English narration with subtitles for submission. This storyboard is a faithful time-coded expansion of that approved direction; no new product claim was added.
