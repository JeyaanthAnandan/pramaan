"""Text a spreadsheet would run. A value read from a photo (a supplier can upload one through a public
link) or typed by a person that starts with "=", "+", "-" or "@" is a formula to Excel; the verifier pack
is opened in Excel. The exports store such text as text, so opening them can run nothing (OWASP: CSV
injection). Numbers, and the "-" used for "none", are left as they are."""

from __future__ import annotations

import csv
import re
from typing import Any

from openpyxl import Workbook

_NUMBER = re.compile(r"^[-+]?\d[\d,]*(\.\d+)?$")


def csv_safe(v: Any) -> Any:
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r") and v != "-" and not _NUMBER.match(v):
        return "'" + v
    return v


class SafeWriter:
    """csv.writer whose rows can carry no formula."""

    def __init__(self, f: Any) -> None:
        self._w = csv.writer(f)

    def writerow(self, row: list[Any]) -> Any:
        return self._w.writerow([csv_safe(v) for v in row])


def text_only(wb: Workbook) -> None:
    """Every cell openpyxl would write as a formula (any string starting with "=") is written as text."""
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if cell.data_type == "f":
                    cell.data_type = "s"
