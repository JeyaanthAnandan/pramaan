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
            assert len(ev) == 222
            amber = [e for e in ev if e["status"] == "NEEDS_REVIEW"]
            assert c.patch(f"/api/projects/demo-shivalik/evidence/{amber[0]['id']}", json={"action": "approve"}).status_code == 200
            res = c.get("/api/projects/demo-shivalik/results").json()
            assert not [g for g in res["gaps"] if g["group"] == "review"]
            run_id = c.get("/api/projects/demo-shivalik").json()["last_run"]["id"]
            assert c.get(f"/api/projects/demo-shivalik/runs/{run_id}/events").text.count("event: timeline") > 100
            tok = c.post("/api/projects/demo-shivalik/share").json()["token"]
            assert c.get(f"/api/share/{tok}").status_code == 200
            # the owner's delete removes an own project and its links from Firestore too
            from app.evidence.models import ShareLink

            own = c.post("/api/projects", json={"name": "x", "company": "Delete Me (SAMPLE)"}).json()["id"]
            st.store().put_share(ShareLink(token=f"t-{own}", project_id=own, summary_snapshot={}))
            assert c.delete(f"/api/projects/{own}").status_code == 200
            assert st.store().get_project(own) is None and st.store().get_share(f"t-{own}") is None
            assert st.store().get_share(tok) is not None  # another project's link stays
            # ids Firestore cannot hold (reserved __names__, over 1,500 bytes) are not found, never a 500
            for bad in ("__x__", "a" * 1600):
                assert c.get(f"/api/projects/{bad}").status_code == 404
                assert c.get(f"/api/share/{bad}").status_code == 404
                assert c.get(f"/api/supplier/{bad}").status_code == 404
                assert c.get(f"/api/projects/demo-shivalik/runs/{bad}").status_code == 404
                assert c.get(f"/api/projects/demo-shivalik/documents/{bad}/image").status_code == 404
                assert c.patch(f"/api/projects/demo-shivalik/evidence/{bad}", json={"action": "approve"}).status_code == 404
    finally:
        st.set_store(None)
