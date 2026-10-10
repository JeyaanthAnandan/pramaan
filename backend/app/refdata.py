"""Read-only access to the versioned reference data in backend/refdata/.

All lookups return the value together with a citation so the calculation tree can show
where every regulatory number came from.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from decimal import Decimal
from functools import cache, lru_cache
from pathlib import Path
from typing import Any

REFDATA_DIR = Path(__file__).resolve().parents[1] / "refdata"


class RefdataError(LookupError):
    pass


@dataclass(frozen=True)
class Ref:
    """A reference value with its provenance."""

    value: Decimal
    unit: str
    file: str
    locator: str
    status: str = "official"  # official | preliminary | assumption
    citation: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    def source(self) -> dict[str, Any]:
        src = {
            "kind": "assumption" if self.status == "assumption" else "refdata",
            "file": self.file,
            "locator": self.locator,
            "status": self.status,
            **({"citation": self.citation} if self.citation else {}),
        }
        mf = manifest()["files"].get(f"json/{self.file}")
        if mf and mf["sources"]:
            s = manifest()["sources"][mf["sources"][0]]
            src["document"] = {"title": s["title"], "url": s["url"], "published": s.get("published"), "sha256": s["sha256"][:16]}
        return src


def _load(name: str) -> dict[str, Any]:
    path = REFDATA_DIR / "json" / name
    if not path.exists():
        raise RefdataError(f"refdata file missing: {name} (run refdata/build_refdata.py)")
    return json.loads(path.read_text())


@lru_cache(maxsize=1)
def manifest() -> dict[str, Any]:
    return json.loads((REFDATA_DIR / "manifest.json").read_text())


@cache
def data(name: str) -> dict[str, Any]:
    return _load(name)


def norm_cn(cn: str) -> str:
    return re.sub(r"\D", "", cn)


def fmt_cn(cn: str) -> str:
    d = norm_cn(cn)
    return " ".join([d[:4]] + [d[i : i + 2] for i in range(4, len(d), 2)]).strip()


# ---------------------------------------------------------------- default values


def default_value(country: str, cn: str) -> Ref:
    """Country-specific default SEE (direct, no mark-up) by longest CN prefix.

    Falls back to 'Other Countries and Territories' when the country table has no value
    (Guidance 3, p. 114). Iron & steel goods count direct emissions only.
    """
    dv = data("default_values_iron_steel.json")
    cnd = norm_cn(cn)
    tried = []
    for table_name in [country, "Other Countries and Territories"]:
        table = dv["countries"].get(table_name)
        if table is None:
            tried.append(f"{table_name}: no table")
            continue
        for n in range(len(cnd), 3, -1):
            row = table.get(cnd[:n])
            if row is None:
                continue
            if row.get("direct") is None:
                tried.append(f"{table_name} {row['cn_display']}: '-'")
                break
            return Ref(
                value=Decimal(row["direct"]),
                unit="t CO2e/t",
                file="default_values_iron_steel.json",
                locator=f"Annex I, {table_name}, CN {row['cn_display']}",
                extra={
                    "country_table": table_name,
                    "fallback": table_name != country,
                    "route": row.get("route"),
                    "cn_matched": row["cn_display"],
                    "description": dv["descriptions"].get(norm_cn(row["cn_display"]), ""),
                    "tried": tried,
                },
            )
        tried.append(f"{table_name}: no CN match")
    raise RefdataError(f"no default value for CN {cn} ({'; '.join(tried)})")


def annex_iv_value(cn: str) -> Ref:
    table = data("default_values_iron_steel.json")["annex_iv"]
    cnd = norm_cn(cn)
    for n in range(len(cnd), 3, -1):
        row = table.get(cnd[:n])
        if row and row.get("total"):
            return Ref(
                Decimal(row["total"]),
                "t CO2e/t",
                "default_values_iron_steel.json",
                f"Annex IV, CN {row['cn_display']}",
                extra={"route": row.get("route")},
            )
    raise RefdataError(f"no Annex IV value for {cn}")


# ---------------------------------------------------------------- benchmarks


def _period_code(year: int) -> str:
    return "1" if year <= 2027 else "2"


def benchmark(cn8: str, column: str, year: int, route: str | None = None) -> Ref:
    """CBAM benchmark (Free Allocation Adjustment Act, Annex section 5).

    column "A": actual-data route (own process). column "B": default route.
    route: production-route code such as "C" (BF/BOF) when the CN has several values.
    Year selects (1) for 2026-27 and (2) for 2028+ (Guidance 4, Table 2-2).
    """
    bms = data("benchmarks.json")["benchmarks"]
    cnd = norm_cn(cn8)
    row = bms.get(cnd)
    if row is None:
        raise RefdataError(f"no benchmark row for CN {cn8} (8-digit CN required)")
    entries = row["col_a" if column.upper() == "A" else "col_b"]
    if not entries:
        raise RefdataError(f"no column {column} benchmark for {cn8}")
    period = _period_code(year)
    route_code = route.strip("()") if route else None

    def codes(ind: str | None) -> set[str]:
        return set(re.findall(r"\(([0-9A-Z])\)", ind or ""))

    candidates = entries
    if len(entries) > 1:
        has_route = any(codes(e["indicator"]) - {"1", "2"} for e in entries)
        has_period = any(codes(e["indicator"]) & {"1", "2"} for e in entries)
        if has_route:
            if not route_code:
                raise RefdataError(f"CN {cn8} column {column} depends on production route; none given")
            candidates = [e for e in candidates if route_code in codes(e["indicator"])]
        if has_period:
            candidates = [e for e in candidates if period in codes(e["indicator"])]
    if len(candidates) != 1:
        raise RefdataError(f"ambiguous benchmark for {cn8} col {column} route={route} year={year}: {candidates}")
    e = candidates[0]
    status = "official"
    if year > 2030 and period == "2" and "2" in codes(e["indicator"]):
        status = "preliminary"  # (2) is defined for 2028-30 only
    return Ref(
        value=Decimal(e["value"]),
        unit="t CO2e/t",
        file="benchmarks.json",
        locator=f"Reg. 2025/2620 Annex s.5, CN {fmt_cn(cnd)}, column {column.upper()}{(' ' + e['indicator']) if e['indicator'] else ''}",
        status=status,
        extra={"indicator": e["indicator"], "description": row["description"]},
    )


# ---------------------------------------------------------------- schedules, prices, fuels


def year_params(year: int) -> dict[str, Ref]:
    sched = data("cbam_schedule.json")["years"]
    y = sched.get(str(year))
    if y is None:
        raise RefdataError(f"no CBAM schedule for {year}")
    return {
        "cbam_factor": Ref(
            Decimal(y["cbam_factor"]), "-", "cbam_schedule.json", f"Guidance 4 Table 2-1, {year}", citation=y["cbam_factor_citation"]
        ),
        "cscf": Ref(
            Decimal(y["cscf"]),
            "-",
            "cbam_schedule.json",
            f"CSCF {year}",
            status="official" if y["cscf_status"] == "official" else "preliminary",
            citation=y["cscf_citation"],
        ),
        "default_markup": Ref(
            Decimal(y.get("default_markup", "0")),
            "-",
            "cbam_schedule.json",
            f"Default value mark-up {year}",
            citation=y.get("markup_citation", {}),
        ),
    }


def quarter_price(year: int, quarter: int) -> Ref:
    q = data("certificate_prices.json")["quarters"].get(f"{year}-Q{quarter}")
    if q and q.get("price_eur"):
        return Ref(
            Decimal(q["price_eur"]),
            "EUR/certificate",
            "certificate_prices.json",
            f"EC price page, Q{quarter} {year} (published {q['published']})",
        )
    if year == 2026 and quarter == 4:
        return assumption("q4_2026_price_eur")
    return assumption("projection_price_eur")


def fuel(key: str) -> dict[str, Ref]:
    f = data("fuel_factors.json")["fuels"].get(key)
    if f is None:
        raise RefdataError(f"unknown fuel {key}")
    cit = f["citation"]
    return {
        "ef": Ref(
            Decimal(f["ef_t_co2_per_tj"]),
            "t CO2/TJ",
            "fuel_factors.json",
            f"Methodology Act Annex II s.G Table 1: {f['name']} EF",
            citation=cit,
        ),
        "ncv": Ref(
            Decimal(f["ncv_tj_per_gg"]),
            "TJ/Gg",
            "fuel_factors.json",
            f"Methodology Act Annex II s.G Table 1: {f['name']} NCV",
            citation=cit,
        ),
    }


def assumption(key: str) -> Ref:
    a = data("assumptions.json")["assumptions"].get(key)
    if a is None:
        raise RefdataError(f"unknown assumption {key}")
    try:
        val = Decimal(a["value"])
    except Exception:  # non-numeric assumption (e.g. allocation key)
        val = Decimal(0)
    return Ref(
        val,
        a.get("unit", "-"),
        "assumptions.json",
        a["citation"],
        status="assumption",
        extra={k: v for k, v in a.items() if k not in {"value"}} | {"raw": a["value"]},
    )


def summary() -> list[dict[str, Any]]:
    m = manifest()
    out = []
    for f, e in sorted(m["files"].items()):
        srcs = [m["sources"][s] for s in e["sources"]]
        out.append(
            {
                "file": f,
                "sha256": e["sha256"][:12],
                "status": e["status"],
                "parser_version": e["parser_version"],
                "sources": [{"title": s["title"], "published": s.get("published"), "downloaded_at": s["downloaded_at"]} for s in srcs],
            }
        )
    return out
