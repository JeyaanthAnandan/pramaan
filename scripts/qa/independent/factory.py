"""Ground truth of a NEW fictional factory the app has never seen (different region, products, suppliers,
layouts, language, numbers and period from the bundled sample). Every number printed on the documents
comes from here; the expected outputs are computed from here by oracle.py, never by the app."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal as D

COMPANY = "Kaveri Precision Fasteners Pvt Ltd (TEST — fictional)"
ADDRESS = "SIDCO Industrial Estate, Kurichi, Coimbatore 641021, Tamil Nadu, India"
GSTIN = "33AAKCK0000T1Z9 (TEST)"
MONTHS = ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06"]
MONTH_NAMES = ["January", "February", "March", "April", "May", "June"]
MONTH_DAYS = [31, 28, 31, 30, 31, 30]

LINES = {
    "P1": {"name": "Carbon-steel hexagon nuts", "cn": "7318 16 92", "rod": "carbon", "rod_name": "Carbon-steel wire rod", "rod_cn": "7213 91 49"},
    "P2": {"name": "Stainless-steel hexagon nuts", "cn": "7318 16 39", "rod": "stainless", "rod_name": "Stainless-steel wire rod", "rod_cn": "7221 00 10"},
}

# production register (t)
PRODUCED = {"P1": [D("110.0"), D("120.0"), D("130.0"), D("125.0"), D("115.0"), D("120.0")],
            "P2": [D("40.0"), D("45.0"), D("50.0"), D("42.0"), D("48.0"), D("45.0")]}
ROD_CONSUMED = {"carbon": [D("128.0"), D("139.5"), D("151.0"), D("145.0"), D("133.5"), D("139.5")],
                "stainless": [D("45.5"), D("51.0"), D("56.8"), D("47.6"), D("54.4"), D("51.0")]}
STOCK = {"carbon": (D("60.0"), D("73.5")), "stainless": (D("60.0"), D("63.7"))}  # opening 01-01, closing 30-06

# scrap log (t), as written. Deliberate defects: carbon March 26.0 (balance needs 21.0) and May 13.5
# (needs 18.5): totals still close, two months do not. Stainless April is written 5.9, struck out, 5.6.
SCRAP = {"carbon": [D("18.0"), D("19.5"), D("26.0"), D("20.0"), D("13.5"), D("19.5")],
         "stainless": [D("5.5"), D("6.0"), D("6.8"), D("5.6"), D("6.4"), D("6.0")]}
SCRAP_CORRECTION = ("stainless", 3, "5.9")  # (rod, month index, crossed-out figure)

ROD_INVOICES = [
    {"file": "rod-CWR-0187", "supplier": "Cauvery Wire Rods Pvt Ltd (TEST)", "rod": "carbon", "no": "CWR/25-26/0187", "date": "08-01-2026",
     "tonnes": D("450.000"), "rate": D("54650"), "cn": "7213 91 49", "grade": "SAE 1010, 5.5 mm", "heat": "C26-0114",
     "c": "0.09", "mn": "0.42", "si": "0.08", "s": "0.018", "p": "0.016", "cr": "0.03", "ni": "0.02", "cu": "0.06", "other": "0.15"},
    {"file": "rod-CWR-0042", "supplier": "Cauvery Wire Rods Pvt Ltd (TEST)", "rod": "carbon", "no": "CWR/26-27/0042", "date": "06-04-2026",
     "tonnes": D("400.000"), "rate": D("55200"), "cn": "7213 91 49", "grade": "SAE 1010, 5.5 mm", "heat": "C26-0398",
     "c": "0.10", "mn": "0.45", "si": "0.07", "s": "0.016", "p": "0.015", "cr": "0.04", "ni": "0.02", "cu": "0.05", "other": "0.14"},
    {"file": "rod-NSR-1109", "supplier": "Nilgiri Stainless Rods Ltd (TEST)", "rod": "stainless", "no": "NSR/2026/1109", "date": "12-02-2026",
     "tonnes": D("160.000"), "rate": D("198400"), "cn": "7221 00 10", "grade": "AISI 304, 5.5 mm", "heat": "S6-2207",
     "c": "0.05", "mn": "1.62", "si": "0.41", "s": "0.004", "p": "0.031", "cr": "18.12", "ni": "8.05", "cu": "0.38", "other": "0.70"},
    {"file": "rod-NSR-1473", "supplier": "Nilgiri Stainless Rods Ltd (TEST)", "rod": "stainless", "no": "NSR/2026/1473", "date": "11-05-2026",
     "tonnes": D("150.000"), "rate": D("201250"), "cn": "7221 00 10", "grade": "AISI 304, 5.5 mm", "heat": "S6-2561",
     "c": "0.04", "mn": "1.58", "si": "0.39", "s": "0.003", "p": "0.029", "cr": "18.20", "ni": "8.10", "cu": "0.35", "other": "0.68"},
]

# gas: target plant gas per tonne (GJ NCV / t, all products) by month; March runs hot on purpose
SEC_TARGET = [D("3.20"), D("3.15"), D("3.85"), D("3.10"), D("3.25"), D("3.18")]
GCV = [9520, 9495, 9510, 9530, 9488, 9502]  # kcal/SCM
RATE = [D("52.40"), D("52.40"), D("53.15"), D("53.15"), D("54.20"), D("54.20")]  # INR/SCM
METER_START = 2_418_906


def q3(x: D) -> D:
    return x.quantize(D("0.001"), rounding=ROUND_HALF_UP)


def gas_bills() -> list[dict]:
    out, reading = [], METER_START
    for i, m in enumerate(MONTHS):
        total = PRODUCED["P1"][i] + PRODUCED["P2"][i]
        gj_gcv = SEC_TARGET[i] * total / D("0.9")
        scm = int((gj_gcv * D(10) ** 6 / (D(GCV[i]) * D("4.1868"))).to_integral_value(rounding=ROUND_HALF_UP))
        mmbtu = q3(D(scm) * D(GCV[i]) * D("4.1868") / D(10) ** 6 / D("1.055056"))
        amount = (D(scm) * RATE[i]).quantize(D("0.01"))
        out.append({"file": f"gas-{m}", "month": m, "no": f"KCG/CBE/{m[2:4]}{m[5:]}/{70411 + i * 37}", "bill_date": f"0{4 + i % 3}-{int(m[5:]) + 1:02d}-2026" if m != "2026-06" else "05-07-2026",
                    "start": f"01-{m[5:]}-2026", "end": f"{MONTH_DAYS[i]}-{m[5:]}-2026", "prev": reading, "curr": reading + scm, "scm": scm,
                    "gcv": GCV[i], "mmbtu": mmbtu, "rate": RATE[i], "amount": amount, "vat": (amount * D("0.145")).quantize(D("0.01"))})
        reading += scm
    return out


ELECTRICITY = {"file": "elec-2026-03", "no": "TNP/CBE/0326/55821", "start": "01-03-2026", "end": "31-03-2026", "kwh": 41860, "md_kva": 182}

EXPORTS = [
    {"file": "export-2026-Q1", "no": "KPF/EXP/2026/007", "date": "27-03-2026", "quarter": "2026-Q1",
     "lines": [("P1", "Hexagon nuts, carbon steel, ISO 4032 M10, zinc plated", 180000, 183150, 360), ("P2", "Hexagon nuts, stainless steel A2-70, ISO 4032 M8", 70000, 71240, 140)]},
    {"file": "export-2026-Q2", "no": "KPF/EXP/2026/019", "date": "25-06-2026", "quarter": "2026-Q2",
     "lines": [("P1", "Hexagon nuts, carbon steel, ISO 4032 M10, zinc plated", 210000, 213670, 420), ("P2", "Hexagon nuts, stainless steel A2-70, ISO 4032 M8", 85000, 86510, 170)]},
]
BUYER = "Lindqvist Fästelement AB (TEST), Importgatan 14, 417 05 Göteborg, Sweden"

STATEMENT = {"file": "stmt-NSR-2026-H1", "supplier": "Nilgiri Stainless Rods Ltd (TEST)", "doc_no": "NSR-CBAM-2026-H1-031", "cn": "7221 00 10",
             "period": "01-01-2026 to 30-06-2026", "route": "Electric arc furnace + AOD, scrap-based", "see": D("2.150"), "sefa": D("0.880"),
             "reducing_agent": "None (scrap-based EAF)", "scrap_per_t": D("0.96"), "pre_consumer_pct": D("35"),
             "verifier": "Meridian Verification Services GmbH (TEST — fictional verifier)", "verification_ref": "MVS-VR-2026-0412",
             "opinion": "Positive opinion with reasonable assurance"}

# The carbon rod supplier's reply to the request letter, sent through its upload link (a separate test,
# after the first run): verified BF-BOF figures like EC Guidance 5d Example 1.
STATEMENT_CARBON = {"file": "stmt-CWR-2026-H1", "supplier": "Cauvery Wire Rods Pvt Ltd (TEST)", "product": "Carbon-steel wire rod",
                    "works": "Blast furnace, BOF & wire rod mill · Tiruchirappalli (TEST)", "doc_no": "CWR-CBAM-2026-H1-007",
                    "cn": "7213 91 49", "period": "01-01-2026 to 30-06-2026", "route": "Blast furnace + basic oxygen furnace (BF-BOF)",
                    "see": D("1.567"), "sefa": D("1.242"), "reducing_agent": "Coke (blast furnace)", "scrap_per_t": D("0.12"),
                    "pre_consumer_pct": D("40"), "verifier": "Meridian Verification Services GmbH (TEST — fictional verifier)",
                    "verification_ref": "MVS-VR-2026-0533", "opinion": "Positive opinion with reasonable assurance"}
