"""Source-document storage: local disk (dev), Cloud Storage (Cloud Run), demo assets (read-only)."""

from __future__ import annotations

import hashlib
import shutil
from functools import lru_cache
from pathlib import Path

from app.config import settings


def save(project_id: str, doc_id: str, filename: str, data: bytes, content_type: str) -> tuple[str, str]:
    """Store bytes; returns (uri, sha256)."""
    digest = hashlib.sha256(data).hexdigest()
    safe = "".join(c for c in filename if c.isalnum() or c in "._-")[-80:] or "upload"
    cfg = settings()
    if cfg.bucket:
        from google.cloud import storage  # type: ignore[attr-defined]

        blob = storage.Client(project=cfg.gcp_project).bucket(cfg.bucket).blob(f"projects/{project_id}/{doc_id}/{safe}")
        blob.upload_from_string(data, content_type=content_type)
        return f"gs://{cfg.bucket}/{blob.name}", digest
    path = cfg.data_dir / "blobs" / project_id / doc_id / safe
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path.resolve().as_uri(), digest


@lru_cache(maxsize=64)
def load(uri: str) -> bytes:
    cfg = settings()
    if uri.startswith("demo://"):
        rel = uri.removeprefix("demo://")
        path = (cfg.demo_dir / rel).resolve()
        if not str(path).startswith(str(cfg.demo_dir.resolve())):
            raise PermissionError("path escapes demo dir")
        return path.read_bytes()
    if uri.startswith("file://"):
        path = Path(uri.removeprefix("file://")).resolve()
        if not str(path).startswith(str(cfg.data_dir.resolve())):
            raise PermissionError("path escapes data dir")
        return path.read_bytes()
    if uri.startswith("gs://"):
        from google.cloud import storage  # type: ignore[attr-defined]

        bucket, _, name = uri.removeprefix("gs://").partition("/")
        return storage.Client(project=cfg.gcp_project).bucket(bucket).blob(name).download_as_bytes()
    raise ValueError(f"unsupported uri {uri}")


def delete_project(project_id: str) -> int:
    """Remove every stored source document of a project (its Cloud Storage prefix or local folder);
    returns how many files were removed. Demo photos (demo://) are bundled and never deleted."""
    cfg = settings()
    load.cache_clear()
    if cfg.bucket:
        from google.cloud import storage  # type: ignore[attr-defined]

        n = 0
        for blob in storage.Client(project=cfg.gcp_project).list_blobs(cfg.bucket, prefix=f"projects/{project_id}/"):
            blob.delete()
            n += 1
        return n
    root = (cfg.data_dir / "blobs").resolve()
    path = (root / project_id).resolve()
    if path.parent != root or not path.is_dir():
        return 0
    n = sum(1 for f in path.rglob("*") if f.is_file())
    shutil.rmtree(path)
    return n
