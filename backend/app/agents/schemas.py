"""Per-document-type extraction schemas (what the Extractor must find, with units)."""

from __future__ import annotations

from typing import Any

# field_key -> (description, expected unit, scope) ; scope: "doc" | "period" | "process" | "process_period" | "line"
FIELDS: dict[str, dict[str, tuple[str, str, str]]] = {
    "gas_invoice": {
        "invoice_no": ("Bill / invoice number", "", "doc"),
        "bill_date": ("Bill date (DD-MM-YYYY)", "", "doc"),
        "period_start": ("Billing period start date", "", "period"),
        "period_end": ("Billing period end date", "", "period"),
        "scm": ("Gas consumption in standard cubic metres", "SCM", "period"),
        "gcv_kcal_per_scm": ("Gross calorific value", "kcal/SCM", "period"),
        "mmbtu": ("Gas energy billed in MMBtu (GCV basis)", "MMBtu", "period"),
    },
    "electricity_bill": {
        "invoice_no": ("Bill number", "", "doc"),
        "period_start": ("Billing period start", "", "period"),
        "period_end": ("Billing period end", "", "period"),
        "kwh": ("Electricity consumed (kWh)", "kWh", "period"),
        "md_kva": ("Maximum demand (kVA)", "kVA", "period"),
    },
    "precursor_invoice": {
        "supplier": ("Seller / supplier name", "", "doc"),
        "invoice_no": ("Invoice number", "", "doc"),
        "invoice_date": ("Invoice date", "", "doc"),
        "cn_code": ("HSN / CN code of the goods", "", "process"),
        "grade": ("Steel grade and size exactly as printed (e.g. 'IS 2062 E250, 5.5 mm')", "", "doc"),
        "tonnes": ("Quantity purchased in metric tonnes", "t", "process"),
        "mn_pct": ("Manganese mass %", "%", "process"),
        "cr_pct": ("Chromium mass %", "%", "process"),
        "ni_pct": ("Nickel mass %", "%", "process"),
        "other_alloy_pct": ("Total other alloy elements mass %", "%", "process"),
    },
    "supplier_emissions_statement": {
        "supplier": ("Issuing supplier", "", "doc"),
        "doc_no": ("Document reference", "", "doc"),
        "product_cn": ("CN code of the product", "", "process"),
        "period": ("Reporting period covered", "", "process"),
        "route": ("Production route", "", "process"),
        "see": ("Specific embedded emissions (SEE)", "t CO2e/t", "process"),
        "sefa": ("Specific free allocation (SEFA, actual)", "t CO2e/t", "process"),
        "reducing_agent": ("Main reducing agent", "", "process"),
        "scrap_per_t": ("Scrap used per t crude steel", "t/t", "process"),
        "pre_consumer_pct": ("Share of pre-consumer scrap", "%", "process"),
        "verifier": ("Verifier name", "", "process"),
        "verification_ref": ("Verification report number", "", "process"),
        "opinion": ("Verification opinion", "", "process"),
    },
    "production_register": {
        "produced_t": ("Tonnes of product produced in the month (one per month and product)", "t", "process_period"),
        "rod_consumed_t": ("Tonnes of wire rod consumed in the month (one per month and rod type)", "t", "process_period"),
        "opening_stock_t": ("Opening rod stock", "t", "process_period"),
        "closing_stock_t": ("Closing rod stock", "t", "process_period"),
    },
    "scrap_log": {
        "scrap_t": ("Tonnes of scrap / cut-offs in the month (one per month and steel type)", "t", "process_period"),
    },
    "export_invoice": {
        "invoice_no": ("Invoice number", "", "doc"),
        "invoice_date": ("Invoice date", "", "doc"),
        "buyer": ("Consignee / buyer name", "", "doc"),
        "country_of_origin": ("Country of origin", "", "doc"),
        "cn_code": ("CN / HS code per line item", "", "line"),
        "net_mass_kg": ("Net weight per line item in kg", "kg", "line"),
    },
    "fuel_invoice": {
        "invoice_no": ("Invoice number", "", "doc"),
        "fuel": ("Fuel type", "", "doc"),
        "quantity": ("Quantity", "", "period"),
    },
    "other": {},
}

# Fields whose value enters the SEE calculation (used for readiness and two-reader priority)
SEE_RELEVANT = {"mmbtu", "produced_t", "rod_consumed_t", "see", "sefa", "net_mass_kg", "scm", "gcv_kcal_per_scm", "verification_ref"}

NUMERIC_UNITS = {"t", "kg", "SCM", "kcal/SCM", "MMBtu", "kWh", "kVA", "%", "t CO2e/t", "t/t"}


def extraction_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "fields": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "field_key": {"type": "string"},
                        "value_text": {"type": "string", "description": "exactly as written on the document"},
                        "value_num": {
                            "type": "string",
                            "description": "plain decimal number with '.' as decimal separator, no thousands separators; empty if not numeric",
                        },
                        "unit": {"type": "string"},
                        "box_2d": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "[ymin, xmin, ymax, xmax] normalised to 0-1000 around the value only",
                        },
                        "label": {"type": "string"},
                        "period": {"type": "string", "description": "YYYY-MM for monthly values, YYYY-Qn for quarters, empty otherwise"},
                        "process": {
                            "type": "string",
                            "description": "product line id (P1, P2, ...) when the value belongs to one line, else empty",
                        },
                    },
                    "required": ["field_key", "value_text", "box_2d"],
                },
            }
        },
        "required": ["fields"],
    }


CLASSIFY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "doc_type": {"type": "string", "enum": list(FIELDS.keys())},
        "languages": {"type": "array", "items": {"type": "string"}, "description": "ISO 639-1 codes of scripts/languages present"},
        "period_start": {"type": "string", "description": "YYYY-MM-DD or empty"},
        "period_end": {"type": "string", "description": "YYYY-MM-DD or empty"},
        "title": {"type": "string", "description": "short human title, e.g. 'Gas invoice March 2026'"},
        "confidence": {"type": "number"},
    },
    "required": ["doc_type", "languages", "confidence", "title"],
}

SECOND_READ_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "value_text": {
            "type": "string",
            "description": "the final value as written; if a value is crossed out, give the value that replaces it",
        },
        "value_num": {"type": "string", "description": "plain decimal number, '.' separator, no grouping; empty if not numeric"},
        "unit": {"type": "string"},
        "legible": {"type": "boolean"},
        "crossed_out": {
            "type": "string",
            "description": "a crossed-out or overwritten figure visible in the crop, if any; empty otherwise",
        },
        "note": {"type": "string"},
    },
    "required": ["value_text", "legible"],
}
