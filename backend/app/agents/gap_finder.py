"""GapFinder: required-data checklist per production process and CN group.

Deterministic (the rules come from the CBAM methodology); the UI renders each gap's
plain-language question in English, Hindi, Tamil or Vietnamese from i18n keys + params.
Colour carries status only: green = verified by two readers / approved, amber = needs a
human tap, red = missing or on default values.
"""

from __future__ import annotations

from typing import Any

from app.evidence.models import Document, Evidence, Project

GOOD = {"VERIFIED_2R", "APPROVED"}


def _colour(statuses: list[str], missing: bool) -> str:
    if missing:
        return "red"
    if any(s not in GOOD for s in statuses):
        return "amber"
    return "green"


def find_gaps(project: Project, evidence: list[Evidence], documents: list[Document], result: dict[str, Any]) -> list[dict[str, Any]]:
    docs = {d.id: d for d in documents}
    gaps: list[dict[str, Any]] = []
    procs = {p["id"]: p for p in result.get("processes", [])}

    def monthly(field: str, process: str) -> tuple[list[Evidence], list[str]]:
        found = {x.period: x for x in evidence if x.field_key == field and x.process == process and x.period}
        return list(found.values()), [m for m in project.months if m not in found]

    for p in project.processes:
        pr = procs.get(p.id, {})
        for field, kind, doc_hint in [
            ("produced_t", "al", "production_register"),
            ("rod_consumed_t", "rod_mass", "production_register"),
            ("scrap_t", "scrap", "scrap_log"),
        ]:
            xs, missing = monthly(field, p.id)
            gaps.append(
                {
                    "id": f"{kind}.{p.id}",
                    "process": p.id,
                    "group": "activity" if kind != "scrap" else "control",
                    "kind": kind,
                    "status": _colour([x.status for x in xs], bool(missing)),
                    "params": {
                        "process": p.name,
                        "precursor": p.precursor_name,
                        "months_found": len(xs),
                        "months_total": len(project.months),
                        "missing": missing,
                    },
                    "evidence_ids": [x.id for x in xs],
                    "suggested_doc": doc_hint,
                    "ask": "production_supervisor",
                    "node": {"al": f"{p.id}.al", "rod_mass": f"{p.id}.rod.mass", "scrap": f"{p.id}.scrap"}[kind],
                }
            )
        pre = pr.get("precursor", {})
        actual = pre.get("data") == "ACTUAL_VERIFIED"
        gaps.append(
            {
                "id": f"precursor_see.{p.id}",
                "process": p.id,
                "group": "precursor",
                "kind": "precursor_see",
                "status": "green" if actual and pre.get("status") in GOOD else ("amber" if actual else "red"),
                "params": {
                    "process": p.name,
                    "precursor": p.precursor_name,
                    "supplier": p.precursor_supplier,
                    "default_value": pre.get("default_value"),
                    "see": pre.get("see"),
                    "data": pre.get("data"),
                    "locator": pre.get("default_locator"),
                },
                "evidence_ids": [],
                "suggested_doc": "supplier_emissions_statement",
                "ask": "supplier",
                "node": pre.get("see_node"),
                "lever": not actual,
            }
        )
        gaps.append(
            {
                "id": f"precursor_sefa.{p.id}",
                "process": p.id,
                "group": "precursor",
                "kind": "precursor_sefa",
                "status": "green" if actual else "red",
                "params": {"process": p.name, "precursor": p.precursor_name, "supplier": p.precursor_supplier, "sefa": pre.get("sefa")},
                "evidence_ids": [],
                "suggested_doc": "supplier_emissions_statement",
                "ask": "supplier",
                "node": pre.get("sefa_node"),
            }
        )
        gaps.append(
            {
                "id": f"exports.{p.id}",
                "process": p.id,
                "group": "exports",
                "kind": "exports",
                "status": _colour(
                    [x.status for x in evidence if x.field_key == "net_mass_kg" and x.process == p.id], not pr.get("exports_by_quarter")
                ),
                "params": {
                    "process": p.name,
                    "cn": p.cn_display,
                    "quarters": list((pr.get("exports_by_quarter") or {}).keys()),
                    "tonnes": pr.get("exports_t"),
                },
                "evidence_ids": [x.id for x in evidence if x.field_key == "net_mass_kg" and x.process == p.id],
                "suggested_doc": "export_invoice",
                "ask": "accountant",
                "node": f"{p.id}.exports",
            }
        )
        for key, item in (pr.get("extra_parameters") or {}).items():
            st = item.get("status")
            colour = (
                "green"
                if st in GOOD or st in {"DERIVED", "NOT_APPLICABLE"}
                else ("amber" if item.get("optional") and st == "MISSING" else ("amber" if st not in {"MISSING"} else "red"))
            )
            gaps.append(
                {
                    "id": f"extra.{key}.{p.id}",
                    "process": p.id,
                    "group": "extra",
                    "kind": f"extra_{key}",
                    "status": colour,
                    "params": {
                        "process": p.name,
                        "value": item.get("value"),
                        "note": item.get("note"),
                        "optional": item.get("optional", False),
                    },
                    "evidence_ids": item.get("evidence", []),
                    "suggested_doc": "precursor_invoice" if key.endswith("_pct") else "supplier_emissions_statement",
                    "ask": "supplier" if key == "main_reducing_agent" else "quality_manager",
                }
            )
    gas = [x for x in evidence if x.field_key == "mmbtu" and docs.get(x.doc_id) and docs[x.doc_id].doc_type == "gas_invoice"]
    gas_missing = [m for m in project.months if m not in {x.period for x in gas}]
    gaps.append(
        {
            "id": "fuel.natural_gas",
            "process": None,
            "group": "energy",
            "kind": "fuel_gas",
            "status": _colour([x.status for x in gas], bool(gas_missing)),
            "params": {"months_found": len(project.months) - len(gas_missing), "months_total": len(project.months), "missing": gas_missing},
            "evidence_ids": [x.id for x in gas],
            "suggested_doc": "gas_invoice",
            "ask": "accountant",
            "node": "gas.mmbtu",
        }
    )
    gaps.append(
        {
            "id": "electricity",
            "process": None,
            "group": "energy",
            "kind": "electricity",
            "status": "info",
            "params": {"bills": len({x.doc_id for x in evidence if x.field_key == "kwh"})},
            "evidence_ids": [x.id for x in evidence if x.field_key == "kwh"],
            "suggested_doc": "electricity_bill",
            "ask": "accountant",
        }
    )
    for x in evidence:
        if x.status in {"NEEDS_REVIEW", "PENDING"}:
            d = docs.get(x.doc_id)
            gaps.append(
                {
                    "id": f"review.{x.id}",
                    "process": x.process,
                    "group": "review",
                    "kind": "review",
                    "status": "amber",
                    "params": {
                        "label": x.label or x.field_key,
                        "first": x.value_text,
                        "second": x.second_reading.reading_value if x.second_reading else None,
                        "reason": x.second_reading.reason if x.second_reading else "",
                        "doc_title": d.title if d else x.doc_id,
                        "period": x.period,
                        "unit": x.unit,
                    },
                    "evidence_ids": [x.id],
                    "suggested_doc": d.doc_type if d else None,
                    "ask": "owner",
                }
            )
    order = {"red": 0, "amber": 1, "green": 2, "info": 3}
    gaps.sort(key=lambda g: (order.get(g["status"], 4), g["group"] != "review", g["id"]))
    return gaps
