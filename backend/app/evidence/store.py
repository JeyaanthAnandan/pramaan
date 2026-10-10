"""Persistence: in-memory (local/dev, JSON snapshot) or Firestore (Cloud Run).

Firestore layout (brief 7.4):
    projects/{pid}
      documents/{doc_id} · evidence/{eid} · runs/{run_id} · results/{run_id}
    share_links/{token}       (top level so a buyer link resolves without the project id)
"""

from __future__ import annotations

import json
import threading
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
        self.snapshot = snapshot
        if snapshot and snapshot.exists():
            self._load()

    # ---- persistence
    def _save(self) -> None:
        if not self.snapshot:
            return
        self.snapshot.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "projects": [p.model_dump() for p in self.projects.values()],
            "documents": {k: [d.model_dump() for d in v.values()] for k, v in self.documents.items()},
            "evidence": {k: [e.model_dump() for e in v.values()] for k, v in self.evidence.items()},
            "runs": {k: [r.model_dump() for r in v.values()] for k, v in self.runs.items()},
            "results": {k: v[-3:] for k, v in self.results.items()},
            "shares": [s.model_dump() for s in self.shares.values()],
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
            for d in (self.projects, self.documents, self.evidence, self.runs, self.results):
                d.pop(pid, None)
            self.shares = {k: v for k, v in self.shares.items() if v.project_id != pid}
            self._save()

    # ---- documents
    def put_document(self, d: Document) -> None:
        with self._lock:
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
        s = self._p(pid).get()
        return Project(**(s.to_dict() or {})) if s.exists else None

    def list_projects(self) -> list[Project]:
        return [Project(**(s.to_dict() or {})) for s in self.db.collection("projects").stream()]

    def delete_project(self, pid: str) -> None:
        for sub in ["documents", "evidence", "runs", "results"]:
            for s in self._p(pid).collection(sub).stream():
                s.reference.delete()
        self._p(pid).delete()

    def put_document(self, d: Document) -> None:
        self._p(d.project_id).collection("documents").document(d.id).set(d.model_dump())

    def get_document(self, pid: str, doc_id: str) -> Document | None:
        s = self._p(pid).collection("documents").document(doc_id).get()
        return Document(**(s.to_dict() or {})) if s.exists else None

    def list_documents(self, pid: str) -> list[Document]:
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
        s = self._p(pid).collection("evidence").document(eid).get()
        return Evidence(**(s.to_dict() or {})) if s.exists else None

    def list_evidence(self, pid: str) -> list[Evidence]:
        return [Evidence(**s.to_dict()) for s in self._p(pid).collection("evidence").stream()]

    def delete_evidence_for_doc(self, pid: str, doc_id: str) -> None:
        for s in self._p(pid).collection("evidence").where("doc_id", "==", doc_id).stream():
            s.reference.delete()

    def put_run(self, r: Run) -> None:
        self._p(r.project_id).collection("runs").document(r.id).set(r.model_dump())

    def get_run(self, pid: str, run_id: str) -> Run | None:
        s = self._p(pid).collection("runs").document(run_id).get()
        return Run(**(s.to_dict() or {})) if s.exists else None

    def list_runs(self, pid: str) -> list[Run]:
        return sorted((Run(**s.to_dict()) for s in self._p(pid).collection("runs").stream()), key=lambda r: r.started_at)

    def append_event(self, pid: str, run_id: str, ev: TimelineEvent) -> None:
        from google.cloud import firestore

        self._p(pid).collection("runs").document(run_id).update({"events": firestore.ArrayUnion([ev.model_dump()])})

    def put_result(self, pid: str, run_id: str, result: dict[str, Any]) -> None:
        self._p(pid).collection("results").document(run_id).set(
            {"run_id": run_id, "result_json": json.dumps(result), "created": result.get("computed_at")}
        )

    def get_latest_result(self, pid: str) -> dict[str, Any] | None:
        docs = list(self._p(pid).collection("results").order_by("created", direction="DESCENDING").limit(1).stream())
        return json.loads(docs[0].to_dict()["result_json"]) if docs else None

    def put_share(self, s: ShareLink) -> None:
        self.db.collection("share_links").document(s.token).set(s.model_dump())

    def get_share(self, token: str) -> ShareLink | None:
        s = self.db.collection("share_links").document(token).get()
        return ShareLink(**(s.to_dict() or {})) if s.exists else None


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
