"""Persistence: in-memory (local/dev, JSON snapshot) or Firestore (Cloud Run).

Firestore layout (brief 7.4):
    projects/{pid}
      documents/{doc_id} · evidence/{eid} · runs/{run_id} · results/{run_id}
      ledger/{seq:08d}        (the change log: a hash chain, see ledger.py)
    share_links/{token}       (top level so a buyer link resolves without the project id)
    attestations/{id}         (signed report receipts: top level, checked by anyone holding the id)
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Protocol

from app.config import settings
from app.evidence.models import Document, Evidence, Project, Run, ShareLink, TimelineEvent


class Store(Protocol):
    def put_project(self, p: Project) -> None: ...
    def get_project(self, pid: str) -> Project | None: ...
    def list_projects(self) -> list[Project]: ...
    def delete_project(self, pid: str) -> None: ...
    def put_document(self, d: Document) -> None: ...
    def put_documents(self, items: list[Document]) -> None: ...
    def get_document(self, pid: str, doc_id: str) -> Document | None: ...
    def list_documents(self, pid: str) -> list[Document]: ...
    def put_evidence(self, items: list[Evidence]) -> None: ...
    def get_evidence(self, pid: str, eid: str) -> Evidence | None: ...
    def list_evidence(self, pid: str) -> list[Evidence]: ...
    def delete_evidence_for_doc(self, pid: str, doc_id: str) -> None: ...
    def put_run(self, r: Run) -> None: ...
    def get_run(self, pid: str, run_id: str) -> Run | None: ...
    def list_runs(self, pid: str) -> list[Run]: ...
    def append_event(self, pid: str, run_id: str, ev: TimelineEvent) -> None: ...
    def put_result(self, pid: str, run_id: str, result: dict[str, Any]) -> None: ...
    def get_latest_result(self, pid: str) -> dict[str, Any] | None: ...
    def put_share(self, s: ShareLink) -> None: ...
    def get_share(self, token: str) -> ShareLink | None: ...
    def append_ledger(self, pid: str, entry: dict[str, Any]) -> bool: ...
    def ledger_head(self, pid: str) -> dict[str, Any] | None: ...
    def list_ledger(self, pid: str) -> list[dict[str, Any]]: ...
    def put_attestation(self, a: dict[str, Any]) -> None: ...
    def get_attestation(self, aid: str) -> dict[str, Any] | None: ...


class MemoryStore:
    """Thread-safe dict store with an optional JSON snapshot (survives local restarts)."""

    def __init__(self, snapshot: Path | None = None) -> None:
        self._lock = threading.RLock()
        self.projects: dict[str, Project] = {}
        self.documents: dict[str, dict[str, Document]] = {}
        self.evidence: dict[str, dict[str, Evidence]] = {}
        self.runs: dict[str, dict[str, Run]] = {}
        self.results: dict[str, list[tuple[str, dict[str, Any]]]] = {}
        self.shares: dict[str, ShareLink] = {}
        self.ledger: dict[str, list[dict[str, Any]]] = {}
        self.attestations: dict[str, dict[str, Any]] = {}
        self.snapshot = snapshot
        self._timer: threading.Timer | None = None
        if snapshot and snapshot.exists():
            self._load()

    # ---- persistence
    def _save(self) -> None:
        """Debounced: many small writes during a run collapse into one snapshot write."""
        if not self.snapshot:
            return
        if self._timer is None or not self._timer.is_alive():
            self._timer = threading.Timer(1.0, self._flush)
            self._timer.daemon = True
            self._timer.start()

    def _flush(self) -> None:
        if not self.snapshot:
            return
        with self._lock:
            self._write()

    def _write(self) -> None:
        assert self.snapshot
        self.snapshot.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "projects": [p.model_dump() for p in self.projects.values()],
            "documents": {k: [d.model_dump() for d in v.values()] for k, v in self.documents.items()},
            "evidence": {k: [e.model_dump() for e in v.values()] for k, v in self.evidence.items()},
            "runs": {k: [r.model_dump() for r in v.values()] for k, v in self.runs.items()},
            "results": {k: v[-3:] for k, v in self.results.items()},
            "shares": [s.model_dump() for s in self.shares.values()],
            "ledger": self.ledger,
            "attestations": list(self.attestations.values()),
        }
        tmp = self.snapshot.with_suffix(".tmp")
        tmp.write_text(json.dumps(data))
        tmp.replace(self.snapshot)

    def _load(self) -> None:
        assert self.snapshot
        try:
            data = json.loads(self.snapshot.read_text())
        except (OSError, json.JSONDecodeError):
            return
        self.projects = {p["id"]: Project(**p) for p in data.get("projects", [])}
        self.documents = {k: {d["id"]: Document(**d) for d in v} for k, v in data.get("documents", {}).items()}
        self.evidence = {k: {e["id"]: Evidence(**e) for e in v} for k, v in data.get("evidence", {}).items()}
        self.runs = {k: {r["id"]: Run(**r) for r in v} for k, v in data.get("runs", {}).items()}
        self.results = {k: [tuple(x) for x in v] for k, v in data.get("results", {}).items()}  # type: ignore[misc]
        self.shares = {s["token"]: ShareLink(**s) for s in data.get("shares", [])}
        self.ledger = data.get("ledger", {})
        self.attestations = {a["id"]: a for a in data.get("attestations", [])}

    # ---- projects
    def put_project(self, p: Project) -> None:
        with self._lock:
            self.projects[p.id] = p
            self._save()

    def get_project(self, pid: str) -> Project | None:
        return self.projects.get(pid)

    def list_projects(self) -> list[Project]:
        return list(self.projects.values())

    def delete_project(self, pid: str) -> None:
        with self._lock:
            for d in (self.projects, self.documents, self.evidence, self.runs, self.results, self.ledger):
                d.pop(pid, None)
            self.shares = {k: v for k, v in self.shares.items() if v.project_id != pid}
            self.attestations = {k: v for k, v in self.attestations.items() if v.get("project_id") != pid}
            self._save()

    # ---- documents
    def put_document(self, d: Document) -> None:
        with self._lock:
            self.documents.setdefault(d.project_id, {})[d.id] = d
            self._save()

    def put_documents(self, items: list[Document]) -> None:
        with self._lock:
            for d in items:
                self.documents.setdefault(d.project_id, {})[d.id] = d
            self._save()

    def get_document(self, pid: str, doc_id: str) -> Document | None:
        return self.documents.get(pid, {}).get(doc_id)

    def list_documents(self, pid: str) -> list[Document]:
        return list(self.documents.get(pid, {}).values())

    # ---- evidence
    def put_evidence(self, items: list[Evidence]) -> None:
        with self._lock:
            for e in items:
                self.evidence.setdefault(e.project_id, {})[e.id] = e
            self._save()

    def get_evidence(self, pid: str, eid: str) -> Evidence | None:
        return self.evidence.get(pid, {}).get(eid)

    def list_evidence(self, pid: str) -> list[Evidence]:
        return list(self.evidence.get(pid, {}).values())

    def delete_evidence_for_doc(self, pid: str, doc_id: str) -> None:
        with self._lock:
            ev = self.evidence.get(pid, {})
            for k in [k for k, v in ev.items() if v.doc_id == doc_id]:
                ev.pop(k)
            self._save()

    # ---- runs
    def put_run(self, r: Run) -> None:
        with self._lock:
            self.runs.setdefault(r.project_id, {})[r.id] = r
            self._save()

    def get_run(self, pid: str, run_id: str) -> Run | None:
        return self.runs.get(pid, {}).get(run_id)

    def list_runs(self, pid: str) -> list[Run]:
        if not valid_id(pid):
            return []
        return sorted(self.runs.get(pid, {}).values(), key=lambda r: r.started_at)

    def append_event(self, pid: str, run_id: str, ev: TimelineEvent) -> None:
        with self._lock:
            r = self.runs.get(pid, {}).get(run_id)
            if r and not any(e.seq == ev.seq for e in r.events):
                r.events.append(ev)

    # ---- results
    def put_result(self, pid: str, run_id: str, result: dict[str, Any]) -> None:
        with self._lock:
            self.results.setdefault(pid, []).append((run_id, result))
            self.results[pid] = self.results[pid][-3:]
            self._save()

    def get_latest_result(self, pid: str) -> dict[str, Any] | None:
        r = self.results.get(pid)
        return r[-1][1] if r else None

    # ---- share links
    def put_share(self, s: ShareLink) -> None:
        with self._lock:
            self.shares[s.token] = s
            self._save()

    def get_share(self, token: str) -> ShareLink | None:
        return self.shares.get(token)

    # ---- change log and signed receipts
    def append_ledger(self, pid: str, entry: dict[str, Any]) -> bool:
        with self._lock:
            chain = self.ledger.setdefault(pid, [])
            if entry["seq"] != len(chain) + 1:
                return False
            chain.append(entry)
            self._save()
            return True

    def ledger_head(self, pid: str) -> dict[str, Any] | None:
        chain = self.ledger.get(pid) or []
        return chain[-1] if chain else None

    def list_ledger(self, pid: str) -> list[dict[str, Any]]:
        return list(self.ledger.get(pid) or [])

    def put_attestation(self, a: dict[str, Any]) -> None:
        with self._lock:
            self.attestations[a["id"]] = a
            self._save()

    def get_attestation(self, aid: str) -> dict[str, Any] | None:
        return self.attestations.get(aid)


def valid_id(*ids: str) -> bool:
    """False for an id Firestore rejects outright (empty, "." or "..", a "/", a reserved __name__, more than
    1,500 bytes): such an id comes from a mistyped or hostile URL and cannot exist, so it is not found
    instead of turning into a server error."""
    return all(
        x and x not in {".", ".."} and "/" not in x and not (x.startswith("__") and x.endswith("__")) and len(x.encode()) <= 1500
        for x in ids
    )


class FirestoreStore:
    """Firestore (Native mode) implementation used on Cloud Run."""

    def __init__(self, project: str) -> None:
        from google.cloud import firestore  # lazy: not needed for local runs

        self.db = firestore.Client(project=project)

    def _p(self, pid: str) -> Any:
        return self.db.collection("projects").document(pid)

    def put_project(self, p: Project) -> None:
        self._p(p.id).set(p.model_dump())

    def get_project(self, pid: str) -> Project | None:
        if not valid_id(pid):
            return None
        s = self._p(pid).get()
        return Project(**(s.to_dict() or {})) if s.exists else None

    def list_projects(self) -> list[Project]:
        return [Project(**(s.to_dict() or {})) for s in self.db.collection("projects").stream()]

    def delete_project(self, pid: str) -> None:
        # batched: a sample copy is ~250 records, and deleting them one call at a time took ~2 s per copy
        subs = ["documents", "evidence", "runs", "results", "ledger"]
        refs = [s.reference for sub in subs for s in self._p(pid).collection(sub).stream()]
        refs += [s.reference for s in self.db.collection("share_links").where("project_id", "==", pid).stream()]  # buyer + supplier links
        refs += [s.reference for s in self.db.collection("attestations").where("project_id", "==", pid).stream()]
        refs.append(self._p(pid))
        batch = self.db.batch()
        for n, ref in enumerate(refs, 1):
            batch.delete(ref)
            if n % 400 == 0:
                batch.commit()
                batch = self.db.batch()
        batch.commit()

    def put_document(self, d: Document) -> None:
        self._p(d.project_id).collection("documents").document(d.id).set(d.model_dump())

    def put_documents(self, items: list[Document]) -> None:
        batch = self.db.batch()
        for d in items:
            batch.set(self._p(d.project_id).collection("documents").document(d.id), d.model_dump())
        batch.commit()

    def get_document(self, pid: str, doc_id: str) -> Document | None:
        if not valid_id(pid, doc_id):
            return None
        s = self._p(pid).collection("documents").document(doc_id).get()
        return Document(**(s.to_dict() or {})) if s.exists else None

    def list_documents(self, pid: str) -> list[Document]:
        if not valid_id(pid):
            return []
        return [Document(**s.to_dict()) for s in self._p(pid).collection("documents").stream()]

    def put_evidence(self, items: list[Evidence]) -> None:
        batch = self.db.batch()
        for n, e in enumerate(items, 1):
            batch.set(self._p(e.project_id).collection("evidence").document(e.id), e.model_dump())
            if n % 400 == 0:
                batch.commit()
                batch = self.db.batch()
        batch.commit()

    def get_evidence(self, pid: str, eid: str) -> Evidence | None:
        if not valid_id(pid, eid):
            return None
        s = self._p(pid).collection("evidence").document(eid).get()
        return Evidence(**(s.to_dict() or {})) if s.exists else None

    def list_evidence(self, pid: str) -> list[Evidence]:
        if not valid_id(pid):
            return []
        return [Evidence(**s.to_dict()) for s in self._p(pid).collection("evidence").stream()]

    def delete_evidence_for_doc(self, pid: str, doc_id: str) -> None:
        for s in self._p(pid).collection("evidence").where("doc_id", "==", doc_id).stream():
            s.reference.delete()

    def put_run(self, r: Run) -> None:
        self._p(r.project_id).collection("runs").document(r.id).set(r.model_dump())

    def get_run(self, pid: str, run_id: str) -> Run | None:
        if not valid_id(pid, run_id):
            return None
        s = self._p(pid).collection("runs").document(run_id).get()
        return Run(**(s.to_dict() or {})) if s.exists else None

    def list_runs(self, pid: str) -> list[Run]:
        if not valid_id(pid):
            return []
        return sorted((Run(**s.to_dict()) for s in self._p(pid).collection("runs").stream()), key=lambda r: r.started_at)

    def append_event(self, pid: str, run_id: str, ev: TimelineEvent) -> None:
        from google.cloud import firestore

        self._p(pid).collection("runs").document(run_id).update({"events": firestore.ArrayUnion([ev.model_dump()])})

    def put_result(self, pid: str, run_id: str, result: dict[str, Any]) -> None:
        # high-precision key: several results (run, recalculations) can land within the same second
        self._p(pid).collection("results").document(run_id).set(
            {"run_id": run_id, "result_json": json.dumps(result), "created": time.time_ns()}
        )

    def get_latest_result(self, pid: str) -> dict[str, Any] | None:
        if not valid_id(pid):
            return None
        docs = list(self._p(pid).collection("results").order_by("created", direction="DESCENDING").limit(1).stream())
        return json.loads(docs[0].to_dict()["result_json"]) if docs else None

    def put_share(self, s: ShareLink) -> None:
        self.db.collection("share_links").document(s.token).set(s.model_dump())

    def get_share(self, token: str) -> ShareLink | None:
        if not valid_id(token):
            return None
        s = self.db.collection("share_links").document(token).get()
        return ShareLink(**(s.to_dict() or {})) if s.exists else None

    def append_ledger(self, pid: str, entry: dict[str, Any]) -> bool:
        """create() fails if the number is taken: of two writers at once, one appends and one retries."""
        from google.api_core.exceptions import AlreadyExists

        try:
            self._p(pid).collection("ledger").document(f"{entry['seq']:08d}").create(entry)
            return True
        except AlreadyExists:
            return False

    def ledger_head(self, pid: str) -> dict[str, Any] | None:
        docs = list(self._p(pid).collection("ledger").order_by("seq", direction="DESCENDING").limit(1).stream())
        return docs[0].to_dict() if docs else None

    def list_ledger(self, pid: str) -> list[dict[str, Any]]:
        if not valid_id(pid):
            return []
        return [s.to_dict() or {} for s in self._p(pid).collection("ledger").order_by("seq").stream()]

    def put_attestation(self, a: dict[str, Any]) -> None:
        self.db.collection("attestations").document(a["id"]).set(a)

    def get_attestation(self, aid: str) -> dict[str, Any] | None:
        if not valid_id(aid):
            return None
        s = self.db.collection("attestations").document(aid).get()
        return s.to_dict() if s.exists else None


_store: Store | None = None


def store() -> Store:
    global _store
    if _store is None:
        cfg = settings()
        if cfg.store_backend == "firestore":
            _store = FirestoreStore(cfg.gcp_project)
        else:
            _store = MemoryStore(cfg.data_dir / "store.json")
    return _store


def set_store(s: Store | None) -> None:
    """Tests inject a fresh MemoryStore."""
    global _store
    _store = s
