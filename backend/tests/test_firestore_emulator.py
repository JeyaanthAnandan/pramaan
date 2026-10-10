"""Production storage path against the Firestore emulator (opt-in).

Run: gcloud emulators firestore start --host-port=127.0.0.1:8085
     FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 pytest tests/test_firestore_emulator.py
"""

from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(not os.environ.get("FIRESTORE_EMULATOR_HOST"), reason="needs the Firestore emulator")


def test_full_flow_on_firestore() -> None:
    from app.evidence import store as st

    st.set_store(st.FirestoreStore(f"demo-{uuid.uuid4().hex[:8]}"))
    from app.main import app

    try:
        with TestClient(app) as c:
            assert c.post("/api/demo/load", json={"replay": True, "shared": True}).status_code == 200
            ev = c.get("/api/projects/demo-shivalik/evidence").json()
            assert len(ev) == 213
            amber = [e for e in ev if e["status"] == "NEEDS_REVIEW"]
            assert c.patch(f"/api/projects/demo-shivalik/evidence/{amber[0]['id']}", json={"action": "approve"}).status_code == 200
            res = c.get("/api/projects/demo-shivalik/results").json()
            assert not [g for g in res["gaps"] if g["group"] == "review"]
            run_id = c.get("/api/projects/demo-shivalik").json()["last_run"]["id"]
            assert c.get(f"/api/projects/demo-shivalik/runs/{run_id}/events").text.count("event: timeline") > 100
            tok = c.post("/api/projects/demo-shivalik/share").json()["token"]
            assert c.get(f"/api/share/{tok}").status_code == 200
    finally:
        st.set_store(None)
