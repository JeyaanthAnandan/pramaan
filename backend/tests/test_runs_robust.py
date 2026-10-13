"""Runs on Cloud Run: a run cut off by an instance restart never blocks the project or spins in the UI
forever, and live (paid) runs are capped per address as well as per project."""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.agents import llm
from app.evidence.models import Run
from app.evidence.store import store
from app.main import app

PID = "demo-shivalik"
sys.path.insert(0, str(Path(__file__).parent))


@pytest.fixture()
def client(mem_store):  # noqa: ARG001
    with TestClient(app) as c:
        assert c.post("/api/demo/load", json={"replay": True, "shared": True}).status_code == 200
        yield c


def test_a_run_cut_off_by_a_restart_is_released(client: TestClient) -> None:
    old = (dt.datetime.now(dt.UTC) - dt.timedelta(minutes=31)).isoformat(timespec="seconds")
    stuck = Run(project_id=PID, mode="live", started_at=old)  # status "running", not executing anywhere
    store().put_run(stuck)
    assert client.get(f"/api/projects/{PID}").json()["running"] is False
    r = store().get_run(PID, stuck.id)
    assert r and r.status == "error" and "interrupted" in (r.error or "")
    assert client.post(f"/api/projects/{PID}/runs", json={"mode": "replay"}).status_code == 200  # not 409


def test_a_recent_run_still_counts_as_running(client: TestClient) -> None:
    store().put_run(Run(project_id=PID, mode="live"))
    assert client.get(f"/api/projects/{PID}").json()["running"] is True
    assert client.post(f"/api/projects/{PID}/runs", json={"mode": "replay"}).status_code == 409


def test_live_runs_are_capped_per_address(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from test_agent_scenarios import FakeGemini

    from app.api import routes

    real = routes.settings()
    monkeypatch.setattr(
        routes,
        "settings",
        lambda: SimpleNamespace(**{**real.__dict__, "gemini_configured": True, "live_runs_enabled": True, "max_runs_per_hour": 50}),
    )
    monkeypatch.setitem(routes.AI_CALLS_PER_HOUR, "run", 1)
    routes._ai_log.clear()
    routes._run_log.clear()
    llm.set_gemini(FakeGemini())
    try:
        h = {"x-forwarded-for": "198.51.100.7"}
        first = client.post(f"/api/projects/{PID}/runs", json={"mode": "live"}, headers=h)
        second = client.post(f"/api/projects/{PID}/runs", json={"mode": "live"}, headers=h)
        replay = client.post(f"/api/projects/{PID}/runs", json={"mode": "replay"}, headers=h)
    finally:
        llm.set_gemini(None)
        routes._ai_log.clear()
    assert first.status_code == 200 and first.json()["mode"] == "live"
    assert second.status_code == 429
    assert replay.status_code == 200  # replays cost nothing and are not capped per address
