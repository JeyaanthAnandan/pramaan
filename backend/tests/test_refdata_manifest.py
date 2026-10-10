"""Reference-data integrity: every refdata file is traceable to an official source."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

REFDATA = Path(__file__).resolve().parents[1] / "refdata"
MANIFEST = json.loads((REFDATA / "manifest.json").read_text())


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_every_json_file_has_a_manifest_entry() -> None:
    on_disk = {f"json/{p.name}" for p in (REFDATA / "json").glob("*.json")}
    missing = on_disk - set(MANIFEST["files"])
    assert not missing, f"refdata files without manifest entry: {missing}"
    stale = set(MANIFEST["files"]) - on_disk
    assert not stale, f"manifest lists files that do not exist: {stale}"


@pytest.mark.parametrize("name", sorted(MANIFEST["files"]))
def test_json_hash_matches_manifest(name: str) -> None:
    assert _sha(REFDATA / name) == MANIFEST["files"][name]["sha256"], f"{name} changed without rebuilding the manifest"


@pytest.mark.parametrize("name", sorted(MANIFEST["files"]))
def test_file_entry_has_parser_version_and_known_sources(name: str) -> None:
    e = MANIFEST["files"][name]
    assert e["parser_version"] == MANIFEST["parser_version"]
    for sid in e["sources"]:
        assert sid in MANIFEST["sources"], f"{name} cites unknown source {sid}"
    if e["status"] == "official":
        assert e["sources"], f"{name} is official but cites no source"


@pytest.mark.parametrize("sid", sorted(MANIFEST["sources"]))
def test_source_has_url_date_and_matching_hash(sid: str) -> None:
    s = MANIFEST["sources"][sid]
    assert s["url"].startswith("https://")
    assert len(s["downloaded_at"]) == 10
    path = (REFDATA / s["path"]).resolve()
    assert path.exists(), f"source file missing: {path}"
    assert _sha(path) == s["sha256"], f"source {sid} differs from manifest"


def test_assumptions_are_flagged_and_cited() -> None:
    a = json.loads((REFDATA / "json" / "assumptions.json").read_text())["assumptions"]
    assert a
    for key, v in a.items():
        assert v["status"] == "assumption", key
        assert v["citation"], key


def test_no_hand_typed_values_in_engine_source() -> None:
    """The engine module must not embed regulatory constants (they come from refdata)."""
    src = (Path(__file__).resolve().parents[1] / "app" / "cbam" / "engine.py").read_text()
    for forbidden in ["56.1", "0.975", "1.364", "82.32", "75.36", "0.038", "5.720"]:
        assert forbidden not in src, f"engine.py contains a hard-coded regulatory value {forbidden}"
