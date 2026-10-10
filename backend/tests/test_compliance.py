"""Hackathon rules and brief section 7.2 as code: only Gemini 3.x models, no deprecated sampling
parameters, fictional data only, no secrets in the repository."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CODE = [
    p
    for d in ("backend/app", "frontend/src", "backend/eval", "backend/adk_eval")
    for p in (ROOT / d).rglob("*")
    if p.suffix in {".py", ".ts", ".tsx"}
]


def test_only_gemini_3_models_configured() -> None:
    from app.config import settings

    cfg = settings()
    for m in (cfg.model_flash, cfg.model_lite, cfg.model_transcribe):
        assert re.match(r"gemini-3\.\d", m), m


def test_no_forbidden_models_in_code() -> None:
    bad = re.compile(r"gemini-(1|2)\.\d|veo-\d|deep-research-pro-preview")
    hits = [
        f"{p.relative_to(ROOT)}:{i}"
        for p in CODE
        for i, line in enumerate(p.read_text(errors="ignore").splitlines(), 1)
        if bad.search(line) and "FORBIDDEN" not in line and "forbidden" not in line
    ]
    assert not hits, hits


def test_no_sampling_parameters_sent() -> None:
    """temperature / top_p / top_k are deprecated (21 Jul 2026) and never set."""
    llm = (ROOT / "backend/app/agents/llm.py").read_text()
    assert not re.search(r"[\"'](temperature|top_p|top_k)[\"']\s*:", llm)


def test_sample_documents_are_watermarked_fictional() -> None:
    tpl = (ROOT / "demo/templates/_macros.j2").read_text()
    assert "SAMPLE — FICTIONAL" in tpl
    for t in (ROOT / "demo/templates").glob("*.html.j2"):
        assert "watermark()" in t.read_text(), t.name


def test_no_env_files_or_keys_committed() -> None:
    assert not (ROOT / ".env.local").exists() or ".env.local" in (ROOT / ".gitignore").read_text()
    key = re.compile(r"AIza[0-9A-Za-z_\-]{35}")
    for p in CODE:
        assert not key.search(p.read_text(errors="ignore")), p
