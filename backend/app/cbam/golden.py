"""Golden cases from EC Guidance No. 5d (iron and steel, 14 Aug 2026), section 4.

Shared by ``tests/test_golden_ec.py`` (CI gate) and ``GET /golden`` (the in-app
"EC example reproduced" badge). Inputs are copied from the guidance tables; expected values
are the guidance's printed results. EC tables round intermediates to 3 decimals, hence the
tolerance of +/-0.002 t CO2/t for SEE/SEFA.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Callable

from app import refdata
from app.cbam import engine as e

D = Decimal
TOL = D("0.002")
GUIDANCE = "EC Guidance No. 5d - iron and steel (14 Aug 2026)"


@dataclass(frozen=True)
class Expect:
    key: str
    label: str
    expected: Decimal
    tolerance: Decimal
    unit: str


@dataclass(frozen=True)
class GoldenCase:
    id: str
    title: str
    source: str
    inputs: dict[str, str]
    expects: tuple[Expect, ...]
    compute: Callable[[], dict[str, Decimal]]

    def run(self) -> dict[str, object]:
        got = self.compute()
        rows = []
        ok = True
        for x in self.expects:
            v = got[x.key]
            passed = abs(v - x.expected) <= x.tolerance
            ok &= passed
            rows.append(
                {
                    "key": x.key,
                    "label": x.label,
                    "expected": str(x.expected),
                    "computed": str(v.quantize(D("0.0001"))),
                    "tolerance": str(x.tolerance),
                    "unit": x.unit,
                    "pass": passed,
                }
            )
        return {"id": self.id, "title": self.title, "source": self.source, "inputs": self.inputs, "checks": rows, "pass": ok}


def _gas_direct(al: Decimal) -> Decimal:
    # Example 3: natural gas 3.5 GJ (NCV) per t product, EF 56.1 t CO2/TJ (Table 4-12)
    return e.fuel_emissions_t(D("3.5") * al, D("56.1"))


def _g1() -> dict[str, Decimal]:
    al = D("17000")
    r = e.see(al, _gas_direct(al), [e.PrecursorUse(D("20000"), D("1.567"), "carbon steel rod")])
    return {"direct": r.direct_specific, "precursor": r.precursor_specific, "see": r.see, "m": r.m[0]}


def _g2() -> dict[str, Decimal]:
    al = D("8200")
    r = e.see(al, _gas_direct(al), [e.PrecursorUse(D("10000"), D("1.783"), "high-alloy steel rod")])
    return {"direct": r.direct_specific, "precursor": r.precursor_specific, "see": r.see, "m": r.m[0]}


def _factor_2027() -> tuple[Decimal, Decimal]:
    p = refdata.year_params(2027)
    return p["cbam_factor"].value, p["cscf"].value


def _g3() -> dict[str, Decimal]:
    s = e.sefa(D("0.057"), [e.PrecursorSEFA(D("1.042"), D("1.156"), "crude steel")])
    f, c = _factor_2027()
    return {"sefa": s, "sefa_2027": e.sefa_year(s, f, c), "cbam_factor_2027": f}


def _g4() -> dict[str, Decimal]:
    r = e.certificates([e.ImportLine(D("10000"), D("1.539") + D("0.028"), D("1.198"), "rails")])
    return {"ee": r.embedded_t, "faa": r.faa_t, "certificates": r.certificates}


def _g5() -> dict[str, Decimal]:
    s = e.sefa(D("0.057"), [e.PrecursorSEFA(D("1.083"), D("0.748"), "crude steel slabs")])
    f, c = _factor_2027()
    sy = e.sefa_year(s, f, c)
    r = e.certificates([e.ImportLine(D("100"), D("1.783"), sy, "stainless pipes")])
    return {"sefa": s, "faa": r.faa_t, "certificates": r.certificates}


def _g6() -> dict[str, Decimal]:
    sheets = e.sefa(D("0.044"), [e.PrecursorSEFA(D("1.042"), D("1.156"))])
    bars = e.sefa(D("0.038"), [e.PrecursorSEFA(D("1.042"), D("1.156"))])
    return {"sheets": sheets, "bars": bars}


def _g7() -> dict[str, Decimal]:
    m1 = e.mass_ratio(D("20000"), D("17000"))
    m2 = e.mass_ratio(D("10000"), D("8200"))
    return {
        "carbon": e.sefa(D("0.038"), [e.PrecursorSEFA(m1, D("1.242"))]),
        "stainless": e.sefa(D("0.038"), [e.PrecursorSEFA(m2, D("0.919"))]),
    }


def _g8() -> dict[str, Decimal]:
    """Benchmarks used above, re-read from the official benchmark file (not hand-typed)."""
    return {
        "bm_rails_a": refdata.benchmark("73021050", "A", 2027).value,
        "bm_bars_a": refdata.benchmark("72139149", "A", 2027).value,
        "bm_screws_a": refdata.benchmark("73181290", "A", 2027).value,
        "bm_screws_b": refdata.benchmark("73181290", "B", 2027, route="C").value,
        "bm_stainless_screws_b": refdata.benchmark("73181210", "B", 2027).value,
        "ng_ef": refdata.fuel("natural_gas")["ef"].value,
    }


CASES: dict[str, GoldenCase] = {
    c.id: c
    for c in [
        GoldenCase(
            "G1",
            "Example 3 - carbon-steel screws and nuts: SEE",
            f"{GUIDANCE}, s.4.3, Tables 4-12 and 4-13, p. 53",
            {"AL": "17,000 t", "rod consumed": "20,000 t (scrap 3,000 t)", "rod SEE": "1.567", "natural gas": "3.5 GJ(NCV)/t, EF 56.1 t CO2/TJ"},
            (
                Expect("direct", "Direct (natural gas)", D("0.196"), TOL, "t CO2/t"),
                Expect("precursor", "Precursor (rod)", D("1.843"), TOL, "t CO2/t"),
                Expect("see", "SEE", D("2.039"), TOL, "t CO2/t"),
                Expect("m", "m (rod per t product)", D("1.176"), D("0.0005"), "t/t"),
            ),
            _g1,
        ),
        GoldenCase(
            "G2",
            "Example 3 - high-alloy screws and nuts: SEE",
            f"{GUIDANCE}, s.4.3, Tables 4-12 and 4-13, p. 53",
            {"AL": "8,200 t", "rod consumed": "10,000 t (scrap 1,800 t)", "rod SEE": "1.783", "natural gas": "3.5 GJ/t"},
            (
                Expect("precursor", "Precursor (rod)", D("2.175"), TOL, "t CO2/t"),
                Expect("see", "SEE", D("2.371"), TOL, "t CO2/t"),
                Expect("m", "m (rod per t product)", D("1.220"), D("0.0005"), "t/t"),
            ),
            _g2,
        ),
        GoldenCase(
            "G3",
            "Example 1 - SEFA of rails, import year 2027",
            f"{GUIDANCE}, s.4.1, Table 4-6 (p. 43) and SEFA_2027 formula (p. 44)",
            {"BM col. A (rails)": "0.057", "m crude steel": "1.042", "SEFA crude steel": "1.156", "CBAM factor 2027": "from refdata (Guidance 4 Table 2-1)", "CSCF": "1 (Decision 2026/1862)"},
            (
                Expect("sefa", "SEFA rails", D("1.261"), TOL, "t CO2/t"),
                Expect("sefa_2027", "SEFA rails, 2027", D("1.198"), TOL, "t CO2/t"),
                Expect("cbam_factor_2027", "CBAM factor 2027 (refdata)", D("0.95"), D("0"), "-"),
            ),
            _g3,
        ),
        GoldenCase(
            "G4",
            "Example 1 - certificates for 10,000 t of rails, 2027",
            f"{GUIDANCE}, s.4.1, p. 44",
            {"mass": "10,000 t", "SEE": "1.539 direct + 0.028 indirect (sintered-ore precursor)", "SEFA_2027": "1.198"},
            (
                Expect("ee", "Embedded emissions", D("15670"), D("1"), "t CO2"),
                Expect("faa", "Free allocation adjustment", D("11980"), D("1"), "t CO2"),
                Expect("certificates", "Certificates", D("3690"), D("1"), "certificates"),
            ),
            _g4,
        ),
        GoldenCase(
            "G5",
            "Example 2 - certificates for 100 t of stainless pipes, 2027",
            f"{GUIDANCE}, s.4.2, Table 4-11 and p. 51",
            {"mass": "100 t", "SEE": "1.783", "SEFA": "0.057 + 1.083 x 0.748", "year": "2027"},
            (
                Expect("sefa", "SEFA pipes", D("0.867"), TOL, "t CO2/t"),
                Expect("faa", "Free allocation adjustment", D("82.4"), D("0.1"), "t CO2"),
                Expect("certificates", "Certificates", D("95.9"), D("0.1"), "certificates"),
            ),
            _g5,
        ),
        GoldenCase(
            "G6",
            "Example 1 - SEFA of sheets and bars",
            f"{GUIDANCE}, s.4.1, Table 4-6, p. 43",
            {"sheets": "0.044 + 1.042 x 1.156", "bars": "0.038 + 1.042 x 1.156"},
            (
                Expect("sheets", "SEFA sheets", D("1.248"), TOL, "t CO2/t"),
                Expect("bars", "SEFA bars", D("1.242"), TOL, "t CO2/t"),
            ),
            _g6,
        ),
        GoldenCase(
            "G7",
            "Example 3 - SEFA of screws and nuts (additional)",
            f"{GUIDANCE}, s.4.3, Table 4-14, p. 54",
            {"carbon": "0.038 + 1.176 x 1.242", "stainless": "0.038 + 1.220 x 0.919"},
            (
                Expect("carbon", "SEFA carbon-steel screws", D("1.499"), TOL, "t CO2/t"),
                Expect("stainless", "SEFA stainless screws", D("1.159"), TOL, "t CO2/t"),
            ),
            _g7,
        ),
        GoldenCase(
            "G8",
            "Refdata cross-check - benchmarks and gas factor used in Examples 1 and 3 (additional)",
            "Benchmarks Excel (Reg. 2025/2620, 13 Feb 2026) and Methodology Act Annex II s.G (Guidance 3 Annex D, p. 139)",
            {"lookup": "official files parsed by build_refdata.py"},
            (
                Expect("bm_rails_a", "BM col. A rails 7302 10 50", D("0.057"), D("0"), "t CO2/t"),
                Expect("bm_bars_a", "BM col. A bars 7213 91 49", D("0.038"), D("0"), "t CO2/t"),
                Expect("bm_screws_a", "BM col. A screws 7318 12 90", D("0.038"), D("0"), "t CO2/t"),
                Expect("bm_screws_b", "BM col. B screws (C)", D("1.364"), D("0"), "t CO2/t"),
                Expect("bm_stainless_screws_b", "BM col. B stainless screws (1)", D("1.154"), D("0"), "t CO2/t"),
                Expect("ng_ef", "Natural gas EF", D("56.1"), D("0"), "t CO2/TJ"),
            ),
            _g8,
        ),
    ]
}


def run_all() -> dict[str, object]:
    results = [c.run() for c in CASES.values()]
    return {"guidance": GUIDANCE, "all_pass": all(r["pass"] for r in results), "cases": results}
