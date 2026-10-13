"""M10: verifier pack (zip): report, workbook, source images, evidence index, control log,
reference-data manifest, run receipts and the draft monitoring plan."""

from __future__ import annotations

import io
import json
import zipfile
from typing import Any

from app import refdata
from app.evidence import blobs
from app.evidence.models import Document, Evidence, Project, Run
from app.exports import monitoring_plan, pdf, xlsx
from app.exports.cells import SafeWriter

README = """PRAMAAN VERIFIER PACK — PROVISIONAL
Operator: {company}
Period: {period}
Generated: {generated}

Contents
  report.pdf                 CBAM embedded-emissions report (all numbers from the calculation tree)
  workbook.xlsx              inputs, factors, calculations, money on the table, control checks
  evidence_index.csv         every extracted value: document, region (box_2d 0-1000), both readings, status, approver
  control_checks.csv         cross-document control activities (EC Guidance No. 2, Step 7)
  calculation_tree.json      full calculation tree (every node -> evidence, refdata or assumption)
  refdata_manifest.json      official source files with SHA-256, download date, parser version
  run_receipts.json          agent timeline of each processing run (models, durations, tokens)
  monitoring_plan_en.md / _hi.md   DRAFT monitoring plan (Methodology Act Annex II A.5)
  sources/                   the original document photos

Pramaan is not a substitute for an accredited verifier. Values marked NEEDS_REVIEW, DEFAULT_USED or ASSUMPTION need attention.
"""


def _mp_md(mp: dict[str, Any]) -> str:
    lines = [f"# {mp['title']}", "", f"**{mp['status']}** · basis: {mp['basis']}", "", f"Summary: {mp['summary']}", ""]
    for e in mp["elements"]:
        lines += [f"## {e['no']}. {e['title']}", "", e["content"], ""]
    return "\n".join(lines)


def render(project: Project, result: dict[str, Any], evidence: list[Evidence], documents: list[Document], runs: list[Run]) -> bytes:
    buf = io.BytesIO()
    docs = {d.id: d for d in documents}
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("README.txt", README.format(company=project.company, period=result["period_label"], generated=result["computed_at"]))
        z.writestr("report.pdf", pdf.render(project, result))
        z.writestr("workbook.xlsx", xlsx.render(project, result, evidence, documents))
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
                ]
            )
        z.writestr("evidence_index.csv", s.getvalue())
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
        z.writestr("spot_check.csv", s.getvalue())
        s = io.StringIO()
        w = SafeWriter(s)
        w.writerow(["id", "name", "formula", "inputs", "result", "tolerance", "status", "evidence_ids", "reference"])
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
                ]
            )
        z.writestr("control_checks.csv", s.getvalue())
        z.writestr("calculation_tree.json", json.dumps(result["calc_tree"], indent=1, ensure_ascii=False))
        z.writestr("refdata_manifest.json", json.dumps(refdata.manifest(), indent=1))
        z.writestr("run_receipts.json", json.dumps([r.model_dump() for r in runs], indent=1, ensure_ascii=False))
        for lang in ("en", "hi"):
            z.writestr(f"monitoring_plan_{lang}.md", _mp_md(monitoring_plan.build(project, result, documents, lang)))
        for d in documents:
            try:
                z.writestr(f"sources/{d.filename}", blobs.load(d.uri))
            except Exception as exc:  # keep the pack usable even if one blob is unavailable
                z.writestr(f"sources/{d.filename}.missing.txt", str(exc))
    return buf.getvalue()
