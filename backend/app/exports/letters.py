"""M8 Precursor Lever: supplier data request letter (English + Hindi).

Only facts from the calculation result are used (share of the precursor in SEE, the default
value applied, the buyer's cost on defaults). Nothing is hypothetical in the letter.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.cbam.tree import q
from app.evidence.models import ProcessDef, Project


def _facts(project: Project, proc: ProcessDef, result: dict[str, Any]) -> dict[str, str]:
    p = next(x for x in result["processes"] if x["id"] == proc.id)
    tree = result["calc_tree"]
    see = Decimal(p["see"])
    contrib = Decimal(tree[f"{proc.id}.rod.contrib"]["value"])
    share = (contrib / see * 100).quantize(Decimal("1"))
    pre = p["precursor"]
    mass = tree[f"{proc.id}.rod.mass"]["value"]
    s2026 = result["money"]["series"][proc.id][0]
    return {
        "company": project.company,
        "city": project.city,
        "supplier": proc.precursor_supplier,
        "precursor": proc.precursor_name,
        "precursor_cn": pre["cn_display"],
        "product": proc.name,
        "product_cn": proc.cn_display,
        "tonnes": q(Decimal(mass), 0) or "",
        "share": str(share),
        "default_value": q(Decimal(pre["default_value"]), 3) or "",
        "default_with_markup": q(Decimal(pre["see"]), 3) or "",
        "data_status": pre["data"],
        "cost_actual": q(Decimal(s2026["actual_eur_t"]), 0) or "",
        "cost_default": q(Decimal(s2026["default_eur_t"]), 0) or "",
        "period": project.period_label,
    }


EN = """Subject: Request for verified CBAM embedded-emissions data — {precursor} (CN {precursor_cn})

Dear {supplier} team,

We buy {precursor} from you ({tonnes} t consumed in {period}) to manufacture {product} (CN {product_cn}), which we export to the European Union.

Since 1 January 2026 the EU Carbon Border Adjustment Mechanism (CBAM) is in its definitive phase: our EU buyer must declare the emissions embedded in our goods and buy CBAM certificates for them. Your rod accounts for about {share}% of the embedded emissions of our bolts.

Because we do not yet have your verified data, we must use the EU default value for India: {default_value} t CO2e per tonne of rod, increased by the 2026 mark-up to {default_with_markup} t CO2e/t. On this basis our buyer currently faces about EUR {cost_actual} per tonne of bolts with our data, against EUR {cost_default} per tonne on full EU default values. Verified data from you would replace the default.

Could you please send us, for the rod delivered to us in 2026:
1. The specific embedded emissions (SEE) of the rod in t CO2e/t and the production route (for example BF-BOF or scrap-EAF).
2. The verification report of an accredited verifier covering the production period of the rod.
3. The actual specific free allocation (SEFA) value of the rod.
4. Any carbon price effectively paid in India for these emissions.
5. The extra parameters for iron or steel (EC Guidance No. 5d, Table 3-1): main reducing agent; mass % of Mn, Cr, Ni and total other alloy elements; tonnes of scrap used per tonne of crude steel; share of pre-consumer scrap.

The Commission's template for the operator's emissions report, or a signed statement with the same items, is fine. A reply by 15 November 2026 would let our buyer prepare the first CBAM declaration, due by 30 September 2027 for 2026 imports.

We will use your data only for CBAM reporting. Our EU buyer receives only the aggregated SEE of our goods, never your installation data.

With regards,
{company}
{city}
"""

HI = """विषय: सत्यापित CBAM embedded-emissions डेटा का अनुरोध — {precursor} (CN {precursor_cn})

आदरणीय {supplier} टीम,

हम आपसे {precursor} खरीदते हैं ({period} में {tonnes} टन उपयोग) और इससे {product} (CN {product_cn}) बनाकर यूरोपीय संघ (EU) को निर्यात करते हैं।

1 जनवरी 2026 से EU का Carbon Border Adjustment Mechanism (CBAM) अपने definitive चरण में है: हमारे EU खरीदार को हमारे माल में निहित उत्सर्जन (embedded emissions) घोषित करने होते हैं और उनके लिए CBAM certificates खरीदने होते हैं। हमारे बोल्ट के embedded emissions में आपकी रॉड का हिस्सा लगभग {share}% है।

आपका सत्यापित डेटा अभी हमारे पास नहीं है, इसलिए हमें भारत के लिए EU default value लेनी पड़ रही है: रॉड के प्रति टन {default_value} t CO2e, जो 2026 के mark-up के साथ {default_with_markup} t CO2e/t हो जाती है। इस आधार पर हमारे खरीदार की लागत हमारे डेटा के साथ लगभग EUR {cost_actual} प्रति टन बोल्ट है, जबकि पूरी तरह EU default values पर EUR {cost_default} प्रति टन। आपका सत्यापित डेटा default value की जगह लेगा।

कृपया 2026 में हमें भेजी गई रॉड के लिए निम्न जानकारी भेजें:
1. रॉड के specific embedded emissions (SEE), t CO2e/t में, और उत्पादन मार्ग (जैसे BF-BOF या scrap-EAF)।
2. रॉड की उत्पादन अवधि को कवर करने वाली मान्यता-प्राप्त (accredited) verifier की verification report।
3. रॉड का वास्तविक specific free allocation (SEFA) मान।
4. इन उत्सर्जनों पर भारत में वास्तव में चुकाया गया कोई carbon price, यदि हो।
5. लोहा/इस्पात के अतिरिक्त पैरामीटर (EC Guidance No. 5d, Table 3-1): मुख्य reducing agent; Mn, Cr, Ni और अन्य alloy तत्वों का mass %; प्रति टन crude steel में प्रयुक्त scrap (टन); pre-consumer scrap का हिस्सा।

Commission का operator's emissions report template, या इन्हीं बिंदुओं वाला हस्ताक्षरित वक्तव्य, दोनों स्वीकार्य हैं। 15 नवंबर 2026 तक उत्तर मिलने पर हमारा खरीदार 2026 के आयात की पहली CBAM declaration (30 सितंबर 2027 तक देय) तैयार कर पाएगा।

आपका डेटा केवल CBAM रिपोर्टिंग के लिए उपयोग होगा। हमारे EU खरीदार को केवल हमारे माल का कुल SEE मिलेगा, आपके संयंत्र का डेटा कभी नहीं।

सादर,
{company}
{city}
"""


def supplier_letter(project: Project, proc: ProcessDef, result: dict[str, Any], lang: str = "en") -> dict[str, Any]:
    f = _facts(project, proc, result)
    return {
        "process_id": proc.id,
        "supplier": proc.precursor_supplier,
        "lang": "hi" if lang == "hi" else "en",
        "text": (HI if lang == "hi" else EN).format(**f),
        "facts": f,
        "requested_items": [
            "SEE + production route",
            "verification report",
            "actual SEFA",
            "carbon price paid",
            "extra parameters (Guidance 5d Table 3-1)",
        ],
    }
