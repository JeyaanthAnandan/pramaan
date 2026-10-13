"""Pramaan - CBAM proof from a phone photo. One Cloud Run service: API + built SPA."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from app import refdata
from app.api.routes import router
from app.api.supplier import router as supplier_router
from app.api.try_one import router as try_router
from app.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(title="Pramaan", version=settings().version, docs_url="/api/docs", openapi_url="/api/openapi.json")
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.include_router(router)
app.include_router(supplier_router)
app.include_router(try_router)


@app.middleware("http")
async def security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    return resp


# Cloud Run's front end reserves some paths ending in "z" (/healthz returns 404 there), so the
# SPA and the deploy smoke test use /api/health; /healthz stays for local runs and CI.
@app.get("/healthz")
@app.get("/api/health")
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


class HashedAssets(StaticFiles):
    """Vite puts a content hash in every asset name, so browsers may keep them for a year."""

    async def get_response(self, path: str, scope: Any) -> Response:
        resp = await super().get_response(path, scope)
        if resp.status_code == 200:
            resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return resp


static: Path = settings().static_dir
if static.exists():
    app.mount("/assets", HashedAssets(directory=static / "assets"), name="assets")
    _index: dict[str, Any] = {}  # index.html, re-read when a new build replaces it

    # GET and HEAD: link-preview crawlers and uptime checks often send HEAD first
    @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def spa(path: str, request: Request) -> Response:
        candidate = (static / path).resolve()
        if path and candidate.is_file() and str(candidate).startswith(str(static.resolve())):
            # public files without a content hash (hero photos, icon, og card): a day in the browser
            return FileResponse(candidate, headers={"Cache-Control": "public, max-age=86400"})
        idx = static / "index.html"
        if _index.get("mtime") != (m := idx.stat().st_mtime):
            _index.update(mtime=m, html=idx.read_text())
        origin = settings().public_base_url or str(request.base_url).rstrip("/")
        return HTMLResponse(_index["html"].replace("__ORIGIN__", origin), headers={"Cache-Control": "no-cache"})
