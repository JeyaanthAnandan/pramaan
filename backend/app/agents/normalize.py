"""Deterministic clean-up of the Extractor's output, before the blind second read.

The first live run on Cloud Run (2026-10-12, 24 sample photos, 213 values) showed that Gemini
read almost every figure correctly but sometimes put it in the wrong *place*: supplier-statement
values with no product line, a monthly tag on an invoice number, a CN code inside a description, a
reference number with its date appended, model text appended to a number. Those slips moved the
carbon bolts from SEE 2.040 to 5.722. The rules below come from the field schema
(``schemas.FIELDS``: unit and scope of every field) and the factory's product lines, not from the
sample's values, and they are idempotent: correct values pass through unchanged.
"""

from __future__ import annotations

import calendar
import re
from collections import Counter
from decimal import Decimal

from app.agents.schemas import FIELDS
from app.agents.second_reader import norm_text, parse_num
from app.evidence.models import ExtractedField, Project

CN_FIELDS = {"cn_code", "product_cn"}
REF_FIELDS = {"invoice_no", "doc_no", "verification_ref"}

_CN = re.compile(r"(?<![\d.,])(\d{4})[ .]?(\d{2})[ .]?(\d{2})(?![\d.,])")
_PLAIN_NUM = re.compile(r"[-+]?\d+(?:\.\d+)?")
_LEAD_NUM = re.compile(r"\s*[-+]?\d[\d,]*(?:\.\d+)?")
# "KA-VR-2026-0147 dated 2026-10-02", "INV/22 dt. 03.04.2026": the date is not part of the reference
_ISO = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
_DMY = re.compile(r"(?<!\d)(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})(?!\d)")
# "Ref. NWRM-CBAM-2026-07", "Invoice No: SF/EXP/2526/041": the printed label is not part of the reference
_LEADING_LABEL = re.compile(
    r"^\s*(?:ref(?:erence)?|doc(?:ument)?\s*no|invoice\s*no|inv\s*no|bill\s*no|statement\s*no|no)\s*[.:#]+\s*", re.IGNORECASE
)
_TRAILING_DATE = re.compile(r"\s*[,;]?\s+(?:dated|dt\.?|date)\s*[:.]?\s*\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}.*$", re.IGNORECASE)


def canonical_cn(text: str | None) -> str | None:
    """The one 8-digit CN/HSN code in a text, as 'dddd dd dd' (None if there is not exactly one)."""
    codes = {"".join(m) for m in _CN.findall(text or "")}
    if len(codes) != 1:
        return None
    c = codes.pop()
    return f"{c[:4]} {c[4:6]} {c[6:]}"


def canonical_text(field_key: str, text: str | None) -> str:
    """Same canonical form for both readers: CN codes without their description, references
    without a trailing date. Anything else is returned as read."""
    t = (text or "").strip()
    if field_key in CN_FIELDS:
        return canonical_cn(t) or t
    if field_key in REF_FIELDS:
        return _LEADING_LABEL.sub("", _TRAILING_DATE.sub("", t)).strip() or t
    return t


def clean_number(value_num: str | None, value_text: str, numeric: bool) -> str | None:
    """A plain decimal string for numeric fields: keeps a clean value_num, salvages the leading
    number when the model appended text to it, else reads the printed text. Text fields keep
    whatever the model returned (a date must not become the number 3)."""
    v = (value_num or "").strip()
    if not numeric:
        return v or None
    if _PLAIN_NUM.fullmatch(v):
        return v
    m = _LEAD_NUM.match(v) if v else None
    d = parse_num(m.group(0)) if m else None
    if d is None:
        d = parse_num(value_text)
    return _plain(d) if d is not None else None


def _plain(d: Decimal) -> str:
    return format(d, "f")


def _cn_line(cn: str, project: Project) -> str | None:
    """The product line whose steel input (else product) has this CN code: 8 digits, else the
    6-digit HS heading (Indian HSN and EU CN differ in the last two digits)."""
    c = cn.replace(" ", "")
    for width in (8, 6):
        for attr in ("precursor_cn", "cn"):
            hits = {p.id for p in project.processes if getattr(p, attr)[:width] == c[:width]}
            if len(hits) == 1:
                return hits.pop()
    return None


def document_line(fields: list[ExtractedField], project: Project) -> str | None:
    """One product line for a single-material document (steel-input invoice, supplier statement):
    the CN code printed on it, else the line most of its values were tagged with, else the supplier
    named on it, else the factory's only line."""
    ids = {p.id for p in project.processes}
    for f in fields:
        if f.field_key in CN_FIELDS:
            cn = canonical_cn(f.value_text)
            line = _cn_line(cn, project) if cn else None
            if line:
                return line
    tags = Counter(f.process for f in fields if f.process in ids).most_common(2)
    if tags and (len(tags) == 1 or tags[0][1] > tags[1][1]):
        return tags[0][0]
    for f in fields:
        if f.field_key == "supplier" and norm_text(f.value_text):
            s = norm_text(f.value_text)
            hits = {
                p.id
                for p in project.processes
                if p.precursor_supplier and (norm_text(p.precursor_supplier) in s or s in norm_text(p.precursor_supplier))
            }
            if len(hits) == 1:
                return hits.pop()
    return project.processes[0].id if len(project.processes) == 1 else None


_QUARTER = re.compile(r"\d{4}-Q[1-4]")
_MONTH = re.compile(r"\d{4}-(0[1-9]|1[0-2])")


def quarter_of(date_text: str | None) -> str | None:
    """'2026-Q2' for a date string the model read ('15-06-2026', '2026-06-15'); None if no date."""
    d = iso_date(date_text)
    return f"{d[:4]}-Q{(int(d[5:7]) - 1) // 3 + 1}" if d else None


def normalize_fields(fields: list[ExtractedField], doc_type: str, project: Project) -> list[ExtractedField]:
    """Apply the schema's unit and scope to every extracted value (in place; also returned)."""
    spec = FIELDS.get(doc_type, {})
    line = document_line(fields, project) if any(spec.get(f.field_key, ("", "", ""))[2] == "process" for f in fields) else None
    # A line quantity belongs to the calendar quarter of its invoice date. The second live run
    # (2026-10-13) left the period off one line of an otherwise correct export invoice.
    doc_quarter = quarter_of(next((f.value_text for f in fields if f.field_key == "invoice_date"), None))
    # A one-month bill's values belong to that month. The same run left the month off whole bills
    # that were read correctly, and the engine then counted those months as missing.
    start, end = document_period(fields, None)
    doc_month = start[:7] if start and start[:7] == end[:7] else None
    cn_rows = [f for f in fields if f.field_key in CN_FIELDS and f.process]
    for f in fields:
        _desc, unit, scope = spec.get(f.field_key, ("", "", ""))
        f.value_text = canonical_text(f.field_key, f.value_text)
        f.value_num = clean_number(f.value_num, f.value_text, numeric=bool(unit))
        if unit and not f.unit:
            f.unit = unit
        if scope == "doc":
            f.period, f.process = None, None
        elif scope == "period":
            f.process = None
            if doc_month and not (f.period and _MONTH.fullmatch(f.period)):
                f.period = doc_month
        elif scope == "process":
            f.period = None
            if line:
                f.process = line
        elif scope == "line" and not unit:
            f.period = None  # a CN code describes the line; only its quantity belongs to a quarter
        else:
            if scope == "line" and not (f.period and _QUARTER.fullmatch(f.period)):
                f.period = doc_quarter
            if scope == "line" and not f.process:
                f.process = _row_line(f, cn_rows)
    return fields


def _row_line(f: ExtractedField, cn_rows: list[ExtractedField]) -> str | None:
    """The product line of the CN code printed on the same row as a line quantity (the nearest
    row by its box's vertical centre), else the invoice's only line."""
    lines = {c.process for c in cn_rows}
    if len(lines) == 1:
        return lines.pop()
    if not f.box_2d or not cn_rows:
        return None
    mid = (f.box_2d[0] + f.box_2d[2]) / 2
    boxed = [c for c in cn_rows if c.box_2d]
    if not boxed:
        return None
    dist = sorted((abs((c.box_2d[0] + c.box_2d[2]) / 2 - mid), c.process) for c in boxed if c.box_2d)
    # Two rows equally close: not ours to guess.
    if len(dist) > 1 and dist[0][0] == dist[1][0] and dist[0][1] != dist[1][1]:
        return None
    return dist[0][1]


def all_dates(text: str | None) -> list[str]:
    """Every date in a text as YYYY-MM-DD, in order: ISO dates, then Indian DD-MM-YYYY ones."""
    t = text or ""
    found: list[tuple[int, str]] = []
    for m in _ISO.finditer(t):
        found.append((m.start(), _ymd(int(m[1]), int(m[2]), int(m[3]))))
    for m in _DMY.finditer(t):
        found.append((m.start(), _ymd(int(m[3]), int(m[2]), int(m[1]))))
    return [d for _, d in sorted(found) if d]


def iso_date(text: str | None) -> str:
    """The first date in a model string ('' if none): models sometimes append notes to a date."""
    ds = all_dates(text)
    return ds[0] if ds else ""


def _ymd(y: int, m: int, d: int) -> str:
    if not (1 <= m <= 12 and 1 <= d <= calendar.monthrange(y, m)[1]):
        return ""
    return f"{y:04d}-{m:02d}-{d:02d}"


def document_period(fields: list[ExtractedField], current: list[str] | None) -> list[str]:
    """The period a document covers, from its own (verified) values when it states one: billing
    period, statement period, invoice date, or the months of a register. Else the classifier's."""
    start, end = ([iso_date(x) for x in (current or [])] + ["", ""])[:2]
    vals = {f.field_key: f.value_text for f in fields}
    months = sorted({f.period for f in fields if f.period and re.fullmatch(r"\d{4}-\d{2}", f.period)})
    if "period_start" in vals or "period_end" in vals:
        start, end = iso_date(vals.get("period_start")) or start, iso_date(vals.get("period_end")) or end
    elif len(ds := all_dates(vals.get("period"))) >= 2:
        start, end = ds[0], ds[-1]
    elif d := iso_date(vals.get("invoice_date")):
        start, end = d, d
    elif months:
        y, m = (int(x) for x in months[-1].split("-"))
        start, end = f"{months[0]}-01", f"{months[-1]}-{calendar.monthrange(y, m)[1]:02d}"
    return [start, end]
