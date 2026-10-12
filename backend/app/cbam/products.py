"""Product-line setup for an exporter's own project.

A product line = one exported CN group made from one purchased steel precursor. Every CN code a
person types or the ProductLines agent proposes is checked against the official refdata before it
is used: the good needs a benchmark row (column A for actual data, column B for the default path)
and a default value for the country; the precursor needs a default value and a column B benchmark.
"""

from __future__ import annotations

import re
from typing import Any

from app import refdata
from app.evidence.models import ProcessDef, Project, SupplierRequest

STEEL = "Iron & Steel"


def countries() -> list[str]:
    return sorted(refdata.data("default_values_iron_steel.json")["countries"].keys())


def cn_info(cn: str, country: str = "India", role: str = "good") -> dict[str, Any]:
    """Validate one CN code for its role ("good" or "precursor") against the official files."""
    cnd = refdata.norm_cn(cn)
    out: dict[str, Any] = {
        "cn": cnd,
        "cn_display": refdata.fmt_cn(cnd) if cnd else "",
        "role": role,
        "ok": False,
        "description": "",
        "default_value": None,
        "default_locator": None,
        "default_fallback": False,
        "route": None,
        "errors": [],
    }
    if len(cnd) != 8:
        out["errors"].append("A CN code has 8 digits (for example 7318 15 82).")
        return out
    row = refdata.data("benchmarks.json")["benchmarks"].get(cnd)
    if row is None or row.get("sector") != STEEL:
        out["errors"].append("Not an iron or steel good in the CBAM benchmark list (Reg. 2025/2620).")
        return out
    out["description"] = row["description"]
    try:
        dv = refdata.default_value(country, cnd)
    except refdata.RefdataError as exc:
        out["errors"].append(f"No default value: {exc}")
        return out
    out["default_value"] = str(dv.value)
    out["default_locator"] = dv.locator
    out["default_fallback"] = bool(dv.extra.get("fallback"))
    route = (dv.extra.get("route") or "").strip("()") or None
    out["route"] = route
    try:
        if role == "good":
            refdata.benchmark(cnd, "A", 2026)
        refdata.benchmark(cnd, "B", 2026, route=route)
        refdata.benchmark(cnd, "B", 2028, route=route)
    except refdata.RefdataError as exc:
        out["errors"].append(f"Benchmark not usable: {exc}")
        return out
    out["ok"] = True
    return out


def search(q: str, country: str = "India", limit: int = 12) -> list[dict[str, Any]]:
    """Iron & steel CN codes whose description (or digits) match every word of the query."""
    q = q.strip().lower()
    if not q:
        return []
    digits = refdata.norm_cn(q)
    words = [w for w in re.split(r"[^a-z0-9]+", q) if len(w) > 1 and not w.isdigit()]
    out = []
    for cn, row in refdata.data("benchmarks.json")["benchmarks"].items():
        if row.get("sector") != STEEL:
            continue
        desc = row["description"].lower()
        if digits and not words:
            hit = cn.startswith(digits)
        else:
            hit = all(w in desc for w in words) and (not digits or cn.startswith(digits))
        if hit:
            out.append({"cn": cn, "cn_display": refdata.fmt_cn(cn), "description": row["description"]})
        if len(out) >= limit * 3:
            break
    out.sort(key=lambda r: (len(r["description"]), r["cn"]))
    return out[:limit]


def build_line(raw: dict[str, Any], pid: str, country: str, source: str = "owner") -> tuple[ProcessDef | None, list[str]]:
    """Turn a typed or proposed product line into a validated ProcessDef (or the reasons it is not usable)."""
    errors: list[str] = []
    name = str(raw.get("name") or "").strip()[:80]
    pre_name = str(raw.get("precursor_name") or "").strip()[:80]
    supplier = str(raw.get("precursor_supplier") or "").strip()[:120]
    if not name:
        errors.append("Give the product a name.")
    if not pre_name:
        errors.append("Name the steel input (for example 'Stainless wire rod').")
    if not supplier:
        errors.append("Name the supplier of the steel input.")
    good = cn_info(str(raw.get("cn") or ""), country, "good")
    pre = cn_info(str(raw.get("precursor_cn") or ""), country, "precursor")
    errors += [f"Product CN: {e}" for e in good["errors"]]
    errors += [f"Input CN: {e}" for e in pre["errors"]]
    if errors:
        return None, errors
    return (
        ProcessDef(
            id=pid,
            name=name,
            cn=good["cn"],
            cn_display=good["cn_display"],
            cn_desc=good["description"],
            precursor_name=pre_name,
            precursor_cn=pre["cn"],
            precursor_supplier=supplier,
            precursor_country=str(raw.get("precursor_country") or country),
            source=source,  # type: ignore[arg-type]
            evidence_docs=[str(x) for x in (raw.get("doc_ids") or [])][:12],
            rationale=str(raw.get("rationale") or "")[:300],
        ),
        [],
    )


def sync_supplier_requests(project: Project) -> None:
    """One supplier-request tracker per product line (kept when the line and supplier are unchanged)."""
    keep = {(s.process_id, s.supplier): s for s in project.supplier_requests}
    project.supplier_requests = [
        keep.get((p.id, p.precursor_supplier)) or SupplierRequest(process_id=p.id, supplier=p.precursor_supplier) for p in project.processes
    ]


def months_upto(year: int, last_month: int) -> tuple[list[str], str]:
    last_month = max(1, min(12, last_month))
    months = [f"{year}-{m:02d}" for m in range(1, last_month + 1)]
    names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    label = f"Jan-{names[last_month - 1]} {year}" + (" (full year)" if last_month == 12 else " (provisional, year-to-date)")
    return months, label
