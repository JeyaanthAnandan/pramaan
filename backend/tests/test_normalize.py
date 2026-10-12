"""Clean-up of the Extractor's output (app/agents/normalize.py), the corrected-figure rule and the
per-call time limit. The cases are the slips seen in the first live run on Cloud Run (2026-10-12)."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any

import pytest

from app.agents import llm, replay
from app.agents.normalize import canonical_text, clean_number, document_period, iso_date, normalize_fields
from app.agents.readers import parse_fields
from app.agents.second_reader import compare
from app.demo import loader
from app.evidence.models import ExtractedField


def _f(key: str, text: str, num: str | None = None, **kw: Any) -> ExtractedField:
    return ExtractedField(field_key=key, value_text=text, value_num=num, doc_id="d", **kw)


def test_supplier_statement_values_get_the_line_of_the_printed_cn_code() -> None:
    p = loader.demo_project()
    fs = [
        _f("supplier", "Northern Wire Rod Mills (SAMPLE)"),
        _f("product_cn", "Wire rod, carbon steel — CN 7213 91 49", process="P1"),
        _f("see", "1.567", "1.567"),  # the live run left these without a product line
        _f("sefa", "1.242", "1.242"),
        _f("verification_ref", "KA-VR-2026-0147 dated 2026-10-02", process="P1"),
    ]
    normalize_fields(fs, "supplier_emissions_statement", p)
    by = {f.field_key: f for f in fs}
    assert by["see"].process == by["sefa"].process == "P1" and by["supplier"].process is None
    assert by["product_cn"].value_text == "7213 91 49"
    assert by["verification_ref"].value_text == "KA-VR-2026-0147"
    assert by["see"].unit == "t CO2e/t"


def test_input_invoice_number_with_model_text_appended_is_salvaged() -> None:
    p = loader.demo_project()
    fs = [
        _f("cn_code", "7221 00 10"),
        _f("grade", "AISI 304", process="P2"),
        _f("tonnes", "390.000", "390.000ecd unit: t scope: process -> unit: t, value_num: 390.000 process: P2"),
        _f("cr_pct", "18.20", "18.20", unit="%", period="2026-06"),
    ]
    normalize_fields(fs, "precursor_invoice", p)
    by = {f.field_key: f for f in fs}
    assert (by["tonnes"].value_num, by["tonnes"].unit, by["tonnes"].process) == ("390.000", "t", "P2")
    assert by["cr_pct"].process == "P2" and by["cr_pct"].period is None
    assert by["grade"].process is None  # a document-level field belongs to no line


def test_indian_hsn_code_matches_the_line_on_its_six_digit_heading() -> None:
    p = loader.demo_project()
    fs = [_f("cn_code", "HSN 7213 91 90"), _f("tonnes", "120.5", "120.5")]
    normalize_fields(fs, "precursor_invoice", p)
    assert fs[1].process == "P1"


def test_document_level_and_line_fields_lose_a_stray_period() -> None:
    p = loader.demo_project()
    gas = [_f("invoice_no", "DCG/26/08/030508", period="2026-08"), _f("scm", "21,192", "21192", period="2026-08", process="P1")]
    normalize_fields(gas, "gas_invoice", p)
    assert gas[0].period is None and (gas[1].period, gas[1].process) == ("2026-08", None)
    exp = [
        _f("cn_code", "7318 15 82", period="2026-Q2", process="P1"),
        _f("net_mass_kg", "300,000", "300000", period="2026-Q2", process="P1"),
    ]
    normalize_fields(exp, "export_invoice", p)
    assert (exp[0].period, exp[0].process) == (None, "P1") and exp[1].period == "2026-Q2"


def test_numbers_and_text_fields() -> None:
    assert clean_number("1,10,460.80", "", numeric=True) == "110460.80"
    assert clean_number(None, "19,514 SCM", numeric=True) == "19514"
    assert clean_number("03-04-2026", "03-04-2026", numeric=False) == "03-04-2026"  # a date is not the number 3
    assert canonical_text("invoice_no", "INV/22 dt. 03.04.2026") == "INV/22"
    assert canonical_text("invoice_no", "UPDATE-2026-11") == "UPDATE-2026-11"
    assert canonical_text("cn_code", "7318 15 82 / 7318 15 75") == "7318 15 82 / 7318 15 75"  # two codes: left as read


def test_ground_truth_passes_through_unchanged() -> None:
    """Idempotent on correct output: the replayed sample (and so every golden number) is untouched."""
    p = loader.demo_project()
    for name, doc in replay.truth().items():
        before = parse_fields({"fields": replay.extract(name)}, "d")
        after = normalize_fields([f.model_copy() for f in before], doc["doc_type"], p)
        assert [f.model_dump() for f in after] == [f.model_dump() for f in before], name
        assert document_period(after, doc["period"]) == doc["period"], name


def test_dates_from_model_strings() -> None:
    assert iso_date("2026-05-01Bytes") == "2026-05-01"
    assert iso_date("2026-07-01Customer/Bill period start date: 01-07-2026 -> 2026-07-01") == "2026-07-01"
    assert iso_date("2026-09-01T00:00:00Z") == "2026-09-01"
    assert iso_date("31-01-2026") == "2026-01-31"
    assert iso_date("2026-13-01") == "" and iso_date(None) == ""


def test_document_period_from_its_own_values() -> None:
    gas = [_f("period_start", "01-02-2026"), _f("period_end", "28-02-2026")]
    assert document_period(gas, ["2026-02-01T00:00:00.000Z", ""]) == ["2026-02-01", "2026-02-28"]
    reg = [_f("produced_t", "10", "10", period="2026-06"), _f("produced_t", "11", "11", period="2026-09")]
    assert document_period(reg, ["2026-06-01Grade/Month start", ""]) == ["2026-06-01", "2026-09-30"]
    stmt = [_f("period", "01-01-2026 to 30-09-2026")]
    assert document_period(stmt, ["2026-01-01-00-00-00", ""]) == ["2026-01-01", "2026-09-30"]


def test_second_reader_may_read_the_line_under_a_name() -> None:
    r2 = {"value_text": "Rhein Befestigungstechnik GmbH (SAMPLE)\nHafenstrasse 12, 47119 Duisburg", "legible": True}
    assert compare("Rhein Befestigungstechnik GmbH (SAMPLE)", None, "", r2, "m", [0, 0, 1, 1]).agrees
    longer_id = {"value_text": "KA-VR-2026-01478", "legible": True}
    assert not compare("KA-VR-2026-0147", None, "", longer_id, "m", [0, 0, 1, 1]).agrees


def test_figure_corrected_by_hand_goes_to_a_person() -> None:
    sr = compare(
        "15.4", "15.4", "t", {"value_text": "15.4", "value_num": "15.4", "crossed_out": "15.9", "legible": True}, "m", [0, 0, 1, 1]
    )
    assert sr.agrees and sr.corrected_from == "15.9" and "crossed out" in sr.reason
    clean = compare("15.4", "15.4", "t", {"value_text": "15.4", "crossed_out": "", "legible": True}, "m", [0, 0, 1, 1])
    assert clean.corrected_from is None


def test_a_stalled_call_is_cut_off_and_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    real_sleep = asyncio.sleep
    calls = {"n": 0}

    async def create(**body: Any) -> Any:
        calls["n"] += 1
        if calls["n"] == 1:
            await real_sleep(5)  # the stall
        return SimpleNamespace(
            output_text=json.dumps({"doc_type": "gas_invoice"}),
            steps=None,
            usage=SimpleNamespace(total_input_tokens=3, total_output_tokens=2, total_thought_tokens=0),
        )

    async def no_wait(_s: float) -> None:
        return None

    monkeypatch.setattr(llm, "TIMEOUT_S", {"low": 0.05})
    monkeypatch.setattr(asyncio, "sleep", no_wait)
    g = llm.Gemini.__new__(llm.Gemini)
    g._sem, g._sem_lite, g.use_interactions = asyncio.Semaphore(2), asyncio.Semaphore(2), True
    g.client = SimpleNamespace(aio=SimpleNamespace(interactions=SimpleNamespace(create=create)))
    r = asyncio.run(g.json("gemini-3.8-flash", "sys", [llm.text_part("x")], {"type": "object"}, thinking_level="low"))
    assert r.data == {"doc_type": "gas_invoice"} and calls["n"] == 2


def test_copilot_falls_back_to_cited_pages_when_gemini_does_not_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.copilot import service

    real = service.settings()
    fake = SimpleNamespace(gemini_configured=True, model_flash=real.model_flash, regulation_dir=real.regulation_dir, data_dir=real.data_dir)
    monkeypatch.setattr(service, "settings", lambda: fake)

    class Silent:
        async def text(self, *a: Any, **k: Any) -> Any:
            raise TimeoutError

    llm.set_gemini(Silent())
    try:
        a = asyncio.run(service.answer("Is scrap counted?"))
    finally:
        llm.set_gemini(None)
    assert a["mode"] == "retrieval" and a["citations"] and "did not answer" in a["note"]
