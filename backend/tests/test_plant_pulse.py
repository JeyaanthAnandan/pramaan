"""Plant pulse: gas per tonne month by month against the plant's own median month. The sample's June
runs hot (EC Example 3's 3.5 GJ/t moves month to month, the period total does not), so the report
names the month, prices the excess at the bill's own rate and traces every figure to the bills."""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app

PID = "demo-shivalik"


@pytest.fixture()
def result(mem_store):  # noqa: ARG001
    with TestClient(app) as c:
        assert c.post("/api/demo/load", json={"replay": True, "shared": True}).status_code == 200
        yield c.get(f"/api/projects/{PID}/results").json()


def test_june_runs_hot_and_the_excess_is_priced_at_the_bills_rate(result: dict) -> None:
    gp = result["operations"]["gas_pulse"]
    assert gp["hot_months"] == ["2026-06"] and gp["best"]["month"] == "2026-04"
    assert abs(Decimal(gp["median"]) - Decimal("3.4407")) < Decimal("0.0005")
    june = next(m for m in gp["months"] if m["month"] == "2026-06")
    assert abs(Decimal(june["delta_pct"]) - Decimal("18.5")) < Decimal("0.1")
    assert abs(Decimal(gp["excess_gj"]) - Decimal("135.0")) < Decimal("0.1")
    assert abs(Decimal(gp["excess_inr"]) - Decimal("200905")) < Decimal("2")  # ≈ ₹2.0 lakh of gas
    assert abs(Decimal(gp["excess_tco2"]) - Decimal("7.574")) < Decimal("0.01")


def test_every_pulse_figure_traces_to_the_bills(result: dict) -> None:
    tree = result["calc_tree"]

    def leaves(nid: str) -> list[dict]:
        n = tree[nid]
        return [n] if not n["children"] else [x for ch in n["children"] for x in leaves(ch)]

    inr = leaves("ops.gas.excess_inr")
    docs = {x["source"].get("doc_title") for x in inr if x["source"]["kind"] == "evidence"}
    assert any("June" in (d or "") for d in docs)  # the June bill: its gas and its rate
    assert any(x["label"].startswith("Gas rate 2026-06") and x["value"] == "53.10" for x in inr)
    assert all(x["source"]["box_2d"] for x in inr if x["source"]["kind"] == "evidence")


def test_flat_months_leave_golden_numbers_unchanged(result: dict) -> None:
    p1 = next(p for p in result["processes"] if p["id"] == "P1")
    assert p1["see"].startswith("2.0398")  # the period's gas is the same as EC Example 3's 3.5 GJ/t
    assert abs(Decimal(p1["buyer"]["annual_gap_eur"]) - Decimal("409544.5")) < Decimal("1")
