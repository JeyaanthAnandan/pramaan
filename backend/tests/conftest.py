from __future__ import annotations

import os

os.environ.setdefault("GEMINI_VERTEX_READY", "0")  # tests never call Gemini
os.environ.setdefault("LIVE_RUNS_ENABLED", "0")

import pytest

from app.evidence.store import MemoryStore, set_store


@pytest.fixture()
def mem_store():
    s = MemoryStore(None)
    set_store(s)
    yield s
    set_store(None)
