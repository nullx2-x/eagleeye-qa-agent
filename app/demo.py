from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="EagleEye Demo App")


@app.get("/", response_class=HTMLResponse)
def form() -> str:
    return """<!doctype html><html><head><meta charset='utf-8'><title>EagleEye Demo</title></head><body>
<main><h1>User registration</h1><form action='/success' method='get'>
<label for='email'>Email</label><input id='email' name='email' type='email' required>
<button type='submit'>Register</button></form></main></body></html>"""


@app.get("/success", response_class=HTMLResponse)
def success() -> str:
    return "<main><h1>Registration completed</h1></main>"
