"""Bundled, data-free browser target for a five-minute EagleEye evaluation."""

from __future__ import annotations


def demo_site_html(sample_page: bool = False) -> str:
    heading = "Sample Page" if sample_page else "EagleEye Local QA Lab"
    copy = (
        "This public sample page is the deterministic destination used by EagleEye Replay."
        if sample_page
        else "A login-free local site for recording a normal browser journey."
    )
    link = (
        '<a class="button" href="/demo-site/">Back to sample home</a>'
        if sample_page
        else '<a class="button" href="/demo-site/sample" aria-label="Sample Page">Open Sample Page</a>'
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>EagleEye Local QA Lab</title>
  <style>
    :root {{ color-scheme: light dark; font-family: Inter, system-ui, sans-serif; }}
    body {{ margin: 0; min-height: 100vh; display: grid; place-items: center;
      background: #071019; color: #edf8f6; }}
    main {{ width: min(720px, calc(100% - 40px)); padding: 56px;
      border: 1px solid #28404c; border-radius: 18px; background: #101b25; }}
    .eyebrow {{ color: #34d6b4; font-weight: 800; letter-spacing: .16em; font-size: 12px; }}
    h1 {{ margin: 12px 0; font-size: clamp(36px, 7vw, 68px); line-height: 1.05; }}
    p {{ color: #adc0c6; font-size: 18px; max-width: 580px; }}
    .button {{ display: inline-block; margin-top: 22px; padding: 13px 18px; border-radius: 9px;
      background: #34d6b4; color: #06201b; text-decoration: none; font-weight: 900; }}
  </style>
</head>
<body><main><div class="eyebrow">BUNDLED · LOGIN-FREE · LOCAL</div>
  <h1>{heading}</h1><p>{copy}</p>{link}
</main></body></html>"""
