"""Supplier upload links: the Precursor Lever's loop, closed. The exporter sends one link; the rod
supplier uploads its verified statement without an account; the agents read it and the stainless
line moves from the EU default to verified actual data (= golden G2, as the what-if predicted)."""

from __future__ import annotations

import io
import json
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app

PID = "demo-shivalik"


@pytest.fixture()
def client(mem_store):  # noqa: ARG001
    with TestClient(app) as c:
        assert c.post("/api/demo/load", json={"replay": True, "shared": True}).status_code == 200
        yield c


def _link(c: TestClient, pid: str = PID, process_id: str = "P2") -> dict:
    r = c.post(f"/api/projects/{pid}/supplier-link", json={"process_id": process_id})
    assert r.status_code == 200, r.text
    return r.json()


def _p2(c: TestClient) -> dict:
    return next(p for p in c.get(f"/api/projects/{PID}/results").json()["processes"] if p["id"] == "P2")


def test_one_link_per_line_and_the_request_counts_as_sent(client: TestClient) -> None:
    a, b = _link(client), _link(client)
    assert a["token"] == b["token"] and a["url"].endswith(f"/supplier/{a['token']}")
    sr = next(s for s in client.get(f"/api/projects/{PID}").json()["project"]["supplier_requests"] if s["process_id"] == "P2")
    assert sr["status"] == "requested" and sr["link_token"] == a["token"]


def test_supplier_sees_what_is_asked_but_no_plant_data(client: TestClient) -> None:
    v = client.get(f"/api/supplier/{_link(client)['token']}").json()
    assert v["request"]["supplier"] == "Indus Stainless Rods (SAMPLE)" and v["request"]["precursor_cn"] == "7221 00 10"
    assert v["sample_available"] and v["documents"] == [] and v["status"] == "requested" and not v["failed"]
    body = json.dumps(v)
    assert "MMBtu" not in body and "Doaba" not in body and "409" not in body  # no energy bills, no money


def test_verified_statement_from_the_supplier_moves_the_line_to_actual_data(client: TestClient) -> None:
    p1_before = next(p for p in client.get(f"/api/projects/{PID}/results").json()["processes"] if p["id"] == "P1")
    assert _p2(client)["precursor"]["data"] == "DEFAULT_USED"
    tok = _link(client)["token"]
    r = client.post(f"/api/supplier/{tok}/sample")  # the test client finishes the background run first
    assert r.status_code == 200, r.text
    p2 = _p2(client)
    assert p2["precursor"]["data"] == "ACTUAL_VERIFIED" and p2["precursor"]["see"] == "1.783"
    assert abs(Decimal(p2["see"]) - Decimal("2.371")) <= Decimal("0.002")  # = G2, as the what-if predicted
    v = client.get(f"/api/supplier/{tok}").json()
    assert v["status"] == "verified" and not v["running"] and not v["failed"]
    assert {x["field_key"] for x in v["values"]} >= {"see", "sefa", "verification_ref"}
    assert all(x["status"] == "VERIFIED_2R" for x in v["values"])
    img = client.get(f"/api/supplier/{tok}/documents/{v['documents'][0]['id']}/image")
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg"
    p1 = next(p for p in client.get(f"/api/projects/{PID}/results").json()["processes"] if p["id"] == "P1")
    assert p1["see"] == p1_before["see"]  # only the new document was read
    assert client.post(f"/api/supplier/{tok}/sample").status_code == 409  # sent once


def test_buyer_and_supplier_links_do_not_mix(client: TestClient) -> None:
    buyer = client.post(f"/api/projects/{PID}/share").json()["token"]
    sup = _link(client)["token"]
    assert client.get(f"/api/supplier/{buyer}").status_code == 404
    assert client.get(f"/api/share/{sup}").status_code == 404
    assert client.get("/api/supplier/not-a-token").status_code == 404


def test_the_request_letter_carries_the_upload_link(client: TestClient) -> None:
    en = client.post(f"/api/projects/{PID}/supplier-letter", json={"process_id": "P2", "lang": "en"}).json()
    hi = client.post(f"/api/projects/{PID}/supplier-letter", json={"process_id": "P2", "lang": "hi"}).json()
    assert en["link"]["url"] in en["text"] and hi["link"]["url"] in hi["text"] and en["link"]["token"] == hi["link"]["token"]


def test_private_project_takes_supplier_uploads_through_the_link_only(client: TestClient) -> None:
    lines = [
        {
            "id": "P1",
            "name": "Hex bolts",
            "cn": "73181582",
            "cn_display": "7318 15 82",
            "cn_desc": "Hexagon screws and bolts",
            "precursor_name": "Wire rod",
            "precursor_cn": "72139149",
            "precursor_supplier": "Test Rod Mill (SAMPLE)",
            "source": "owner",
        }
    ]
    own = client.post("/api/projects", json={"name": "Own", "company": "Test Co (SAMPLE)", "processes": lines}).json()
    pid = own["project"]["id"] if "project" in own else own["id"]
    tok = _link(client, pid, "P1")["token"]
    stranger = TestClient(app)  # no passcode cookie
    assert stranger.get(f"/api/projects/{pid}").status_code == 401
    assert stranger.get(f"/api/supplier/{tok}").json()["sample_available"] is False
    buf = io.BytesIO()
    Image.new("RGB", (800, 1000), "white").save(buf, "JPEG")
    up = stranger.post(f"/api/supplier/{tok}/documents", files={"files": ("statement.jpg", buf.getvalue(), "image/jpeg")})
    assert up.status_code == 200, up.text
    v = stranger.get(f"/api/supplier/{tok}").json()
    assert len(v["documents"]) == 1 and v["status"] == "received"
    assert v["failed"]  # no Gemini in tests and not a bundled sample: left for the owner, said plainly


def test_the_buyer_link_names_who_verified_the_supplier_data(client: TestClient) -> None:
    def statuses() -> dict[str, str]:
        tok = client.post(f"/api/projects/{PID}/share").json()["token"]
        return {g["cn"]: g["precursor_data"][0]["status"] for g in client.get(f"/api/share/{tok}").json()["summary"]["goods"]}

    s = statuses()
    assert "Kestrel Assurance" in s["7318 15 82"] and "KA-VR-2026-0147" in s["7318 15 82"]
    assert s["7318 15 75"].startswith("EU default")
    client.post(f"/api/supplier/{_link(client)['token']}/sample")
    assert "KA-VR-2026-0233" in statuses()["7318 15 75"]  # the supplier's own verification, now on the buyer link
