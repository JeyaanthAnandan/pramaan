"""Evidence records and project state (brief section 7.4)."""

from __future__ import annotations

import datetime as dt
import secrets
from typing import Any, Literal

from pydantic import BaseModel, Field

DocType = Literal[
    "electricity_bill",
    "gas_invoice",
    "fuel_invoice",
    "precursor_invoice",
    "supplier_emissions_statement",
    "production_register",
    "scrap_log",
    "export_invoice",
    "other",
]
DOC_TYPES: list[str] = list(DocType.__args__)  # type: ignore[attr-defined]

Status = Literal["VERIFIED_2R", "APPROVED", "NEEDS_REVIEW", "MISSING", "DEFAULT_USED", "ASSUMPTION", "PENDING"]


def now() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(6)}"


class ExtractedField(BaseModel):
    """Extractor output for one value (agent contract)."""

    field_key: str
    value_text: str
    value_num: str | None = None
    unit: str = ""
    box_2d: list[int] | None = None  # [ymin, xmin, ymax, xmax] normalised 0-1000
    page: int = 0
    label: str = ""
    period: str | None = None
    process: str | None = None
    item: str | None = None
    doc_id: str = ""


class SecondReading(BaseModel):
    reading_value: str | None = None
    reading_unit: str | None = None
    agrees: bool = False
    delta: str | None = None
    model: str = ""
    crop_box: list[int] | None = None
    reason: str = ""


class Evidence(BaseModel):
    id: str = Field(default_factory=lambda: new_id("ev"))
    project_id: str
    doc_id: str
    page: int = 0
    field_key: str
    label: str = ""
    value_text: str
    value_num: str | None = None
    unit: str = ""
    box_2d: list[int] | None = None
    period: str | None = None
    process: str | None = None
    item: str | None = None
    extractor_model: str = ""
    second_reader_model: str | None = None
    second_reading: SecondReading | None = None
    status: Status = "PENDING"
    approved_by: str | None = None
    approved_at: str | None = None
    notes: str | None = None
    history: list[dict[str, Any]] = Field(default_factory=list)


class Document(BaseModel):
    id: str = Field(default_factory=lambda: new_id("doc"))
    project_id: str
    filename: str
    content_type: str = "image/jpeg"
    uri: str  # demo://out/x.jpg | file://... | gs://...
    doc_type: str | None = None
    doc_type_confidence: float | None = None
    languages: list[str] = Field(default_factory=list)
    period: list[str] | None = None
    title: str = ""
    pages: int = 1
    width: int | None = None
    height: int | None = None
    uploaded_by: str = "owner"
    uploaded_at: str = Field(default_factory=now)
    sha256: str = ""
    state: Literal["uploaded", "classified", "extracted", "failed"] = "uploaded"


class ProcessDef(BaseModel):
    id: str  # P1
    name: str
    cn: str  # 8-digit CN of the good
    cn_display: str
    cn_desc: str = ""
    precursor_name: str
    precursor_cn: str
    precursor_supplier: str
    precursor_country: str = "India"


class SupplierRequest(BaseModel):
    process_id: str
    supplier: str
    status: Literal["not_requested", "requested", "received", "verified"] = "not_requested"
    updated_at: str = Field(default_factory=now)
    letter_lang: str | None = None


class Project(BaseModel):
    id: str = Field(default_factory=lambda: new_id("prj"))
    name: str
    company: str
    country: str = "India"
    city: str = ""
    year: int = 2026
    period_label: str = "Jan-Sep 2026 (provisional, year-to-date)"
    months: list[str] = Field(default_factory=lambda: [f"2026-{m:02d}" for m in range(1, 10)])
    processes: list[ProcessDef] = Field(default_factory=list)
    is_demo: bool = False
    created_at: str = Field(default_factory=now)
    fx_inr_per_eur: str | None = None  # user override; default from refdata assumption
    projection_price_eur: str | None = None
    supplier_requests: list[SupplierRequest] = Field(default_factory=list)
    what_if: dict[str, Any] = Field(default_factory=dict)


class TimelineEvent(BaseModel):
    seq: int = 0
    ts: str = Field(default_factory=now)
    agent: str
    action: str
    status: Literal["start", "done", "error", "info", "review"] = "done"
    input_summary: str = ""
    output_summary: str = ""
    duration_ms: int | None = None
    model: str | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    doc_id: str | None = None


class Run(BaseModel):
    id: str = Field(default_factory=lambda: new_id("run"))
    project_id: str
    mode: Literal["live", "replay"] = "live"
    status: Literal["running", "done", "error"] = "running"
    started_at: str = Field(default_factory=now)
    finished_at: str | None = None
    events: list[TimelineEvent] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class ShareLink(BaseModel):
    token: str = Field(default_factory=lambda: secrets.token_urlsafe(12))
    project_id: str
    summary_snapshot: dict[str, Any]
    created_at: str = Field(default_factory=now)
    expires_at: str | None = None
