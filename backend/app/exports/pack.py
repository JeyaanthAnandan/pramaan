"""M10: verifier pack (zip): report, workbook, source images, evidence index, control log,
reference-data manifest, run receipts and the draft monitoring plan."""

from __future__ import annotations

import base64
import io
import json
import zipfile
from collections.abc import Callable
from typing import Any

from app import refdata
from app.evidence import blobs, ledger
from app.evidence.models import Document, Evidence, Project, Run
from app.evidence.store import store
from app.exports import monitoring_plan, pdf, xlsx
from app.exports.cells import SafeWriter

README = """PRAMAAN VERIFIER PACK — PROVISIONAL
Operator: {company}
Period: {period}
Generated: {generated}

Contents
  report.pdf                 CBAM embedded-emissions report (all numbers from the calculation tree)
  workbook.xlsx              inputs, factors, calculations, money on the table, control checks
  evidence_index.csv         every extracted value: document, region (box_2d 0-1000), both readings, status, approver,
                             what was read before any change by hand
  change_log.json            every approval, change and spot-check mark as a hash chain (each entry hashes the one before)
  control_checks.csv         cross-document control activities (EC Guidance No. 2, Step 7)
  calculation_tree.json      full calculation tree (every node -> evidence, refdata or assumption)
  refdata_manifest.json      official source files with SHA-256, download date, parser version
  run_receipts.json          agent timeline of each processing run (models, durations, tokens)
  monitoring_plan_en.md / _hi.md   DRAFT monitoring plan (Methodology Act Annex II A.5)
  sources/                   the original document photos
  receipt/                   the signed statement (SHA-256 of every file above), its signature and public key: see VERIFY.txt

Pramaan is not a substitute for an accredited verifier. Values marked NEEDS_REVIEW, DEFAULT_USED or ASSUMPTION need attention.
"""


VERIFY = """PRAMAAN RECEIPT {id}

receipt/statement.json is the statement Pramaan signed when this pack was issued: whose report, the
period, the headline figures, how each value was confirmed, and the SHA-256 of every file in this
pack, of each source photo, of the calculation tree and of the official reference data.
receipt/statement.sig is its ECDSA P-256 / SHA-256 signature, made with the key {key}.

Check it with no Pramaan at all (OpenSSL):

  openssl dgst -sha256 -verify receipt/public_key.pem -signature receipt/statement.sig receipt/statement.json

"Verified OK" means the statement is exactly what was signed. Then compare each file:

  shasum -a 256 report.pdf workbook.xlsx evidence_index.csv calculation_tree.json

with "files" in the statement. Online: {url}
"""


def _mp_md(mp: dict[str, Any]) -> str:
    lines = [f"# {mp['title']}", "", f"**{mp['status']}** · basis: {mp['basis']}", "", f"Summary: {mp['summary']}", ""]
    for e in mp["elements"]:
        lines += [f"## {e['no']}. {e['title']}", "", e["content"], ""]
    return "\n".join(lines)


def render(
    project: Project,
    result: dict[str, Any],
    evidence: list[Evidence],
    documents: list[Document],
    runs: list[Run],
    seal: dict[str, Any] | None = None,
    receipt: Callable[[dict[str, bytes]], dict[str, Any]] | None = None,
) -> bytes:
    """The pack as a zip. ``seal`` prints the receipt id on report.pdf; ``receipt`` signs a statement
    over the SHA-256 of every file and the pack then carries it in receipt/ (checkable offline)."""
    buf = io.BytesIO()
    docs = {d.id: d for d in documents}
    files: dict[str, bytes] = {}

    def put(name: str, data: str | bytes) -> None:
        files[name] = data.encode() if isinstance(data, str) else data

    put("README.txt", README.format(company=project.company, period=result["period_label"], generated=result["computed_at"]))
    put("report.pdf", pdf.render(project, result, seal=seal))
    put("workbook.xlsx", xlsx.render(project, result, evidence, documents))
    s = io.StringIO()
    w = SafeWriter(s)
    w.writerow(
        [
            "evidence_id",
            "document",
            "doc_type",
            "page",
            "field_key",
            "label",
            "period",
            "process",
            "value_text",
            "value_num",
            "unit",
            "box_2d",
            "extractor_model",
            "second_reader_model",
            "second_reading",
            "agrees",
            "status",
            "approved_by",
            "approved_at",
            "read_as",
            "changed_by_hand",
        ]
    )
    for e in sorted(evidence, key=lambda x: (x.doc_id, x.field_key, x.period or "")):
        d = docs.get(e.doc_id)
        w.writerow(
            [
                e.id,
                d.filename if d else e.doc_id,
                d.doc_type if d else "",
                e.page,
                e.field_key,
                e.label,
                e.period,
                e.process,
                e.value_text,
                e.value_num,
                e.unit,
                json.dumps(e.box_2d),
                e.extractor_model,
                e.second_reader_model,
                e.second_reading.reading_value if e.second_reading else "",
                e.second_reading.agrees if e.second_reading else "",
                e.status,
                e.approved_by,
                e.approved_at,
                ledger.read_as(e),
                ledger.changed_by_hand(e),
            ]
        )
    put("evidence_index.csv", s.getvalue())
    from app.cbam.spotcheck import items as spot_items

    spot = spot_items(project, evidence, documents)
    s = io.StringIO()
    w = SafeWriter(s)
    w.writerow(
        [
            "evidence_id",
            "why_sampled",
            "field_key",
            "label",
            "value",
            "unit",
            "period",
            "document",
            "checked",
            "matches",
            "note",
            "by",
            "at",
        ]
    )
    for it in spot["items"]:
        m = it["mark"] or {}
        w.writerow(
            [
                it["id"],
                it["why"],
                it["field_key"],
                it["label"],
                it["value_text"],
                it["unit"],
                it["period"],
                it["doc_title"],
                bool(m),
                m.get("match", ""),
                m.get("note", ""),
                m.get("by", ""),
                m.get("at", ""),
            ]
        )
    put("spot_check.csv", s.getvalue())
    s = io.StringIO()
    w = SafeWriter(s)
    w.writerow(["id", "name", "formula", "inputs", "result", "tolerance", "status", "evidence_ids", "reference", "note"])
    for c in result.get("checks", []):
        w.writerow(
            [
                c["id"],
                c["name"],
                c["formula"],
                json.dumps(c["inputs"]),
                c["result"],
                c["tolerance"],
                c["status"],
                " ".join(c["evidence_ids"]),
                c["reference"],
                c.get("note", ""),  # e.g. which months are out of balance, with their figures
            ]
        )
    put("control_checks.csv", s.getvalue())
    put("calculation_tree.json", json.dumps(result["calc_tree"], indent=1, ensure_ascii=False))
    put("refdata_manifest.json", json.dumps(refdata.manifest(), indent=1))
    put("run_receipts.json", json.dumps([r.model_dump() for r in runs], indent=1, ensure_ascii=False))
    put("change_log.json", json.dumps(store().list_ledger(project.id), indent=1, ensure_ascii=False))
    for lang in ("en", "hi"):
        put(f"monitoring_plan_{lang}.md", _mp_md(monitoring_plan.build(project, result, documents, lang)))
    for d in documents:
        try:
            put(f"sources/{d.filename}", blobs.load(d.uri))
        except Exception as exc:  # keep the pack usable even if one blob is unavailable
            put(f"sources/{d.filename}.missing.txt", str(exc))
    if receipt is not None:  # sign a statement listing every file above, then add the receipt itself
        rec = receipt(files)
        files["receipt/statement.json"] = rec["statement"].encode()
        files["receipt/statement.sig"] = base64.b64decode(rec["signature"])
        files["receipt/public_key.pem"] = (rec.get("public_key_pem") or "").encode()
        files["receipt/VERIFY.txt"] = VERIFY.format(id=rec["id"], url=rec.get("url", ""), key=rec["key"]).encode()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()
