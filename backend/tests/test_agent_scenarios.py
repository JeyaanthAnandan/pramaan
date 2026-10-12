"""Agent scenarios (brief section 9): the live code path of the ADK workflow with a scripted
Gemini stand-in. The fake answers like a model would (classification, fields with box_2d, blind
crop readings) from the ground truth, with per-scenario perturbations, so these tests check the
agents' plumbing and routing - not model quality (that is backend/eval)."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from app.agents import llm
from app.agents.llm import LLMResult
from app.agents.second_reader import crop
from app.config import settings
from app.evidence.models import Run
from app.evidence.store import store

GT = json.loads((settings().demo_dir / "ground_truth.json").read_text())


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


class FakeGemini:
    """Behaves like the Interactions client wrapper: json(model, system, parts, schema, ...)."""

    def __init__(self, scenario: dict[str, Any] | None = None) -> None:
        self.sc = scenario or {}
        self.calls: list[str] = []
        self.by_image: dict[str, dict[str, Any]] = {}
        self.by_crop: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
        for d in GT["documents"]:
            data = (settings().demo_dir / d["file"]).read_bytes()
            self.by_image[_sha(data)] = d
            for f in d["fields"]:
                cb, _ = crop(data, f["box_2d"])
                self.by_crop[_sha(cb)] = (d, f)

    async def json(
        self, model: str, system: str, parts: list[dict[str, Any]], schema: dict[str, Any], thinking_level: str = "low", retries: int = 2
    ) -> LLMResult:
        img = base64.b64decode(next(p["data"] for p in parts if p["type"] == "image"))
        props = schema.get("properties", {})
        self.calls.append(model)
        if "doc_type" in props:
            d = self.by_image[_sha(img)]
            out = {
                "doc_type": d["doc_type"],
                "languages": d["languages"],
                "period_start": d["period"][0],
                "period_end": d["period"][1],
                "title": d["title"],
                "confidence": 0.97,
            }
            out.update(self.sc.get("classify", {}).get(d["doc_id"], {}))
            return LLMResult(out, model, 1200, 40, 5)
        if "fields" in props:
            d = self.by_image[_sha(img)]
            fields = [
                {
                    k: f.get(k)
                    for k in ["field_key", "value_text", "value_num", "unit", "box_2d", "label", "period", "process"]
                    if f.get(k) is not None
                }
                for f in d["fields"]
            ]
            fields += self.sc.get("extra_fields", {}).get(d["doc_id"], [])
            if "mutate" in self.sc:
                fields = self.sc["mutate"](d["doc_id"], fields)
            return LLMResult({"fields": fields}, model, 2400, 900, 5)
        d, f = self.by_crop.get(_sha(img), (None, None))
        if f is None:  # crop of a field the fake added: read it as written
            return LLMResult({"value_text": "", "legible": False}, model, 300, 10, 2)
        reading = {
            "value_text": f.get("alt") or f["value_text"],
            "value_num": f.get("alt") or f.get("value_num") or "",
            "unit": "",
            "legible": True,
        }
        reading.update(self.sc.get("second", {}).get((d["doc_id"], f["field_key"], f.get("process")), {}))
        return LLMResult(reading, model, 300, 12, 2)

    async def text(self, *a: Any, **k: Any) -> LLMResult:  # Explainer (live) rewrite: echo the template
        prompt = a[2][0]["text"] if len(a) > 2 else k["parts"][0]["text"]
        return LLMResult(prompt.split("\n\n", 1)[1], a[0] if a else k["model"], 500, 120, 3)


def _run(mem_store: Any, fake: FakeGemini, drop_docs: set[str] | None = None) -> dict[str, Any]:
    from app.agents.workflow import execute
    from app.demo import loader

    llm.set_gemini(fake)
    try:
        p = loader.reset_demo()
        for d in list(store().list_documents(p.id)):
            if drop_docs and Path(d.filename).stem in drop_docs:
                mem_store.documents[p.id].pop(d.id)
        run = Run(project_id=p.id, mode="live")
        store().put_run(run)
        asyncio.run(execute(run, p, "live"))
        r = store().get_run(p.id, run.id)
        assert r is not None and r.status == "done", r.error if r else "no run"
        return {"run": r, "result": store().get_latest_result(p.id), "evidence": store().list_evidence(p.id)}
    finally:
        llm.set_gemini(None)


def test_skewed_handwritten_scrap_log_routes_to_human_review(mem_store: Any) -> None:
    """The 6-degree skewed scrap log with a struck-through figure: reader 2 sees 13.4, the graph
    takes the HumanReview branch and the value waits for a tap."""
    out = _run(mem_store, FakeGemini())
    review = [e for e in out["run"].events if e.agent == "HumanReview"]
    assert review and "15.4" in review[0].output_summary and "13.4" in review[0].output_summary
    amber = [e for e in out["evidence"] if e.status == "NEEDS_REVIEW"]
    assert [(e.field_key, e.period, e.process) for e in amber] == [("scrap_t", "2026-06", "P2")]
    assert out["run"].metrics["tokens_total"] > 0  # live path accounts tokens


def test_hindi_headed_register_feeds_activity_levels(mem_store: Any) -> None:
    """Hindi-headed production register: classified with languages hi+en and its monthly rows
    become the activity levels (P1 1,275 t, P2 615 t)."""
    out = _run(mem_store, FakeGemini())
    p = {x["id"]: x for x in out["result"]["processes"]}
    assert p["P1"]["al_t"] == "1275.0" and p["P2"]["al_t"] == "615.0"
    reg = [d for d in store().list_documents("demo-shivalik") if d.doc_type == "production_register"]
    assert reg and all("hi" in d.languages for d in reg)


def test_bill_with_two_periods(mem_store: Any) -> None:
    """A gas bill that carries an arrears line for the previous month: both periods are kept and the
    January gas is counted once (the first, best-status reading per month)."""
    extra = {
        "gas-2026-02": [
            {
                "field_key": "mmbtu",
                "value_text": "12.500",
                "value_num": "12.5",
                "unit": "MMBtu",
                "box_2d": [600, 600, 620, 700],
                "label": "Arrears (Jan)",
                "period": "2026-01",
            }
        ]
    }
    out = _run(mem_store, FakeGemini({"extra_fields": extra}))
    gas = out["result"]["calc_tree"]["gas.mmbtu"]
    assert len(gas["children"]) == 9  # one value per month, the duplicate period does not double count
    cov = next(c for c in out["result"]["checks"] if c["id"] == "gas.coverage")
    assert cov["status"] == "pass"
    assert any(e.label == "Arrears (Jan)" and e.status == "NEEDS_REVIEW" for e in out["evidence"])  # unreadable crop -> review


def test_missing_supplier_statement_falls_back_to_default(mem_store: Any) -> None:
    """Without the rod supplier's verified statement the carbon-steel rod uses the India default
    with the 2026 mark-up, the gap turns red and the Precursor Lever applies."""
    out = _run(mem_store, FakeGemini(), drop_docs={"stmt-NWRM-2026"})
    p1 = next(x for x in out["result"]["processes"] if x["id"] == "P1")
    assert p1["precursor"]["data"] == "DEFAULT_USED"
    gap = next(g for g in out["result"]["gaps"] if g["id"] == "precursor_see.P1")
    assert gap["status"] == "red" and gap["lever"] is True
    assert float(p1["see"]) > 5  # 4.270 x 1.1 x m + direct


def test_mismatched_unit_needs_review(mem_store: Any) -> None:
    """Reader 2 reads the export net weight as tonnes while reader 1 has kilograms: units differ
    after normalisation, so the value is not auto-verified."""
    second = {("export-2026-Q2", "net_mass_kg", "P1"): {"unit": "MT"}}
    out = _run(mem_store, FakeGemini({"second": second}))
    e = next(x for x in out["evidence"] if x.field_key == "net_mass_kg" and x.period == "2026-Q2" and x.process == "P1")
    assert e.status == "NEEDS_REVIEW" and e.second_reading and "units differ" in e.second_reading.reason


def test_slips_seen_in_the_first_live_run_are_cleaned_before_the_engine(mem_store: Any) -> None:
    """The first live run on Cloud Run read the values right but left supplier-statement values
    without a product line, appended a date to a reference, put a CN code inside a description,
    appended model text to a number and wrote notes into the classifier's dates. After the clean-up
    the engine gives the golden result again (carbon bolts SEE 2.040 on the supplier's verified data)."""

    def slips(doc: str, fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out = []
        for f in (dict(x) for x in fields):
            if doc == "stmt-NWRM-2026":
                if f["field_key"] in {"see", "sefa", "scrap_per_t", "pre_consumer_pct"}:
                    f.pop("process", None)
                if f["field_key"] == "product_cn":
                    f["value_text"] = "Wire rod, carbon steel — CN 7213 91 49"
                if f["field_key"] == "verification_ref":
                    f["value_text"] += " dated 2026-10-02"
            if doc == "rod-ISR-2026-119" and f["field_key"] == "tonnes":
                f["value_num"] = f["value_num"] + "ecd unit: t scope: process -> unit: t"
                f.pop("unit", None)
                f.pop("process", None)
            out.append(f)
        return out

    classify = {
        "stmt-NWRM-2026": {"period_start": "2026-01-01-00-00-00", "period_end": ""},
        "gas-2026-05": {"period_start": "2026-05-01Bytes"},
    }
    out = _run(mem_store, FakeGemini({"mutate": slips, "classify": classify}))
    p = {x["id"]: x for x in out["result"]["processes"]}
    assert p["P1"]["see"].startswith("2.0398") and p["P1"]["precursor"]["data"] == "ACTUAL_VERIFIED"
    assert p["P2"]["see"].startswith("8.889")
    assert not [e for e in out["evidence"] if e.status == "NEEDS_REVIEW" and e.field_key != "scrap_t"]
    docs = {Path(d.filename).stem: d for d in store().list_documents("demo-shivalik")}
    assert docs["stmt-NWRM-2026"].period == ["2026-01-01", "2026-09-30"] and docs["gas-2026-05"].period == ["2026-05-01", "2026-05-31"]


def test_figure_corrected_by_hand_waits_for_a_person_even_when_readers_agree(mem_store: Any) -> None:
    """A live second reader reads the replacement figure (15.4) and reports the crossed-out one
    (13.4): both readers agree, but a hand correction still goes to the owner, with the mass
    balance showing that 15.4 closes. (The stand-in gives this reading for every stainless month on
    that page, so the other months also show readers that disagree: those keep the usual wording.)"""
    second = {("scrap-2026-06-to-09", "scrap_t", "P2"): {"value_text": "15.4", "value_num": "15.4", "crossed_out": "13.4"}}
    out = _run(mem_store, FakeGemini({"second": second}))

    def scrap(month: str) -> Any:
        return next(x for x in out["evidence"] if x.field_key == "scrap_t" and x.period == month and x.process == "P2")

    def gap_for(e: Any) -> dict[str, Any]:
        return next(g for g in out["result"]["gaps"] if g["evidence_ids"] == [e.id])

    june = scrap("2026-06")
    assert (
        june.status == "NEEDS_REVIEW"
        and june.second_reading
        and june.second_reading.agrees
        and june.second_reading.corrected_from == "13.4"
    )
    g = gap_for(june)
    assert g["kind"] == "review_corrected" and g["params"]["crossed"] == "13.4" and g["params"]["balance"]["supports"] == "first"
    assert any("13.4 crossed out" in ev.output_summary for ev in out["run"].events if ev.agent == "HumanReview")
    july = scrap("2026-07")
    assert july.second_reading and not july.second_reading.agrees and gap_for(july)["kind"] == "review"


@pytest.mark.parametrize("model", ["gemini-2.5-flash", "veo-3-preview", "deep-research-pro-preview-12-2025"])
def test_forbidden_models_are_rejected(model: str) -> None:
    with pytest.raises(ValueError):
        llm._check_model(model)


class FakeVoice(FakeGemini):
    async def transcribe(self, model: str, audio: dict[str, Any], transcription_config: dict[str, Any]) -> LLMResult:
        assert model == "gemini-3.5-transcribe" and transcription_config["language_codes"] == ["hi-IN"]
        return LLMResult("अगस्त में साढ़े चौदह टन स्क्रैप निकला", model, 50, 20, 4)

    async def json(
        self, model: str, system: str, parts: list[dict[str, Any]], schema: dict[str, Any], thinking_level: str = "low", retries: int = 2
    ) -> LLMResult:
        if "found" in schema.get("properties", {}):
            return LLMResult(
                {"found": True, "value_text": "साढ़े चौदह टन", "value_num": "14.5", "unit": "t", "quote": "साढ़े चौदह टन स्क्रैप"},
                model,
                80,
                30,
                3,
            )
        return await super().json(model, system, parts, schema, thinking_level, retries)


def test_voice_note_closes_a_gap_after_confirmation(mem_store: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """X1: a Hindi voice answer becomes evidence (audio + transcript), amber until a person confirms it."""
    from fastapi.testclient import TestClient

    from app.main import app

    llm.set_gemini(FakeVoice())
    monkeypatch.setenv("GEMINI_VERTEX_READY", "1")
    try:
        with TestClient(app) as c:
            c.post("/api/demo/load", json={"replay": True, "shared": True})
            r = c.post(
                "/api/projects/demo-shivalik/voice",
                data={"field_key": "scrap_t", "process": "P2", "period": "2026-08", "lang": "hi"},
                files={"audio": ("v.webm", b"\x1a\x45\xdf\xa3fake-webm", "audio/webm")},
            )
            assert r.status_code == 200, r.text
            ev = r.json()["evidence"]
            assert ev["value_num"] == "14.5" and ev["status"] == "NEEDS_REVIEW" and "साढ़े चौदह" in ev["notes"]
            gaps = c.get("/api/projects/demo-shivalik/results").json()["gaps"]
            assert any(g["group"] == "review" and ev["id"] in g["evidence_ids"] for g in gaps)
            ok = c.patch(f"/api/projects/demo-shivalik/evidence/{ev['id']}", json={"action": "approve", "user": "Supervisor"})
            assert ok.json()["evidence"]["status"] == "APPROVED"
            audio = c.get(f"/api/projects/demo-shivalik/documents/{ev['doc_id']}/image")
            assert audio.headers["content-type"].startswith("audio/webm")
    finally:
        llm.set_gemini(None)


def test_voice_needs_live_gemini(mem_store: Any) -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        c.post("/api/demo/load", json={"replay": True, "shared": True})
        r = c.post(
            "/api/projects/demo-shivalik/voice",
            data={"field_key": "scrap_t", "process": "P2", "period": "2026-08"},
            files={"audio": ("v.webm", b"x", "audio/webm")},
        )
        assert r.status_code == 503
