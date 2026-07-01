"""ReceptHyveln — Recipe URL Cleaner API."""

import asyncio
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import (
    ALLOWED_HOSTS,
    ALLOWED_ORIGINS,
    EXTRACT_TIMEOUT_SECONDS,
    OPENAPI_DOCS,
)
from app.extractor import ExtractionError, extract_recipe
from app.fetcher import FetchError, URLValidationError, fetch_html
from app.rate_limit import limiter

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(
    title="ReceptHyveln",
    version="0.1.0",
    docs_url="/docs" if OPENAPI_DOCS else None,
    redoc_url="/redoc" if OPENAPI_DOCS else None,
    openapi_url="/openapi.json" if OPENAPI_DOCS else None,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

if ALLOWED_HOSTS != ["*"]:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)


class ExtractRequest(BaseModel):
    url: HttpUrl


SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "connect-src 'self'; "
        "img-src 'none'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    ),
}


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)

    for header, value in SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)

    origin = request.headers.get("origin")
    if ALLOWED_ORIGINS == ["*"]:
        response.headers["Access-Control-Allow-Origin"] = "*"
    elif origin and origin in ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin

    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/extract")
@limiter.limit("10/minute")
async def extract(request: Request, body: ExtractRequest):
    url = str(body.url)

    try:
        html = await fetch_html(url)
    except URLValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FetchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    try:
        recipe = await asyncio.wait_for(
            asyncio.to_thread(extract_recipe, html, url),
            timeout=EXTRACT_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail="Extraktionen tog för lång tid.",
        ) from exc
    except ExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "title": recipe["title"],
        "yield": recipe["yield"],
        "ingredients": recipe["ingredients"],
        "ingredient_groups": recipe["ingredient_groups"],
        "steps": recipe["steps"],
        "measurement_hints": recipe["measurement_hints"],
    }


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
