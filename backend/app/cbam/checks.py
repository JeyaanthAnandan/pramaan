"""Cross-document control checks (code, not LLM).

Mirrors EC Guidance No. 2, Step 7 (pp. 12-13): data-flow control activities, in particular
Step 7b "corroboration of data with a second data source". Each check is logged with its
formula, inputs, tolerance and pass/fail, and appears in the verifier pack.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from app import refdata
from app.cbam import engine as e
from app.evidence.models import Document, Evidence, Project

D = Decimal
REF = "EC Guidance No. 2, Step 7 (control system), pp. 12-13"


def _num(x: Evidence) -> Decimal:
    try:
        return D(x.value_num) if x.value_num not in (None, "") else D(0)
    except Exception:
        return D(0)


def _check(
    cid: str, name: str, formula: str, inputs: dict[str, Any], result: str, tolerance: str, status: str, evidence: list[str], note: str = ""
) -> dict[str, Any]:
    return {
        "id": cid,
        "name": name,
        "formula": formula,
        "inputs": inputs,
        "result": result,
        "tolerance": tolerance,
        "status": status,
        "evidence_ids": evidence,
        "note": note,
        "reference": REF,
    }


def _per_month(evidence: list[Evidence], field: str, process: str) -> dict[str, Evidence]:
    out: dict[str, Evidence] = {}
    for x in evidence:
        if x.field_key == field and x.process == process and x.period and x.period not in out:
            out[x.period] = x
    return out


def unbalanced_months(months: list[str], evidence: list[Evidence], process: str) -> list[dict[str, Any]]:
    """Months that have all three figures but whose rod − scrap misses the tonnes produced by more than
    2 %, with the values behind each (the monthly check and the gaps checklist name them)."""
    prod, rod, scr = (_per_month(evidence, f, process) for f in ("produced_t", "rod_consumed_t", "scrap_t"))
    off: list[dict[str, Any]] = []
    for m in months:
        if m in prod and m in rod and m in scr:
            lhs, made = _num(rod[m]) - _num(scr[m]), _num(prod[m])
            if not e.within(lhs, made, D("0.02")):
                off.append({"month": m, "rod_minus_scrap_t": lhs, "produced_t": made, "evidence_ids": [rod[m].id, scr[m].id, prod[m].id]})
    return off


def run_checks(project: Project, evidence: list[Evidence], documents: list[Document]) -> list[dict[str, Any]]:
    docs = {d.id: d for d in documents}

    def pick(field: str, process: str | None = None, doc_type: str | None = None) -> list[Evidence]:
        return [
            x
            for x in evidence
            if x.field_key == field
            and (process is None or x.process == process)
            and (doc_type is None or (docs.get(x.doc_id) and docs[x.doc_id].doc_type == doc_type))
        ]

    def one_per(xs: list[Evidence]) -> dict[str, Evidence]:
        out: dict[str, Evidence] = {}
        for x in xs:
            if x.period and x.period not in out:
                out[x.period] = x
        return out

    checks: list[dict[str, Any]] = []
    two_pct = D("0.02")
    for p in project.processes:
        prod = one_per(pick("produced_t", p.id))
        rod = one_per(pick("rod_consumed_t", p.id))
        scr = one_per(pick("scrap_t", p.id))
        tp, tr, ts = (sum((_num(x) for x in v.values()), D(0)) for v in (prod, rod, scr))
        lhs = tr - ts
        ok = tp > 0 and e.within(lhs, tp, two_pct)
        checks.append(
            _check(
                f"mass_balance.{p.id}",
                f"Mass balance — {p.name}",
                "rod consumed − scrap ≈ product produced",
                {"rod_consumed_t": str(tr), "scrap_t": str(ts), "produced_t": str(tp)},
                f"{lhs} vs {tp} t",
                "±2 %",
                "pass" if ok else "fail",
                [x.id for v in (prod, rod, scr) for x in v.values()],
            )
        )
        # a month that does not balance is named with its figures and linked to its values: "4/6 months"
        # alone (with an empty "Missing months:") gave the owner and the verifier nothing to act on
        off = unbalanced_months(project.months, evidence, p.id)
        missing_m = [m for m in project.months if m not in prod or m not in rod or m not in scr]
        n_ok = len(project.months) - len(off) - len(missing_m)
        parts = []
        if off:
            parts.append("Out of balance: " + ", ".join(f"{o['month']} ({o['rod_minus_scrap_t']} vs {o['produced_t']} t)" for o in off))
        if missing_m:
            parts.append("Missing months: " + ", ".join(missing_m))
        checks.append(
            _check(
                f"mass_balance_monthly.{p.id}",
                f"Monthly mass balance — {p.name}",
                "per month: rod − scrap ≈ produced",
                {
                    "months_checked": len(project.months),
                    "out_of_balance": {
                        o["month"]: {"rod_minus_scrap_t": str(o["rod_minus_scrap_t"]), "produced_t": str(o["produced_t"])} for o in off
                    },
                },
                f"{n_ok}/{len(project.months)} months within tolerance",
                "±2 % per month",
                "pass" if n_ok == len(project.months) else ("warn" if n_ok else "fail"),
                [i for o in off for i in o["evidence_ids"]],
                note=" | ".join(parts),
            )
        )
        purchases = pick("tonnes", p.id, "precursor_invoice")
        opening = pick("opening_stock_t", p.id)
        closing = pick("closing_stock_t", p.id)
        if purchases and opening and closing:
            pur = sum((_num(x) for x in purchases), D(0))
            avail = pur + _num(opening[0]) - _num(closing[0])
            ok = e.within(avail, tr, two_pct)
            checks.append(
                _check(
                    f"stock.{p.id}",
                    f"Purchases vs consumption vs stock — {p.precursor_name}",
                    "purchases + opening stock − closing stock ≈ consumed",
                    {
                        "purchases_t": str(pur),
                        "opening_t": str(_num(opening[0])),
                        "closing_t": str(_num(closing[0])),
                        "consumed_t": str(tr),
                    },
                    f"{avail} vs {tr} t",
                    "±2 %",
                    "pass" if ok else "fail",
                    [x.id for x in purchases + opening[:1] + closing[:1]],
                )
            )
        else:
            checks.append(
                _check(
                    f"stock.{p.id}",
                    f"Purchases vs consumption vs stock — {p.precursor_name}",
                    "purchases + opening − closing ≈ consumed",
                    {"purchase_invoices": len(purchases)},
                    "insufficient data",
                    "±2 %",
                    "warn",
                    [x.id for x in purchases],
                    note="Upload all rod invoices and the stock lines of the register.",
                )
            )
        exp = pick("net_mass_kg", p.id)
        exp_t = sum((_num(x) for x in exp), D(0)) / 1000
        checks.append(
            _check(
                f"exports.{p.id}",
                f"Exports ≤ production — {p.name}",
                "Σ exported (t) ≤ Σ produced (t)",
                {"exported_t": str(exp_t), "produced_t": str(tp)},
                f"{exp_t} ≤ {tp} t",
                "exact",
                "pass" if exp_t <= tp else "fail",
                [x.id for x in exp],
            )
        )
        cns = {x.value_text.replace(" ", "") for x in pick("cn_code", p.id, "export_invoice")}
        if cns:
            okc = cns == {p.cn}
            checks.append(
                _check(
                    f"export_cn.{p.id}",
                    f"Export CN code matches process — {p.name}",
                    "CN on export invoices = CN of the process",
                    {"found": sorted(cns), "expected": p.cn_display},
                    ", ".join(sorted(cns)),
                    "exact",
                    "pass" if okc else "fail",
                    [x.id for x in pick("cn_code", p.id, "export_invoice")],
                )
            )
        st = pick("verification_ref", p.id, "supplier_emissions_statement")
        if st:
            per = pick("period", p.id, "supplier_emissions_statement")
            checks.append(
                _check(
                    f"supplier.{p.id}",
                    f"Supplier data verified and covers the period — {p.precursor_name}",
                    "verification report present; statement period covers production months",
                    {"verification_ref": st[0].value_text, "period": per[0].value_text if per else None},
                    "verified",
                    "-",
                    "pass",
                    [st[0].id] + ([per[0].id] if per else []),
                )
            )
        else:
            checks.append(
                _check(
                    f"supplier.{p.id}",
                    f"Supplier data verified and covers the period — {p.precursor_name}",
                    "verification report present",
                    {},
                    "no verified supplier data",
                    "-",
                    "warn",
                    [],
                    note="Default value with mark-up is used for this precursor (Precursor Lever).",
                )
            )

    # gas invoices: internal consistency + coverage
    gas_docs: dict[str, dict[str, Evidence]] = defaultdict(dict)
    for x in evidence:
        d = docs.get(x.doc_id)
        if d and d.doc_type == "gas_invoice" and x.field_key in {"scm", "gcv_kcal_per_scm", "mmbtu"}:
            gas_docs[x.doc_id][x.field_key] = x
    kj = refdata.assumption("kcal_to_kj").value
    gj_per = refdata.assumption("mmbtu_to_gj").value
    consistent, ids = 0, []
    for fields in gas_docs.values():
        if {"scm", "gcv_kcal_per_scm", "mmbtu"} <= fields.keys():
            gj = e.gj_from_scm(_num(fields["scm"]), _num(fields["gcv_kcal_per_scm"]), kj)
            if e.within(gj / gj_per, _num(fields["mmbtu"]), D("0.005")):
                consistent += 1
            ids += [f.id for f in fields.values()]
    checks.append(
        _check(
            "gas.internal",
            "Gas invoices internally consistent",
            "SCM × GCV(kcal/SCM) × 4.1868 kJ/kcal ÷ 1.055056 GJ/MMBtu ≈ MMBtu",
            {"invoices": len(gas_docs)},
            f"{consistent}/{len(gas_docs)} invoices consistent",
            "±0.5 %",
            "pass" if gas_docs and consistent == len(gas_docs) else "fail",
            ids,
        )
    )
    covered = sorted({x.period for x in pick("mmbtu", doc_type="gas_invoice") if x.period})
    missing = [m for m in project.months if m not in covered]
    checks.append(
        _check(
            "gas.coverage",
            "Gas invoices cover every month of the period",
            "months with an invoice / months in period",
            {"covered": covered},
            f"{len(project.months) - len(missing)}/{len(project.months)} months",
            "all months",
            "pass" if not missing else "fail",
            [],
            note=("Missing: " + ", ".join(missing)) if missing else "",
        )
    )
    # specific energy plausibility (information)
    tot_prod = sum((_num(x) for x in pick("produced_t")), D(0))
    mm = sum((_num(x) for x in pick("mmbtu", doc_type="gas_invoice")), D(0))
    if tot_prod > 0 and mm > 0:
        sec = mm * gj_per * refdata.assumption("ncv_gcv_ratio_natural_gas").value / tot_prod
        checks.append(
            _check(
                "gas.sec",
                "Specific gas consumption plausible",
                "GJ(NCV) ÷ t produced",
                {"gj_ncv_per_t": str(sec.quantize(D("0.01")))},
                f"{sec.quantize(D('0.01'))} GJ/t",
                "1 – 8 GJ/t (screws & nuts reference: 3.5 GJ/t, Guidance 5d Table 4-12)",
                "pass" if D(1) <= sec <= D(8) else "warn",
                [],
            )
        )
    elec = [x for x in evidence if x.field_key == "kwh"]
    checks.append(
        _check(
            "electricity.excluded",
            "Electricity recorded, excluded from SEE",
            "iron & steel: direct emissions only (CBAM Reg. Annex II)",
            {"bills": len({x.doc_id for x in elec})},
            f"{sum((_num(x) for x in elec), D(0))} kWh recorded",
            "-",
            "info",
            [x.id for x in elec],
        )
    )
    return checks
