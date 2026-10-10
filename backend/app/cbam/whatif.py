"""X2 - decarbonisation what-if (deterministic, nothing stored).

Levers for a product line:
  * rod_see / rod_sefa - a different supplier's verified values (user-entered or EC example values)
  * heating            - "gas" (current) or "electric": for iron and steel goods only direct
                         emissions count (CBAM Regulation Annex II), so electric heat treatment
                         removes the own-process direct emissions from the SEE.
Returns SEE, SEFA and the buyer's cost per tonne for 2026-2034 next to the current figures.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app import refdata
from app.cbam import engine as e
from app.cbam.project import YEARS

D = Decimal


def simulate(result: dict[str, Any], process_id: str, rod_see: Decimal | None, rod_sefa: Decimal | None, heating: str) -> dict[str, Any]:
    p = next((x for x in result["processes"] if x["id"] == process_id and "see" in x), None)
    if p is None:
        raise ValueError(f"unknown process {process_id}")
    tree = result["calc_tree"]
    m = D(p["m"])
    direct_now = D(p["direct"])
    direct = D(0) if heating == "electric" else direct_now
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
        series.append(
            {
                "year": y,
                "eur_t": str(c.cost_eur_per_t),
                "inr_t": str(c.cost_eur_per_t * fx),
                "now_eur_t": now["actual_eur_t"],
                "default_eur_t": now["default_eur_t"],
            }
        )
    return {
        "process_id": process_id,
        "inputs": {"rod_see": str(see_rod), "rod_sefa": str(sefa_rod), "heating": heating, "m": str(m)},
        "see": str(see),
        "see_now": p["see"],
        "direct": str(direct),
        "direct_now": str(direct_now),
        "sefa": str(sefa),
        "series": series,
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
