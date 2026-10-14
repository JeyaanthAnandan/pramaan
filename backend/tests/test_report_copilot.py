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
        "[F:P2.supplier.saving_t] [Guidance 3, p. 115]."
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
