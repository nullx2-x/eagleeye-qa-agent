# Hackathon demo isolation impact

The hackathon evaluator path is optional and no longer shares imports, routes, startup commands, or
status fields with the EagleEye production runtime.

## Changed surfaces

| Previous surface | New surface | Production effect |
|---|---|---|
| `app/demo.py` and `app/demo_site.py` | `demos/hackathon/target_app.py` | `app.main` imports no demo package |
| `scripts/start-demo.ps1` | `demos/hackathon/start.ps1` | Production startup launches only EagleEye |
| `scripts/verify_browser_extension.py` | `demos/hackathon/verify_browser_extension.py` | Publication capture is explicitly optional |
| Hard-coded `/demo-site/` route | Fixture root on loopback port 8767 | Production route now returns 404 |
| `POST /api/v1/browser-agent/sample/local` | `demos/hackathon/seed_browser_session.py` | Production API no longer manufactures demo sessions |
| `sampleTarget` status fields | Removed | Browser Agent status describes production capabilities only |
| Dashboard local-sample action | Authorized URL Audit form | The main entrypoint now creates a real QA project seed |
| `EAGLEEYE_SAMPLE_TARGET`, `EAGLEEYE_DEMO_TIMEOUT_SECONDS` | Removed | No demo configuration is read by production |

## Retained publication assets

`docs/build-week/` and `videos/eagleeye-build-week/` remain publication evidence and media source.
They contain no production Python import path and are not started by the API or MCP processes.
Moving several megabytes of immutable evidence would create link churn without improving runtime
isolation, so their already explicit Build Week namespaces are retained.

## Compatibility notes

- Evaluators must start `demos/hackathon/start.ps1` before running the optional browser demo.
- Existing callers of the removed sample endpoint receive HTTP 404 and should use an authorized
  Browser Agent recording or the isolated seed helper.
- Existing production sessions, Project QA runs, guided QA, provider configuration, and replay
  storage formats are unchanged.
- URL Audit localhost use is disabled unless both the request and environment opt in. The demo
  README documents that local-only exception; normal public audits do not enable it.

## Verification contract

- Import `app.main` with no `demos` module loaded.
- Confirm production `/demo-site/` and `/api/v1/browser-agent/sample/local` return 404.
- Start the fixture independently and confirm its root, OpenAPI, discovery files, and favicon.
- Run URL Audit against the fixture on a non-production port and inspect its JSON/Markdown hashes.
- Run the full lint, format, pytest, publication audit, and EagleEye Project QA gates.
