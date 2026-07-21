from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

app = FastAPI(
    title="EagleEye Hackathon Fixture",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["127.0.0.1", "localhost", "testserver"],
)


@app.middleware("http")
async def fixture_headers(request, call_next):  # type: ignore[no-untyped-def]
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; style-src 'unsafe-inline'; img-src 'self'; "
        "frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/", response_class=HTMLResponse)
def home(page_id: int | None = None) -> str:
    sample = page_id == 2
    heading = "Sample Page" if sample else "EagleEye Local QA Lab"
    copy = (
        "This deterministic destination is used only by the isolated hackathon fixture."
        if sample
        else "A login-free local site for an authorized browser journey and URL Audit."
    )
    link = (
        '<a class="button" href="/">Back to fixture home</a>'
        if sample
        else '<a class="button" href="/?page_id=2" aria-label="Sample Page">Open Sample Page</a>'
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="/favicon.ico">
  <title>EagleEye Local QA Lab</title>
  <style>
    :root {{ color-scheme: dark; font-family: Inter, system-ui, sans-serif; }}
    body {{ margin: 0; min-height: 100vh; display: grid; place-items: center;
      background: #071019; color: #edf8f6; }}
    main {{ width: min(720px, calc(100% - 40px)); padding: 56px;
      border: 1px solid #28404c; border-radius: 18px; background: #101b25; }}
    .eyebrow {{ color: #34d6b4; font-weight: 800; letter-spacing: .16em; font-size: 12px; }}
    h1 {{ margin: 12px 0; font-size: clamp(36px, 7vw, 68px); line-height: 1.05; }}
    p {{ color: #adc0c6; font-size: 18px; max-width: 580px; }}
    .button {{ display: inline-block; margin: 22px 12px 0 0; padding: 13px 18px;
      border-radius: 9px; background: #34d6b4; color: #06201b; text-decoration: none;
      font-weight: 900; }}
  </style>
</head>
<body><main><div class="eyebrow">HACKATHON · ISOLATED · LOCAL</div>
  <h1>{heading}</h1><p>{copy}</p>{link}
  <a class="button" href="/login" aria-label="Sign in">Sign in hint</a>
</main></body></html>"""


@app.get("/login", response_class=HTMLResponse)
def login_hint() -> str:
    return "<main><h1>Fixture sign in</h1><p>No credential form exists in this demo.</p></main>"


@app.options("/")
def preflight() -> Response:
    return Response(status_code=204)


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots(request: Request) -> str:
    return f"User-agent: *\nDisallow:\nSitemap: {request.base_url}sitemap.xml\n"


@app.get("/sitemap.xml")
def sitemap(request: Request) -> Response:
    content = f"<?xml version='1.0'?><urlset><url><loc>{request.base_url}</loc></url></urlset>"
    return Response(content, media_type="application/xml")


@app.get("/.well-known/security.txt", response_class=PlainTextResponse)
def security_txt() -> str:
    return "Contact: mailto:security@example.invalid\nExpires: 2030-01-01T00:00:00Z\n"


@app.get("/openapi.json")
def openapi_fixture() -> JSONResponse:
    return JSONResponse(
        {
            "openapi": "3.1.0",
            "info": {"title": "EagleEye Hackathon Fixture", "version": "1.0.0"},
            "paths": {"/": {"get": {"responses": {"200": {"description": "Fixture page"}}}}},
        }
    )


@app.api_route("/favicon.ico", methods=["GET", "HEAD"])
def favicon() -> Response:
    return Response(b"EAGLEEYE", media_type="image/x-icon")
