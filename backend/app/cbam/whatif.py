"""X2 - operations & decarbonisation what-if (deterministic, nothing stored).

Levers for a product line:
  * rod_see / rod_sefa - a different supplier's verified values (user-entered or EC example values)
  * scrap_pct          - scrap and cut-offs as % of the rod consumed. Less scrap means less rod per
                         tonne of product (m = 1 / (1 - scrap share)), which lowers both SEE (m x SEE_rod)
                         and SEFA (m x SEFA_rod), so the buyer-cost effect is small while free
                         allocation lasts and grows as it phases out; the rod saved is the plant's win.
  * gas_gj_per_t       - heat-treatment gas per tonne (NCV); direct emissions scale with it
  * heating            - "gas" (current) or "electric": for iron and steel goods only direct
                         emissions count (CBAM Regulation Annex II), so electric heat treatment
                         removes the own-process direct emissions from the SEE.
Returns SEE, SEFA and the buyer's cost per tonne for 2026-2034 next to the current figures. The
buyer pays the cheaper of the exporter's data and the EU default, before and after the change.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app import refdata
from app.cbam import engine as e
from app.cbam.project import YEARS

D = Decimal


def simulate(
    result: dict[str, Any],
    process_id: str,
    rod_see: Decimal | None,
    rod_sefa: Decimal | None,
    heating: str,
    scrap_pct: Decimal | None = None,
    gas_gj_per_t: Decimal | None = None,
) -> dict[str, Any]:
    p = next((x for x in result["processes"] if x["id"] == process_id and "see" in x), None)
    if p is None:
        raise ValueError(f"unknown process {process_id}")
    tree = result["calc_tree"]
    ops = result.get("operations") or {}
    ops_p = (ops.get("processes") or {}).get(process_id) or {}
    m_now = D(p["m"])
    m = D(1) / (D(1) - scrap_pct / D(100)) if scrap_pct is not None else m_now
    direct_now = D(p["direct"])
    gas_now = D(ops["gas_gj_per_t"]) if ops.get("gas_gj_per_t") else None
    gas_new = gas_now
    if heating == "electric":
        direct, gas_new = D(0), D(0)
    elif gas_gj_per_t is not None and gas_now:
        direct, gas_new = direct_now * gas_gj_per_t / gas_now, gas_gj_per_t
    else:
        direct = direct_now
    see_rod = rod_see if rod_see is not None else D(p["precursor"]["see"])
    sefa_rod = rod_sefa if rod_sefa is not None else D(p["precursor"]["sefa"])
    bm_a = D(tree[f"ref.bmA.{p['cn']}"]["value"])
    see = direct + m * see_rod
    sefa = e.sefa(bm_a, [e.PrecursorSEFA(m, sefa_rod)])
    price_2026 = D(result["money"]["price_2026"]["value"])
    price_proj = D(result["money"]["projection_price"]["value"])
    fx = D(result["money"]["fx"]["value"])
    series = []
    for i, y in enumerate(YEARS):
        yp = refdata.year_params(y)
        price = price_2026 if y == 2026 else price_proj
        c = e.cost_per_tonne(see, e.sefa_year(sefa, yp["cbam_factor"].value, yp["cscf"].value), price)
        now = result["money"]["series"][process_id][i]
        default = D(now["default_eur_t"])
        buyer_now = min(D(now["actual_eur_t"]), default)
        buyer = min(c.cost_eur_per_t, default)
        series.append(
            {
                "year": y,
                "eur_t": str(c.cost_eur_per_t),
                "inr_t": str(c.cost_eur_per_t * fx),
                "now_eur_t": now["actual_eur_t"],
                "default_eur_t": now["default_eur_t"],
                "buyer_now_eur_t": str(buyer_now),
                "buyer_eur_t": str(buyer),
                "buyer_inr_t": str(buyer * fx),
                "basis_now": "actual" if D(now["actual_eur_t"]) <= default else "default",
                "basis": "actual" if c.cost_eur_per_t <= default else "default",
            }
        )
    annual = D(12) / D(result.get("period_months") or 12)
    al_year = D(p["al_t"]) * annual
    return {
        "process_id": process_id,
        "inputs": {
            "rod_see": str(see_rod),
            "rod_sefa": str(sefa_rod),
            "heating": heating,
            "m": str(m),
            "scrap_pct": str(scrap_pct) if scrap_pct is not None else ops_p.get("scrap_pct"),
            "gas_gj_per_t": str(gas_new) if gas_new is not None else None,
        },
        "current": {
            "scrap_pct": ops_p.get("scrap_pct"),
            "gas_gj_per_t": ops.get("gas_gj_per_t"),
            "m": str(m_now),
        },
        "see": str(see),
        "see_now": p["see"],
        "direct": str(direct),
        "direct_now": str(direct_now),
        "sefa": str(sefa),
        "series": series,
        "plant": {
            # physical savings per year at current volumes (year-to-date scaled to 12 months)
            "rod_saved_t_per_year": str(al_year * (m_now - m)),
            "gas_saved_gj_per_year": str(al_year * (gas_now - gas_new)) if gas_now is not None and gas_new is not None else None,
            "annual_factor": str(annual),
        },
        "note": "Iron & steel goods: only direct emissions count, so electric heat treatment removes the own-process share; grid electricity is not added to SEE.",
        "presets": {
            "ec_example_1_bars_bf_bof": {"rod_see": "1.567", "rod_sefa": "1.242", "source": "EC Guidance 5d Example 1 (Tables 4-5, 4-6)"},
            "ec_example_2_stainless_eaf": {
                "rod_see": "1.783",
                "rod_sefa": "0.919",
                "source": "EC Guidance 5d Example 2 (Table 4-10) and Table 4-14",
            },
        },
    }
