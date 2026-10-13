"""Try one photo: the three reading steps on a single document, streamed as server-sent events.

Replay (no Gemini) for the bundled samples; the live path with a scripted Gemini stand-in (the same
fake the agent scenarios use, so the crops and the struck-out figure behave as in a full run)."""

from __future__ import annotations

import io
import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.agents import llm
from app.agents.llm import LLMResult
from app.api import routes, try_one
from app.config import settings
from app.main import app
from tests.test_agent_scenarios import FakeGemini


@pytest.fixture()
def client(mem_store):  # noqa: ARG001
    routes._ai_log.clear()
    with TestClient(app) as c:
        yield c


def _events(c: TestClient, path: str, **kw: Any) -> list[dict[str, Any]]:
    with c.stream("POST", path, **kw) as r:
        assert r.status_code == 200, r.read()
        assert r.headers["content-type"].startswith("text/event-stream") and "content-encoding" not in r.headers
        return [json.loads(line[6:]) for line in r.iter_lines() if line.startswith("data: ")]


def test_status_and_sample_images(client: TestClient) -> None:
    s = client.get("/api/try").json()
    assert s["live"] is False and [x["name"] for x in s["samples"]] == list(try_one.SAMPLES)
    img = client.get("/api/try/sample/gas-2026-03/image")
    assert img.status_code == 200 and img.content[:2] == b"\xff\xd8"
    assert client.get("/api/try/sample/nope/image").status_code == 404
    assert client.post("/api/try/sample/nope").status_code == 404


def test_replayed_sample_streams_each_step_and_flags_the_hand_correction(client: TestClient) -> None:
    evs = _events(client, "/api/try/sample/scrap-2026-06-to-09")
    stages = [e["stage"] for e in evs]
    assert stages[:3] == ["start", "classified", "extracted"] and stages[-1] == "done"
    assert evs[0]["live"] is False and evs[0]["reader1"] == "replay:ground-truth"
    assert evs[1]["doc_type"] == "scrap_log" and "hi" in evs[1]["languages"]
    fields = {f["id"]: f for f in evs[2]["fields"]}
    checked = [e for e in evs if e["stage"] == "checked"]
    assert len(checked) == len(evs[2]["checking"]) == len(fields) == 8 and all(f["box_2d"] for f in fields.values())
    review = [(fields[e["id"]]["value_text"], e["reading"]) for e in checked if not e["agrees"]]
    assert review == [("15.4", "13.4")]
    for e in checked:  # the padded crop the second reader saw contains the value's own box
        y0, x0, y1, x1 = fields[e["id"]]["box_2d"]
        cy0, cx0, cy1, cx1 = e["crop_box"]
        assert cy0 <= y0 and cx0 <= x0 and cy1 >= y1 and cx1 >= x1
    assert evs[-1]["agree"] == 7 and evs[-1]["review"] == 1 and evs[-1]["tokens"] == 0


def test_own_photo_needs_live_gemini(client: TestClient) -> None:
    r = client.post("/api/try", files={"file": ("bill.jpg", b"\xff\xd8x", "image/jpeg")})
    assert r.status_code == 503 and "samples work without it" in r.json()["detail"]


def test_live_sample_uses_both_models_and_counts_tokens(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(try_one, "live", lambda: True)
    fake = FakeGemini()
    llm.set_gemini(fake)
    try:
        evs = _events(client, "/api/try/sample/scrap-2026-06-to-09")
    finally:
        llm.set_gemini(None)
    cfg = settings()
    assert evs[0] == {"stage": "start", "live": True, "reader1": cfg.model_flash, "reader2": cfg.model_lite}
    assert fake.calls[:2] == [cfg.model_flash, cfg.model_flash] and set(fake.calls[2:]) == {cfg.model_lite}
    fields = {f["id"]: f for f in evs[2]["fields"]}
    review = [(fields[e["id"]]["value_text"], e["reading"]) for e in evs if e["stage"] == "checked" and not e["agrees"]]
    assert review == [("15.4", "13.4")]
    assert evs[-1]["tokens"] > 0 and evs[-1]["review"] == 1


class _Bill:
    """A scripted Gemini for a visitor's own photo (not one of the samples)."""

    def __init__(self, doc_type: str = "electricity_bill", fail_extract: bool = False) -> None:
        self.doc_type, self.fail_extract, self.prompts = doc_type, fail_extract, []

    async def json(
        self, model: str, system: str, parts: list[dict[str, Any]], schema: dict[str, Any], thinking_level: str = "low", retries: int = 2
    ) -> LLMResult:
        props = schema.get("properties", {})
        if "doc_type" in props:
            return LLMResult(
                {"doc_type": self.doc_type, "languages": ["en"], "title": "Electricity bill", "confidence": 0.93}, model, 900, 30, 3
            )
        if "fields" in props:
            self.prompts.append(system)
            if self.fail_extract:
                raise TimeoutError
            rows = [
                {
                    "field_key": "kwh",
                    "value_text": "25,440",
                    "value_num": "25440",
                    "unit": "kWh",
                    "box_2d": [100, 100, 140, 300],
                    "label": "Units consumed",
                },
                {"field_key": "bill_period", "value_text": "01-08-2026 to 31-08-2026", "box_2d": [200, 100, 240, 500]},
            ]
            return LLMResult({"fields": rows}, model, 2000, 200, 4)
        return LLMResult({"value_text": "25440", "value_num": "25440", "unit": "", "legible": True}, model, 200, 10, 1)


def _photo() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (800, 1000), (250, 250, 245)).save(out, format="PNG")
    return out.getvalue()


def test_live_own_photo_is_read_without_product_lines(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(try_one, "live", lambda: True)
    fake = _Bill()
    llm.set_gemini(fake)
    try:
        evs = _events(client, "/api/try", files={"file": ("bill.png", _photo(), "image/png")})
    finally:
        llm.set_gemini(None)
    assert [e["stage"] for e in evs][:3] == ["start", "classified", "extracted"]
    assert evs[0]["image"].startswith("data:image/jpeg;base64,")  # what the readers saw, for the boxes
    assert evs[1]["doc_type"] == "electricity_bill"
    assert "product lines are not known" in fake.prompts[0]
    labels = {f["field_key"]: f["label"] for f in evs[2]["fields"]}
    assert labels["kwh"] == "Units consumed" and labels["bill_period"]  # the schema's meaning when the model gives no label
    checked = {e["id"]: e["agrees"] for e in evs if e["stage"] == "checked"}
    kwh = next(f["id"] for f in evs[2]["fields"] if f["field_key"] == "kwh")
    assert checked[kwh] is True and evs[-1]["stage"] == "done"


def test_not_a_cbam_document_and_a_failed_read(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(try_one, "live", lambda: True)
    llm.set_gemini(_Bill(doc_type="other"))
    try:
        evs = _events(client, "/api/try", files={"file": ("cat.png", _photo(), "image/png")})
        assert [e["stage"] for e in evs] == ["start", "classified", "done"] and evs[-1]["note"] == "not_cbam"
        llm.set_gemini(_Bill(fail_extract=True))
        evs = _events(client, "/api/try", files={"file": ("bill.png", _photo(), "image/png")})
        assert evs[-1]["stage"] == "error" and "too long" in evs[-1]["message"]
    finally:
        llm.set_gemini(None)


def test_live_tries_are_capped_per_address(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(try_one, "live", lambda: True)
    monkeypatch.setitem(routes.AI_CALLS_PER_HOUR, "try", 1)
    llm.set_gemini(_Bill(doc_type="other"))
    try:
        assert client.post("/api/try/sample/gas-2026-03").status_code == 200
        assert client.post("/api/try/sample/gas-2026-03").status_code == 429
    finally:
        llm.set_gemini(None)
    assert client.post("/api/try", files={"file": ("x.txt", b"hello", "text/plain")}).status_code == 429
