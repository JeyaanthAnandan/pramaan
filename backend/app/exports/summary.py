"""Buyer summary for the read-only share link (M11): no plant-level inputs."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.cbam.tree import q
from app.evidence.models import Evidence, Project


def _verified_by(pid: str, evidence: list[Evidence] | None) -> str:
    """'verified by <verifier>, report <ref>' from the supplier statement's own (two-reader) values."""
    if not evidence:
        return ""
    pick = {
        e.field_key: e.value_text
        for e in evidence
        if e.process == pid and e.field_key in {"verifier", "verification_ref"} and e.status in {"VERIFIED_2R", "APPROVED"}
    }
    who, ref = pick.get("verifier"), pick.get("verification_ref")
    return ", ".join(x for x in (f"verified by {who}" if who else "", f"verification report {ref}" if ref else "") if x)


def buyer_summary(project: Project, result: dict[str, Any], evidence: list[Evidence] | None = None) -> dict[str, Any]:
    goods = []
    for p in result.get("processes", []):
        if "see" not in p:
            continue
        pre = p["precursor"]
        extra = p.get("extra_parameters", {})
        goods.append(
            {
                "cn": p["cn_display"],
                "description": p.get("cn_desc") or p["name"],
                "see_direct": q(Decimal(p["see"]), 3),
                "see_indirect": "not applicable (iron & steel: direct emissions only)",
                "production_route": "Cold heading + heat treatment of purchased wire rod; precursor route: "
                + (pre.get("route") or "unknown"),
                "precursor_data": [
                    {
                        "precursor": f"{pre['name']} (CN {pre['cn_display']})",
                        "status": ("actual — " + (_verified_by(p["id"], evidence) or "verified by the supplier's verifier"))
                        if pre["data"] == "ACTUAL_VERIFIED"
                        else "EU default value with mark-up (supplier data requested)",
                    }
                ],
                "extra_parameters": {
                    "main_reducing_agent_of_precursor": extra.get("main_reducing_agent", {}).get("value") or "unknown",
                    "mn_pct": extra.get("mn_pct", {}).get("value"),
                    "cr_pct": extra.get("cr_pct", {}).get("value"),
                    "ni_pct": extra.get("ni_pct", {}).get("value"),
                    "other_alloy_pct": extra.get("other_alloy_pct", {}).get("value"),
                    "scrap_t_per_t_product": extra.get("scrap_t_per_t", {}).get("value"),
                    "pre_consumer_scrap_pct": "not applicable",
                },
                "sefa": q(Decimal(p["sefa"]), 3),
                "default_see_2026_for_comparison": q(Decimal(p["default_see_2026"]), 3),
            }
        )
    return {
        "operator": project.company,
        "country": project.country,
        "period": result.get("period_label"),
        "goods": goods,
        "readiness_pct": q(Decimal(result["readiness"]["score"]), 0),
        "banner": "PROVISIONAL — year-to-date data, not yet verified by an accredited verifier.",
        "generated_at": result.get("computed_at"),
        "method": "EU CBAM definitive period; Implementing Regulation (EU) 2025/2547; EC Guidance No. 3 and 5d",
    }
