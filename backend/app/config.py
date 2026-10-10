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
    file_search_store: str = field(default_factory=lambda: _env("FILE_SEARCH_STORE", ""))

    store_backend: str = field(default_factory=lambda: _env("STORE_BACKEND", "memory"))  # memory | firestore
    data_dir: Path = field(default_factory=lambda: Path(_env("PRAMAAN_DATA_DIR", str(BACKEND_DIR / ".data"))))
    bucket: str = field(default_factory=lambda: _env("PRAMAAN_BUCKET", ""))
    static_dir: Path = field(default_factory=lambda: Path(_env("PRAMAAN_STATIC_DIR", str(BACKEND_DIR.parent / "frontend" / "dist"))))
    demo_dir: Path = field(default_factory=lambda: Path(_env("PRAMAAN_DEMO_DIR", str(BACKEND_DIR.parent / "demo"))))
    regulation_dir: Path = field(default_factory=lambda: Path(_env("PRAMAAN_REGULATION_DIR", str(BACKEND_DIR.parent / "docs" / "regulation"))))

    live_runs_enabled: bool = field(default_factory=lambda: _bool("LIVE_RUNS_ENABLED", True))
    max_runs_per_hour: int = field(default_factory=lambda: int(_env("MAX_RUNS_PER_HOUR", "12")))
    public_base_url: str = field(default_factory=lambda: _env("PUBLIC_BASE_URL", ""))

    @property
    def gemini_configured(self) -> bool:
        if self.gemini_mode == "api_key":
            return bool(_env("GEMINI_API_KEY") or _env("GOOGLE_API_KEY"))
        # Vertex mode relies on Application Default Credentials (Cloud Run service account).
        return _bool("GEMINI_VERTEX_READY", default=bool(_env("K_SERVICE"))) or _adc_present()


def _adc_present() -> bool:
    if _env("GOOGLE_APPLICATION_CREDENTIALS"):
        return True
    adc = Path.home() / ".config" / "gcloud" / "application_default_credentials.json"
    return adc.exists()


@lru_cache(maxsize=1)
def settings() -> Settings:
    return Settings()
