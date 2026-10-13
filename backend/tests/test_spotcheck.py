"""Verifier spot-check: a risk-based sample of the values behind the result, marked against the photos."""

from __future__ import annotations

import csv
import io
import zipfile
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import app

PID = "demo-shivalik"


@pytest.fixture()
def client(mem_store: Any):  # noqa: ARG001
    with TestClient(app) as c:
        assert c.post("/api/demo/load", json={"replay": True, "shared": True}).status_code == 200
        yield c


def test_the_sample_covers_what_moves_the_result_and_stays_put(client: TestClient) -> None:
    first = client.get(f"/api/projects/{PID}/spotcheck").json()
    whys = [i["why"] for i in first["items"]]
    assert len(whys) == 12 and "manual" not in whys  # nothing approved by a person yet
    assert whys == sorted(whys, key=["supplier", "activity", "rod", "energy", "rod_bought", "scrap", "exports", "other"].index)
    assert {"supplier", "activity", "rod", "energy", "rod_bought", "scrap", "exports"} <= set(whys)
    sup = [i for i in first["items"] if i["why"] == "supplier"]
    assert {i["field_key"] for i in sup} <= {"see", "sefa"} and all(i["doc_type"] == "supplier_emissions_statement" for i in sup)
    assert all(i["crop_box"] and i["doc_id"] and i["mark"] is None for i in first["items"])
    assert [i["id"] for i in client.get(f"/api/projects/{PID}/spotcheck").json()["items"]] == [i["id"] for i in first["items"]]
    assert first["summary"] == {"total": 12, "checked": 0, "match": 0, "differ": 0, "by": None, "at": None}


def test_a_value_a_person_approved_is_always_checked_first(client: TestClient) -> None:
    ev = client.get(f"/api/projects/{PID}/evidence").json()
    amber = next(e for e in ev if e["status"] == "NEEDS_REVIEW")
    assert (
        client.patch(f"/api/projects/{PID}/evidence/{amber['id']}", json={"action": "approve", "user": "Owner (demo)"}).status_code == 200
    )
    items = client.get(f"/api/projects/{PID}/spotcheck").json()["items"]
    assert items[0]["why"] == "manual" and items[0]["id"] == amber["id"] and items[0]["value_text"] == "15.4"
    assert items[0]["approved_by"] == "Owner (demo)" and len(items) == 12


def test_marks_are_kept_with_an_audit_entry_and_go_into_the_pack(client: TestClient) -> None:
    items = client.get(f"/api/projects/{PID}/spotcheck").json()["items"]
    a, b = items[0]["id"], items[1]["id"]
    r = client.post(f"/api/projects/{PID}/spotcheck/{a}", json={"match": True, "by": "A. Verifier (SAMPLE)"})
    assert r.status_code == 200 and r.json()["mark"]["match"] is True
    client.post(f"/api/projects/{PID}/spotcheck/{b}", json={"match": False, "note": "the bill shows 21,129", "by": "A. Verifier (SAMPLE)"})
    s = client.get(f"/api/projects/{PID}/spotcheck").json()["summary"]
    assert (s["checked"], s["match"], s["differ"], s["by"]) == (2, 1, 1, "A. Verifier (SAMPLE)")
    hist = next(e for e in client.get(f"/api/projects/{PID}/evidence").json() if e["id"] == b)["history"]
    assert hist[-1]["action"] == "spot_check" and hist[-1]["note"] == "the bill shows 21,129"
    assert client.post(f"/api/projects/{PID}/spotcheck/nope", json={"match": True}).status_code == 404
    z = zipfile.ZipFile(io.BytesIO(client.get(f"/api/projects/{PID}/export/pack").content))
    rows = list(csv.DictReader(io.StringIO(z.read("spot_check.csv").decode())))
    assert len(rows) == 12 and [r["matches"] for r in rows if r["checked"] == "True"] == ["True", "False"]


def test_a_private_project_keeps_its_spot_check_private(client: TestClient) -> None:
    own = client.post("/api/projects", json={"name": "x", "company": "Private (SAMPLE)"}).json()["id"]
    with TestClient(app) as other:
        assert other.get(f"/api/projects/{own}/spotcheck").status_code == 401
    assert client.get(f"/api/projects/{own}/spotcheck").status_code == 404  # the owner: no results yet
