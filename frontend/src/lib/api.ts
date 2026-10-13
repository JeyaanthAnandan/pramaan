// Typed client for the Pramaan API (all JSON under /api).

export type Status = "VERIFIED_2R" | "APPROVED" | "NEEDS_REVIEW" | "MISSING" | "DEFAULT_USED" | "ASSUMPTION" | "PENDING" | "REFDATA" | "CALCULATED" | "SCENARIO" | string;

export interface CalcNode {
  id: string;
  label: string;
  value: string | null;
  display: string | null;
  unit: string;
  formula: string | null;
  children: string[];
  source: null | {
    kind: "evidence" | "refdata" | "assumption" | "scenario";
    evidence_id?: string;
    doc_id?: string;
    doc_title?: string;
    doc_type?: string;
    box_2d?: number[] | null;
    value_text?: string;
    period?: string | null;
    file?: string;
    locator?: string;
    status?: string;
    citation?: Record<string, unknown>;
    document?: { title: string; url: string; published?: string; sha256?: string };
    note?: string;
  };
  status: Status;
  note: string | null;
}

export interface MoneyPoint {
  year: number;
  price_eur: string;
  price_status: string;
  see_actual: string;
  sefa_y: string;
  see_default: string;
  sefa_default_y: string;
  actual_eur_t: string;
  default_eur_t: string;
  gap_eur_t: string;
  actual_inr_t: string;
  default_inr_t: string;
  gap_inr_t: string;
  buyer_eur_t: string;
  buyer_inr_t: string;
  basis: "actual" | "default";
  nodes: { actual: string; default: string; gap: string };
}

/** What the EU buyer pays: the cheaper of the exporter's data and the EU default (2026 imports). */
export interface BuyerCost {
  basis_2026: "actual" | "default";
  actual_eur_t: string;
  default_eur_t: string;
  buyer_eur_t: string;
  cost_actual_eur: string;
  cost_actual_node: string;
  cost_default_eur: string;
  cost_default_node: string;
  cost_buyer_eur: string;
  cost_buyer_node: string;
  gap_vs_default_eur_t: string;
  annual_factor: string;
  annual_gap_eur: string;
  supplier_saving_eur_t: string | null;
  supplier_saving_annual_eur: string | null;
  with_supplier_eur_t?: string;
}

export interface Operations {
  period_months: number;
  gas_gj_per_t: string | null;
  gas_node: string | null;
  gas_monthly: { month: string; gj_per_t: string }[];
  gas_pulse?: GasPulse | null;
  processes: Record<string, { yield_pct: string; yield_node: string; scrap_pct: string; scrap_node: string; rod_t: string; scrap_t: string; al_t: string; monthly: { month: string; scrap_pct: string | null; yield_pct: string | null }[] }>;
}

export interface ExtraParam { value: string | null; status: string; evidence: string[]; note?: string; optional?: boolean }

export interface ProcessResult {
  id: string;
  name: string;
  cn: string;
  cn_display: string;
  cn_desc: string;
  al_t: string;
  exports_t: string;
  exports_by_quarter: Record<string, string>;
  see: string;
  see_node: string;
  direct: string;
  m: string;
  precursor: {
    name: string; supplier: string; cn: string; cn_display: string; data: "ACTUAL_VERIFIED" | "DEFAULT_USED";
    see: string; see_node: string; sefa: string; sefa_node: string; status: string; default_value: string; default_locator: string; route: string | null;
  };
  sefa: string;
  sefa_node: string;
  sefa_y: string;
  sefa_y_node: string;
  certificates_2026: string;
  certificates_node: string;
  cost_2026_eur: string;
  cost_node: string;
  buyer: BuyerCost;
  contribution: { key: string; label: string; value: string; node: string; status?: string }[];
  extra_parameters: Record<string, ExtraParam>;
  default_see_2026: string;
}

export interface Check { id: string; name: string; formula: string; inputs: Record<string, unknown>; result: string; tolerance: string; status: "pass" | "fail" | "warn" | "info"; evidence_ids: string[]; note: string; reference: string }
export interface Gap { id: string; process: string | null; group: string; kind: string; status: "red" | "amber" | "green" | "info"; params: Record<string, any>; evidence_ids: string[]; suggested_doc?: string | null; ask?: string; node?: string | null; lever?: boolean }

export interface Result {
  computed_at: string;
  project_id: string;
  year: number;
  period_label: string;
  processes: ProcessResult[];
  money: {
    years: number[];
    series: Record<string, MoneyPoint[]>;
    what_if: Record<string, { year: number; eur_t: string; inr_t: string; see: string; node: string }[]>;
    fx: { value: string; status: string; as_of?: string; citation: string };
    projection_price: { value: string; status: string; citation: string };
    price_2026: { value: string; node: string };
  };
  readiness: {
    score: string; total: number; by_status: Record<string, number>; definition: string;
    by_process: Record<string, { score: string; total: number; good: number; missing: number; review: number; precursor: "actual" | "default"; ready: boolean }>;
    lines_ready: number; lines_total: number;
  };
  operations: Operations;
  period_months: number;
  calc_tree: Record<string, CalcNode>;
  assumptions_used: string[];
  checks: Check[];
  gaps: Gap[];
  explanations: { process: string; title: string; text: string; citations: { doc: string; page: number; why: string }[]; model?: string }[];
  explainer_meta: Record<string, unknown>;
  run_id: string | null;
  mode: "live" | "replay" | null;
  buyer_summary: BuyerSummary;
}

export interface BuyerSummary {
  operator: string; country: string; period: string; readiness_pct: string; banner: string; generated_at: string; method: string;
  goods: { cn: string; description: string; see_direct: string; see_indirect: string; production_route: string; precursor_data: { precursor: string; status: string }[];
    extra_parameters: Record<string, string | null>; sefa: string; default_see_2026_for_comparison: string }[];
}

export interface Doc {
  id: string; project_id: string; filename: string; content_type: string; uri: string; doc_type: string | null; doc_type_confidence: number | null;
  languages: string[]; period: string[] | null; title: string; width: number | null; height: number | null; uploaded_at: string; sha256: string; state: string;
}

export interface Evidence {
  id: string; doc_id: string; page: number; field_key: string; label: string; value_text: string; value_num: string | null; unit: string;
  box_2d: number[] | null; period: string | null; process: string | null; extractor_model: string; second_reader_model: string | null;
  second_reading: { reading_value: string | null; reading_unit: string | null; agrees: boolean; delta: string | null; model: string; crop_box: number[] | null; reason: string; corrected_from?: string | null } | null;
  status: Status; approved_by: string | null; approved_at: string | null; notes: string | null; history: { at: string; by: string; action: string; before: Record<string, unknown> }[];
}

export interface TimelineEvent { seq: number; ts: string; agent: string; action: string; status: "start" | "done" | "error" | "info" | "review"; input_summary: string; output_summary: string; duration_ms: number | null; model: string | null; tokens_in: number | null; tokens_out: number | null; doc_id: string | null }
export interface Run { id: string; project_id: string; mode: "live" | "replay"; status: "running" | "done" | "error"; started_at: string; finished_at: string | null; metrics: Record<string, any>; error: string | null; events?: TimelineEvent[] }

export interface ProcessDef {
  id: string; name: string; cn: string; cn_display: string; cn_desc: string; precursor_name: string; precursor_cn: string; precursor_supplier: string;
  precursor_country?: string; source: "sample" | "owner" | "ai"; evidence_docs: string[]; rationale: string;
}

export interface LineIn { name: string; cn: string; precursor_name: string; precursor_cn: string; precursor_supplier: string; source?: string; rationale?: string; doc_ids?: string[] }

export interface CnInfo { cn: string; cn_display: string; role: string; ok: boolean; description: string; default_value: string | null; default_locator: string | null; default_fallback: boolean; route: string | null; errors: string[] }

export interface ProjectBundle {
  project: { id: string; name: string; company: string; country: string; city: string; year: number; period_label: string; months: string[]; is_demo: boolean; fx_inr_per_eur: string | null; projection_price_eur: string | null;
    supplier_requests: { process_id: string; supplier: string; status: "not_requested" | "requested" | "received" | "verified"; updated_at: string; link_token?: string | null }[];
    processes: ProcessDef[]; processes_confirmed: boolean; protected: boolean };
  documents: Doc[];
  last_run: Run | null;
  running: boolean;
  has_result: boolean;
}

export class ApiError extends Error {
  constructor(public status: number, message: string, public detail: unknown = null) { super(message); }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, { ...init, headers: { ...(init?.body && !(init.body instanceof FormData) ? { "Content-Type": "application/json" } : {}), ...(init?.headers || {}) } });
  if (!r.ok) {
    let msg = r.statusText;
    let detail: unknown = null;
    try { const j = await r.json(); detail = j.detail; msg = typeof j.detail === "string" ? j.detail : j.detail?.message ?? JSON.stringify(j.detail); } catch { /* keep statusText */ }
    throw new ApiError(r.status, msg, detail);
  }
  return r.json() as Promise<T>;
}

export const api = {
  health: () => req<any>("/api/health"),
  demoLoad: (replay = false) => req<{ project_id: string; run_id: string; source: string }>("/api/demo/load", { method: "POST", body: JSON.stringify({ replay }) }),
  project: (pid: string) => req<ProjectBundle>(`/api/projects/${pid}`),
  createProject: (body: { name: string; company: string; country?: string; city?: string; months_to?: number }) =>
    req<ProjectBundle["project"] & { access_key: string }>("/api/projects", { method: "POST", body: JSON.stringify(body) }),
  unlock: (pid: string, passcode: string) => req<{ ok: boolean }>(`/api/projects/${pid}/unlock`, { method: "POST", body: JSON.stringify({ passcode }) }),
  putLines: (pid: string, lines: LineIn[], confirm = true) => req<ProjectBundle["project"]>(`/api/projects/${pid}/product-lines`, { method: "PUT", body: JSON.stringify({ lines, confirm }) }),
  suggestLines: (pid: string) => req<{ lines: ProcessDef[]; rejected: { proposal: Record<string, unknown>; errors: string[] }[]; notes: string; model: string | null }>(`/api/projects/${pid}/product-lines/suggest`, { method: "POST" }),
  cn: (cn: string, country: string, role: "good" | "precursor") => req<CnInfo>(`/api/refdata/cn/${encodeURIComponent(cn.replace(/\D/g, "") || "0")}?country=${encodeURIComponent(country)}&role=${role}`),
  cnSearch: (q: string, country: string) => req<{ cn: string; cn_display: string; description: string }[]>(`/api/refdata/cn/search?q=${encodeURIComponent(q)}&country=${encodeURIComponent(country)}`),
  countries: () => req<string[]>("/api/refdata/countries"),
  patchProject: (pid: string, body: Record<string, unknown>) => req<any>(`/api/projects/${pid}`, { method: "PATCH", body: JSON.stringify(body) }),
  upload: (pid: string, files: File[]) => { const fd = new FormData(); files.forEach((f) => fd.append("files", f)); return req<{ documents: Doc[] }>(`/api/projects/${pid}/documents`, { method: "POST", body: fd }); },
  startRun: (pid: string, lang: string, mode?: "live" | "replay") => req<{ run_id: string; mode: string }>(`/api/projects/${pid}/runs`, { method: "POST", body: JSON.stringify({ lang, mode }) }),
  run: (pid: string, rid: string) => req<Run>(`/api/projects/${pid}/runs/${rid}`),
  results: (pid: string) => req<Result>(`/api/projects/${pid}/results`),
  evidence: (pid: string) => req<Evidence[]>(`/api/projects/${pid}/evidence`),
  patchEvidence: (pid: string, eid: string, body: { action: "approve" | "edit"; value_text?: string; value_num?: string; user?: string }) =>
    req<{ evidence: Evidence; readiness: Result["readiness"] }>(`/api/projects/${pid}/evidence/${eid}`, { method: "PATCH", body: JSON.stringify(body) }),
  share: (pid: string) => req<{ token: string; url: string }>(`/api/projects/${pid}/share`, { method: "POST" }),
  getShare: (token: string) => req<{ summary: BuyerSummary; created_at: string }>(`/api/share/${token}`),
  letter: (pid: string, process_id: string, lang: string) => req<{ text: string; lang: string; supplier: string; facts: Record<string, string>; link: { token: string; url: string } }>(`/api/projects/${pid}/supplier-letter`, { method: "POST", body: JSON.stringify({ process_id, lang }) }),
  explanations: (pid: string, lang: string) => req<{ lang: string; sections: Result["explanations"] }>(`/api/projects/${pid}/explanations?lang=${encodeURIComponent(lang)}`),
  reportAsk: (pid: string, question: string, lang: string) => req<ReportAnswer>(`/api/projects/${pid}/ask`, { method: "POST", body: JSON.stringify({ question, lang }) }),
  supplierLink: (pid: string, process_id: string) => req<{ token: string; url: string }>(`/api/projects/${pid}/supplier-link`, { method: "POST", body: JSON.stringify({ process_id }) }),
  supplier: (token: string) => req<SupplierView>(`/api/supplier/${token}`),
  supplierSample: (token: string) => req<{ run_id: string; mode: string; status: string }>(`/api/supplier/${token}/sample`, { method: "POST" }),
  supplierUpload: (token: string, files: File[]) => {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    return req<{ run_id: string; mode: string; status: string }>(`/api/supplier/${token}/documents`, { method: "POST", body: fd });
  },
  plan: (pid: string, lang: string) => req<any>(`/api/projects/${pid}/monitoring-plan?lang=${lang}`),
  golden: () => req<any>("/api/golden"),
  metrics: () => req<any>("/api/metrics"),
  refdata: () => req<any>("/api/refdata"),
  ask: (question: string, lang: string) => req<any>("/api/copilot/ask", { method: "POST", body: JSON.stringify({ question, lang }) }),
  examples: () => req<string[]>("/api/copilot/examples"),
};

export const imageUrl = (pid: string, docId: string) => `/api/projects/${pid}/documents/${docId}/image`;
export const exportUrl = (pid: string, kind: "pdf" | "xlsx" | "pack") => `/api/projects/${pid}/export/${kind}`;

/** What the supplier sees behind its upload link: the request, its own documents and what was read from them. */
export interface SupplierView {
  request: { company: string; city: string; country: string; supplier: string; precursor: string; precursor_cn: string; product: string; product_cn: string; is_demo: boolean };
  status: "not_requested" | "requested" | "received" | "verified";
  updated_at: string;
  running: boolean;
  failed: boolean;
  documents: { id: string; title: string; state: string; doc_type: string | null; width: number | null; height: number | null }[];
  values: { field_key: string; label: string; value_text: string; unit: string; status: string; doc_id: string; box_2d: number[] | null }[];
  sample_available: boolean;
}

export const supplierImageUrl = (token: string, docId: string) => `/api/supplier/${token}/documents/${docId}/image`;

/** One figure of the report, citable by an answer; ``node`` opens the Evidence Lens. */
export interface ReportFact { id: string; label: string; value: string; unit: string; node: string | null }
export interface ReportAnswer {
  mode: "grounded" | "facts";
  answer: string | null;
  note?: "no_gemini" | "withheld" | "no_answer";
  facts: ReportFact[];
  relevant: string[];
  cited?: string[];
  citations: { doc: string; page: number }[];
  model?: string;
}

/** Plant pulse: gas per tonne by month against the plant's own median month (every figure has a lens node). */
export interface GasPulse {
  median: string;
  median_node: string;
  threshold_pct: string;
  months: { month: string; gj_per_t: string; node: string; delta_pct: string; hot: boolean; excess_gj?: string; excess_gj_node?: string; excess_inr?: string; excess_inr_node?: string; excess_tco2?: string; excess_tco2_node?: string }[];
  best: { month: string; gj_per_t: string; node: string };
  hot_months: string[];
  excess_gj?: string;
  excess_gj_node?: string;
  excess_inr?: string;
  excess_inr_node?: string;
  excess_tco2?: string;
  excess_tco2_node?: string;
}
