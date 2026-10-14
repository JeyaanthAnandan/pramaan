"""Ask about this report: answers come from the engine's own figures, cite them, and never carry a
number that is not in the report (the Explainer's numbers guard)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.agents import llm
from app.agents.llm import LLMResult
from app.main import app

PID = "demo-shivalik"


@pytest.fixture()
def client(mem_store):  # noqa: ARG001
    with TestClient(app) as c:
        assert c.post("/api/demo/load", json={"replay": True, "shared": True}).status_code == 200
        yield c


class Scripted:
    def __init__(self, text: str | None = None, fail: bool = False) -> None:
        self.reply, self.fail, self.prompts = text, fail, []

    async def text(self, model: str, system: str, parts: list[dict[str, Any]], thinking_level: str = "low", tools: Any = None) -> LLMResult:
        self.prompts.append(parts[0]["text"])
        if self.fail:
            raise TimeoutError
        return LLMResult(self.reply, model, 900, 80, 5)


def _live(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.copilot import report

    real = report.settings()
    monkeypatch.setattr(report, "settings", lambda: SimpleNamespace(gemini_configured=True, model_flash=real.model_flash))


def _ask(c: TestClient, q: str) -> dict[str, Any]:
    r = c.post(f"/api/projects/{PID}/ask", json={"question": q})
    assert r.status_code == 200, r.text
    return r.json()


def test_without_gemini_the_report_figures_answer(client: TestClient) -> None:
    a = _ask(client, "What default value applies to my stainless bolts from India?")
    assert a["mode"] == "facts" and a["note"] == "no_gemini"
    top = {f["id"]: f for f in a["facts"]}
    assert "ref.dv.73181575" in a["relevant"][:3] and top["ref.dv.73181575"]["value"] == "5.720"
    assert "P2.y2026.default_see" in a["relevant"]


def test_grounded_answer_cites_facts_that_open_the_lens(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _live(monkeypatch)
    fake = Scripted(
        "Indus Stainless Rods has not sent verified data, so the rod is on the EU default with the 2026 mark-up, 7.128 t CO2/t "
        "[F:P2.rod.see]. On your data the buyer would pay 575.73 EUR/t [F:P2.y2026.cost_actual], more than 402.24 EUR/t on EU "
        "defaults [F:P2.y2026.cost_default], so the buyer declares the defaults. Verified supplier data would save 306 EUR/t "
        "[F:P2.supplier.saving_t]."  # no guidance page: p. 115 is not among the pages retrieved for this question
    )
    llm.set_gemini(fake)
    try:
        a = _ask(client, "Why is my stainless line on the EU default?")
    finally:
        llm.set_gemini(None)
    assert a["mode"] == "grounded" and a["answer"].startswith("Indus")
    assert a["cited"] == ["P2.rod.see", "P2.y2026.cost_actual", "P2.y2026.cost_default", "P2.supplier.saving_t"]
    nodes = {f["id"]: f["node"] for f in a["facts"]}
    assert nodes["P2.rod.see"] == "P2.rod.see"  # the chip opens the Evidence Lens on that node
    assert "[F:P2.see]" in fake.prompts[0] and "Question: Why is my stainless line" in fake.prompts[0]


def test_an_answer_with_a_number_not_in_the_report_is_withheld(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _live(monkeypatch)
    llm.set_gemini(Scripted("Your buyer pays about 999 EUR/t for stainless bolts [F:P2.y2026.cost_default]."))
    try:
        a = _ask(client, "What does my buyer pay per tonne?")
    finally:
        llm.set_gemini(None)
    assert a["mode"] == "facts" and a["answer"] is None and a["note"] == "withheld" and "999" in a["rejected_numbers"]
    assert any(fid.endswith("cost_default") for fid in a["relevant"])


def test_when_gemini_does_not_answer_the_facts_still_do(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _live(monkeypatch)
    llm.set_gemini(Scripted(fail=True))
    try:
        a = _ask(client, "What should I do first?")
    finally:
        llm.set_gemini(None)
    assert a["mode"] == "facts" and a["note"] == "no_answer" and a["relevant"]


def test_private_project_needs_its_passcode_to_ask(client: TestClient) -> None:
    own = client.post("/api/projects", json={"name": "Own", "company": "Test Co (SAMPLE)"}).json()
    pid = own["project"]["id"] if "project" in own else own["id"]
    assert TestClient(app).post(f"/api/projects/{pid}/ask", json={"question": "What is my SEE?"}).status_code == 401


def test_explaining_a_lens_number_puts_its_formula_and_inputs_first(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    q = "How is the SEE of the stainless rod worked out?"
    a = client.post(f"/api/projects/{PID}/ask", json={"question": q, "node": "P2.rod.see"}).json()
    assert a["relevant"][0] == "P2.rod.see" and {"ref.dv.72210010", "y2026.default_markup"} <= set(a["relevant"])
    first = next(f for f in a["facts"] if f["id"] == "P2.rod.see")
    assert "formula" in first["label"] and first["node"] == "P2.rod.see"
    _live(monkeypatch)
    fake = Scripted(
        "The default for stainless rod from India is 6.480 [F:ref.dv.72210010], plus the 2026 mark-up of 0.100 [F:y2026.default_markup]: 7.128 t CO2/t [F:P2.rod.see]."
    )
    llm.set_gemini(fake)
    try:
        g = client.post(f"/api/projects/{PID}/ask", json={"question": q, "node": "P2.rod.see"}).json()
    finally:
        llm.set_gemini(None)
    assert g["mode"] == "grounded" and g["cited"] == ["ref.dv.72210010", "y2026.default_markup", "P2.rod.see"]
    assert "[F:P2.rod.see]" in fake.prompts[0].split("FACTS:")[1].split("\n")[1]  # the focus is the first fact


def test_numbers_inside_a_product_name_are_not_figures() -> None:
    """A live Tamil answer about a nut maker (14 Oct 2026) named the line "stainless steel A2-70, ISO 4032 M8"
    in full and was withheld for "70". Numbers printed inside the report's own facts are allowed; a figure
    the model worked out itself still is not."""
    from app.copilot.report import _check

    fs = [
        {
            "id": "P2.product",
            "label": "Product line P2",
            "value": "Hexagon nuts, stainless steel A2-70, ISO 4032 M8, CN 7318 16 39",
            "unit": "",
        },
        {"id": "P2.y2026.cost_actual", "label": "Buyer's cost per t, 2026, your data", "value": "121.54", "unit": "EUR/t"},
    ]
    _, bad = _check("P2 (A2-70 நட்டுகள், ISO 4032 M8): 121.54 EUR/t [F:P2.y2026.cost_actual]", fs, {}, [])
    assert bad == []
    _, bad = _check("P2: 121.54 EUR/t, about 13,175 INR [F:P2.y2026.cost_actual]", fs, {}, [])
    assert bad == ["13175"]


class Sequence:
    """Answers in turn: the first answer, then the repaired one."""

    def __init__(self, *replies: str) -> None:
        self.replies, self.prompts = list(replies), []

    async def text(self, model: str, system: str, parts: list[dict[str, Any]], thinking_level: str = "low", tools: Any = None) -> LLMResult:
        self.prompts.append(parts[0]["text"])
        return LLMResult(self.replies.pop(0), model, 900, 80, 5)


def test_a_number_must_be_the_one_its_cited_fact_shows(client: TestClient) -> None:
    """2026-10-14 review: the stainless line's SEE said as the carbon line's passed, because 8.889 is in the
    report; and 41 of the 94 two-digit numbers passed as a rounding of some figure in the 380-node tree."""
    from app.copilot.report import _check, facts
    from app.evidence.store import store

    p, r = store().get_project(PID), store().get_latest_result(PID)
    assert p and r
    fs, tree = facts(p, r), r["calc_tree"]
    assert _check("Your carbon bolts' SEE is 2.040 t CO2/t [F:P1.see].", fs, tree, [])[1] == []
    assert _check("Your carbon bolts' SEE is 8.889 t CO2/t [F:P1.see].", fs, tree, [])[1] == ["8.889"]  # P2's SEE
    assert _check("Your SEE is 2.040 t CO2/t. About 37% is from gas [F:P1.see].", fs, tree, [])[1] == ["2.040", "37"]
    assert _check("SEE is 2.040 t CO2/t. [F:P1.see]", fs, tree, [])[1] == []  # a citation that opens the next sentence
    # digits in another script are numbers too: "२.०४०" is checked, not skipped
    assert _check("आपका SEE २.०४० t CO2/t है [F:P1.see]।", fs, tree, [])[1] == []
    assert _check("आपका SEE ९.९९९ t CO2/t है [F:P1.see]।", fs, tree, [])[1] == ["9.999"]
    page = {"doc": "Guidance 3", "page": 115, "text": "the mark-up is 10 % in 2026"}
    assert _check("The 2026 mark-up is 10% [Guidance 3, p. 115].", fs, tree, [page])[1] == []
    assert _check("The 2026 mark-up is 30% [Guidance 3, p. 115].", fs, tree, [page])[1] == ["30"]


def test_an_answer_with_an_unbound_number_is_repaired_once(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _live(monkeypatch)
    fake = Sequence(
        "Your carbon bolts' SEE is 8.889 t CO2/t [F:P1.see].",
        "Your carbon bolts' SEE is 2.040 t CO2/t [F:P1.see].",
    )
    llm.set_gemini(fake)
    try:
        a = _ask(client, "What is the SEE of my carbon bolts?")
    finally:
        llm.set_gemini(None)
    assert a["mode"] == "grounded" and "2.040" in a["answer"]
    assert a["guard"] == {"numbers": 1, "repaired": ["8.889"], "withheld": []}
    assert "8.889 is not shown by a fact" in fake.prompts[1]


def test_a_cited_page_the_model_was_not_given_is_withheld(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _live(monkeypatch)
    bad = "Scrap carries zero embedded emissions [Guidance 4, p. 999]."
    llm.set_gemini(Sequence(bad, bad))
    try:
        a = _ask(client, "Is scrap counted?")
    finally:
        llm.set_gemini(None)
    assert a["mode"] == "facts" and a["note"] == "withheld" and "[Guidance 4 p.999]" in a["guard"]["withheld"]


def test_guidance_answers_print_only_what_the_cited_page_prints(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    from app.copilot import service

    real = service.settings()
    fake_cfg = SimpleNamespace(
        gemini_configured=True, model_flash=real.model_flash, regulation_dir=real.regulation_dir, data_dir=real.data_dir
    )
    monkeypatch.setattr(service, "settings", lambda: fake_cfg)
    page = service.retrieve("Is scrap counted?")[0]
    cite = f"[{page['doc']}, p. {page['page']}]"
    invented = f"Scrap counts at 37.5% of its mass {cite}."
    llm.set_gemini(Sequence(invented, invented))
    try:
        a = asyncio.run(service.answer("Is scrap counted?"))
    finally:
        llm.set_gemini(None)
    assert a["mode"] == "retrieval" and a["answer"] is None and "37.5" in a["guard"]["withheld"] and a["passages"]
    good = f"Scrap is taken with zero embedded emissions {cite}."
    llm.set_gemini(Sequence(invented, good))
    try:
        a = asyncio.run(service.answer("Is scrap counted?"))
    finally:
        llm.set_gemini(None)
    assert a["mode"] == "grounded" and a["answer"] == good and a["guard"]["repaired"] == ["37.5"]
    assert service.unsourced("Declarations are due by 31 May 2027 [Guidance 1, p. 1].", []) == ["31"]
