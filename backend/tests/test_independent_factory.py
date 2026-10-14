"""A factory the app had never seen: Kaveri Precision Fasteners (TEST - fictional), Coimbatore, Jan-Jun 2026,
carbon and stainless hexagon nuts from two rod suppliers. Its 16 documents (new layouts, a Tamil handwritten
scrap log with one figure struck out) were read by live Gemini on 14 Oct 2026: 158 of 162 values right and
none wrong; the 4 the reader missed (alloy content on one stainless invoice) come from the generator's
ground truth. Every expected number below comes from a separate calculator that reads the Commission's own
default-value and benchmark files, not from this engine. The plant has two deliberate faults: the carbon
scrap log is off by 5 t in March and May (the totals still balance) and March gas runs hot."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.agents.workflow import recalculate
from app.evidence.models import Document, Evidence, SecondReading
from app.evidence.store import store
from app.main import app

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "independent_factory.json").read_text(encoding="utf-8"))


def near(got: Any, want: str, tol: str) -> bool:
    return abs(Decimal(str(got)) - Decimal(want)) <= Decimal(tol)


@pytest.fixture()
def kaveri(mem_store: Any) -> Any:  # noqa: ARG001
    with TestClient(app) as c:
        r = c.post("/api/projects", json={"name": "CBAM 2026 H1", "company": FIXTURE["company"], "city": FIXTURE["city"], "months_to": 6})
        assert r.status_code == 200, r.text
        pid = r.json()["id"]
        assert c.put(f"/api/projects/{pid}/product-lines", json={"lines": FIXTURE["lines"]}).status_code == 200
        docs = {
            d["doc"]: Document(
                project_id=pid,
                filename=f"{d['doc']}.jpg",
                uri=f"file:///independent/{d['doc']}.jpg",
                doc_type=d["doc_type"],
                width=d["width"],
                height=d["height"],
                title=d["title"],
                state="extracted",
            )
            for d in FIXTURE["documents"]
        }
        evidence = []
        for row in FIXTURE["evidence"]:
            corrected = row.get("corrected_from")
            evidence.append(
                Evidence(
                    project_id=pid,
                    doc_id=docs[row["doc"]].id,
                    field_key=row["field_key"],
                    label=row["field_key"],
                    value_text=row["value_text"],
                    value_num=row["value_num"],
                    unit=row["unit"],
                    period=row["period"],
                    process=row["process"],
                    box_2d=row["box_2d"],
                    status="NEEDS_REVIEW" if corrected else "VERIFIED_2R",
                    second_reading=SecondReading(
                        reading_value=row["value_text"],
                        agrees=True,
                        corrected_from=corrected,
                        reason=f"corrected on the document: {corrected} crossed out" if corrected else "",
                    ),
                )
            )
        store().put_documents(list(docs.values()))
        store().put_evidence(evidence)
        result = recalculate(pid)
        yield c, pid, result


def line(result: dict[str, Any], pid: str) -> dict[str, Any]:
    return next(p for p in result["processes"] if p["id"] == pid)


def test_embedded_emissions_match_the_independent_calculator(kaveri: Any) -> None:
    _, _, res = kaveri
    p1, p2 = line(res, "P1"), line(res, "P2")
    # gas: 3,265.0 GJ NCV for 990 t -> 3.2979 GJ/t -> 0.18501 t CO2/t on both lines (mass allocation)
    assert near(p1["direct"], "0.185013", "0.000001") and near(p2["direct"], "0.185013", "0.000001")
    assert near(p1["m"], "1.161806", "0.000001") and near(p2["m"], "1.134444", "0.000001")  # 836.5/720, 306.3/270
    # carbon rod on the India default 4.270 (7213 91 49) + 10 % mark-up; stainless on the verified statement
    assert p1["precursor"]["data"] == "DEFAULT_USED" and near(p1["precursor"]["see"], "4.697", "0.0000001")
    assert p2["precursor"]["data"] == "ACTUAL_VERIFIED" and near(p2["precursor"]["see"], "2.150", "0")
    assert near(p1["see"], "5.642014", "0.000001") and near(p2["see"], "2.624069", "0.000001")
    # SEFA = BM_A of the nut (0.038) + m x SEFA of the rod (column B 1.364 default route; 0.880 verified)
    assert near(p1["sefa"], "1.622703", "0.000001") and near(p2["sefa"], "1.036311", "0.000001")
    assert near(p1["sefa_y"], "1.582135", "0.000001") and near(p2["sefa_y"], "1.010403", "0.000001")  # x 0.975


def test_buyer_cost_on_data_and_on_eu_defaults(kaveri: Any) -> None:
    _, _, res = kaveri
    b1, b2 = line(res, "P1")["buyer"], line(res, "P2")["buyer"]
    # India default for the nut: 5.140 (7318 16) + 10 %, column B 1.364 / 1.154; 2026 price ~EUR 75.32/t
    assert near(b1["actual_eur_t"], "305.78", "0.01") and near(b1["default_eur_t"], "325.68", "0.01")
    assert near(b2["actual_eur_t"], "121.54", "0.01") and near(b2["default_eur_t"], "341.10", "0.01")
    assert b1["basis_2026"] == b2["basis_2026"] == "actual"  # both cheaper on the factory's own data
    # 390 t and 155 t exported in six months, doubled for a year
    assert near(b1["annual_gap_eur"], "15522", "1") and near(b2["annual_gap_eur"], "68064", "1")


def test_a_rod_on_its_default_shows_what_verified_supplier_data_would_save(kaveri: Any) -> None:
    """The Precursor Lever existed only for the bundled sample: an own factory got no "More within reach"
    and no "ask your supplier" step. With EC Guidance 5d Example 1 (SEE 1.567, SEFA 1.242) for the carbon
    rod: SEE 2.0056, SEFA_2026 1.4439, EUR 42.30/t instead of 305.78."""
    _, _, res = kaveri
    b1, b2 = line(res, "P1")["buyer"], line(res, "P2")["buyer"]
    assert near(b1["with_supplier_eur_t"], "42.30", "0.01")
    assert near(b1["supplier_saving_eur_t"], "263.48", "0.01") and near(b1["supplier_saving_annual_eur"], "205512", "2")
    assert b2["supplier_saving_eur_t"] is None  # already on verified supplier data
    assert set(res["money"]["what_if"]) == {"P1"}
    assert "Example 1" in res["calc_tree"]["whatif.P1.rod.see"]["label"]


def test_months_out_of_balance_are_named_with_their_figures(kaveri: Any) -> None:
    """Rod - scrap misses production in March (125.0 vs 130.0 t) and May (120.0 vs 115.0 t); the totals
    balance. The check said "4/6 months" with an empty "Missing months:" and no values to look at."""
    _, _, res = kaveri
    checks = {x["id"]: x for x in res["checks"]}
    p1 = checks["mass_balance_monthly.P1"]
    assert p1["status"] == "warn" and p1["result"].startswith("4/6")
    assert p1["note"] == "Out of balance: 2026-03 (125.0 vs 130.0 t), 2026-05 (120.0 vs 115.0 t)"
    assert len(p1["evidence_ids"]) == 6 and set(p1["inputs"]["out_of_balance"]) == {"2026-03", "2026-05"}
    assert checks["mass_balance_monthly.P2"]["status"] == "pass" and checks["mass_balance_monthly.P2"]["note"] == ""
    assert checks["mass_balance.P1"]["status"] == "pass"  # the six-month totals close
    gaps = {g["id"]: g for g in res["gaps"]}
    assert gaps["scrap.P1"]["kind"] == "scrap_unbalanced" and gaps["scrap.P1"]["status"] == "amber"
    assert gaps["scrap.P1"]["params"]["months"] == ["2026-03", "2026-05"]
    assert gaps["scrap.P2"]["kind"] == "scrap"


def test_plant_pulse_finds_the_hot_month(kaveri: Any) -> None:
    _, _, res = kaveri
    gp = res["operations"]["gas_pulse"]
    assert gp["hot_months"] == ["2026-03"] and gp["best"]["month"] == "2026-04"
    assert near(gp["median"], "3.190", "0.0005")
    march = next(m for m in gp["months"] if m["month"] == "2026-03")
    assert near(march["delta_pct"], "20.7", "0.05")
    assert near(gp["excess_gj"], "118.8", "0.05") and near(gp["excess_inr"], "176194", "2")  # at March's 53.15/SCM


def test_controls_and_readiness(kaveri: Any) -> None:
    _, _, res = kaveri
    status = {x["id"]: x["status"] for x in res["checks"]}
    # 16 checks: 13 pass, electricity is recorded but outside the scope (info), two warnings
    assert len(status) == 16 and status["electricity.excluded"] == "info"
    assert [k for k, s in status.items() if s not in ("pass", "info")] == ["mass_balance_monthly.P1", "supplier.P1"]
    assert status["stock.P1"] == status["stock.P2"] == status["gas.internal"] == "pass"  # purchases, stocks and bills reconcile
    ready = res["readiness"]["by_process"]
    assert ready["P2"]["ready"] is True and ready["P1"]["ready"] is False and res["readiness"]["lines_ready"] == 1


def test_alloy_content_is_weighted_by_the_rod_delivered(kaveri: Any) -> None:
    """Guidance 5d Table 3-1 extra parameters, from the mill-test figures on each rod invoice weighted by
    its tonnes (carbon 450 t + 400 t; stainless 160 t + 150 t). A plain mean gave Mn 0.44, Cr 0.04 and
    Ni 8.08."""
    _, _, res = kaveri
    got = {
        p["id"]: {k: p["extra_parameters"][k]["value"] for k in ("mn_pct", "cr_pct", "ni_pct", "other_alloy_pct")} for p in res["processes"]
    }
    assert got["P1"] == {"mn_pct": "0.43", "cr_pct": "0.03", "ni_pct": "0.02", "other_alloy_pct": "0.15"}
    assert got["P2"] == {"mn_pct": "1.60", "cr_pct": "18.16", "ni_pct": "8.07", "other_alloy_pct": "0.69"}
    assert len(line(res, "P2")["extra_parameters"]["ni_pct"]["evidence"]) == 4  # two Ni readings and two tonnages


def test_the_report_speaks_about_this_factory(kaveri: Any) -> None:
    from app.api.routes import _project, _result
    from app.exports.pdf import html

    _, pid, _ = kaveri
    h = html(_project(pid), _result(pid))
    assert "Kaveri Precision Fasteners" in h and "Your data saves your buyer" in h and "EUR 83,586" in h
    assert "More within reach" in h and "+EUR 205,512" in h
    assert "Ask Cauvery Wire Rods Pvt Ltd (TEST) for verified data" in h
    assert "Out of balance: 2026-03 (125.0 vs 130.0 t)" in h and "Missing months: <" not in h
    assert "MVS-VR-2026-0412" in h and "Mar ran hot" in h
    assert 'default + mark-up</span> <span class="small">(SEE 4.697)' in h and "(SEE 2.150)" in h  # the rod's own SEE
    assert "own gas bills ÷ tonnes produced" in h and "Mode: None" not in h  # this plant's gas, no empty run line
    assert "-0 %" not in h and "Confirm 1 value that needs a person" in h  # June is 0.3 % under the median
    for text in ("sample factory", "in the demo", "(SAMPLE)"):
        assert text not in h, text


def test_letter_plan_and_explanations_fit_this_factory(kaveri: Any) -> None:
    """Wording written for the sample's bolts ("per tonne of bolts", "into bolts", "Two production
    processes") reached every factory's supplier letter, monitoring plan and explanations."""
    c, pid, _ = kaveri
    letters = {
        lang: c.post(f"/api/projects/{pid}/supplier-letter", json={"process_id": "P1", "lang": lang}).json()["text"]
        for lang in ("en", "hi")
    }
    for text in letters.values():
        assert "Cauvery Wire Rods Pvt Ltd (TEST)" in text and f"{FIXTURE['lines'][0]['name']} (CN 7318 16 92)" in text
        assert "bolt" not in text.lower() and "बोल्ट" not in text
    en = letters["en"]
    assert "about 97% of the embedded emissions of these goods" in en  # 1.1618 x 4.697 of SEE 5.642
    assert "4.270 t CO2e per tonne of rod" in en and "to 4.697 t CO2e/t" in en
    assert "EUR 306 per tonne of these goods with our data, against EUR 326 per tonne" in en
    plan = c.get(f"/api/projects/{pid}/monitoring-plan").json()
    text = " ".join(e["content"] for e in plan["elements"])
    assert "Two production processes" in text and "bolt" not in text.lower() and "Kaveri Precision Fasteners" in text
    ex = c.get(f"/api/projects/{pid}/explanations", params={"lang": "en"}).json()
    assert "bolt" not in json.dumps(ex).lower() and "t rod per t of product" in json.dumps(ex)


def test_the_verifier_pack_names_the_months_too(kaveri: Any) -> None:
    import csv
    import io
    import zipfile

    c, pid, _ = kaveri
    r = c.get(f"/api/projects/{pid}/export/pack")
    assert r.status_code == 200
    z = zipfile.ZipFile(io.BytesIO(r.content))
    rows = {row["id"]: row for row in csv.DictReader(io.StringIO(z.read("control_checks.csv").decode("utf-8")))}
    m = rows["mass_balance_monthly.P1"]
    assert m["note"].startswith("Out of balance: 2026-03 (125.0 vs 130.0 t)") and len(m["evidence_ids"].split()) == 6
    plan = z.read("monitoring_plan_en.md").decode("utf-8")
    assert "Kaveri Precision Fasteners" in plan and "bolt" not in plan.lower()


def test_the_carbon_rod_supplier_replies(kaveri: Any) -> None:
    """Cauvery answers the request with a verified statement (BF-BOF, SEE 1.567, SEFA 1.242). Read live on
    14 Oct 2026 without its verification section, the line rightly stayed on the default, but the checklist
    said only "no verified data"; it now says the statement came without a verification report number.
    Read in full, the line moves to the independent calculator's figures: SEE 2.005563, EUR 42.30/t."""
    _, pid, _ = kaveri
    stmt = Document(project_id=pid, filename="stmt-CWR-2026-H1.jpg", uri="file:///independent/stmt-CWR-2026-H1.jpg")
    stmt.doc_type, stmt.state = "supplier_emissions_statement", "extracted"
    store().put_document(stmt)

    def put(rows: list[tuple[str, str, str | None]]) -> None:
        store().put_evidence(
            [
                Evidence(
                    project_id=pid,
                    doc_id=stmt.id,
                    field_key=k,
                    value_text=v,
                    value_num=n,
                    process="P1",
                    box_2d=[100, 100, 120, 300],
                    status="VERIFIED_2R",
                    second_reading=SecondReading(reading_value=v, agrees=True),
                )
                for k, v, n in rows
            ]
        )

    put([("product_cn", "7213 91 49", None), ("period", "01-01-2026 to 30-06-2026", None), ("see", "1.567 t CO2e / t", "1.567")])
    res = recalculate(pid)
    assert line(res, "P1")["precursor"]["data"] == "DEFAULT_USED"  # an unverified figure is not declared
    gap = next(g for g in res["gaps"] if g["id"] == "precursor_see.P1")
    assert gap["kind"] == "precursor_unverified" and gap["status"] == "amber" and gap["params"]["see_sent"] == "1.567"

    put(
        [
            ("sefa", "1.242 t CO2e / t", "1.242"),
            ("verifier", "Meridian Verification Services GmbH (TEST)", None),
            ("verification_ref", "MVS-VR-2026-0533", None),
        ]
    )
    res = recalculate(pid)
    p1 = line(res, "P1")
    assert p1["precursor"]["data"] == "ACTUAL_VERIFIED"
    assert near(p1["see"], "2.005563", "0.000001") and near(p1["sefa"], "1.480963", "0.000001")
    assert near(p1["buyer"]["actual_eur_t"], "42.30", "0.01") and p1["buyer"]["basis_2026"] == "actual"
    assert near(p1["buyer"]["annual_gap_eur"], "221035", "2")  # (325.68 - 42.30) x 780 t a year
    assert res["readiness"]["lines_ready"] == 2 and set(res["money"]["what_if"]) == set()
    assert next(g for g in res["gaps"] if g["id"] == "precursor_see.P1")["status"] == "green"
