"""Tamper evidence: the change log is a hash chain, and every report that leaves Pramaan carries a
signed receipt that anyone can check (here with the development key; on Cloud Run with Cloud KMS)."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.evidence import attest, ledger
from app.evidence.store import store
from app.main import app


@pytest.fixture()
def client(mem_store: Any) -> Any:
    with TestClient(app) as c:
        yield c


def _sample(c: TestClient) -> str:
    return str(c.post("/api/demo/load", json={}).json()["project_id"])


def _amber(c: TestClient, pid: str) -> dict[str, Any]:
    return next(e for e in c.get(f"/api/projects/{pid}/evidence").json() if e["status"] == "NEEDS_REVIEW")


def test_every_change_is_a_link_in_a_hash_chain(client: TestClient) -> None:
    pid = _sample(client)
    ev = _amber(client, pid)
    client.patch(
        f"/api/projects/{pid}/evidence/{ev['id']}", json={"action": "edit", "value_text": "15.9", "value_num": "15.9", "user": "Owner"}
    )
    client.post(f"/api/projects/{pid}/spotcheck/{ev['id']}", json={"match": False, "note": "the bill says 15.4", "by": "Verifier"})
    chain = store().list_ledger(pid)
    assert [e["action"] for e in chain] == ["values_read", "edit", "spot_check"]
    assert chain[1]["before"]["value_text"] == "15.4" and chain[1]["after"]["value_num"] == "15.9"
    assert chain[1]["prev"] == chain[0]["hash"] and ledger.verify(pid) == {
        "ok": True,
        "entries": 3,
        "broken_at": None,
        "head": chain[2]["hash"],
    }
    chain[1]["after"]["value_num"] = "15.4"  # someone quietly rewrites the edit in the database
    assert ledger.verify(pid)["broken_at"] == 2
    e = store().get_evidence(pid, ev["id"])
    assert e and ledger.changed_by_hand(e) and ledger.read_as(e) == "15.4"


def test_a_downloaded_report_matches_its_signed_receipt(client: TestClient) -> None:
    pid = _sample(client)
    r = client.get(f"/api/projects/{pid}/export/pdf")
    aid = r.headers["x-pramaan-receipt"]
    assert aid.startswith("PR-") and aid.encode() in _pdf_text(r.content)
    rec = client.get(f"/api/receipts/{aid}").json()
    st = rec["statement"]
    assert rec["signature_valid"] and rec["key"]["trusted"] is False  # development key outside Cloud Run
    assert st["fingerprints"]["files"]["report.pdf"] == hashlib.sha256(r.content).hexdigest()
    assert st["project"]["company"].startswith("Shivalik") and st["headline"]["buyer_saves_eur_per_year"]
    assert st["values"]["total"] == st["values"]["two_readers_agree"] + st["values"]["waiting_for_review"]
    assert rec["now"]["values_match"] and rec["now"]["calculation_matches"] and rec["now"]["changes_since"] == []
    # the browser checks the same signature in r||s form with WebCrypto
    assert len(base64.b64decode(rec["signature_raw"])) == 64
    assert client.get("/api/receipts/PR-NONE-NONE-NONE").status_code == 404


def test_a_change_after_issue_is_shown_and_a_doctored_statement_fails(client: TestClient) -> None:
    pid = _sample(client)
    aid = client.get(f"/api/projects/{pid}/export/pdf").headers["x-pramaan-receipt"]
    ev = _amber(client, pid)
    client.patch(
        f"/api/projects/{pid}/evidence/{ev['id']}", json={"action": "edit", "value_text": "15.9", "value_num": "15.9", "user": "Owner"}
    )
    rec = client.get(f"/api/receipts/{aid}").json()
    assert rec["signature_valid"] and not rec["now"]["values_match"] and not rec["now"]["calculation_matches"]
    assert [c["action"] for c in rec["now"]["changes_since"]] == ["edit"] and rec["now"]["log_matches_receipt"]
    # a new receipt counts the value as changed by hand
    aid2 = client.get(f"/api/projects/{pid}/export/pdf").headers["x-pramaan-receipt"]
    assert client.get(f"/api/receipts/{aid2}").json()["statement"]["values"]["changed_by_hand"] == 1
    # someone edits the stored statement to show a better figure: the signature no longer holds
    stored = store().get_attestation(aid)
    assert stored
    stored["statement"] = stored["statement"].replace('"changed_by_hand":0', '"changed_by_hand":0 ')
    store().put_attestation(stored)
    assert client.get(f"/api/receipts/{aid}").json()["signature_valid"] is False


def test_the_verifier_pack_checks_offline_with_openssl(client: TestClient, tmp_path: Path) -> None:
    pid = _sample(client)
    r = client.get(f"/api/projects/{pid}/export/pack")
    z = zipfile.ZipFile(io.BytesIO(r.content))
    names = set(z.namelist())
    assert {"receipt/statement.json", "receipt/statement.sig", "receipt/public_key.pem", "receipt/VERIFY.txt", "change_log.json"} <= names
    body, sig, pem = z.read("receipt/statement.json"), z.read("receipt/statement.sig"), z.read("receipt/public_key.pem").decode()
    assert attest.verify(pem, sig, body)
    st = json.loads(body)
    assert st["id"] == r.headers["x-pramaan-receipt"] and st["kind"] == "verifier-pack"
    for name, digest in st["fingerprints"]["files"].items():  # every file in the pack is the one that was signed
        assert hashlib.sha256(z.read(name)).hexdigest() == digest, name
    assert "read_as" in z.read("evidence_index.csv").decode().splitlines()[0]
    if shutil.which("openssl"):  # the command VERIFY.txt gives
        z.extractall(tmp_path)
        cmd = [
            "openssl",
            "dgst",
            "-sha256",
            "-verify",
            "receipt/public_key.pem",
            "-signature",
            "receipt/statement.sig",
            "receipt/statement.json",
        ]
        out = subprocess.run(cmd, cwd=tmp_path, capture_output=True, text=True, check=False)  # noqa: S603
        assert out.stdout.strip() == "Verified OK", out.stderr


def test_a_buyer_link_carries_the_receipt_of_its_summary(client: TestClient) -> None:
    pid = _sample(client)
    tok = client.post(f"/api/projects/{pid}/share").json()["token"]
    s = client.get(f"/api/share/{tok}").json()
    rec = client.get(f"/api/receipts/{s['receipt_id']}").json()
    assert rec["signature_valid"] and rec["statement"]["kind"] == "buyer-link"
    assert rec["statement"]["fingerprints"]["files"]["summary.json"] == hashlib.sha256(ledger.canonical(s["summary"])).hexdigest()


def _pdf_text(pdf: bytes) -> bytes:
    import pypdf

    return "".join(p.extract_text() or "" for p in pypdf.PdfReader(io.BytesIO(pdf)).pages).encode()
