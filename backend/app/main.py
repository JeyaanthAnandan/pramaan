"""Pramaan - CBAM proof from a phone photo. One Cloud Run service: API + built SPA."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import refdata
from app.api.routes import router
from app.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(title="Pramaan", version=settings().version, docs_url="/api/docs", openapi_url="/api/openapi.json")
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.include_router(router)


@app.middleware("http")
async def security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    return resp


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    cfg = settings()
    m = refdata.manifest()
    return {
        "status": "ok",
        "service": cfg.service,
        "version": cfg.version,
        "git_sha": cfg.git_sha,
        "region": cfg.region,
        "models": {
            "extraction": cfg.model_flash,
            "second_reader": cfg.model_lite,
            "embedding": cfg.model_embedding,
            "gemini_location": cfg.gemini_location,
            "gemini_mode": cfg.gemini_mode,
            "gemini_configured": cfg.gemini_configured,
        },
        "store": cfg.store_backend,
        "refdata": {"parser_version": m["parser_version"], "generated_at": m["generated_at"], "files": refdata.summary()},
    }


@app.exception_handler(refdata.RefdataError)
async def refdata_error(_: Request, exc: refdata.RefdataError) -> JSONResponse:
    return JSONResponse({"detail": f"reference data: {exc}"}, status_code=422)


static: Path = settings().static_dir
if static.exists():
    app.mount("/assets", StaticFiles(directory=static / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        candidate = (static / path).resolve()
        if path and candidate.is_file() and str(candidate).startswith(str(static.resolve())):
            return FileResponse(candidate)
        return FileResponse(static / "index.html", headers={"Cache-Control": "no-cache"})
