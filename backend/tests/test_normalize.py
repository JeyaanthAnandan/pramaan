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


def test_a_slow_call_is_hedged_and_the_first_answer_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    """Second live run: one extraction stalled past its limit twice in a row, then took 13 s."""
    calls = {"n": 0}

    async def create(**body: Any) -> Any:
        calls["n"] += 1
        n = calls["n"]
        await asyncio.sleep(5 if n == 1 else 0)  # the first request stalls, the backup answers
        return SimpleNamespace(
            output_text=json.dumps({"request": n}),
            steps=None,
            usage=SimpleNamespace(total_input_tokens=3, total_output_tokens=2, total_thought_tokens=0),
        )

    monkeypatch.setattr(llm, "HEDGE_S", {"low": 0.05})
    g = llm.Gemini.__new__(llm.Gemini)
    g._sem, g._sem_lite, g.use_interactions = asyncio.Semaphore(2), asyncio.Semaphore(2), True
    g.client = SimpleNamespace(aio=SimpleNamespace(interactions=SimpleNamespace(create=create)))
    r = asyncio.run(asyncio.wait_for(g.json("gemini-3.8-flash", "sys", [llm.text_part("x")], {"type": "object"}), 2))
    assert r.data == {"request": 2} and calls["n"] == 2


def test_a_failure_names_the_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    async def create(**body: Any) -> Any:
        raise TimeoutError

    async def no_wait(_s: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", no_wait)
    g = llm.Gemini.__new__(llm.Gemini)
    g._sem, g._sem_lite, g.use_interactions = asyncio.Semaphore(2), asyncio.Semaphore(2), True
    g.client = SimpleNamespace(aio=SimpleNamespace(interactions=SimpleNamespace(create=create)))
    with pytest.raises(RuntimeError, match="TimeoutError"):
        asyncio.run(g.json("gemini-3.8-flash", "sys", [llm.text_part("x")], {"type": "object"}))


def test_a_looping_extraction_is_read_again(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fourth live run: scm came back as 20240.000... (~100 zeros) and the rest of the bill was lost."""
    from app.agents import readers

    looped = {"fields": [{"field_key": "scm", "value_text": "20,240", "value_num": "20240." + "0" * 100}]}
    clean = {
        "fields": [{"field_key": "scm", "value_text": "20,240", "value_num": "20240"}, {"field_key": "mmbtu", "value_text": "771.864"}]
    }
    answers = iter([looped, clean])

    class Fake:
        async def json(self, *a: Any, **k: Any) -> Any:
            return llm.LLMResult(next(answers), "gemini-3.8-flash", 1, 1, 1, "")

    monkeypatch.setattr(readers, "gemini", lambda: Fake())
    r = asyncio.run(readers.extract(b"", "image/jpeg", "gas_invoice", loader.demo_project()))
    assert r.data == clean
    assert readers.degenerate(looped) and not readers.degenerate(clean)


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


def test_export_line_without_a_period_gets_the_quarter_of_its_invoice_date() -> None:
    """Second live run (2026-10-13): the 15-06-2026 invoice's carbon line came back with no period,
    and the engine failed the whole run on 'int("?")'."""
    p = loader.demo_project()
    exp = [
        _f("invoice_date", "15-06-2026"),
        _f("cn_code", "7318 15 82", process="P1"),
        _f("net_mass_kg", "300,000", "300000", process="P1"),
        _f("net_mass_kg", "130,000", "130000", period="Q2 2026", process="P2"),
    ]
    normalize_fields(exp, "export_invoice", p)
    assert [f.period for f in exp] == [None, None, "2026-Q2", "2026-Q2"]


def test_engine_shows_an_undated_export_line_as_a_gap_instead_of_failing() -> None:
    from app.cbam.project import compute
    from app.cbam.tree import MISSING
    from app.config import settings
    from app.evidence.models import Document, Evidence

    snap = json.loads((settings().demo_dir / "cache" / "replay_run.json").read_text())
    p = loader.demo_project()
    docs = [Document(**{**d, "project_id": p.id}) for d in snap["documents"]]
    ev = [Evidence(**{**e, "project_id": p.id}) for e in snap["evidence"]]
    next(x for x in ev if x.field_key == "net_mass_kg" and x.process == "P1").period = None
    node = compute(p, ev, docs)["calc_tree"]["P1.exports"]
    assert node["status"] == MISSING and "280,000" in node["note"]


def test_untagged_values_get_their_bill_month_and_their_row_line() -> None:
    """Same run: whole bills read right but with no month, and export quantities with no product line
    (the boxes below are the ones Gemini returned for the 15-06-2026 invoice)."""
    p = loader.demo_project()
    gas = [_f("period_start", "01-05-2026"), _f("period_end", "31-05-2026"), _f("scm", "20,240", "20240")]
    normalize_fields(gas, "gas_invoice", p)
    assert [f.period for f in gas] == ["2026-05"] * 3
    exp = [
        _f("invoice_date", "15-06-2026"),
        _f("cn_code", "7318 15 82", process="P1", box_2d=[427, 473, 440, 556]),
        _f("net_mass_kg", "300,000", "300000", period="2026-Q2", box_2d=[422, 697, 434, 755]),
        _f("cn_code", "7318 15 75", process="P2", box_2d=[465, 475, 477, 557]),
        _f("net_mass_kg", "130,000", "130000", period="2026-Q2", box_2d=[459, 698, 471, 757]),
    ]
    normalize_fields(exp, "export_invoice", p)
    assert [(f.period, f.process) for f in exp if f.field_key == "net_mass_kg"] == [("2026-Q2", "P1"), ("2026-Q2", "P2")]
    register = [_f("period", "April - September 2026"), _f("produced_t", "41.2", "41.2", process="P1")]
    normalize_fields(register, "production_register", p)
    assert register[1].period is None  # a multi-month register: no month to give a row


def test_tamil_voice_note_in_the_wrong_script_is_transcribed_again(monkeypatch: pytest.MonkeyPatch) -> None:
    """Live test: a Tamil note came back in Kannada script ('original script' was not enough)."""
    from app.agents import voice

    answers = iter(["ಆಗಸ್ಟ್ ಮಾದಮ್ ನಾಲ್ಕರೈ ಟನ್", "ஆகஸ்ட் மாதம் நான்கரை டன்"])
    seen: list[str] = []

    class Fake:
        async def text(self, model: str, system: str, parts: Any, **k: Any) -> Any:
            seen.append(system)
            t = next(answers)
            return llm.LLMResult(t, model, 1, 1, 1, t)

    monkeypatch.setattr(voice, "gemini", lambda: Fake())
    r = asyncio.run(voice.transcribe(b"", "audio/wav", "ta"))
    assert r.data.startswith("ஆகஸ்ட்") and len(seen) == 2 and "Tamil script" in seen[0]


def test_a_text_field_is_not_sent_to_review_over_a_unit() -> None:
    """Final live run: identical grade text, first unit "text", second "mm" -> wrongly amber."""
    same = compare("AISI 304, 8.0 mm", None, "text", {"value_text": "AISI 304, 8.0 mm", "unit": "mm"}, "m", [0, 0, 1, 1])
    assert same.agrees
    # numbers still need matching units
    assert not compare("21,192", "21192", "SCM", {"value_text": "21,192", "unit": "kWh"}, "m", [0, 0, 1, 1]).agrees


def test_the_second_readers_printed_digits_count_over_its_own_conversion() -> None:
    """Live runs: Flash-Lite read "380.000" / "699.317" as text, then wrote 380000 / 699317."""
    for text, wrong in (("380.000", "380000"), ("699.317", "699317")):
        r = compare(text, text, "t", {"value_text": text, "value_num": wrong}, "m", [0, 0, 1, 1])
        assert r.agrees, text
    # a real disagreement is still one
    assert not compare("380.000", "380.000", "t", {"value_text": "330.000", "value_num": "330"}, "m", [0, 0, 1, 1]).agrees


def test_a_reference_loses_its_printed_label() -> None:
    assert canonical_text("doc_no", "Ref. NWRM-CBAM-2026-07") == "NWRM-CBAM-2026-07"
    assert canonical_text("invoice_no", "Invoice No: SF/EXP/2526/041") == "SF/EXP/2526/041"
    assert canonical_text("invoice_no", "NOV-2026-11") == "NOV-2026-11"  # a reference that starts like a label


def test_an_untagged_register_is_read_again(monkeypatch: pytest.MonkeyPatch) -> None:
    """Live run: all eight scrap-log figures right, none with its month or product line."""
    from app.agents import readers

    bare = {"fields": [{"field_key": "scrap_t", "value_text": "15.4"}, {"field_key": "scrap_t", "value_text": "25.1"}]}
    tagged = {
        "fields": [
            {"field_key": "scrap_t", "value_text": "15.4", "period": "2026-06", "process": "P2"},
            {"field_key": "scrap_t", "value_text": "25.1", "period": "2026-06", "process": "P1"},
        ]
    }
    answers = iter([bare, tagged])

    class Fake:
        async def json(self, *a: Any, **k: Any) -> Any:
            return llm.LLMResult(next(answers), "gemini-3.8-flash", 1, 1, 1, "")

    monkeypatch.setattr(readers, "gemini", lambda: Fake())
    r = asyncio.run(readers.extract(b"", "image/jpeg", "scrap_log", loader.demo_project()))
    assert r.data == tagged and readers.untagged(bare, "scrap_log") == 1.0


def test_a_page_read_without_product_lines_is_not_read_again(monkeypatch: pytest.MonkeyPatch) -> None:
    """Try one photo has no product lines: dated values without a line are complete, so no second
    (paid) extraction; a value without its month still is not."""
    from app.agents import readers
    from app.evidence.models import Project

    dated = {"fields": [{"field_key": "scrap_t", "value_text": "15.4", "period": "2026-06"}]}
    calls: list[int] = []

    class Fake:
        async def json(self, *a: Any, **k: Any) -> Any:
            calls.append(1)
            return SimpleNamespace(data=dated)

    monkeypatch.setattr(readers, "gemini", lambda: Fake())
    r = asyncio.run(readers.extract(b"", "image/jpeg", "scrap_log", Project(name="Try one photo", company="")))
    assert r.data == dated and len(calls) == 1
    assert readers.untagged(dated, "scrap_log", need_line=False) == 0.0 and readers.untagged(dated, "scrap_log") == 1.0
    assert readers.untagged({"fields": [{"field_key": "scrap_t", "value_text": "15.4"}]}, "scrap_log", need_line=False) == 1.0


def test_a_statement_missing_its_verification_is_read_again_for_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """A live supplier reply (14 Oct 2026) came back with its SEE but no SEFA, verifier or report number,
    so the product line stayed on the EU default. The page is read again for just those fields; the
    first reading's values stay, and a field that was not asked for is not taken from the second."""
    from app.agents import readers

    partial = {
        "fields": [
            {"field_key": "see", "value_text": "1.567 t CO2e / t", "value_num": "1.567", "process": "P1"},
            {"field_key": "route", "value_text": "Blast furnace + basic oxygen furnace (BF-BOF)", "process": "P1"},
        ]
    }
    rest = {
        "fields": [
            {"field_key": "sefa", "value_text": "1.242 t CO2e / t", "value_num": "1.242", "process": "P1"},
            {"field_key": "verifier", "value_text": "Meridian Verification Services GmbH (TEST)", "process": "P1"},
            {"field_key": "verification_ref", "value_text": "MVS-VR-2026-0533", "process": "P1"},
            {"field_key": "see", "value_text": "1.576", "value_num": "1.576", "process": "P1"},
        ]
    }
    answers = iter([partial, rest])
    asks: list[str] = []

    class Fake:
        async def json(self, model: str, system: str, parts: list[dict[str, Any]], *a: Any, **k: Any) -> Any:
            asks.append(parts[0]["text"])
            return llm.LLMResult(next(answers), "gemini-3.8-flash", 100, 50, 10, "")

    monkeypatch.setattr(readers, "gemini", lambda: Fake())
    r = asyncio.run(readers.extract(b"", "image/jpeg", "supplier_emissions_statement", loader.demo_project()))
    assert [f["field_key"] for f in r.data["fields"]] == ["see", "route", "sefa", "verifier", "verification_ref"]
    assert r.data["fields"][0]["value_num"] == "1.567" and r.tokens_in == 200
    assert len(asks) == 2 and "- sefa:" in asks[1] and "- route:" not in asks[1]
    assert readers.missing_keys(r.data, "supplier_emissions_statement") == []


def test_a_complete_statement_is_read_once(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.agents import readers

    full = {
        "fields": [
            {"field_key": k, "value_text": v}
            for k, v in (("see", "2.150"), ("sefa", "0.880"), ("verifier", "M"), ("verification_ref", "R-1"))
        ]
    }
    calls: list[int] = []

    class Fake:
        async def json(self, *a: Any, **k: Any) -> Any:
            calls.append(1)
            return llm.LLMResult(full, "gemini-3.8-flash", 1, 1, 1, "")

    monkeypatch.setattr(readers, "gemini", lambda: Fake())
    r = asyncio.run(readers.extract(b"", "image/jpeg", "supplier_emissions_statement", loader.demo_project()))
    assert r.data == full and len(calls) == 1
