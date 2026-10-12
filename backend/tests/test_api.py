"""End-to-end API tests on the sample factory (replay mode, in-memory store)."""

from __future__ import annotations

import io
import json
import zipfile
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.agents.explainer import guard
from app.config import settings
from app.main import app


@pytest.fixture()
def client(mem_store):  # noqa: ARG001
    with TestClient(app) as c:
        r = c.post("/api/demo/load", json={"replay": True, "shared": True})
        assert r.status_code == 200, r.text
        yield c


PID = "demo-shivalik"


def test_healthz(client: TestClient) -> None:
    h = client.get("/healthz").json()
    assert h["status"] == "ok"
    assert h["models"]["extraction"] == "gemini-3.8-flash"
    assert h["models"]["second_reader"] == "gemini-3.5-flash-lite"
    assert h["refdata"]["files"]
    assert client.get("/api/health").json() == h  # alias used on Cloud Run, where /healthz is reserved


def test_sample_factory_results_match_golden(client: TestClient) -> None:
    r = client.get(f"/api/projects/{PID}/results").json()
    p1 = next(p for p in r["processes"] if p["id"] == "P1")
    p2 = next(p for p in r["processes"] if p["id"] == "P2")
    assert abs(Decimal(p1["see"]) - Decimal("2.039")) <= Decimal("0.002")  # = G1
    assert p1["precursor"]["data"] == "ACTUAL_VERIFIED"
    assert p2["precursor"]["data"] == "DEFAULT_USED"
    wi = r["money"]["what_if"]["P2"][0]
    assert abs(Decimal(wi["see"]) - Decimal("2.371")) <= Decimal("0.002")  # = G2
    assert len(r["money"]["series"]["P1"]) == 9
    assert all(c["status"] in {"pass", "warn", "info"} for c in r["checks"])


def test_every_number_in_report_has_a_source(client: TestClient) -> None:
    r = client.get(f"/api/projects/{PID}/results").json()
    tree = r["calc_tree"]
    for nid, n in tree.items():
        if not n["children"]:
            assert n["source"], f"leaf {nid} without source"
            assert n["source"]["kind"] in {"evidence", "refdata", "assumption", "scenario"}
            if n["source"]["kind"] == "evidence":
                assert n["source"]["box_2d"], f"evidence leaf {nid} without region"


def test_human_approval_turns_amber_green(client: TestClient) -> None:
    ev = client.get(f"/api/projects/{PID}/evidence").json()
    amber = [e for e in ev if e["status"] == "NEEDS_REVIEW"]
    assert len(amber) == 1 and amber[0]["value_text"] == "15.4" and amber[0]["second_reading"]["reading_value"] == "13.4"
    r = client.patch(f"/api/projects/{PID}/evidence/{amber[0]['id']}", json={"action": "approve", "user": "Owner (demo)"})
    assert r.status_code == 200
    e = r.json()["evidence"]
    assert e["status"] == "APPROVED" and e["approved_by"] == "Owner (demo)" and e["approved_at"]
    gaps = client.get(f"/api/projects/{PID}/results").json()["gaps"]
    assert not [g for g in gaps if g["group"] == "review"]


def test_exports(client: TestClient) -> None:
    pdf = client.get(f"/api/projects/{PID}/export/pdf")
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    x = client.get(f"/api/projects/{PID}/export/xlsx")
    assert x.status_code == 200 and x.content[:2] == b"PK"
    pack = client.get(f"/api/projects/{PID}/export/pack")
    z = zipfile.ZipFile(io.BytesIO(pack.content))
    names = set(z.namelist())
    for required in [
        "report.pdf",
        "workbook.xlsx",
        "evidence_index.csv",
        "control_checks.csv",
        "refdata_manifest.json",
        "calculation_tree.json",
        "monitoring_plan_hi.md",
    ]:
        assert required in names
    assert sum(1 for n in names if n.startswith("sources/")) == 24


def test_buyer_link_has_no_plant_inputs(client: TestClient) -> None:
    tok = client.post(f"/api/projects/{PID}/share").json()["token"]
    s = client.get(f"/api/share/{tok}").json()
    blob = json.dumps(s)
    assert "PROVISIONAL" in blob
    for leak in ['"mmbtu"', '"produced_t"', '"rod_consumed_t"', '"scrap_t"', "box_2d", "evidence_id", "Doaba", "calc_tree", "MMBtu", "gas"]:
        assert leak not in blob, leak
    assert {g["cn"] for g in s["summary"]["goods"]} == {"7318 15 82", "7318 15 75"}


def test_supplier_letter_en_hi(client: TestClient) -> None:
    en = client.post(f"/api/projects/{PID}/supplier-letter", json={"process_id": "P2", "lang": "en"}).json()
    hi = client.post(f"/api/projects/{PID}/supplier-letter", json={"process_id": "P2", "lang": "hi"}).json()
    assert "verification report" in en["text"] and "Indus Stainless Rods" in en["text"]
    assert "सत्यापित" in hi["text"]
    p = client.get(f"/api/projects/{PID}").json()["project"]
    assert next(s for s in p["supplier_requests"] if s["process_id"] == "P2")["status"] == "requested"


def test_monitoring_plan_has_22_elements(client: TestClient) -> None:
    mp = client.get(f"/api/projects/{PID}/monitoring-plan?lang=hi").json()
    assert len(mp["elements"]) == 22 and "ड्राफ्ट" in mp["status"]


def test_golden_endpoint(client: TestClient) -> None:
    g = client.get("/api/golden").json()
    assert g["all_pass"] is True and len(g["cases"]) == 8


def test_fx_override_recalculates(client: TestClient) -> None:
    before = client.get(f"/api/projects/{PID}/results").json()["money"]["series"]["P1"][0]["gap_inr_t"]
    client.patch(f"/api/projects/{PID}", json={"fx_inr_per_eur": "100"})
    after = client.get(f"/api/projects/{PID}/results").json()["money"]
    assert after["fx"]["value"] == "100"
    assert after["series"]["P1"][0]["gap_inr_t"] != before


def test_run_rate_limit_and_replay_run(client: TestClient) -> None:
    r = client.post(f"/api/projects/{PID}/runs", json={"lang": "en"})
    assert r.status_code == 200 and r.json()["mode"] == "replay"
    run = client.get(f"/api/projects/{PID}/runs/{r.json()['run_id']}").json()
    assert run["status"] == "done", run.get("error")
    events = client.get(f"/api/projects/{PID}/runs/{r.json()['run_id']}/events")
    assert "event: timeline" in events.text and "event: end" in events.text


def test_copilot_retrieval_mode_cites_pages(client: TestClient) -> None:
    a = client.post("/api/copilot/ask", json={"question": "Is scrap counted?"}).json()
    assert a["mode"] == "retrieval" and a["citations"]
    assert any(c["doc"] in {"Guidance 3", "Guidance 5d"} for c in a["citations"])


def test_gemini_backed_endpoints_are_capped_per_address(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api import routes

    monkeypatch.setitem(routes.AI_CALLS_PER_HOUR, "copilot", 2)
    routes._ai_log.clear()
    h = {"x-forwarded-for": "203.0.113.9"}
    codes = [client.post("/api/copilot/ask", json={"question": "Is scrap counted?"}, headers=h).status_code for _ in range(3)]
    other = client.post("/api/copilot/ask", json={"question": "Is scrap counted?"}, headers={"x-forwarded-for": "203.0.113.10"})
    routes._ai_log.clear()
    assert codes == [200, 200, 429] and other.status_code == 200


@pytest.mark.skipif(not (settings().static_dir / "index.html").exists(), reason="frontend not built")
def test_spa_answers_head_and_fills_link_preview_urls(client: TestClient) -> None:
    assert client.head("/").status_code == 200  # link-preview crawlers and uptime checks
    html = client.get("/p/demo-x/report").text
    assert 'property="og:image" content="http://testserver/og.jpg"' in html and "__ORIGIN__" not in html


def test_explainer_guard_rejects_invented_numbers(client: TestClient) -> None:
    r = client.get(f"/api/projects/{PID}/results").json()
    ok, _ = guard(r["explanations"][0]["text"], r["calc_tree"], [53, 115])
    assert ok
    ok, bad = guard("Your SEE is 1.234 t CO2/t and the buyer pays 999 EUR.", r["calc_tree"])
    assert not ok and "1.234" in bad


def test_each_visitor_gets_a_private_sample(client: TestClient) -> None:
    a = client.post("/api/demo/load", json={}).json()["project_id"]
    b = client.post("/api/demo/load", json={}).json()["project_id"]
    assert a != b and a.startswith("demo-") and b.startswith("demo-")
    ev = [e for e in client.get(f"/api/projects/{a}/evidence").json() if e["status"] == "NEEDS_REVIEW"]
    client.patch(f"/api/projects/{a}/evidence/{ev[0]['id']}", json={"action": "approve"})
    still_amber = [e for e in client.get(f"/api/projects/{b}/evidence").json() if e["status"] == "NEEDS_REVIEW"]
    assert len(still_amber) == 1  # b is unaffected by a's approval


def test_upload_normalises_png_and_pdf(client: TestClient) -> None:
    import io as _io

    from PIL import Image

    pid = client.post("/api/projects", json={"name": "Test", "company": "Test Co (SAMPLE)"}).json()["id"]
    png = _io.BytesIO()
    Image.new("RGB", (400, 600), "white").save(png, format="PNG")
    pdf = _io.BytesIO()
    Image.new("RGB", (400, 600), "white").save(pdf, format="PDF", save_all=True, append_images=[Image.new("RGB", (400, 600), "gray")])
    r = client.post(
        f"/api/projects/{pid}/documents",
        files=[("files", ("bill.png", png.getvalue(), "image/png")), ("files", ("register.pdf", pdf.getvalue(), "application/pdf"))],
    )
    assert r.status_code == 200, r.text
    docs = r.json()["documents"]
    assert [d["filename"] for d in docs] == ["bill.jpg", "register-p1.jpg", "register-p2.jpg"]
    assert all(d["content_type"] == "image/jpeg" and d["width"] for d in docs)
    img = client.get(f"/api/projects/{pid}/documents/{docs[1]['id']}/image")
    assert img.status_code == 200 and img.content[:2] == b"\xff\xd8"


def test_upload_rejects_unsupported_types(client: TestClient) -> None:
    pid = client.post("/api/projects", json={"name": "Test", "company": "Test Co (SAMPLE)"}).json()["id"]
    r = client.post(f"/api/projects/{pid}/documents", files=[("files", ("x.exe", b"MZ", "application/x-msdownload"))])
    assert r.status_code == 415


def test_whatif_electric_heating_and_supplier_switch(client: TestClient) -> None:
    w = client.post(
        f"/api/projects/{PID}/whatif", json={"process_id": "P2", "rod_see": "1.783", "rod_sefa": "0.919", "heating": "gas"}
    ).json()
    assert abs(Decimal(w["see"]) - Decimal("2.371")) <= Decimal("0.002")  # = G2
    e = client.post(
        f"/api/projects/{PID}/whatif", json={"process_id": "P2", "rod_see": "1.783", "rod_sefa": "0.919", "heating": "electric"}
    ).json()
    assert Decimal(e["direct"]) == 0 and Decimal(e["see"]) < Decimal(w["see"])
    assert len(e["series"]) == 9 and Decimal(e["series"][0]["eur_t"]) < Decimal(w["series"][0]["eur_t"])
    assert client.post(f"/api/projects/{PID}/whatif", json={"process_id": "P2", "heating": "coal"}).status_code == 422
