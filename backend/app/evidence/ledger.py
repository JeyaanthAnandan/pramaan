"""The change log: every change to a project's values, as a hash chain.

Each entry (values read by a run, a value approved or changed by hand, a verifier's spot-check mark,
a report issued) carries the SHA-256 of the entry before it, so an entry cannot be edited, removed
or slipped in later without breaking every hash after it. ``verify`` recomputes the chain; each
signed report (``attest``) records the chain's head at the time it was issued, which anchors the
log outside the database.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.evidence.models import Evidence, now
from app.evidence.store import store

GENESIS = "0" * 64


def canonical(obj: Any) -> bytes:
    """One byte string per value: sorted keys, no spaces, UTF-8 (what is hashed and signed)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()


def sha256(obj: Any) -> str:
    return hashlib.sha256(obj if isinstance(obj, bytes) else canonical(obj)).hexdigest()


def entry_hash(e: dict[str, Any]) -> str:
    return sha256({k: v for k, v in e.items() if k != "hash"})


def values_digest(evidence: list[Evidence]) -> str:
    """The values a report is computed from: what each one is, what it says and who stands behind it."""
    keys = ("id", "doc_id", "field_key", "period", "process", "value_text", "value_num", "unit", "status")
    return sha256(sorted(([getattr(e, k) for k in keys] for e in evidence), key=lambda r: str(r[0])))


def append(
    pid: str,
    action: str,
    actor: str,
    subject: str | None = None,
    before: Any = None,
    after: Any = None,
    note: str | None = None,
) -> dict[str, Any]:
    """Add one entry at the end of the chain. Two writers at once: the store refuses the second
    entry with the same number, which then re-reads the head and tries again."""
    for _ in range(8):
        head = store().ledger_head(pid)
        e: dict[str, Any] = {
            "seq": head["seq"] + 1 if head else 1,
            "at": now(),
            "actor": actor[:80],
            "action": action,
            "subject": subject,
            "before": before,
            "after": after,
            "note": (note or None) and note[:300],
            "prev": head["hash"] if head else GENESIS,
        }
        e["hash"] = entry_hash(e)
        if store().append_ledger(pid, e):
            return e
    raise RuntimeError("the change log is busy; try again")


def verify(pid: str) -> dict[str, Any]:
    """Recompute the chain: every hash matches its entry, links to the one before, numbers run 1..n."""
    chain = store().list_ledger(pid)
    prev = GENESIS
    for i, e in enumerate(chain, 1):
        if e.get("seq") != i or e.get("prev") != prev or entry_hash(e) != e.get("hash"):
            return {"ok": False, "entries": len(chain), "broken_at": i, "head": None}
        prev = e["hash"]
    return {"ok": True, "entries": len(chain), "broken_at": None, "head": prev if chain else GENESIS}


def changed_by_hand(e: Evidence) -> bool:
    """A value a person changed (not just approved as read)."""
    for h in e.history:
        b = h.get("before") or {}
        if h.get("action") == "edit" and (b.get("value_num") != e.value_num or b.get("value_text") != e.value_text):
            return True
    return False


def read_as(e: Evidence) -> str:
    """The value as the readers read it, before any change by hand."""
    edits = [h for h in e.history if h.get("action") == "edit"]
    return str((edits[0].get("before") or {}).get("value_text") or "") if edits else e.value_text
