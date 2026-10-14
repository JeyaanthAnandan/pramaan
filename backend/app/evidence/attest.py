"""Signed report receipts: anyone holding a Pramaan report can check that it is genuine and unaltered.

When a report leaves Pramaan (the PDF, the verifier pack, a buyer link) a statement is written: whose
report and which period, the headline figures, how every value behind them was confirmed (two
readers agreed, a person approved it as read, a person changed it, still waiting for review), and
SHA-256 fingerprints of the calculation tree, the values, every source photo, the official reference
data, the change log's head and each file issued. The statement is signed with an EC P-256 key in
Google Cloud KMS: the private key never leaves KMS, and changing anything after signing (a figure in
the statement, one byte of the PDF) makes the check fail.

The receipt id is printed on the report. /r/{id} shows the statement, checks the signature in the
reader's own browser and compares a dropped-in PDF with the file that was issued; the verifier pack
carries the statement, the signature and the public key, so `openssl` checks it with no Pramaan at
all. Without a KMS key (local, CI) a development key signs and every receipt says it is not trusted.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import secrets
import threading
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from app import refdata
from app.access import ALPHABET
from app.config import settings
from app.evidence import ledger
from app.evidence.models import Document, Evidence, Project, now
from app.evidence.store import store

log = logging.getLogger("pramaan.attest")

ALG = "ECDSA_P256_SHA256"
SCHEMA = "pramaan.report-receipt/1"
_lock = threading.Lock()


@dataclass(frozen=True)
class Key:
    name: str  # the KMS key version, or "dev:<fingerprint>"
    pem: str
    trusted: bool  # False for the development key

    @property
    def fingerprint(self) -> str:
        return fingerprint(self.pem)


def fingerprint(pem: str) -> str:
    """SHA-256 of the public key (DER), as printed on reports and in the README."""
    from cryptography.hazmat.primitives import serialization

    der = serialization.load_pem_public_key(pem.encode()).public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    h = hashlib.sha256(der).hexdigest()
    return " ".join(h[i : i + 4] for i in range(0, 32, 4))


# ------------------------------------------------------------------ keys


def _kms() -> Any:
    import google.auth
    from google.auth.transport.requests import AuthorizedSession

    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    return AuthorizedSession(creds)


@lru_cache(maxsize=8)
def _kms_public_pem(name: str) -> str:
    r = _kms().get(f"https://cloudkms.googleapis.com/v1/{name}/publicKey", timeout=20)
    r.raise_for_status()
    return str(r.json()["pem"])


@lru_cache(maxsize=1)
def _dev_private() -> Any:
    """A development key kept next to the local store (never used when SIGNING_KEY is set)."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    path = settings().data_dir / "dev_signing_key.pem"
    if path.exists():
        return serialization.load_pem_private_key(path.read_bytes(), password=None)
    k = ec.generate_private_key(ec.SECP256R1())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    path.chmod(0o600)
    return k


def key() -> Key:
    name = settings().signing_key
    if name:
        return Key(name, _kms_public_pem(name), True)
    from cryptography.hazmat.primitives import serialization

    pem = _dev_private().public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    return Key(f"dev:{fingerprint(pem).replace(' ', '')[:16]}", pem, False)


def key_pem(name: str) -> str | None:
    """The public key that signed a receipt: a KMS key version, or the development key if it is this one."""
    if name.startswith("dev:"):
        k = key()
        return k.pem if k.name == name else None
    try:
        return _kms_public_pem(name)
    except Exception as exc:
        log.warning("attest: public key %s not available (%s)", name, str(exc)[:160])
        return None


def sign(data: bytes) -> bytes:
    """A DER-encoded ECDSA P-256 signature over SHA-256(data)."""
    name = settings().signing_key
    if name:
        digest = base64.b64encode(hashlib.sha256(data).digest()).decode()
        r = _kms().post(f"https://cloudkms.googleapis.com/v1/{name}:asymmetricSign", json={"digest": {"sha256": digest}}, timeout=20)
        r.raise_for_status()
        return base64.b64decode(r.json()["signature"])
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec

    return bytes(_dev_private().sign(data, ec.ECDSA(hashes.SHA256())))


def verify(pem: str, signature: bytes, data: bytes) -> bool:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    pub = serialization.load_pem_public_key(pem.encode())
    if not isinstance(pub, ec.EllipticCurvePublicKey):
        return False
    try:
        pub.verify(signature, data, ec.ECDSA(hashes.SHA256()))
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def raw_signature(der: bytes) -> bytes:
    """r || s (64 bytes): the form a browser's WebCrypto verifies."""
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

    r, s = decode_dss_signature(der)
    return r.to_bytes(32, "big") + s.to_bytes(32, "big")


# ------------------------------------------------------------------ the statement


def new_id() -> str:
    raw = "".join(secrets.choice(ALPHABET) for _ in range(12))
    return f"PR-{raw[:4]}-{raw[4:8]}-{raw[8:]}"


def confirmation(evidence: list[Evidence]) -> dict[str, int]:
    """How each value behind the report was confirmed."""
    st = Counter(e.status for e in evidence)
    changed = sum(1 for e in evidence if ledger.changed_by_hand(e))
    return {
        "total": len(evidence),
        "two_readers_agree": st["VERIFIED_2R"],
        "approved_as_read": st["APPROVED"] - changed,
        "changed_by_hand": changed,
        "waiting_for_review": st["NEEDS_REVIEW"] + st["PENDING"],
    }


def headline(project: Project, result: dict[str, Any]) -> dict[str, Any]:
    from app.copilot.report import facts

    tree = result["calc_tree"]
    fs = {f["id"]: f["value"] for f in facts(project, result)}
    return {
        "lines": [
            {
                "line": p["id"],
                "product": p["name"],
                "cn": p["cn_display"],
                "see_t_co2_per_t": tree[p["see_node"]]["display"],
                "buyer_declares_2026": "actual data" if p["buyer"]["basis_2026"] == "actual" else "EU default values",
            }
            for p in result["processes"]
            if p.get("see_node") in tree
        ],
        "buyer_saves_eur_per_year": fs.get("verdict.secured"),
        "lines_on_actual_data": fs.get("report.lines_ready"),
    }


def statement(
    aid: str,
    kind: str,
    project: Project,
    result: dict[str, Any],
    evidence: list[Evidence],
    documents: list[Document],
    files: dict[str, str],
) -> dict[str, Any]:
    chain = ledger.verify(project.id)
    return {
        "schema": SCHEMA,
        "id": aid,
        "kind": kind,
        "issued_at": now(),
        "issuer": "Pramaan",
        "project": {"id": project.id, "company": project.company, "period": result["period_label"], "fictional_sample": project.is_demo},
        "report": {"computed_at": result["computed_at"], "run_id": result.get("run_id"), "code_version": settings().git_sha},
        "headline": headline(project, result),
        "values": confirmation(evidence),
        "fingerprints": {
            "calculation_tree": ledger.sha256(result["calc_tree"]),
            "values": ledger.values_digest(evidence),
            "source_documents": sorted(({"file": d.filename, "sha256": d.sha256} for d in documents), key=lambda x: x["file"]),
            "reference_data": ledger.sha256(refdata.manifest()),
            "change_log": {"entries": chain["entries"], "head": chain["head"], "intact": chain["ok"]},
            "files": files,
        },
    }


def issue(
    aid: str,
    kind: str,
    project: Project,
    result: dict[str, Any],
    evidence: list[Evidence],
    documents: list[Document],
    files: dict[str, bytes],
) -> dict[str, Any]:
    """Write, sign and keep the receipt for one report leaving Pramaan; log it in the change log."""
    with _lock:
        st = statement(aid, kind, project, result, evidence, documents, {n: hashlib.sha256(b).hexdigest() for n, b in files.items()})
        body = ledger.canonical(st)
        k = key()
        rec = {
            "id": aid,
            "project_id": project.id,
            "kind": kind,
            "issued_at": st["issued_at"],
            "statement": body.decode(),
            "signature": base64.b64encode(sign(body)).decode(),
            "key": k.name,
            "alg": ALG,
        }
        store().put_attestation(rec)
    ledger.append(project.id, "report_issued", "Pramaan", subject=aid, after={"kind": kind, "statement_sha256": ledger.sha256(body)})
    return rec


def check(aid: str) -> dict[str, Any] | None:
    """Everything /r/{id} shows: the statement, whether its signature holds, and whether the project
    still matches it (or what changed since, from the change log)."""
    rec = store().get_attestation(aid)
    if rec is None:
        return None
    body = rec["statement"].encode()
    sig = base64.b64decode(rec["signature"])
    pem = key_pem(rec["key"])
    st = json.loads(body)
    out: dict[str, Any] = {
        "id": aid,
        "statement": st,
        "statement_json": rec["statement"],
        "signature": rec["signature"],
        "signature_raw": base64.b64encode(raw_signature(sig)).decode(),
        "alg": rec["alg"],
        "key": {
            "name": rec["key"],
            "pem": pem,
            "fingerprint": fingerprint(pem) if pem else None,
            "trusted": not rec["key"].startswith("dev:"),
        },
        "signature_valid": bool(pem) and verify(pem or "", sig, body),
    }
    p = store().get_project(rec["project_id"])
    if p is None:
        out["now"] = {"project": "deleted"}
        return out
    evidence = store().list_evidence(p.id)
    result = store().get_latest_result(p.id) or {}
    fp = st["fingerprints"]
    chain = store().list_ledger(p.id)
    issued_at = fp["change_log"]["entries"]
    since = [e for e in chain[issued_at:] if e.get("action") != "report_issued"]
    out["now"] = {
        "project": "exists",
        "values_match": ledger.values_digest(evidence) == fp["values"],
        "calculation_matches": bool(result) and ledger.sha256(result.get("calc_tree")) == fp["calculation_tree"],
        "log": ledger.verify(p.id),
        "log_matches_receipt": issued_at == 0 or (len(chain) >= issued_at and chain[issued_at - 1].get("hash") == fp["change_log"]["head"]),
        "changes_since": [{k: e.get(k) for k in ("seq", "at", "actor", "action", "subject", "before", "after")} for e in since[-20:]],
    }
    return out
