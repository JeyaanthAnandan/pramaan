"""Shivalik Fasteners Pvt Ltd (SAMPLE - fictional): single source of truth for the demo.

Every synthetic document and its ground truth is generated from these numbers. Ratios mirror
EC Guidance 5d Example 3 at reduced scale (rod/product 20/17 and 750/615; natural gas
3.5 GJ NCV per tonne), so the sample SEE equals golden tests G1/G2 and judges can check them.
All names are fictional. No real company, logo or utility branding is used.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

D = Decimal
MONTHS = ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]
MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September"]
MONTH_DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30]

COMPANY = {
    "name": "Shivalik Fasteners Pvt Ltd (SAMPLE - fictional)",
    "short": "Shivalik Fasteners (SAMPLE)",
    "address": "Plot 214-B, Phase VIII, Focal Point, Ludhiana, Punjab 141010, India",
    "gstin": "03SAMPLE0000F1Z0",
    "iec": "SAMPLE-IEC-0000",
    "country": "India",
}
BUYER = {
    "name": "Rhein Befestigungstechnik GmbH (SAMPLE)",
    "address": "Hafenstrasse 12, 47119 Duisburg, Germany (fictional)",
    "eori": "DE-SAMPLE-000000",
}
GAS_SUPPLIER = {"name": "Doaba City Gas (SAMPLE)", "address": "Ferozepur Road, Ludhiana (fictional)"}
POWER_SUPPLIER = {"name": "Sutlej Power (SAMPLE)", "address": "Division Office, Focal Point, Ludhiana (fictional)"}
ROD_SUPPLIERS = {
    "NWRM": {
        "name": "Northern Wire Rod Mills (SAMPLE)",
        "address": "GT Road, Mandi Gobindgarh, Punjab (fictional)",
        "country": "India",
    },
    "ISR": {
        "name": "Indus Stainless Rods (SAMPLE)",
        "address": "Industrial Area, Jagadhri, Haryana (fictional)",
        "country": "India",
    },
}
VERIFIER = {"name": "Kestrel Assurance (SAMPLE - fictional verifier)", "accreditation": "SAMPLE-ACC-0000"}

PROCESSES = {
    "P1": {
        "name": "Carbon-steel hexagon bolts",
        "cn": "73181582",
        "cn_display": "7318 15 82",
        "cn_desc": "Hexagon screws and bolts, of iron or steel other than stainless",
        "rod_supplier": "NWRM",
        "rod_cn": "72139149",
        "rod_cn_display": "7213 91 49",
        "rod_grade": "SAE 1018, 10.0 mm",
        "composition": {"mn": "0.75", "cr": "0.03", "ni": "0.02", "other": "0.25"},
    },
    "P2": {
        "name": "Stainless hexagon bolts (A2/304)",
        "cn": "73181575",
        "cn_display": "7318 15 75",
        "cn_desc": "Hexagon screws and bolts, of stainless steel",
        "rod_supplier": "ISR",
        "rod_cn": "72210010",
        "rod_cn_display": "7221 00 10",
        "rod_grade": "AISI 304, 8.0 mm",
        "composition": {"mn": "1.60", "cr": "18.20", "ni": "8.10", "other": "0.85"},
    },
}

# ------------------------------------------------------------------ production (t)
PRODUCED = {
    "P1": [D(x) for x in ["135", "140", "150", "138", "145", "142", "140", "145", "140"]],  # 1,275 t
    "P2": [D(x) for x in ["65", "70", "68", "66", "72", "70", "68", "66", "70"]],  # 615 t
}
ROD_TOTAL = {"P1": D("1500"), "P2": D("750")}  # consumed; scrap 225 / 135
OPENING_STOCK = {"P1": D("40.0"), "P2": D("10.0")}
CLOSING_STOCK = {"P1": D("60.0"), "P2": D("30.0")}


def _r1(x: Decimal) -> Decimal:
    return x.quantize(D("0.1"), rounding=ROUND_HALF_UP)


def rod_consumed(p: str) -> list[Decimal]:
    al = sum(PRODUCED[p])
    vals = [_r1(m * ROD_TOTAL[p] / al) for m in PRODUCED[p]]
    vals[-1] = ROD_TOTAL[p] - sum(vals[:-1])  # close the balance exactly
    return vals


def scrap(p: str) -> list[Decimal]:
    return [c - m for c, m in zip(rod_consumed(p), PRODUCED[p], strict=True)]


# ------------------------------------------------------------------ natural gas
GAS_SEC_GJ_NCV_PER_T = D("3.5")  # EC Example 3, Table 4-12
NCV_GCV = D("0.9")  # assumption (IPCC 2006 Vol.2 Ch.1), mirrored in backend/refdata/assumptions.json
KJ_PER_KCAL = D("4.1868")
GJ_PER_MMBTU = D("1.055056")
GCV_KCAL_PER_SCM = [D(x) for x in ["9520", "9480", "9555", "9500", "9610", "9470", "9530", "9495", "9560"]]
GAS_RATE_INR_PER_SCM = [D(x) for x in ["51.80", "51.80", "52.40", "52.40", "52.40", "53.10", "53.10", "53.10", "53.60"]]


# Heat-treatment gas per tonne moves month to month around EC Example 3's 3.5 GJ/t (June runs hot,
# April is the best month), as a real furnace does. The period's gas stays exactly the same (the last
# month absorbs the difference to the meter), so SEE 2.0399 and every golden number are unchanged.
# January and March, the bills in the screenshots, keep their figures.
GAS_INTENSITY = [D(x) for x in ["1.000", "0.975", "1.000", "0.930", "0.965", "1.165", "1.020", "0.960"]]  # + September: balancing


def _scm_mmbtu(gj_ncv: Decimal, gcv: Decimal) -> tuple[Decimal, Decimal]:
    scm = (gj_ncv / NCV_GCV * D(1_000_000) / (gcv * KJ_PER_KCAL)).quantize(D(1), rounding=ROUND_HALF_UP)
    return scm, _mmbtu(scm, gcv)


def _mmbtu(scm: Decimal, gcv: Decimal) -> Decimal:
    return (scm * gcv * KJ_PER_KCAL / D(1_000_000) / GJ_PER_MMBTU).quantize(D("0.001"), rounding=ROUND_HALF_UP)


def _tonnes(i: int) -> Decimal:
    return PRODUCED["P1"][i] + PRODUCED["P2"][i]


def gas_month(i: int) -> dict[str, Decimal]:
    gcv = GCV_KCAL_PER_SCM[i]
    last = len(GCV_KCAL_PER_SCM) - 1
    if i < last:
        scm, mmbtu = _scm_mmbtu(GAS_SEC_GJ_NCV_PER_T * GAS_INTENSITY[i] * _tonnes(i), gcv)
    else:  # September: whatever keeps the period's gas (MMBtu) where EC Example 3's 3.5 GJ/t puts it
        flat = sum(_scm_mmbtu(GAS_SEC_GJ_NCV_PER_T * _tonnes(k), GCV_KCAL_PER_SCM[k])[1] for k in range(last + 1))
        target = flat - sum(gas_month(k)["mmbtu"] for k in range(last))
        guess = target * GJ_PER_MMBTU * D(1_000_000) / (gcv * KJ_PER_KCAL)
        scm = min((guess.to_integral_value(rounding="ROUND_FLOOR") + d for d in (0, 1)), key=lambda x: abs(_mmbtu(x, gcv) - target))
        mmbtu = _mmbtu(scm, gcv)
    amount = (scm * GAS_RATE_INR_PER_SCM[i]).quantize(D("0.01"), rounding=ROUND_HALF_UP)
    return {"scm": scm, "gcv": gcv, "mmbtu": mmbtu, "rate": GAS_RATE_INR_PER_SCM[i], "amount": amount}


# ------------------------------------------------------------------ electricity (recorded, excluded from SEE)
ELECTRICITY = [
    {"month": "2026-07", "kwh": D("84250"), "md_kva": D("412"), "amount": D("693410.00")},
    {"month": "2026-08", "kwh": D("86910"), "md_kva": D("418"), "amount": D("715270.00")},
    {"month": "2026-09", "kwh": D("83120"), "md_kva": D("409"), "amount": D("684100.00")},
]

# ------------------------------------------------------------------ rod purchases
ROD_INVOICES = [
    {"id": "NWRM/26/0112", "supplier": "NWRM", "process": "P1", "date": "2026-01-06", "tonnes": D("760.000"), "rate": D("58400")},
    {"id": "NWRM/26/0583", "supplier": "NWRM", "process": "P1", "date": "2026-05-04", "tonnes": D("760.000"), "rate": D("57900")},
    {"id": "ISR/2026/038", "supplier": "ISR", "process": "P2", "date": "2026-02-04", "tonnes": D("380.000"), "rate": D("214500")},
    {"id": "ISR/2026/119", "supplier": "ISR", "process": "P2", "date": "2026-06-08", "tonnes": D("390.000"), "rate": D("211800")},
]

# Verified supplier communication (P1 rod only). Values mirror EC Example 1 (bars and rods).
SUPPLIER_STATEMENT = {
    "supplier": "NWRM",
    "doc_no": "NWRM-CBAM-2026-07",
    "period": "01-01-2026 to 30-09-2026",
    "product_cn": "72139149",
    "see": D("1.567"),
    "sefa": D("1.242"),
    "route": "BF-BOF (C)",
    "reducing_agent": "Coke (blast furnace)",
    "scrap_per_t": D("0.12"),
    "pre_consumer_pct": D("35"),
    "verification_ref": "KA-VR-2026-0147",
    "verification_date": "2026-10-02",
    "opinion": "Reasonable assurance - verified without material misstatement",
    "carbon_price_paid": "None",
}
# What-if: stainless rod supplier sends verified data (values of EC Example 2 / Table 4-14)
WHAT_IF_ISR = {"see": D("1.783"), "sefa": D("0.919"), "source": "EC Guidance 5d Example 2 (SEE) and Table 4-14 (SEFA 0.919), illustrative"}

# ------------------------------------------------------------------ exports to the EU buyer
EXPORTS = [
    {"id": "SF/EXP/2526/041", "date": "2026-03-12", "quarter": "2026-Q1", "lines": {"P1": D("280000"), "P2": D("120000")}},
    {"id": "SF/EXP/2627/009", "date": "2026-06-15", "quarter": "2026-Q2", "lines": {"P1": D("300000"), "P2": D("130000")}},
    {"id": "SF/EXP/2627/022", "date": "2026-09-10", "quarter": "2026-Q3", "lines": {"P1": D("320000"), "P2": D("150000")}},
]  # net mass in kg (P1 900 t, P2 400 t)


def summary() -> dict[str, object]:
    gas = [gas_month(i) for i in range(len(MONTHS))]
    mmbtu = sum(g["mmbtu"] for g in gas)
    return {
        "al": {p: sum(v) for p, v in PRODUCED.items()},
        "rod": {p: sum(rod_consumed(p)) for p in PROCESSES},
        "scrap": {p: sum(scrap(p)) for p in PROCESSES},
        "gas_mmbtu": mmbtu,
        "gas_gj_ncv": mmbtu * GJ_PER_MMBTU * NCV_GCV,
        "exports_t": {p: sum(e["lines"][p] for e in EXPORTS) / 1000 for p in PROCESSES},
    }


if __name__ == "__main__":
    import json

    print(json.dumps(summary(), indent=1, default=str))
