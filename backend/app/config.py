"""Runtime configuration (environment variables only; no secrets in code)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _bool(name: str, default: bool = False) -> bool:
    v = _env(name)
    return default if not v else v.lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    service: str = "pramaan"
    version: str = field(default_factory=lambda: _env("PRAMAAN_VERSION", "0.9.0"))
    git_sha: str = field(default_factory=lambda: _env("GIT_SHA", "dev"))

    gcp_project: str = field(default_factory=lambda: _env("GOOGLE_CLOUD_PROJECT", "copilot-manufacturing"))
    region: str = field(default_factory=lambda: _env("PRAMAAN_REGION", "asia-southeast1"))
    # Gemini 3.8 Flash and 3.5 Flash-Lite are served from global / us / eu only (Agent Platform model pages).
    gemini_location: str = field(default_factory=lambda: _env("GEMINI_LOCATION", "global"))
    # "vertex" = Gemini Enterprise Agent Platform with the service account (production);
    # "api_key" = Gemini Developer API with GEMINI_API_KEY from .env.local (local dev, File Search).
    gemini_mode: str = field(default_factory=lambda: _env("GEMINI_MODE", "vertex"))

    model_flash: str = field(default_factory=lambda: _env("MODEL_FLASH", "gemini-3.8-flash"))
    model_lite: str = field(default_factory=lambda: _env("MODEL_LITE", "gemini-3.5-flash-lite"))
    model_embedding: str = field(default_factory=lambda: _env("MODEL_EMBEDDING", "gemini-embedding-2"))
    model_transcribe: str = field(default_factory=lambda: _env("MODEL_TRANSCRIBE", "gemini-3.5-transcribe"))
    file_search_store: str = field(default_factory=lambda: _env("FILE_SEARCH_STORE", ""))
    # Call Pramaan (voice calls). Gemini 3.8 Live is served from us-central1 on Agent Platform, not
    # from global or asia-southeast1 (probed 2026-10-13), so the call session has its own location.
    model_live: str = field(default_factory=lambda: _env("MODEL_LIVE", "gemini-3.8-live"))
    live_location: str = field(default_factory=lambda: _env("LIVE_LOCATION", "us-central1"))
    call_max_seconds: int = field(default_factory=lambda: int(_env("CALL_MAX_SECONDS", "300")))

    store_backend: str = field(default_factory=lambda: _env("STORE_BACKEND", "memory"))  # memory | firestore
    data_dir: Path = field(default_factory=lambda: Path(_env("PRAMAAN_DATA_DIR", str(BACKEND_DIR / ".data"))))
    bucket: str = field(default_factory=lambda: _env("PRAMAAN_BUCKET", ""))
    static_dir: Path = field(default_factory=lambda: Path(_env("PRAMAAN_STATIC_DIR", str(BACKEND_DIR.parent / "frontend" / "dist"))))
    demo_dir: Path = field(default_factory=lambda: Path(_env("PRAMAAN_DEMO_DIR", str(BACKEND_DIR.parent / "demo"))))
    regulation_dir: Path = field(
        default_factory=lambda: Path(_env("PRAMAAN_REGULATION_DIR", str(BACKEND_DIR.parent / "docs" / "regulation")))
    )

    live_runs_enabled: bool = field(default_factory=lambda: _bool("LIVE_RUNS_ENABLED", True))
    # How many X-Forwarded-For entries Google's front end appends after the caller's own address (1: the
    # caller, then a proxy, as Google's load balancers do; 0: the caller last). See routes.client_ip.
    client_ip_hops: int = field(default_factory=lambda: int(_env("CLIENT_IP_HOPS", "1")))
    max_runs_per_hour: int = field(default_factory=lambda: int(_env("MAX_RUNS_PER_HOUR", "12")))
    public_base_url: str = field(default_factory=lambda: _env("PUBLIC_BASE_URL", ""))

    @property
    def gemini_configured(self) -> bool:
        if self.gemini_mode == "api_key":
            return bool(_env("GEMINI_API_KEY") or _env("GOOGLE_API_KEY"))
        # Vertex mode relies on Application Default Credentials (Cloud Run service account).
        explicit = _env("GEMINI_VERTEX_READY")
        if explicit:
            return explicit.lower() in {"1", "true", "yes", "on"}
        return bool(_env("K_SERVICE")) or _adc_present()


def _adc_present() -> bool:
    if _env("GOOGLE_APPLICATION_CREDENTIALS"):
        return True
    adc = Path.home() / ".config" / "gcloud" / "application_default_credentials.json"
    return adc.exists()


@lru_cache(maxsize=1)
def settings() -> Settings:
    return Settings()
