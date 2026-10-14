"""Verifier spot-check: a risk-based sample of the values behind the result, each with its crop.

A verifier does not re-read every bill; it samples the data points that matter (ISO 14065 / 14064-3
style). The sample takes every value a person changed or approved, the supplier's own emissions data,
then the activity data in order of weight: production (the denominator of every SEE), rod consumed
and bought (about 90 % of a bolt's emissions come with the rod), gas energy (the plant's direct
emissions), scrap and exported quantities. Within a stratum the pick is random but fixed per project,
so the sample does not change while the verifier works through it. The verifier marks each value as
matching the document or not; the marks are kept on the evidence (with an audit-trail entry) and go
into the verifier pack.
"""

from __future__ import annotations

import hashlib
import random
from typing import Any

from app.evidence.ledger import changed_by_hand
from app.evidence.models import Document, Evidence, Project

SIZE = 12
# stratum, how many, which values (field_key, document type or None for any)
STRATA: list[tuple[str, int, set[str], set[str] | None]] = [
    ("supplier", 2, {"see", "sefa"}, {"supplier_emissions_statement"}),
    ("activity", 2, {"produced_t"}, {"production_register"}),
    ("rod", 2, {"rod_consumed_t"}, {"production_register"}),
    ("energy", 2, {"mmbtu"}, {"gas_invoice"}),
    ("rod_bought", 1, {"tonnes"}, {"precursor_invoice"}),
    ("scrap", 1, {"scrap_t"}, {"scrap_log"}),
    ("exports", 1, {"net_mass_kg"}, {"export_invoice"}),
]
MANUAL_CAP = 3


def _padded(box: list[int]) -> list[int]:
    """The region with the same 15 % padding the second reader's crop uses."""
    ymin, xmin, ymax, xmax = box
    py, px = max((ymax - ymin) * 0.15, 6), max((xmax - xmin) * 0.15, 6)
    return [max(0, int(ymin - py)), max(0, int(xmin - px)), min(1000, int(ymax + py)), min(1000, int(xmax + px))]


def sample(project: Project, evidence: list[Evidence], documents: list[Document], size: int = SIZE) -> list[tuple[str, Evidence]]:
    """(stratum, evidence) pairs in the order a verifier should check them."""
    rng = random.Random(int(hashlib.sha256(project.id.encode()).hexdigest()[:12], 16))
    doc_type = {d.id: d.doc_type for d in documents}
    boxed = sorted((e for e in evidence if e.box_2d), key=lambda e: e.id)
    picked: list[tuple[str, Evidence]] = []
    seen: set[str] = set()

    def take(why: str, pool: list[Evidence], n: int) -> None:
        pool = [e for e in pool if e.id not in seen]
        for e in rng.sample(pool, min(n, len(pool))):
            picked.append((why, e))
            seen.add(e.id)

    # values a person changed come first (a verifier asks about every manual correction), then approvals
    manual = [e for e in boxed if e.status == "APPROVED" or e.approved_by]
    changed = [e for e in manual if changed_by_hand(e)]
    take("manual", changed, MANUAL_CAP)
    take("manual", manual, MANUAL_CAP - len(picked))
    for why, n, keys, types in STRATA:
        take(why, [e for e in boxed if e.field_key in keys and (types is None or doc_type.get(e.doc_id) in types)], n)
    if len(picked) < size:  # a factory without some of these documents: fill from the other inputs
        relevant = {k for _, _, keys, _ in STRATA for k in keys} | {"scm", "gcv_kcal_per_scm", "opening_stock_t", "closing_stock_t"}
        take("other", [e for e in boxed if e.field_key in relevant], size - len(picked))
    return picked[: max(size, len([p for p in picked if p[0] == "manual"]))]


def items(project: Project, evidence: list[Evidence], documents: list[Document]) -> dict[str, Any]:
    docs = {d.id: d for d in documents}
    lines = {p.id: p.name for p in project.processes}
    picked = sample(project, evidence, documents)
    out: list[dict[str, Any]] = []
    for why, e in picked:
        d = docs.get(e.doc_id)
        sr = e.second_reading
        out.append(
            {
                "id": e.id,
                "why": why,
                "field_key": e.field_key,
                "label": e.label,
                "value_text": e.value_text,
                "unit": e.unit,
                "period": e.period,
                "line": lines.get(e.process or "", None),
                "doc_id": e.doc_id,
                "doc_title": d.title if d else e.doc_id,
                "doc_type": d.doc_type if d else None,
                "width": d.width if d else None,
                "height": d.height if d else None,
                "crop_box": sr.crop_box if sr and sr.crop_box else _padded(e.box_2d or [0, 0, 1000, 1000]),
                "status": e.status,
                "approved_by": e.approved_by,
                "second": sr.reading_value if sr else None,
                "mark": e.spot_check,
            }
        )
    marks: list[dict[str, Any]] = [e.spot_check for _, e in picked if e.spot_check]
    last = max(marks, key=lambda m: m.get("at") or "") if marks else None
    return {
        "items": out,
        "summary": {
            "total": len(out),
            "checked": len(marks),
            "match": sum(1 for m in marks if m.get("match")),
            "differ": sum(1 for m in marks if not m.get("match")),
            "by": last.get("by") if last else None,
            "at": last.get("at") if last else None,
        },
    }
