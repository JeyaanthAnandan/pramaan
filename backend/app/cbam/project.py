"""Bind evidence to the engine and build the project's full calculation tree.

This is the Calculator tool behind the ADK workflow: deterministic, Decimal, and every node
points back to evidence, refdata or an explicit assumption.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app import refdata
from app.cbam import engine as e
from app.cbam.tree import (
    APPROVED,
    ASSUMPTION,
    CALCULATED,
    DEFAULT_USED,
    GOOD_STATUSES,
    MISSING,
    NEEDS_REVIEW,
    REFDATA,
    VERIFIED_2R,
    Tree,
    q,
)
from app.evidence.models import Document, Evidence, Project, now

D = Decimal
YEARS = list(range(2026, 2035))
STATUS_RANK = {VERIFIED_2R: 0, APPROVED: 0, NEEDS_REVIEW: 2, "PENDING": 2, DEFAULT_USED: 3, MISSING: 4}


def _worst(statuses: list[str]) -> str:
    if not statuses:
        return MISSING
    worst = max(statuses, key=lambda s: STATUS_RANK.get(s, 1))
    if worst in (VERIFIED_2R, APPROVED):
        return APPROVED if APPROVED in statuses else VERIFIED_2R
    return worst


@dataclass
class Ctx:
    project: Project
    tree: Tree
    ev: list[Evidence]
    docs: dict[str, Document]
    used_assumptions: set[str]

    def ref_leaf(self, node_id: str, label: str, ref: refdata.Ref) -> str:
        if node_id not in self.tree.nodes:
            status = ASSUMPTION if ref.status == "assumption" else REFDATA
            if ref.status == "assumption":
                self.used_assumptions.add(ref.locator)
            self.tree.leaf(node_id, label, ref.value, ref.unit, source=ref.source(), status=status, note=ref.locator)
        return node_id

    def ev_leaf(self, ev: Evidence, label: str | None = None) -> str:
        nid = f"ev:{ev.id}"
        if nid not in self.tree.nodes:
            doc = self.docs.get(ev.doc_id)
            self.tree.leaf(
                nid,
                label or ev.label or ev.field_key,
                D(ev.value_num) if ev.value_num not in (None, "") else None,
                ev.unit,
                source={
                    "kind": "evidence",
                    "evidence_id": ev.id,
                    "doc_id": ev.doc_id,
                    "doc_title": doc.title if doc else ev.doc_id,
                    "doc_type": doc.doc_type if doc else None,
                    "box_2d": ev.box_2d,
                    "page": ev.page,
                    "value_text": ev.value_text,
                    "period": ev.period,
                },
                status=ev.status if ev.status != "PENDING" else NEEDS_REVIEW,
            )
        return nid

    def pick(self, field_key: str, process: str | None = None, period: str | None = None, doc_type: str | None = None) -> list[Evidence]:
        out = [
            x
            for x in self.ev
            if x.field_key == field_key
            and (process is None or x.process == process)
            and (period is None or x.period == period)
            and (doc_type is None or (self.docs.get(x.doc_id) and self.docs[x.doc_id].doc_type == doc_type))
        ]
        return sorted(out, key=lambda x: (STATUS_RANK.get(x.status, 1), x.doc_id))


def _num(ev: Evidence) -> Decimal:
    return D(ev.value_num) if ev.value_num not in (None, "") else D(0)


def _sum_monthly(c: Ctx, node_id: str, label: str, field_key: str, process: str, unit: str) -> tuple[str, list[str]]:
    """Sum one value per month (best-status evidence for each month). Returns node id and missing months."""
    children: list[str] = []
    missing: list[str] = []
    total = D(0)
    for m in c.project.months:
        found = c.pick(field_key, process, m)
        if not found:
            missing.append(m)
            continue
        children.append(c.ev_leaf(found[0]))
        total += _num(found[0])
    note = f"Missing months: {', '.join(missing)}" if missing else None
    status = MISSING if missing else CALCULATED
    c.tree.calc(node_id, label, total if children else None, unit, "Σ monthly values", children, note=note, status=status)
    return node_id, missing


def _gas(c: Ctx) -> dict[str, Any]:
    t = c.tree
    invoices = c.pick("mmbtu", doc_type="gas_invoice")
    by_month: dict[str, Evidence] = {}
    for x in invoices:
        if x.period and x.period not in by_month:
            by_month[x.period] = x
    children = [c.ev_leaf(x, f"Gas energy {x.period} (GCV)") for x in sorted(by_month.values(), key=lambda x: x.period or "")]
    missing = [m for m in c.project.months if m not in by_month]
    mmbtu = sum((_num(x) for x in by_month.values()), D(0))
    t.calc(
        "gas.mmbtu",
        "Natural gas billed (GCV)",
        mmbtu,
        "MMBtu",
        "Σ monthly gas invoices",
        children,
        note=f"Missing invoices: {', '.join(missing)}" if missing else None,
        status=MISSING if missing else CALCULATED,
    )
    gj_per = refdata.assumption("mmbtu_to_gj")
    ratio = refdata.assumption("ncv_gcv_ratio_natural_gas")
    c.ref_leaf("as.mmbtu_to_gj", "GJ per MMBtu", gj_per)
    c.ref_leaf("as.ncv_gcv", "NCV/GCV ratio, natural gas", ratio)
    gj_gcv = e.gj_gcv_from_mmbtu(mmbtu, gj_per.value)
    t.calc("gas.gj_gcv", "Gas energy, gross (GCV)", gj_gcv, "GJ", "MMBtu × 1.055056", ["gas.mmbtu", "as.mmbtu_to_gj"])
    gj_ncv = e.ncv_from_gcv(gj_gcv, ratio.value)
    t.calc("gas.gj_ncv", "Gas energy, net (NCV) = activity data", gj_ncv, "GJ", "GJ(GCV) × NCV/GCV", ["gas.gj_gcv", "as.ncv_gcv"])
    f = refdata.fuel("natural_gas")
    c.ref_leaf("ref.ng.ef", "Emission factor, natural gas", f["ef"])
    tco2 = e.fuel_emissions_t(gj_ncv, f["ef"].value)
    t.calc("gas.tco2", "Direct emissions from natural gas", tco2, "t CO2", "AD(TJ, NCV) × EF × OxF(1)", ["gas.gj_ncv", "ref.ng.ef"])
    monthly_gj = {m: e.ncv_from_gcv(e.gj_gcv_from_mmbtu(_num(x), gj_per.value), ratio.value) for m, x in by_month.items()}
    return {"tco2": tco2, "missing": missing, "gj_ncv": gj_ncv, "monthly_gj_ncv": monthly_gj}


def _price_2026(c: Ctx, process_exports: dict[str, dict[str, Decimal]]) -> tuple[str, Decimal]:
    """2026 price = export-weighted average of the quarterly prices of the actual import quarters."""
    qty: dict[int, Decimal] = defaultdict(lambda: D(0))
    for per_q in process_exports.values():
        for quarter, t in per_q.items():
            qty[int(quarter[-1])] += t
    if not qty:
        qty = {1: D(1), 2: D(1), 3: D(1), 4: D(1)}
    children = []
    total_q = sum(qty.values(), D(0))
    weighted = D(0)
    for qn in sorted(qty):
        ref = refdata.quarter_price(2026, qn)
        nid = c.ref_leaf(f"ref.price.2026Q{qn}", f"CBAM certificate price Q{qn} 2026", ref)
        children.append(nid)
        weighted += ref.value * qty[qn]
    price = weighted / total_q
    c.tree.calc(
        "y2026.price", "Certificate price 2026 (export-weighted)", price, "EUR/certificate", "Σ price_q × tonnes_q / Σ tonnes_q", children
    )
    return "y2026.price", price


HOT_MONTH = D("0.10")  # a month runs hot when its gas per tonne is 10 % or more above the median month


def _median(xs: list[Decimal]) -> Decimal:
    v = sorted(xs)
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


def _gas_pulse(c: Ctx) -> dict[str, Any] | None:
    """Plant pulse: gas per tonne month by month against the plant's own median month, and what the
    hot months cost in gas (rupees, at each bill's own rate), energy and CO2. Operations insight from
    the same verified bills and register; it does not change SEE. Every figure is a calculation node,
    so the Evidence Lens opens it down to the bill."""
    t = c.tree
    gj_per = refdata.assumption("mmbtu_to_gj")
    ratio = refdata.assumption("ncv_gcv_ratio_natural_gas")
    kj = refdata.assumption("kcal_to_kj")
    c.ref_leaf("as.kcal_to_kj", "kJ per kcal", kj)
    rows: list[dict[str, Any]] = []
    for m in c.project.months:
        bills = c.pick("mmbtu", None, m, doc_type="gas_invoice")
        prods = [x[0] for p in c.project.processes if (x := c.pick("produced_t", p.id, m))]
        prod = sum((_num(x) for x in prods), D(0))
        if not bills or prod <= 0:
            continue
        gj = _num(bills[0]) * gj_per.value * ratio.value
        t.calc(
            f"ops.gas.{m}.gj",
            f"Gas energy {m} (NCV)",
            gj,
            "GJ",
            "MMBtu × GJ/MMBtu × NCV/GCV",
            [c.ev_leaf(bills[0], f"Gas energy {m} (GCV)"), "as.mmbtu_to_gj", "as.ncv_gcv"],
        )
        t.calc(f"ops.prod.{m}", f"Tonnes produced {m}", prod, "t", "Σ production register, all lines", [c.ev_leaf(x) for x in prods])
        t.calc(
            f"ops.gas.{m}.gj_per_t",
            f"Gas per tonne {m}",
            gj / prod,
            "GJ/t",
            "GJ(NCV) ÷ tonnes produced",
            [f"ops.gas.{m}.gj", f"ops.prod.{m}"],
        )
        rows.append({"month": m, "v": gj / prod, "prod": prod})
    if len(rows) < 3:
        return None
    med = _median([r["v"] for r in rows])
    t.calc(
        "ops.gas.median",
        "Median month, gas per tonne",
        med,
        "GJ/t",
        f"median of {len(rows)} months",
        [f"ops.gas.{r['month']}.gj_per_t" for r in rows],
    )
    best = min(rows, key=lambda r: r["v"])
    months, tot = [], {"gj": D(0), "inr": D(0), "tco2": D(0)}
    have_inr = True
    for r in rows:
        m = r["month"]
        row: dict[str, Any] = {
            "month": m,
            "gj_per_t": str(r["v"]),
            "node": f"ops.gas.{m}.gj_per_t",
            "delta_pct": str((r["v"] / med - 1) * 100),
            "hot": r["v"] >= med * (1 + HOT_MONTH),
        }
        if row["hot"]:
            ex = (r["v"] - med) * r["prod"]
            t.calc(
                f"ops.gas.{m}.excess_gj",
                f"Gas above the median month, {m}",
                ex,
                "GJ",
                "(GJ/t − median) × tonnes produced",
                [f"ops.gas.{m}.gj_per_t", "ops.gas.median", f"ops.prod.{m}"],
            )
            co2 = ex * c.tree.get("ref.ng.ef").value / D(1000)
            t.calc(
                f"ops.gas.{m}.excess_tco2",
                f"CO2 from that gas, {m}",
                co2,
                "t CO2",
                "GJ × EF ÷ 1000",
                [f"ops.gas.{m}.excess_gj", "ref.ng.ef"],
            )
            row |= {
                "excess_gj": str(ex),
                "excess_gj_node": f"ops.gas.{m}.excess_gj",
                "excess_tco2": str(co2),
                "excess_tco2_node": f"ops.gas.{m}.excess_tco2",
            }
            tot["gj"] += ex
            tot["tco2"] += co2
            gcv = c.pick("gcv_kcal_per_scm", None, m, doc_type="gas_invoice")
            rate = c.pick("rate_inr_per_scm", None, m, doc_type="gas_invoice")
            if gcv and rate and _num(gcv[0]) > 0:
                scm = ex / ratio.value * D(1_000_000) / (_num(gcv[0]) * kj.value)
                t.calc(
                    f"ops.gas.{m}.excess_scm",
                    f"Gas volume above the median month, {m}",
                    scm,
                    "SCM",
                    "GJ(NCV) ÷ NCV/GCV × 10⁶ ÷ (kcal/SCM × kJ/kcal)",
                    [f"ops.gas.{m}.excess_gj", "as.ncv_gcv", c.ev_leaf(gcv[0], f"Gross calorific value {m}"), "as.kcal_to_kj"],
                )
                inr = scm * _num(rate[0])
                t.calc(
                    f"ops.gas.{m}.excess_inr",
                    f"Cost of that gas, {m}",
                    inr,
                    "INR",
                    "SCM × the bill's rate",
                    [f"ops.gas.{m}.excess_scm", c.ev_leaf(rate[0], f"Gas rate {m}")],
                )
                row |= {"excess_inr": str(inr), "excess_inr_node": f"ops.gas.{m}.excess_inr"}
                tot["inr"] += inr
            else:
                have_inr = False
        months.append(row)
    hot = [r for r in months if r["hot"]]
    out: dict[str, Any] = {
        "median": str(med),
        "median_node": "ops.gas.median",
        "threshold_pct": str(HOT_MONTH * 100),
        "months": months,
        "best": {"month": best["month"], "gj_per_t": str(best["v"]), "node": f"ops.gas.{best['month']}.gj_per_t"},
        "hot_months": [r["month"] for r in hot],
    }
    if hot:
        t.calc(
            "ops.gas.excess_gj",
            "Gas above the median month, all hot months",
            tot["gj"],
            "GJ",
            "Σ hot months",
            [r["excess_gj_node"] for r in hot],
        )
        t.calc("ops.gas.excess_tco2", "CO2 from that gas", tot["tco2"], "t CO2", "Σ hot months", [r["excess_tco2_node"] for r in hot])
        out |= {
            "excess_gj": str(tot["gj"]),
            "excess_gj_node": "ops.gas.excess_gj",
            "excess_tco2": str(tot["tco2"]),
            "excess_tco2_node": "ops.gas.excess_tco2",
        }
        if have_inr:
            t.calc(
                "ops.gas.excess_inr",
                "Cost of the gas above the median month",
                tot["inr"],
                "INR",
                "Σ hot months",
                [r["excess_inr_node"] for r in hot],
            )
            out |= {"excess_inr": str(tot["inr"]), "excess_inr_node": "ops.gas.excess_inr"}
    return out


def _operations(c: Ctx, al: dict[str, Decimal], gas: dict[str, Any]) -> dict[str, Any]:
    """Operational KPIs from the same evidence (yield, scrap share of rod, gas energy per tonne).

    Informational: none of these enter SEE directly; they show where the plant's own levers are
    (less scrap -> less rod per tonne; less gas per tonne -> lower direct emissions)."""
    t = c.tree
    months = c.project.months
    total_al = sum(al.values(), D(0))
    out: dict[str, Any] = {"period_months": len(months), "processes": {}, "gas_gj_per_t": None, "gas_node": None, "gas_monthly": []}
    if total_al > 0 and gas["gj_ncv"] > 0:
        t.calc(
            "gas.gj_per_t",
            "Gas energy per tonne produced (NCV)",
            gas["gj_ncv"] / total_al,
            "GJ/t",
            "GJ(NCV) ÷ Σ AL",
            ["gas.gj_ncv", *[f"{p.id}.al" for p in c.project.processes]],
        )
        out["gas_gj_per_t"], out["gas_node"] = str(gas["gj_ncv"] / total_al), "gas.gj_per_t"
        for m in months:
            prod = sum((_num(x[0]) for p in c.project.processes if (x := c.pick("produced_t", p.id, m))), D(0))
            gj = gas["monthly_gj_ncv"].get(m)
            if gj is not None and prod > 0:
                out["gas_monthly"].append({"month": m, "gj_per_t": str(gj / prod)})
        out["gas_pulse"] = _gas_pulse(c)
    for p in c.project.processes:
        a = al.get(p.id, D(0))
        rod = t.get(f"{p.id}.rod.mass").value or D(0)
        scrap = t.get(f"{p.id}.scrap").value or D(0)
        if a <= 0 or rod <= 0:
            continue
        t.calc(f"{p.id}.yield", f"Yield — {p.name}", a / rod * 100, "%", "AL ÷ rod consumed × 100", [f"{p.id}.al", f"{p.id}.rod.mass"])
        t.calc(
            f"{p.id}.scrap_share",
            f"Scrap share of rod — {p.name}",
            scrap / rod * 100,
            "%",
            "scrap ÷ rod consumed × 100",
            [f"{p.id}.scrap", f"{p.id}.rod.mass"],
        )
        monthly = []
        for m in months:
            r_, s_, a_ = c.pick("rod_consumed_t", p.id, m), c.pick("scrap_t", p.id, m), c.pick("produced_t", p.id, m)
            if r_ and _num(r_[0]) > 0:
                monthly.append(
                    {
                        "month": m,
                        "scrap_pct": str(_num(s_[0]) / _num(r_[0]) * 100) if s_ else None,
                        "yield_pct": str(_num(a_[0]) / _num(r_[0]) * 100) if a_ else None,
                    }
                )
        out["processes"][p.id] = {
            "yield_pct": str(a / rod * 100),
            "yield_node": f"{p.id}.yield",
            "scrap_pct": str(scrap / rod * 100),
            "scrap_node": f"{p.id}.scrap_share",
            "rod_t": str(rod),
            "scrap_t": str(scrap),
            "al_t": str(a),
            "monthly": monthly,
        }
    return out


def _year_params(c: Ctx, year: int) -> dict[str, tuple[str, Decimal]]:
    p = refdata.year_params(year)
    out = {}
    for k, label in [
        ("cbam_factor", "CBAM factor"),
        ("cscf", "Cross-sectoral correction factor"),
        ("default_markup", "Default-value mark-up"),
    ]:
        nid = c.ref_leaf(f"y{year}.{k}", f"{label} {year}", p[k])
        out[k] = (nid, p[k].value)
    return out


def compute(project: Project, evidence: list[Evidence], documents: list[Document]) -> dict[str, Any]:
    tree = Tree()
    c = Ctx(project, tree, [x for x in evidence], {d.id: d for d in documents}, set())
    gas = _gas(c)

    # ---- activity levels, precursor masses, exports
    procs = project.processes
    al: dict[str, Decimal] = {}
    for p in procs:
        nid, _ = _sum_monthly(c, f"{p.id}.al", f"Activity level — {p.name}", "produced_t", p.id, "t")
        al[p.id] = tree.get(nid).value or D(0)
        _sum_monthly(c, f"{p.id}.rod.mass", f"{p.precursor_name} consumed", "rod_consumed_t", p.id, "t")
        _sum_monthly(c, f"{p.id}.scrap", f"Scrap / cut-offs — {p.name}", "scrap_t", p.id, "t")
    total_al = sum(al.values(), D(0))

    exports: dict[str, dict[str, Decimal]] = {}
    for p in procs:
        per_q: dict[str, Decimal] = {}
        kids = []
        for x in c.pick("net_mass_kg", p.id):
            quarter = x.period or "2026-Q?"
            if quarter in per_q:
                continue
            per_q[quarter] = _num(x) / D(1000)
            kids.append(c.ev_leaf(x, f"Exported to EU {quarter} (kg)"))
        exports[p.id] = per_q
        tree.calc(
            f"{p.id}.exports", f"Exported to the EU — {p.name}", sum(per_q.values(), D(0)), "t", "Σ export invoices (kg ÷ 1000)", kids
        )

    _, price_2026 = _price_2026(c, exports)
    proj_price = refdata.assumption("projection_price_eur")
    if project.projection_price_eur:
        proj_price = refdata.Ref(
            D(project.projection_price_eur), "EUR/certificate", "assumptions.json", "User-set projection price", status="assumption"
        )
    c.ref_leaf("as.price_projection", "Projected certificate price 2027+", proj_price)
    fx = refdata.assumption("fx_inr_per_eur")
    if project.fx_inr_per_eur:
        fx = refdata.Ref(D(project.fx_inr_per_eur), "INR/EUR", "assumptions.json", "User-set exchange rate", status="assumption")
    c.ref_leaf("as.fx", "Exchange rate INR per EUR", fx)
    c.ref_leaf("as.gas_alloc", "Gas allocation key: tonnes produced", refdata.assumption("gas_allocation_key"))
    c.ref_leaf("as.cpp", "Carbon price paid in country of origin", refdata.assumption("carbon_price_paid_eur_per_t"))

    years = {y: _year_params(c, y) for y in YEARS}
    out_procs: list[dict[str, Any]] = []
    money: dict[str, list[dict[str, Any]]] = {}
    whatif_money: dict[str, list[dict[str, Any]]] = {}
    see_inputs: list[tuple[str, str]] = []  # (node_id, status) for readiness
    proc_inputs: dict[str, list[tuple[str, str]]] = {}
    proc_actual: dict[str, bool] = {}
    annual = D(12) / D(len(project.months) or 12)  # year-to-date -> per year at current volumes

    for p in procs:
        pid = p.id
        a = al[pid]
        if a <= 0:
            out_procs.append({"id": pid, "name": p.name, "cn": p.cn, "cn_display": p.cn_display, "error": "no production data"})
            continue
        share = a / total_al
        tree.calc(
            f"{pid}.gas_share",
            f"Share of gas attributed to {pid}",
            share,
            "-",
            "AL_p ÷ Σ AL",
            [f"{pid}.al", *[f"{o.id}.al" for o in procs if o.id != pid], "as.gas_alloc"],
        )
        attr = gas["tco2"] * share
        tree.calc(
            f"{pid}.attr_em",
            f"Attributed direct emissions — {pid}",
            attr,
            "t CO2",
            "gas emissions × share",
            ["gas.tco2", f"{pid}.gas_share"],
        )
        direct = attr / a
        tree.calc(f"{pid}.direct", "Own process (direct, specific)", direct, "t CO2/t", "AttrEm ÷ AL", [f"{pid}.attr_em", f"{pid}.al"])
        mass = tree.get(f"{pid}.rod.mass").value or D(0)
        m = e.mass_ratio(mass, a)
        tree.calc(f"{pid}.rod.m", f"m — {p.precursor_name} per t product", m, "t/t", "M_rod ÷ AL", [f"{pid}.rod.mass", f"{pid}.al"])

        # ---- precursor SEE / SEFA: actual (verified supplier statement) or default
        st_see = c.pick("see", pid, doc_type="supplier_emissions_statement")
        st_sefa = c.pick("sefa", pid, doc_type="supplier_emissions_statement")
        st_ver = c.pick("verification_ref", pid, doc_type="supplier_emissions_statement")
        actual = bool(st_see and st_ver)
        dv_rod = refdata.default_value(p.precursor_country, p.precursor_cn)
        c.ref_leaf(f"ref.dv.{p.precursor_cn}", f"Default value {p.precursor_country}, CN {refdata.fmt_cn(p.precursor_cn)}", dv_rod)
        rod_route = (dv_rod.extra.get("route") or "").strip("()") or None
        bm_a = refdata.benchmark(p.cn, "A", project.year)
        c.ref_leaf(f"ref.bmA.{p.cn}", f"Benchmark col. A, CN {p.cn_display}", bm_a)

        def rod_see_node(year: int) -> tuple[str, Decimal, str]:
            if actual:
                nid = f"{pid}.rod.see"
                if nid not in tree.nodes:
                    leaf = c.ev_leaf(st_see[0], f"{p.precursor_name} SEE (supplier, verified)")
                    ver = c.ev_leaf(st_ver[0], "Verification report reference")
                    tree.calc(
                        nid,
                        f"SEE of {p.precursor_name} — actual (verified)",
                        _num(st_see[0]),
                        "t CO2/t",
                        "supplier's verified SEE",
                        [leaf, ver],
                        status=st_see[0].status if st_see[0].status != "PENDING" else NEEDS_REVIEW,
                    )
                return nid, _num(st_see[0]), tree.get(nid).status
            nid = f"{pid}.rod.see" if year == project.year else f"{pid}.y{year}.rod.see"
            if nid not in tree.nodes:
                mk_nid, mk = years[year]["default_markup"]
                v = e.default_see(dv_rod.value, mk)
                tree.calc(
                    nid,
                    f"SEE of {p.precursor_name} — DEFAULT ({year})",
                    v,
                    "t CO2/t",
                    "DV(country, CN) × (1 + mark-up)",
                    [f"ref.dv.{p.precursor_cn}", mk_nid],
                    status=DEFAULT_USED,
                    note="No verified supplier data: country default value with mark-up (Guidance 3 s.4.10.1).",
                )
            return nid, tree.get(nid).value or D(0), DEFAULT_USED

        def rod_sefa_node(year: int) -> tuple[str, Decimal]:
            if actual and st_sefa:
                nid = f"{pid}.rod.sefa"
                if nid not in tree.nodes:
                    leaf = c.ev_leaf(st_sefa[0], f"{p.precursor_name} SEFA (supplier, verified)")
                    tree.calc(
                        nid,
                        f"SEFA of {p.precursor_name} — actual (verified)",
                        _num(st_sefa[0]),
                        "t CO2/t",
                        "supplier's verified SEFA",
                        [leaf],
                    )
                return nid, tree.get(nid).value or D(0)
            ref = refdata.benchmark(p.precursor_cn, "B", year, route=rod_route)
            nid = c.ref_leaf(
                f"ref.bmB.{p.precursor_cn}.{'1' if year <= 2027 else '2'}",
                f"Benchmark col. B, CN {refdata.fmt_cn(p.precursor_cn)} ({ref.extra.get('indicator') or '-'})",
                ref,
            )
            return nid, ref.value

        def see_for(year: int, prefix: str) -> tuple[str, Decimal]:
            rs_nid, rs, _ = rod_see_node(year)
            contrib_nid = f"{prefix}.rod.contrib"
            if contrib_nid not in tree.nodes:
                tree.calc(
                    contrib_nid, f"Precursor contribution — {p.precursor_name}", m * rs, "t CO2/t", "m × SEE_rod", [f"{pid}.rod.m", rs_nid]
                )
            see_nid = f"{prefix}.see"
            if see_nid not in tree.nodes:
                tree.calc(
                    see_nid,
                    f"Specific embedded emissions — {p.name}" + ("" if prefix == pid else f" ({year})"),
                    direct + m * rs,
                    "t CO2/t",
                    "AttrEm/AL + Σ m_i × SEE_i",
                    [f"{pid}.direct", contrib_nid],
                )
            return see_nid, direct + m * rs

        see_nid, see_val = see_for(project.year, pid)
        rs_nid, rs_val, rs_status = rod_see_node(project.year)
        sefa_rod_nid, sefa_rod = rod_sefa_node(project.year)
        sefa_val = e.sefa(bm_a.value, [e.PrecursorSEFA(m, sefa_rod)])
        tree.calc(
            f"{pid}.sefa",
            f"Specific free allocation — {p.name}",
            sefa_val,
            "t CO2/t",
            "BM_A(own) + m × SEFA_rod",
            [f"ref.bmA.{p.cn}", f"{pid}.rod.m", sefa_rod_nid],
        )

        # readiness inputs: evidence leaves under SEE + defaulted precursor slot
        mine: list[tuple[str, str]] = []
        for leaf in tree.leaves_under(see_nid):
            if leaf.source and leaf.source.get("kind") == "evidence":
                mine.append((leaf.id, leaf.status))
        if not actual:
            mine.append((rs_nid, DEFAULT_USED))
        for m_ in [n for n in [f"{pid}.al", f"{pid}.rod.mass"] if tree.get(n).status == MISSING]:
            mine.append((m_, MISSING))
        see_inputs.extend(mine)
        proc_inputs[pid] = mine
        proc_actual[pid] = actual

        # ---- certificates for 2026 imports (per quarter)
        cert_kids = []
        cert_lines = []
        cost_2026 = D(0)
        y = years[project.year]
        sy = e.sefa_year(sefa_val, y["cbam_factor"][1], y["cscf"][1])
        tree.calc(
            f"{pid}.y{project.year}.sefa_y",
            f"SEFA {project.year} — {p.name}",
            sy,
            "t CO2/t",
            "CBAM factor × CSCF × SEFA",
            [y["cbam_factor"][0], y["cscf"][0], f"{pid}.sefa"],
        )
        for quarter, t_q in sorted(exports[pid].items()):
            line = e.ImportLine(t_q, see_val, sy, quarter)
            cert_lines.append(line)
            r = e.certificates([line])
            qn = int(quarter[-1])
            pref = refdata.quarter_price(project.year, qn)
            pn = c.ref_leaf(f"ref.price.{project.year}Q{qn}", f"CBAM certificate price Q{qn} {project.year}", pref)
            nid = f"{pid}.cert.{quarter}"
            tree.calc(
                nid,
                f"Certificates for {quarter} imports",
                r.certificates,
                "certificates",
                "M × (SEE − SEFA_y)",
                [f"{pid}.exports", see_nid, f"{pid}.y{project.year}.sefa_y"],
            )
            cnid = f"{pid}.cost.{quarter}"
            tree.calc(cnid, f"Buyer's CBAM cost {quarter}", r.certificates * pref.value, "EUR", "certificates × price(quarter)", [nid, pn])
            cost_2026 += r.certificates * pref.value
            cert_kids.append(cnid)
        total_cert = e.certificates(cert_lines)
        tree.calc(
            f"{pid}.cert.total",
            f"Certificates for 2026 imports — {p.name}",
            total_cert.certificates,
            "certificates",
            "Σ EE − Σ FAA − carbon price deduction",
            [f"{pid}.cert.{qq}" for qq in sorted(exports[pid])] + ["as.cpp"],
        )
        tree.calc(
            f"{pid}.cost.total",
            f"Buyer's CBAM cost, 2026 imports — {p.name}",
            cost_2026,
            "EUR",
            "Σ quarterly cost",
            cert_kids or ["as.cpp"],
        )

        # ---- money on the table per year: actual vs default
        dv_good = refdata.default_value(project.country, p.cn)
        c.ref_leaf(f"ref.dv.{p.cn}", f"Default value {project.country}, CN {p.cn_display}", dv_good)
        good_route = (dv_good.extra.get("route") or "").strip("()") or None
        series: list[dict[str, Any]] = []
        for yr in YEARS:
            yp = years[yr]
            if yr == 2026:
                pr_nid, price = "y2026.price", price_2026
            else:
                pr_nid, price = "as.price_projection", proj_price.value
            # actual path
            s_nid, s_val = (see_nid, see_val) if (actual or yr == project.year) else see_for(yr, f"{pid}.y{yr}")
            sr_nid, sr_val = rod_sefa_node(yr)
            sefa_g = e.sefa(bm_a.value, [e.PrecursorSEFA(m, sr_val)])
            sefa_g_nid = f"{pid}.sefa" if sr_nid == sefa_rod_nid else f"{pid}.y{yr}.sefa"
            if sefa_g_nid not in tree.nodes:
                tree.calc(
                    sefa_g_nid,
                    f"SEFA {p.name} ({yr} benchmarks)",
                    sefa_g,
                    "t CO2/t",
                    "BM_A(own) + m × SEFA_rod",
                    [f"ref.bmA.{p.cn}", f"{pid}.rod.m", sr_nid],
                )
            sy_val = e.sefa_year(sefa_g, yp["cbam_factor"][1], yp["cscf"][1])
            sy_nid = f"{pid}.y{yr}.sefa_y"
            if sy_nid not in tree.nodes:
                tree.calc(
                    sy_nid,
                    f"SEFA {yr} — {p.name}",
                    sy_val,
                    "t CO2/t",
                    "CBAM factor × CSCF × SEFA",
                    [yp["cbam_factor"][0], yp["cscf"][0], sefa_g_nid],
                )
            ca = e.cost_per_tonne(s_val, sy_val, price)
            ca_nid = f"{pid}.y{yr}.cost_actual"
            tree.calc(
                ca_nid,
                f"Buyer cost per t {yr} — actual data",
                ca.cost_eur_per_t,
                "EUR/t",
                "max(0, SEE − SEFA_y) × price",
                [s_nid, sy_nid, pr_nid],
            )
            # default path
            d_see = e.default_see(dv_good.value, yp["default_markup"][1])
            d_see_nid = f"{pid}.y{yr}.default_see"
            tree.calc(
                d_see_nid,
                f"Default SEE {yr} — CN {p.cn_display}",
                d_see,
                "t CO2/t",
                "DV(country, CN) × (1 + mark-up)",
                [f"ref.dv.{p.cn}", yp["default_markup"][0]],
                status=DEFAULT_USED,
            )
            bmb = refdata.benchmark(p.cn, "B", yr, route=good_route)
            bmb_nid = c.ref_leaf(
                f"ref.bmB.{p.cn}.{'1' if yr <= 2027 else '2'}",
                f"Benchmark col. B, CN {p.cn_display} ({bmb.extra.get('indicator') or '-'})",
                bmb,
            )
            d_sy = e.sefa_year(bmb.value, yp["cbam_factor"][1], yp["cscf"][1])
            d_sy_nid = f"{pid}.y{yr}.default_sefa_y"
            tree.calc(
                d_sy_nid,
                f"Default SEFA {yr} — CN {p.cn_display}",
                d_sy,
                "t CO2/t",
                "CBAM factor × CSCF × BM_B(good)",
                [yp["cbam_factor"][0], yp["cscf"][0], bmb_nid],
            )
            cd = e.cost_per_tonne(d_see, d_sy, price)
            cd_nid = f"{pid}.y{yr}.cost_default"
            tree.calc(
                cd_nid,
                f"Buyer cost per t {yr} — EU default values",
                cd.cost_eur_per_t,
                "EUR/t",
                "max(0, SEE_default − SEFA_default,y) × price",
                [d_see_nid, d_sy_nid, pr_nid],
            )
            gap = cd.cost_eur_per_t - ca.cost_eur_per_t
            gap_nid = f"{pid}.y{yr}.gap"
            tree.calc(gap_nid, f"Money on the table per t {yr}", gap, "EUR/t", "default cost − actual cost", [cd_nid, ca_nid])
            # The buyer can only gain from the exporter's data when it beats the default: while a
            # precursor is on its marked-up default, the good's own default can be the cheaper path.
            basis = "actual" if ca.cost_eur_per_t <= cd.cost_eur_per_t else "default"
            buyer = min(ca.cost_eur_per_t, cd.cost_eur_per_t)
            series.append(
                {
                    "year": yr,
                    "price_eur": str(price),
                    "price_status": "official" if yr == 2026 else "assumption",
                    "see_actual": str(s_val),
                    "sefa_y": str(sy_val),
                    "see_default": str(d_see),
                    "sefa_default_y": str(d_sy),
                    "actual_eur_t": str(ca.cost_eur_per_t),
                    "default_eur_t": str(cd.cost_eur_per_t),
                    "gap_eur_t": str(gap),
                    "buyer_eur_t": str(buyer),
                    "basis": basis,
                    "actual_inr_t": str(ca.cost_eur_per_t * fx.value),
                    "default_inr_t": str(cd.cost_eur_per_t * fx.value),
                    "gap_inr_t": str(gap * fx.value),
                    "buyer_inr_t": str(buyer * fx.value),
                    "nodes": {"actual": ca_nid, "default": cd_nid, "gap": gap_nid},
                }
            )
        money[pid] = series

        # ---- the same 2026 imports on EU default values (per quarter, like the actual path)
        y0 = project.year
        d_see0 = tree.get(f"{pid}.y{y0}.default_see").value or D(0)
        d_sy0 = tree.get(f"{pid}.y{y0}.default_sefa_y").value or D(0)
        dcost_kids = []
        cost_default = D(0)
        for quarter, t_q in sorted(exports[pid].items()):
            r = e.certificates([e.ImportLine(t_q, d_see0, d_sy0, quarter)])
            qn = int(quarter[-1])
            dnid = f"{pid}.cert_default.{quarter}"
            tree.calc(
                dnid,
                f"Certificates for {quarter} imports — EU default values",
                r.certificates,
                "certificates",
                "M × (SEE_default − SEFA_default,y)",
                [f"{pid}.exports", f"{pid}.y{y0}.default_see", f"{pid}.y{y0}.default_sefa_y"],
            )
            pref = refdata.quarter_price(y0, qn)
            pn = c.ref_leaf(f"ref.price.{y0}Q{qn}", f"CBAM certificate price Q{qn} {y0}", pref)
            cnid = f"{pid}.cost_default.{quarter}"
            tree.calc(
                cnid,
                f"Buyer's CBAM cost {quarter} — EU default values",
                r.certificates * pref.value,
                "EUR",
                "certificates × price(quarter)",
                [dnid, pn],
            )
            cost_default += r.certificates * pref.value
            dcost_kids.append(cnid)
        tree.calc(
            f"{pid}.cost_default.total",
            f"Buyer's CBAM cost, 2026 imports on EU default values — {p.name}",
            cost_default,
            "EUR",
            "Σ quarterly cost",
            dcost_kids or ["as.cpp"],
        )
        s0 = series[0]
        basis0 = s0["basis"]
        tree.calc(
            f"{pid}.cost_buyer.total",
            f"Buyer's CBAM cost, 2026 imports — cheaper path ({'your data' if basis0 == 'actual' else 'EU default values'})",
            cost_2026 if basis0 == "actual" else cost_default,
            "EUR",
            "min(cost on your data, cost on EU default values)",
            [f"{pid}.cost.total", f"{pid}.cost_default.total"],
        )
        exp_t = sum(exports[pid].values(), D(0))
        buyer_info: dict[str, Any] = {
            "basis_2026": basis0,
            "actual_eur_t": s0["actual_eur_t"],
            "default_eur_t": s0["default_eur_t"],
            "buyer_eur_t": s0["buyer_eur_t"],
            "cost_actual_eur": str(cost_2026),
            "cost_actual_node": f"{pid}.cost.total",
            "cost_default_eur": str(cost_default),
            "cost_default_node": f"{pid}.cost_default.total",
            "cost_buyer_eur": str(cost_2026 if basis0 == "actual" else cost_default),
            "cost_buyer_node": f"{pid}.cost_buyer.total",
            "gap_vs_default_eur_t": s0["gap_eur_t"],
            "annual_factor": str(annual),
            "annual_gap_eur": str(D(s0["gap_eur_t"]) * exp_t * annual),
            "supplier_saving_eur_t": None,
            "supplier_saving_annual_eur": None,
        }

        # ---- what-if: supplier sends verified data (Precursor Lever)
        wi = project.what_if.get(pid)
        if wi:
            wi_see, wi_sefa = D(str(wi["see"])), D(str(wi["sefa"]))
            tree.leaf(
                f"whatif.{pid}.rod.see",
                f"What-if: supplier SEE ({wi.get('source', 'scenario')})",
                wi_see,
                "t CO2/t",
                source={"kind": "scenario", "note": wi.get("source", "")},
                status="SCENARIO",
            )
            tree.leaf(
                f"whatif.{pid}.rod.sefa",
                "What-if: supplier SEFA",
                wi_sefa,
                "t CO2/t",
                source={"kind": "scenario", "note": wi.get("source", "")},
                status="SCENARIO",
            )
            w_see = direct + m * wi_see
            tree.calc(
                f"whatif.{pid}.see",
                f"What-if SEE — {p.name}",
                w_see,
                "t CO2/t",
                "AttrEm/AL + m × SEE_rod(supplier)",
                [f"{pid}.direct", f"{pid}.rod.m", f"whatif.{pid}.rod.see"],
                status="SCENARIO",
            )
            w_sefa = e.sefa(bm_a.value, [e.PrecursorSEFA(m, wi_sefa)])
            tree.calc(
                f"whatif.{pid}.sefa",
                f"What-if SEFA — {p.name}",
                w_sefa,
                "t CO2/t",
                "BM_A(own) + m × SEFA_rod(supplier)",
                [f"ref.bmA.{p.cn}", f"{pid}.rod.m", f"whatif.{pid}.rod.sefa"],
                status="SCENARIO",
            )
            ws: list[dict[str, Any]] = []
            for yr in YEARS:
                yp = years[yr]
                price = price_2026 if yr == 2026 else proj_price.value
                sy_w = e.sefa_year(w_sefa, yp["cbam_factor"][1], yp["cscf"][1])
                cw = e.cost_per_tonne(w_see, sy_w, price)
                nid = f"whatif.{pid}.y{yr}.cost"
                tree.calc(
                    nid,
                    f"What-if buyer cost per t {yr}",
                    cw.cost_eur_per_t,
                    "EUR/t",
                    "max(0, SEE − SEFA_y) × price",
                    [
                        f"whatif.{pid}.see",
                        f"whatif.{pid}.sefa",
                        yp["cbam_factor"][0],
                        yp["cscf"][0],
                        "y2026.price" if yr == 2026 else "as.price_projection",
                    ],
                    status="SCENARIO",
                )
                ws.append(
                    {
                        "year": yr,
                        "eur_t": str(cw.cost_eur_per_t),
                        "inr_t": str(cw.cost_eur_per_t * fx.value),
                        "see": str(w_see),
                        "node": nid,
                    }
                )
            whatif_money[pid] = ws
            with_supplier = min(D(ws[0]["eur_t"]), D(s0["default_eur_t"]))
            saving = D(s0["buyer_eur_t"]) - with_supplier
            buyer_info["supplier_saving_eur_t"] = str(saving)
            buyer_info["supplier_saving_annual_eur"] = str(saving * exp_t * annual)
            buyer_info["with_supplier_eur_t"] = str(with_supplier)

        # ---- extra parameters (Guidance 5d Table 3-1)
        def avg(field: str) -> dict[str, Any]:
            xs = c.pick(field, pid, doc_type="precursor_invoice")
            if not xs:
                return {"value": None, "status": MISSING, "evidence": []}
            v = sum((_num(x) for x in xs), D(0)) / len(xs)
            return {"value": q(v, 2), "status": _worst([x.status for x in xs]), "evidence": [x.id for x in xs]}

        ra = c.pick("reducing_agent", pid, doc_type="supplier_emissions_statement")
        route = c.pick("route", pid, doc_type="supplier_emissions_statement")
        extra = {
            "main_reducing_agent": {
                "value": ra[0].value_text if ra else None,
                "status": (ra[0].status if ra else MISSING),
                "evidence": [ra[0].id] if ra else [],
                "optional": True,
            },
            "mn_pct": avg("mn_pct"),
            "cr_pct": avg("cr_pct"),
            "ni_pct": avg("ni_pct"),
            "other_alloy_pct": avg("other_alloy_pct"),
            "scrap_t_per_t": {
                "value": "0.00",
                "status": "DERIVED",
                "evidence": [],
                "note": "No scrap is charged as input; cut-offs are an output (zero embedded emissions).",
            },
            "pre_consumer_scrap_pct": {
                "value": None,
                "status": "NOT_APPLICABLE",
                "evidence": [],
                "note": "Not applicable: no scrap input.",
            },
        }
        tree.calc(
            f"{pid}.own_share", f"Own-process share of SEE — {p.name}", direct / see_val, "-", "direct ÷ SEE", [f"{pid}.direct", see_nid]
        )
        contrib = [
            {"key": "own", "label": "Own process (natural gas)", "value": str(direct), "node": f"{pid}.direct"},
            {
                "key": "rod",
                "label": f"{p.precursor_name} — {p.precursor_supplier}",
                "value": str(m * rs_val),
                "node": f"{pid}.rod.contrib",
                "status": "ACTUAL" if actual else DEFAULT_USED,
            },
        ]
        out_procs.append(
            {
                "id": pid,
                "name": p.name,
                "cn": p.cn,
                "cn_display": p.cn_display,
                "cn_desc": p.cn_desc,
                "al_t": str(a),
                "exports_t": str(sum(exports[pid].values(), D(0))),
                "exports_by_quarter": {k: str(v) for k, v in sorted(exports[pid].items())},
                "see": str(see_val),
                "see_node": see_nid,
                "direct": str(direct),
                "m": str(m),
                "precursor": {
                    "name": p.precursor_name,
                    "supplier": p.precursor_supplier,
                    "cn": p.precursor_cn,
                    "cn_display": refdata.fmt_cn(p.precursor_cn),
                    "data": "ACTUAL_VERIFIED" if actual else DEFAULT_USED,
                    "see": str(rs_val),
                    "see_node": rs_nid,
                    "sefa": str(sefa_rod),
                    "sefa_node": sefa_rod_nid,
                    "status": rs_status,
                    "default_value": str(dv_rod.value),
                    "default_locator": dv_rod.locator,
                    "route": route[0].value_text if route else (f"({rod_route}) default route" if rod_route else None),
                },
                "sefa": str(sefa_val),
                "sefa_node": f"{pid}.sefa",
                "sefa_y": str(sy),
                "sefa_y_node": f"{pid}.y{project.year}.sefa_y",
                "certificates_2026": str(total_cert.certificates),
                "certificates_node": f"{pid}.cert.total",
                "cost_2026_eur": str(cost_2026),
                "cost_node": f"{pid}.cost.total",
                "buyer": buyer_info,
                "contribution": contrib,
                "extra_parameters": extra,
                "default_see_2026": series[0]["see_default"],
                "production_route_good": good_route,
            }
        )

    good = [s for _, s in see_inputs if s in GOOD_STATUSES]
    by_status: dict[str, int] = defaultdict(int)
    for _, s in see_inputs:
        by_status[s] += 1
    by_process: dict[str, dict[str, Any]] = {}
    for pid_, items in proc_inputs.items():
        ok = sum(1 for _, s in items if s in GOOD_STATUSES)
        missing = sum(1 for _, s in items if s == MISSING)
        review = sum(1 for _, s in items if s in (NEEDS_REVIEW, "PENDING"))
        by_process[pid_] = {
            "score": str(D(ok) / D(len(items)) * 100 if items else D(0)),
            "total": len(items),
            "good": ok,
            "missing": missing,
            "review": review,
            "precursor": "actual" if proc_actual[pid_] else "default",
            # declarable on actual data: verified precursor data and every SEE input read and agreed/approved
            "ready": proc_actual[pid_] and ok == len(items),
        }
    readiness = {
        "score": str((D(len(good)) / D(len(see_inputs)) * 100) if see_inputs else D(0)),
        "total": len(see_inputs),
        "by_status": dict(by_status),
        "by_process": by_process,
        "lines_ready": sum(1 for v in by_process.values() if v["ready"]),
        "lines_total": len(by_process),
        "definition": "Share of SEE-relevant inputs that are VERIFIED_2R (two readers agree) or APPROVED (human).",
    }
    operations = _operations(c, al, gas)
    return {
        "computed_at": now(),
        "project_id": project.id,
        "year": project.year,
        "period_label": project.period_label,
        "processes": out_procs,
        "money": {
            "years": YEARS,
            "series": money,
            "what_if": whatif_money,
            "fx": {"value": str(fx.value), "status": "assumption", "as_of": fx.extra.get("as_of"), "citation": fx.locator},
            "projection_price": {"value": str(proj_price.value), "status": "assumption", "citation": proj_price.locator},
            "price_2026": {"value": str(price_2026), "node": "y2026.price"},
        },
        "gas": {"tco2": str(gas["tco2"]), "missing": gas["missing"]},
        "operations": operations,
        "period_months": len(project.months),
        "readiness": readiness,
        "calc_tree": tree.to_json(),
        "assumptions_used": sorted(c.used_assumptions),
    }
