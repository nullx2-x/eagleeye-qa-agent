# EagleEye hackathon demo is an optional fixture isolated from the production runtime.

Nothing under `demos/` is imported by `app.main`, the MCP server, or the production startup scripts.
The fixture exists only for a repeatable evaluator journey and publication evidence.

## Run the isolated fixture

```powershell
.\demos\hackathon\start.ps1
```

It listens on `http://127.0.0.1:8767`. Start production EagleEye separately on port 8766.

To create a demonstration Browser Agent session after both services are running:

```powershell
uv run python demos/hackathon/seed_browser_session.py
```

For a localhost URL Audit, use the explicit two-part opt-in:

```powershell
$env:EAGLEEYE_URL_AUDIT_ALLOW_LOCALHOST = '1'
.\scripts\run-url-audit.ps1 -Url http://127.0.0.1:8767 -AllowLocalhost
```

The environment opt-in should remain unset for ordinary public-URL audits.
