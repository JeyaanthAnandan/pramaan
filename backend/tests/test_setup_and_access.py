"""Own projects: passcode privacy, product-line setup (typed or proposed by the ProductLines agent),
one consistent buyer cost, readiness per product line and the operations levers."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.agents import llm
from app.agents.llm import LLMResult
from app.demo import loader
from app.evidence.models import Run
from app.evidence.store import store
from app.main import app
from tests.test_agent_scenarios import FakeGemini

LINES = [
    {
        "name": "Carbon-steel hexagon bolts",
        "cn": "7318 15 82",
        "precursor_name": "Carbon-steel wire rod",
        "precursor_cn": "72139149",
        "precursor_supplier": "Northern Wire Rod Mills (SAMPLE)",
    },
    {
        "name": "Stainless hexagon bolts",
        "cn": "73181575",
        "precursor_name": "Stainless wire rod",
        "precursor_cn": "7221 00 10",
        "precursor_supplier": "Indus Stainless Rods (SAMPLE)",
    },
]


@pytest.fixture()
def client(mem_store: Any):  # noqa: ARG001
    with TestClient(app) as c:
        yield c


def _own(c: TestClient, **kw: Any) -> dict[str, Any]:
    r = c.post("/api/projects", json={"name": "CBAM 2026", "company": "Test Fasteners (SAMPLE)", **kw})
    assert r.status_code == 200, r.text
    return r.json()


# ------------------------------------------------------------------ privacy


def test_own_project_is_private(client: TestClient) -> None:
    p = _own(client)
    pid, code = p["id"], p["access_key"]
    assert p["protected"] is True and "access_hash" not in p and len(code) == 14
    assert client.get(f"/api/projects/{pid}").status_code == 200  # creator's cookie
    assert "access_hash" not in client.get(f"/api/projects/{pid}").json()["project"]
    with TestClient(app) as other:
        assert other.get(f"/api/projects/{pid}").status_code == 401
        assert other.get(f"/api/projects/{pid}/evidence").status_code == 401
        assert other.post(f"/api/projects/{pid}/unlock", json={"passcode": "AAAA-BBBB-CCCC"}).status_code == 401
        assert other.get(f"/api/projects/{pid}", headers={"X-Pramaan-Key": code.lower().replace("-", " ")}).status_code == 200
        assert other.post(f"/api/projects/{pid}/unlock", json={"passcode": code}).status_code == 200
        assert other.get(f"/api/projects/{pid}").status_code == 200  # cookie set by unlock


def test_the_owner_deletes_an_own_project_for_good(client: TestClient) -> None:
    """Photos, readings and links all go, only with the passcode; the sample cannot be deleted."""
    import io

    from PIL import Image

    from app.config import settings
    from app.evidence.models import ShareLink

    p = _own(client)
    pid = p["id"]
    png = io.BytesIO()
    Image.new("RGB", (60, 80), (240, 240, 235)).save(png, format="PNG")
    assert client.post(f"/api/projects/{pid}/documents", files={"files": ("bill.png", png.getvalue(), "image/png")}).status_code == 200
    folder = settings().data_dir / "blobs" / pid
    assert any(folder.rglob("*.jpg"))
    store().put_share(ShareLink(token=f"t-{pid}", project_id=pid, summary_snapshot={}))
    with TestClient(app) as other:  # no passcode
        assert other.delete(f"/api/projects/{pid}").status_code == 401
    r = client.delete(f"/api/projects/{pid}")
    assert r.status_code == 200 and r.json() == {"deleted": pid, "documents": 1, "files": 1}
    assert client.get(f"/api/projects/{pid}").status_code == 404
    assert not folder.exists() and store().get_share(f"t-{pid}") is None
    sample = client.post("/api/demo/load", json={"replay": True}).json()["project_id"]
    assert client.delete(f"/api/projects/{sample}").status_code == 403


def test_sample_copies_stay_open(client: TestClient) -> None:
    pid = client.post("/api/demo/load", json={"replay": True}).json()["project_id"]
    with TestClient(app) as other:
        r = other.get(f"/api/projects/{pid}")
        assert r.status_code == 200 and r.json()["project"]["protected"] is False


# ------------------------------------------------------------------ CN lookup and product lines


def test_cn_lookup_and_search(client: TestClient) -> None:
    g = client.get("/api/refdata/cn/73181575", params={"country": "India"}).json()
    assert g["ok"] and "stainless" in g["description"].lower() and g["default_value"]
    rod = client.get("/api/refdata/cn/72210010", params={"country": "India", "role": "precursor"}).json()
    assert rod["ok"] and rod["cn_display"] == "7221 00 10"
    assert not client.get("/api/refdata/cn/1234").json()["ok"]
    assert not client.get("/api/refdata/cn/76011000").json()["ok"]  # aluminium, not iron or steel
    hits = client.get("/api/refdata/cn/search", params={"q": "hexagon bolts stainless"}).json()
    assert any(h["cn"] == "73181575" for h in hits)
    assert "Viet Nam" in client.get("/api/refdata/countries").json()


def test_product_lines_are_validated_and_confirmed(client: TestClient) -> None:
    pid = _own(client)["id"]
    bad = client.put(f"/api/projects/{pid}/product-lines", json={"lines": [{**LINES[0], "cn": "7318"}]})
    assert bad.status_code == 422 and "8 digits" in str(bad.json())
    dup = client.put(f"/api/projects/{pid}/product-lines", json={"lines": [LINES[0], LINES[0]]})
    assert dup.status_code == 422
    ok = client.put(f"/api/projects/{pid}/product-lines", json={"lines": LINES}).json()
    assert [x["cn"] for x in ok["processes"]] == ["73181582", "73181575"] and ok["processes_confirmed"] is True
    assert [s["supplier"] for s in ok["supplier_requests"]] == [LINES[0]["precursor_supplier"], LINES[1]["precursor_supplier"]]
    assert ok["processes"][1]["cn_desc"].lower().startswith("hexagon screws and bolts, of stainless")
    demo = client.post("/api/demo/load", json={"replay": True}).json()["project_id"]
    assert client.put(f"/api/projects/{demo}/product-lines", json={"lines": LINES}).status_code == 409


def test_setup_fields_and_period(client: TestClient) -> None:
    pid = _own(client, months_to=6)["id"]
    p = client.get(f"/api/projects/{pid}").json()["project"]
    assert p["months"][-1] == "2026-06" and "Jan-Jun 2026" in p["period_label"]
    r = client.patch(f"/api/projects/{pid}", json={"company": "Kaveri Wire (SAMPLE)", "city": "Coimbatore", "months_to": 12}).json()
    assert r["company"] == "Kaveri Wire (SAMPLE)" and len(r["months"]) == 12 and "full year" in r["period_label"]
    assert client.patch(f"/api/projects/{pid}", json={"country": "Atlantis"}).status_code == 422
    assert client.post("/api/projects", json={"name": "x", "company": "y", "country": "Atlantis"}).status_code == 422


class FakeSetup(FakeGemini):
    """Also answers the ProductLines agent: two lines from the invoices plus one code that is not a
    steel good, which the refdata check must reject."""

    async def json(
        self, model: str, system: str, parts: list[dict[str, Any]], schema: dict[str, Any], thinking_level: str = "low", retries: int = 2
    ) -> LLMResult:
        if "lines" in schema.get("properties", {}):
            self.calls.append("product_lines")
            assert sum(1 for p in parts if p["type"] == "image") >= 2
            out = [{**x, "doc_ids": [], "rationale": "export and rod invoices"} for x in LINES]
            out.append({**LINES[0], "name": "Aluminium bars", "cn": "76042100"})
            return LLMResult({"lines": out, "notes": ""}, model, 9000, 300, 40)
        return await super().json(model, system, parts, schema, thinking_level, retries)


def test_product_lines_agent_sets_up_an_own_project(mem_store: Any) -> None:
    """Live path with a scripted model: no product lines set -> the ProductLines node proposes them
    from the invoices, the CN check rejects the aluminium code, values are assigned to the proposed
    lines, and the lines wait for the owner's confirmation."""
    from app.agents.workflow import execute

    fake = FakeSetup()
    llm.set_gemini(fake)
    try:
        with TestClient(app) as c:
            pid = _own(c)["id"]
            store().put_documents(loader.demo_documents(pid))
            p = store().get_project(pid)
            assert p is not None and not p.processes
            run = Run(project_id=pid, mode="live")
            store().put_run(run)
            asyncio.run(execute(run, p, "live"))
            r = store().get_run(pid, run.id)
            assert r is not None and r.status == "done", r.error if r else ""
            ev = [e for e in r.events if e.agent == "ProductLines" and e.status == "done"]
            assert ev and ev[0].model == "gemini-3.8-flash" and "1 rejected" in ev[0].output_summary
            p = store().get_project(pid)
            assert p is not None and [x.source for x in p.processes] == ["ai", "ai"] and not p.processes_confirmed
            res = c.get(f"/api/projects/{pid}/results").json()
            p1 = next(x for x in res["processes"] if x["id"] == "P1")
            assert abs(Decimal(p1["see"]) - Decimal("2.039")) <= Decimal("0.002")
            assert any(g["id"] == "setup.product_lines" and g["status"] == "amber" for g in res["gaps"])
            lines = [{**x, "cn": x["cn"], "source": "ai"} for x in c.get(f"/api/projects/{pid}").json()["project"]["processes"]]
            assert c.put(f"/api/projects/{pid}/product-lines", json={"lines": lines, "confirm": True}).status_code == 200
            res = c.get(f"/api/projects/{pid}/results").json()
            assert not any(g["id"] == "setup.product_lines" for g in res["gaps"])
    finally:
        llm.set_gemini(None)


def test_replay_without_product_lines_says_what_to_do(mem_store: Any) -> None:
    from app.agents.workflow import execute

    with TestClient(app) as c:
        pid = _own(c)["id"]
        p = store().get_project(pid)
        assert p is not None
        run = Run(project_id=pid, mode="replay")
        store().put_run(run)
        asyncio.run(execute(run, p, "replay"))
        r = store().get_run(pid, run.id)
        assert r is not None and r.status == "error" and "No product lines" in (r.error or "")


def test_suggest_needs_live_gemini(client: TestClient) -> None:
    pid = _own(client)["id"]
    assert client.post(f"/api/projects/{pid}/product-lines/suggest").status_code == 503


# ------------------------------------------------------------------ one buyer cost, readiness, operations


@pytest.fixture()
def sample(client: TestClient) -> tuple[TestClient, str]:
    pid = client.post("/api/demo/load", json={"replay": True}).json()["project_id"]
    return client, pid


def test_buyer_cost_is_the_cheaper_path(sample: tuple[TestClient, str]) -> None:
    c, pid = sample
    r = c.get(f"/api/projects/{pid}/results").json()
    p = {x["id"]: x for x in r["processes"]}
    b1, b2 = p["P1"]["buyer"], p["P2"]["buyer"]
    assert b1["basis_2026"] == "actual" and b1["buyer_eur_t"] == b1["actual_eur_t"] and b1["cost_buyer_eur"] == b1["cost_actual_eur"]
    # stainless: the rod is on its marked-up default, so the good's own default is cheaper for the buyer
    assert b2["basis_2026"] == "default" and b2["buyer_eur_t"] == b2["default_eur_t"] and b2["cost_buyer_eur"] == b2["cost_default_eur"]
    assert Decimal(b2["cost_default_eur"]) < Decimal(b2["cost_actual_eur"])
    assert abs(Decimal(b2["cost_default_eur"]) / Decimal(p["P2"]["exports_t"]) - Decimal(b2["default_eur_t"])) < 2
    assert Decimal(b2["supplier_saving_eur_t"]) == Decimal(b2["buyer_eur_t"]) - Decimal(b2["with_supplier_eur_t"])
    s0 = r["money"]["series"]["P2"][0]
    assert s0["basis"] == "default" and s0["buyer_eur_t"] == s0["default_eur_t"]
    tree = r["calc_tree"]
    assert tree["P2.cost_buyer.total"]["children"] == ["P2.cost.total", "P2.cost_default.total"]


def test_readiness_per_product_line(sample: tuple[TestClient, str]) -> None:
    c, pid = sample
    rd = c.get(f"/api/projects/{pid}/results").json()["readiness"]
    assert rd["lines_total"] == 2 and rd["lines_ready"] == 1
    assert rd["by_process"]["P1"]["ready"] is True and rd["by_process"]["P2"]["precursor"] == "default"


def test_operations_kpis(sample: tuple[TestClient, str]) -> None:
    c, pid = sample
    ops = c.get(f"/api/projects/{pid}/results").json()["operations"]
    assert abs(Decimal(ops["gas_gj_per_t"]) - Decimal("3.5")) < Decimal("0.01")  # = EC Example 3
    assert abs(Decimal(ops["processes"]["P1"]["scrap_pct"]) - 15) < Decimal("0.01")
    assert abs(Decimal(ops["processes"]["P2"]["yield_pct"]) - 82) < Decimal("0.01")
    assert len(ops["processes"]["P1"]["monthly"]) == 9 and len(ops["gas_monthly"]) == 9


def test_whatif_yield_and_gas_levers(sample: tuple[TestClient, str]) -> None:
    c, pid = sample
    base = c.post(f"/api/projects/{pid}/whatif", json={"process_id": "P1"}).json()
    assert abs(Decimal(base["see"]) - Decimal(base["see_now"])) < Decimal("1e-9")
    assert Decimal(base["plant"]["rod_saved_t_per_year"]) == 0
    w = c.post(f"/api/projects/{pid}/whatif", json={"process_id": "P1", "scrap_pct": "10"}).json()
    assert abs(Decimal(w["inputs"]["m"]) - Decimal(1) / Decimal("0.9")) < Decimal("1e-9")
    assert Decimal(w["see"]) < Decimal(base["see"])
    assert Decimal(w["plant"]["rod_saved_t_per_year"]) > 100  # 1,275 t x 12/9 x (1.176 - 1.111)
    # SEFA falls with the rod per tonne too, so the 2026 buyer cost moves far less than SEE
    d_see = Decimal(base["see"]) - Decimal(w["see"])
    d_cost26 = Decimal(base["series"][0]["eur_t"]) - Decimal(w["series"][0]["eur_t"])
    d_cost34 = Decimal(base["series"][-1]["eur_t"]) - Decimal(w["series"][-1]["eur_t"])
    assert 0 < d_cost26 < d_cost34 and d_see > 0
    g = c.post(f"/api/projects/{pid}/whatif", json={"process_id": "P1", "gas_gj_per_t": "3.0"}).json()
    ratio = Decimal(g["direct"]) / Decimal(g["direct_now"])
    assert abs(ratio - Decimal("3.0") / Decimal(base["current"]["gas_gj_per_t"])) < Decimal("1e-9")
    assert Decimal(g["plant"]["gas_saved_gj_per_year"]) > 0
    s = c.post(f"/api/projects/{pid}/whatif", json={"process_id": "P2", "rod_see": "1.783", "rod_sefa": "0.919"}).json()
    assert s["series"][0]["basis_now"] == "default" and s["series"][0]["basis"] == "actual"
    assert c.post(f"/api/projects/{pid}/whatif", json={"process_id": "P1", "scrap_pct": "75"}).status_code == 422


def test_results_saved_by_an_older_engine_are_recomputed(sample: tuple[TestClient, str]) -> None:
    c, pid = sample
    old = {k: v for k, v in store().get_latest_result(pid).items() if k not in {"operations", "period_months"}}  # type: ignore[union-attr]
    for p in old["processes"]:
        p.pop("buyer", None)
    store().put_result(pid, "old-engine", old)
    r = c.get(f"/api/projects/{pid}/results").json()
    assert "operations" in r and all("buyer" in p for p in r["processes"] if "see" in p)
