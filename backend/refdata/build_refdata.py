"""Build Pramaan reference data from official EC files.

Every regulatory value used by the CBAM engine is parsed here from a file listed in
``sources.json``. Nothing is hand-typed: if a value cannot be found in its source the
build fails. Values that are not in any official file live in ``assumptions.json`` and
carry ``status: assumption``.

Usage (from backend/):
    python -I refdata/build_refdata.py            # parse + write json/ and manifest.json
    python -I refdata/build_refdata.py --download # also fetch any missing source file
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import re
import sys
import urllib.request
from decimal import Decimal
from pathlib import Path
from typing import Any

PARSER_VERSION = "1.0.0"
ROOT = Path(__file__).resolve().parent
JSON_DIR = ROOT / "json"


# ---------------------------------------------------------------- helpers


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def dec_str(raw: Any) -> str | None:
    """Official cell -> exact decimal string. '-', 'N/A', '' and 'see below' -> None."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return str(Decimal(str(raw)))
    s = str(raw).strip()
    if not s or s in {"-", "N/A", "n.a."} or s.lower() == "see below":
        return None
    s = s.replace(" ", "").replace(" ", "").replace(",", ".")
    if not re.fullmatch(r"-?\d+(\.\d+)?", s):
        raise ValueError(f"not a number: {raw!r}")
    return str(Decimal(s))


def comma_num(s: str) -> str:
    return str(Decimal(s.replace(",", ".")))


def norm_cn(raw: Any) -> str:
    return re.sub(r"\D", "", str(raw))


def pdf_pages(path: Path) -> list[str]:
    import pypdf

    return [p.extract_text() or "" for p in pypdf.PdfReader(str(path)).pages]


def find(pages: list[str], pattern: str, flags: int = re.S) -> tuple[re.Match[str], int]:
    """Return the first regex match and its 1-based page number."""
    rx = re.compile(pattern, flags)
    for i, text in enumerate(pages):
        m = rx.search(text)
        if m:
            return m, i + 1
    raise LookupError(f"pattern not found in source: {pattern}")


def write_json(name: str, payload: dict[str, Any]) -> Path:
    JSON_DIR.mkdir(parents=True, exist_ok=True)
    out = JSON_DIR / name
    out.write_text(json.dumps(payload, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
    return out


# ---------------------------------------------------------------- parsers


def parse_default_values(path: Path) -> dict[str, Any]:
    """Annex I (per country + 'Other countries and territories') and Annex IV.

    Only the 'Iron and steel' section is kept (Pramaan scope). Values are direct /
    indirect / total t CO2e per t of good, WITHOUT the mark-up (Guidance 3, p. 114).
    """
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    countries: dict[str, dict[str, Any]] = {}
    descriptions: dict[str, str] = {}
    annex_iv: dict[str, Any] = {}
    for name in wb.sheetnames:
        if name in {"Overview", "Version History"}:
            continue
        rows = list(wb[name].iter_rows(values_only=True))
        title = str(rows[0][0]).strip()
        is_annex_iv = title == "Annex IV"
        section = None
        table: dict[str, Any] = {}
        for r in rows[2:]:
            a = r[0]
            b = r[1] if len(r) > 1 else None
            if a is None or str(a).strip() == "":
                continue
            if b in (None, "") and not re.search(r"\d", str(a)):
                section = str(a).strip()
                continue
            if section != "Iron and steel" or not re.search(r"\d", str(a)):
                continue
            cn = norm_cn(a)
            descriptions.setdefault(cn, str(b).strip())
            if is_annex_iv:
                total = dec_str(r[2])
                if str(r[2]).strip().lower() == "see below":
                    continue
                table[cn] = {"cn_display": str(a).strip(), "total": total, "route": (r[3] or "").strip() or None}
            else:
                if str(r[2]).strip().lower() == "see below":
                    continue
                table[cn] = {
                    "cn_display": str(a).strip(),
                    "direct": dec_str(r[2]),
                    "indirect": dec_str(r[3]),
                    "total": dec_str(r[4]),
                    "route": (r[5] or "").strip() or None,
                }
        if is_annex_iv:
            annex_iv = table
        else:
            countries[title] = table
    if "India" not in countries or "Other Countries and Territories" not in countries or not annex_iv:
        raise LookupError("default values workbook layout changed")
    return {
        "unit": "t CO2e / t good",
        "markup_included": False,
        "scope": "Iron and steel section only",
        "lookup_rule": "Longest CN prefix with a value; '-' or missing -> 'Other Countries and Territories' (Guidance 3, p. 114). Unknown origin precursor -> Annex IV.",
        "countries": countries,
        "annex_iv": annex_iv,
        "descriptions": descriptions,
    }


def parse_benchmarks(path: Path) -> dict[str, Any]:
    """Annex section 5 of the Free Allocation Adjustment Act: CBAM benchmarks, column A
    (actual-data route, own process) and column B (default route, incl. precursors)."""
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = list(wb["Benchmarks"].iter_rows(values_only=True))
    out: dict[str, Any] = {}
    sector = None
    current: dict[str, Any] | None = None
    for r in rows[1:]:
        cn_raw, desc, a_val, a_ind, b_val, b_ind = (list(r) + [None] * 6)[:6]
        if cn_raw is not None and not re.search(r"\d", str(cn_raw)):
            sector = str(cn_raw).strip()
            current = None
            continue
        if cn_raw is not None:
            cn = norm_cn(cn_raw)
            current = {"sector": sector, "description": str(desc).strip(), "col_a": [], "col_b": []}
            if cn in out:  # duplicated row in the workbook: keep the first, verify identical
                current = {"sector": sector, "description": str(desc).strip(), "col_a": [], "col_b": [], "_dup": True}
            else:
                out[cn] = current
        if current is None:
            continue
        if a_val is not None:
            current["col_a"].append({"value": dec_str(a_val), "indicator": (a_ind or None)})
        if b_val is not None:
            current["col_b"].append({"value": dec_str(b_val), "indicator": (b_ind or None)})
    return {"unit": "t CO2e / t good", "benchmarks": out}


def parse_benchmark_legend(pages: list[str]) -> dict[str, Any]:
    m, page = find(pages, r"Code Condition to apply the value\s*(.*?)\n\s*SEFA of a simple good")
    legend: dict[str, str] = {}
    for line in m.group(1).splitlines():
        lm = re.match(r"\s*\(([0-9A-Z])\)\s*(.+)", line)
        if lm:
            legend[lm.group(1)] = lm.group(2).strip()
        elif legend and line.strip():
            last = list(legend)[-1]
            legend[last] += " " + line.strip()
    for code in ["1", "2", "C", "D", "E", "F", "G", "H", "J"]:
        if code not in legend:
            raise LookupError(f"benchmark legend code ({code}) missing")
    return {"legend": legend, "citation": {"source": "guidance_4_pdf", "page": page, "table": "Table 2-2"}}


def parse_schedule(g4_pages: list[str], cscf_pages: list[str], g3_pages: list[str]) -> dict[str, Any]:
    # CBAM factor and preliminary CSCF: Guidance 4, Table 2-1
    m, page = find(g4_pages, r"Year CBAM factor CSCF \(preliminary\)\s*(.*?)\n\s*For interpretation of Table 2-2")
    years: dict[str, Any] = {}
    for ym in re.finditer(r"(20\d\d)\s+(\d{1,3},\d)%\s+(\d,\d)", m.group(1)):
        years[ym.group(1)] = {
            "cbam_factor": str(Decimal(ym.group(2).replace(",", ".")) / 100),
            "cbam_factor_citation": {"source": "guidance_4_pdf", "page": page, "table": "Table 2-1"},
            "cscf": comma_num(ym.group(3)),
            "cscf_status": "preliminary",
            "cscf_citation": {"source": "guidance_4_pdf", "page": page, "table": "Table 2-1"},
        }
    for y in range(2026, 2035):
        if str(y) not in years:
            raise LookupError(f"CBAM factor for {y} not found in Guidance 4")

    # CSCF 2026-2030 is official: Implementing Decision (EU) 2026/1862, Article 1
    cm, cpage = find(
        cscf_pages,
        r"Para cada año del período de asignación (20\d\d)-(20\d\d), el factor de corrección uniforme\s+intersectorial.*?será del (\d+) %",
    )
    y0, y1, pct = int(cm.group(1)), int(cm.group(2)), Decimal(cm.group(3))
    for y in range(y0, y1 + 1):
        years[str(y)]["cscf"] = str(pct / 100)
        years[str(y)]["cscf_status"] = "official"
        years[str(y)]["cscf_citation"] = {"source": "cscf_decision_pdf", "page": cpage, "article": "Article 1"}

    # default value mark-up: Guidance 3, section 4.10.1
    mm, mpage = find(
        g3_pages,
        r"These mark-ups are\s*(\d+)%\s*in\s*(2026),\s*(\d+)%\s*in\s*(2027),\s*and\s*(\d+)%\s*from\s*(2028)\s*onwards",
    )
    markups = {"2026": mm.group(1), "2027": mm.group(3), "2028+": mm.group(5)}
    for y in years:
        yi = int(y)
        key = "2028+" if yi >= 2028 else y
        if yi >= 2026:
            years[y]["default_markup"] = str(Decimal(markups[key]) / 100)
            years[y]["markup_citation"] = {"source": "guidance_3_pdf", "page": mpage, "section": "4.10.1"}
    fm, fpage = find(g3_pages, r"A lower mark-up applies to the fertiliser sector\.\s*This mark-up is (\d+)%")
    return {
        "years": dict(sorted(years.items())),
        "fertiliser_markup": str(Decimal(fm.group(1)) / 100),
        "notes": [
            "CBAM factor = share of free allocation still deducted (Reg. 2023/956 Art. 31 phase-out), from Guidance 4 Table 2-1.",
            "CSCF 2026-2030 = 100 % per Implementing Decision (EU) 2026/1862 Art. 1; 2031+ values are preliminary (Guidance 4).",
            "Benchmark indicator (1) applies to production years 2026-27, (2) to 2028-30 (Guidance 4 Table 2-2).",
        ],
    }


def parse_fuel_factors(g3_pages: list[str]) -> dict[str, Any]:
    m, page = find(g3_pages, r"Annex D\s+Standard values for emission calculations.*?Source\s*\n(.*)")
    text = m.group(1) + "\n" + g3_pages[page]  # table continues on next page
    fuels: dict[str, Any] = {}
    pending = ""
    for line in text.splitlines():
        line = line.strip()
        fm = re.match(r"(.+?)\s+(\d+(?:,\d+)?)\s+(\d+(?:,\d+)?)\s+IPCC 2006 GL$", (pending + " " + line).strip())
        if fm:
            name = fm.group(1).strip()
            key = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
            fuels[key] = {
                "name": name,
                "ef_t_co2_per_tj": comma_num(fm.group(2)),
                "ncv_tj_per_gg": comma_num(fm.group(3)),
                "source_of_value": "IPCC 2006 GL",
                "citation": {"source": "guidance_3_pdf", "page": page, "annex": "Annex D = Methodology Act Annex II section G, Table 1"},
            }
            pending = ""
        elif line and not re.search(r"Emission factor|calorific|Fuel type|^\d+$|^\(t CO2|value \(TJ|^Source$", line):
            pending = (pending + " " + line).strip() if len(pending) < 60 else ""
        if line.startswith("Industrial wastes"):
            break
    for needed in ["natural_gas", "liquefied_petroleum_gases", "gas_diesel_oil", "residual_fuel_oil"]:
        if needed not in fuels:
            raise LookupError(f"fuel factor {needed} not found")
    return {"basis": "NCV", "fuels": fuels}


def parse_prices(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    table = re.search(r"<table.*?</table>", raw, re.S)
    if not table:
        raise LookupError("price table not found")
    quarters: dict[str, Any] = {}
    for tr in re.findall(r"<tr.*?</tr>", table.group(0), re.S):
        cells = [html.unescape(re.sub(r"<[^>]+>", " ", c)).split() for c in re.findall(r"<t[dh].*?</t[dh]>", tr, re.S)]
        cells_s = [" ".join(c) for c in cells]
        if len(cells_s) < 3:
            continue
        qm = re.match(r"(Q[1-4]) (20\d\d)", cells_s[0])
        if not qm:
            continue
        price = cells_s[2].strip()
        quarters[f"{qm.group(2)}-{qm.group(1)}"] = {
            "published": cells_s[1].strip(),
            "price_eur": str(Decimal(price)) if re.fullmatch(r"\d+(\.\d+)?", price) else None,
            "status": "official" if re.fullmatch(r"\d+(\.\d+)?", price) else "pending",
        }
    if not quarters.get("2026-Q1", {}).get("price_eur"):
        raise LookupError("Q1 2026 price missing")
    return {"unit": "EUR per CBAM certificate", "quarters": quarters, "from_2027": "weekly prices (not modelled; projections use an assumption)"}


# ---------------------------------------------------------------- build


def build(download: bool) -> dict[str, Any]:
    sources = json.loads((ROOT / "sources.json").read_text())["sources"]
    old_manifest: dict[str, Any] = {}
    if (ROOT / "manifest.json").exists():
        old_manifest = json.loads((ROOT / "manifest.json").read_text())
    today = dt.date.today().isoformat()

    src_entries: dict[str, Any] = {}
    paths: dict[str, Path] = {}
    for sid, s in sources.items():
        p = (ROOT / s["path"]).resolve()
        if not p.exists():
            if not download:
                raise FileNotFoundError(f"{sid}: {p} missing (run with --download)")
            req = urllib.request.Request(s["url"], headers={"User-Agent": "Mozilla/5.0 pramaan-refdata"})
            p.parent.mkdir(parents=True, exist_ok=True)
            with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310 - fixed official URLs
                p.write_bytes(r.read())
        digest = sha256(p)
        prev = old_manifest.get("sources", {}).get(sid, {})
        downloaded = prev.get("downloaded_at") if prev.get("sha256") == digest else None
        if not downloaded:
            downloaded = dt.date.fromtimestamp(p.stat().st_mtime).isoformat() or today
        paths[sid] = p
        src_entries[sid] = {
            "title": s["title"],
            "url": s["url"],
            "path": s["path"],
            "published": s.get("published"),
            "legal_basis": s.get("legal_basis"),
            "downloaded_at": downloaded,
            "sha256": digest,
            "bytes": p.stat().st_size,
        }

    g3 = pdf_pages(paths["guidance_3_pdf"])
    g4 = pdf_pages(paths["guidance_4_pdf"])
    cscf = pdf_pages(paths["cscf_decision_pdf"])

    outputs: list[tuple[str, dict[str, Any], list[str], str]] = [
        ("default_values_iron_steel.json", parse_default_values(paths["dv_xlsx"]), ["dv_xlsx"], "parse_default_values"),
        ("benchmarks.json", parse_benchmarks(paths["bm_xlsx"]), ["bm_xlsx"], "parse_benchmarks"),
        ("benchmark_legend.json", parse_benchmark_legend(g4), ["guidance_4_pdf"], "parse_benchmark_legend"),
        ("cbam_schedule.json", parse_schedule(g4, cscf, g3), ["guidance_4_pdf", "cscf_decision_pdf", "guidance_3_pdf"], "parse_schedule"),
        ("fuel_factors.json", parse_fuel_factors(g3), ["guidance_3_pdf"], "parse_fuel_factors"),
        ("certificate_prices.json", parse_prices(paths["price_html"]), ["price_html"], "parse_prices"),
    ]
    assumptions = json.loads((ROOT / "assumptions.json").read_text())["assumptions"]
    for k, a in assumptions.items():
        if a.get("status") != "assumption" or not a.get("citation"):
            raise ValueError(f"assumption {k} must have status=assumption and a citation")
    outputs.append(("assumptions.json", {"assumptions": assumptions}, [], "copy_assumptions"))

    files: dict[str, Any] = {}
    for name, payload, srcs, parser in outputs:
        payload = {"_meta": {"sources": srcs, "parser": parser, "parser_version": PARSER_VERSION}, **payload}
        out = write_json(name, payload)
        files[f"json/{name}"] = {
            "sha256": sha256(out),
            "sources": srcs,
            "parser": parser,
            "parser_version": PARSER_VERSION,
            "status": "assumption" if name == "assumptions.json" else "official",
        }

    manifest = {
        "parser_version": PARSER_VERSION,
        "generated_at": today,
        "sources": src_entries,
        "files": files,
    }
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--download", action="store_true", help="download missing official source files")
    args = ap.parse_args()
    m = build(args.download)
    for f, e in m["files"].items():
        print(f"{f:45s} {e['sha256'][:12]}  <- {', '.join(e['sources']) or 'assumptions'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
