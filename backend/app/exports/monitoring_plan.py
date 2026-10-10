"""S3 / USP 6: draft Monitoring Plan built on the minimum elements of Annex II section A.5 of
the Methodology Act (reproduced in EC Guidance No. 3, Table 4-4, pp. 49-51).

Clearly marked "DRAFT for verifier review". Elements that do not apply to a cold-forming
fastener plant are kept and marked not applicable with the reason (completeness).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.cbam.tree import q
from app.evidence.models import Document, Project

TITLES = {
    "en": [
        "Date and version number of the MP",
        "Description of the installation and production processes",
        "Goods produced by CN code and functional unit, incl. precursors",
        "CBAM production processes and routes; goods per process",
        "Non-CBAM goods per production process",
        "Relevant CBAM benchmarks for the free allocation adjustment",
        "Monitoring methods per production process (calculation-based)",
        "Calculation factors and sampling plan",
        "Source streams and emission sources per process",
        "Source streams under the standard / mass-balance method",
        "Emission sources under measurement-based methodology",
        "PFC monitoring (primary aluminium)",
        "Diagram, system boundaries, no double counting or gaps",
        "Precursors per process; supplier name and country",
        "Zero-rated fuels",
        "Measurable heat imported or exported",
        "Electricity produced inside the installation",
        "Evidence for actual indirect emissions",
        "Electricity imported as a good",
        "Waste gases",
        "CO2 capture, storage or use",
        "Control system for data quality",
    ],
    "hi": [
        "MP की तिथि और संस्करण संख्या",
        "संयंत्र और उत्पादन प्रक्रियाओं का विवरण",
        "CN code और functional unit अनुसार उत्पादित माल, precursors सहित",
        "CBAM उत्पादन प्रक्रियाएँ और मार्ग; प्रत्येक प्रक्रिया का माल",
        "प्रत्येक प्रक्रिया के non-CBAM माल",
        "free allocation adjustment हेतु संबंधित CBAM benchmarks",
        "प्रत्येक प्रक्रिया की निगरानी विधि (calculation-based)",
        "calculation factors और sampling plan",
        "प्रत्येक प्रक्रिया के source streams और emission sources",
        "standard / mass-balance विधि वाले source streams",
        "measurement-based विधि वाले emission sources",
        "PFC निगरानी (primary aluminium)",
        "आरेख, system boundaries, दोहरी गणना या कमी नहीं",
        "प्रत्येक प्रक्रिया के precursors; आपूर्तिकर्ता का नाम और देश",
        "zero-rated ईंधन",
        "measurable heat का आयात या निर्यात",
        "संयंत्र में उत्पादित बिजली",
        "वास्तविक indirect emissions के साक्ष्य",
        "माल के रूप में आयातित बिजली",
        "waste gases",
        "CO2 capture, storage या use",
        "डेटा गुणवत्ता हेतु control system",
    ],
}
NA = {"en": "Not applicable", "hi": "लागू नहीं"}


def build(project: Project, result: dict[str, Any], documents: list[Document], lang: str = "en") -> dict[str, Any]:
    lang = "hi" if lang == "hi" else "en"
    procs = result["processes"]
    hi = lang == "hi"
    na = NA[lang]
    goods = "; ".join(f"{p['id']}: {p['name']} — CN {p['cn_display']} ({p.get('cn_desc', '')}); functional unit: tonne" for p in procs)
    bms = "; ".join(
        f"CN {p['cn_display']}: column A {result['calc_tree'][f'ref.bmA.{p["cn"]}']['display']} t CO2/t (Reg. 2025/2620)" for p in procs
    )
    precs = "; ".join(
        f"{p['id']}: {p['precursor']['name']} (CN {p['precursor']['cn_display']}) from {p['precursor']['supplier']}, India — "
        + ("verified actual data" if p["precursor"]["data"] == "ACTUAL_VERIFIED" else "default value until verified data is received")
        for p in procs
    )
    passed = sum(1 for c in result.get("checks", []) if c["status"] == "pass")
    n_checks = len(result.get("checks", []))
    gas_doc = sum(1 for d in documents if d.doc_type == "gas_invoice")
    body = [
        f"Version 0.1 (DRAFT), generated {result['computed_at'][:10]} by Pramaan from the evidence of {project.period_label}.",
        (
            f"{project.company}, {project.city}. Cold heading, thread rolling and gas-fired heat treatment of purchased wire rod into bolts. "
            f"Two production processes, one per CN group (Guidance 5d, Example 3 approach)."
        ),
        goods,
        "; ".join(f"{p['id']}: wire rod → cold heading → threading → heat treatment (natural gas) → {p['name']}" for p in procs),
        "None reported. Cut-offs and turnings are scrap (zero embedded emissions) and are sold to a dealer.",
        bms,
        (
            "a) Calculation-based: AttrEm = Σ AD × NCV × EF × OxF for natural gas; SEE = AttrEm/AL + Σ m_i × SEE_i. "
            "AD from monthly PNG invoices (MMBtu, GCV basis) converted with 1.055056 GJ/MMBtu and NCV/GCV 0.9 (stated assumptions). "
            "AL from the production register; precursor mass from the register, reconciled with purchase invoices and stock. "
            "b) Measuring instruments: utility gas meter (custody transfer, read by the supplier); in-house weighbridge for rod and products."
        ),
        "Standard factors from Methodology Act Annex II section G (natural gas EF 56.1 t CO2/TJ, IPCC 2006). No sampling: commercial fuel.",
        f"Source stream: natural gas (piped), {gas_doc} monthly invoices in the period. Emission sources: heat-treatment furnaces. No process emissions.",
        "Natural gas — calculation-based standard method (Methodology Act Annex II point B.3.4); commercial standard fuel, quantities from supplier invoices.",
        na + " — no continuous emission measurement.",
        na + " — no aluminium production.",
        "System boundary: bolt shop (receipt of rod to dispatch). Gas attributed to processes by tonnes produced (equal specific consumption, Guidance 5d Table 4-12). Mass balance: rod − scrap = product.",
        precs,
        na + " — no biomass fuels.",
        na + " — no measurable heat imported or exported.",
        "No on-site generation. Grid electricity is recorded (monthly bills) but excluded: iron and steel goods count direct emissions only.",
        na + " — indirect emissions not relevant for iron and steel goods.",
        na + ".",
        na + " — no waste gases.",
        na + ".",
        (
            f"Two-reader check on every value (Gemini extraction + blind second reader on the crop), human approval of disagreements with user and time stamp, "
            f"{passed}/{n_checks} automated control checks (mass balance, stock reconciliation, invoice consistency, exports ≤ production), "
            "versioned reference data with SHA-256 manifest, run logs kept as receipts. Calibration: utility meter certificates on file; weighbridge annual calibration (to be attached)."
        ),
    ]
    if hi:
        body[0] = f"संस्करण 0.1 (ड्राफ्ट), {result['computed_at'][:10]} को Pramaan द्वारा {project.period_label} के साक्ष्यों से तैयार।"
        body[4] = "कोई नहीं। कटिंग/टर्निंग स्क्रैप के embedded emissions शून्य हैं; स्क्रैप डीलर को बेचा जाता है।"
        body[16] = "संयंत्र में बिजली उत्पादन नहीं। ग्रिड बिजली दर्ज की जाती है पर गिनी नहीं जाती: लोहा/इस्पात में केवल direct emissions गिने जाते हैं।"
    elements = [{"no": i + 1, "title": TITLES[lang][i], "content": body[i], "applicable": not body[i].startswith(na)} for i in range(22)]
    see = "; ".join(f"{p['id']} SEE {q(Decimal(p['see']), 3)} t CO2/t" for p in procs)
    return {
        "title": "Draft Monitoring Plan — " + project.company if not hi else "ड्राफ्ट निगरानी योजना (Monitoring Plan) — " + project.company,
        "status": "DRAFT for verifier review" if not hi else "ड्राफ्ट — verifier की समीक्षा हेतु",
        "basis": "Methodology Act (Reg. (EU) 2025/2547) Annex II section A.5; EC Guidance No. 3, Table 4-4, pp. 49-51",
        "summary": see,
        "elements": elements,
        "lang": lang,
    }
