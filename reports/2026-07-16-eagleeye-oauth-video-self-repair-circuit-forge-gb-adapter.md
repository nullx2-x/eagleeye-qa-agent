# EagleEye 0.8.0 / Circuit Forge / GB-N64 adapter QA report

Status: **PARTIAL**

Report Hub: accepted / report ID `[redacted]` / 2026-07-16 12:05 JST

## Outcome

EagleEyeのCodex App Server管理ChatGPT OAuth、動画証跡、固定desktop adapter、限定自己修復を実装し、EagleEye自身からCircuit Forge Studio配布版を実行して画像4件とWebM 1件を取得した。GB-N64ダンパー拡張adapterは安全なarchitecture、candidate BOM、protocol、KiCad ERC基盤まで作成したが、所有N64ダンパーを同定できないため製造・通電を停止している。

## Evidence

- EagleEye full regression: Ruff PASS / Pytest 123 passed。
- Operational smoke: API 0.8.0 / MCP 15 tools / real Chromium PASS。
- Browser matrix: Chromium / Firefox / WebKit PASS。
- ChatGPT: App Server managed OAuth connected、structured marker PASS、EagleEyeはtoken非保持。
- Repair model: `codex-agent/gpt-5.6-sol` explicit turn PASS。低能力modelはpolicy拒否。
- Self-repair canary: apply + hashed audit、rollback + retry、atomic one-use、context binding、forged attestation rejectionの5 tests PASS。
- Circuit Forge: npm verify PASS（ESLint、tsc、Vitest 5、Python ruff、pytest 6、renderer/main build）。
- Live desktop QA: `[redacted-run-id]` PASS / exit 0 / 8,617 ms。
- Video: VP8 1440x900 / 7.36 s / 524,835 bytes / SHA-256 `0489d0532488b812ef9b170271f3b0333d5af258392f2e584d8e05d1dccd4241`。
- Scenario checker: 9 cases / score 100 / 0 issues / PASS。Guided sessionは人間承認前`PREPARED`。
- GB adapter: design validator PASS / Ruff PASS / 4 tests PASS / KiCad 10.0.4 ERC PASS。

## Main artifacts

- Video: `artifacts/runs/[redacted-run-id]/desktop/[redacted-video-name].webm`
- Screenshot: `artifacts/runs/[redacted-run-id]/desktop/[redacted-image-name].png`
- EagleEye dashboard: `.workflow/[redacted-workflow]/results/eagleeye-dashboard.png` / SHA-256 `b4a8d0c3609fdc4b207f503f2b979b6b278da091c88d4e424f02cb301cad030a`
- Operational smoke: `.workflow/[redacted-workflow]/results/operational-smoke.json`
- Repair canary: `.workflow/[redacted-workflow]/results/self-repair-canary.xml`
- GB adapter: `[redacted-external-project-path]`
- ERC: SHA-256 `0ff3ed7a72b5aa011fae4d4c6a9244acce27f921db41d4a09efd6469766730ca`
- Architecture SVG: SHA-256 `ff2e182ebf53a60a0358d6317e77f2222893eb02c928912109e3b9ef0f17d1d4`

## Remaining blockers and risks

- Required from the owner: clear front/back photos, product/model, PCB revision, controller, firmware/source or binary hash, insertion direction, contact side, pitch, board thickness/bevel, empty-slot voltages, logic-analyzer traces.
- Until confirmed: no final pin assignment, connector footprint, routed PCB/DRC, fabrication, power-up, hot-plug, cartridge insertion, SRAM/RTC write.
- `BLOCKED_FOR_HARDWARE_IDENTIFICATION` / `fabricationAllowed=false` / N64 12 V NC / ROM read-only remains enforced.
- Local REST API assumes processes under the same Windows user are trusted. Add an authenticated gateway before any LAN/shared-host exposure.
- Video evidence can contain PII already visible on screen; define retention and access controls before broader use.
