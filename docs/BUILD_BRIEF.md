# PRAMAAN — Build Brief for Claude Code
### Google Cloud AI Builder Cup 2026 · Theme: **Manufacturing: Intelligent Operations & Industrial Efficiency**

> **How to use this file (for the human):**
> 1. Create a brand-new **public** GitHub repo (e.g. `pramaan`). The hackathon only accepts code written during the event — do not copy code from any earlier project.
> 2. Save this file as `docs/BUILD_BRIEF.md` in the repo.
> 3. Fill in the **Project settings** block below.
> 4. Open Claude Code in the repo and say:
>    `Read docs/BUILD_BRIEF.md completely. Confirm your understanding in 10 bullets, list any questions, then start Phase 0.`
> 5. After every phase, review what Claude Code reports, then reply `go` for the next phase.

---

## 0. Project settings

```
GCP_ACCOUNT         = sudarssan73@gmail.com
GCP_PROJECT_NAME    = CopilotManufacturing
GCP_PROJECT_ID      = copilot-manufacturing
GCP_PROJECT_NUMBER  = 646454690406
GCP_REGION          = asia-southeast1          # Singapore — use for Cloud Run, Firestore, Cloud Storage
GEMINI_LOCATION     = global                   # unless the docs confirm the models are served in asia-southeast1
BILLING             = NOT LINKED YET — blocks Phase 0 (see 0.1)
CONSOLE             = https://console.cloud.google.com/home/dashboard?project=copilot-manufacturing
GITHUB_REPO         = <org>/pramaan
TEAM_NAME           = Innovative Warriors
LOCAL_GEMINI_KEY    = in .env.local only (never committed); production uses the Cloud Run service account
FX_INR_PER_EUR      = <rate> as of <date>       # shown in UI with its date; user-editable
```

### 0.1 One-time GCP setup (the human does steps 1–3; Claude Code verifies and does the rest)

1. **Link a billing account** to `copilot-manufacturing` (Console → Billing). Cloud Run, Firestore and Gemini on Agent Platform all fail without it. If the account is eligible, the Google Cloud free trial credit covers this hackathon comfortably.
2. **Create a budget alert** on that billing account (for example ₹2,000 with alerts at 50%, 90%, 100%), scoped to this project.
3. **Authenticate locally** as the project owner: `gcloud auth login`, `gcloud auth application-default login`, `gcloud config set project copilot-manufacturing`, `gcloud config set run/region asia-southeast1`.
4. Claude Code then enables the APIs: `run`, `cloudbuild`, `artifactregistry`, `aiplatform`, `firestore`, `storage`, `secretmanager`, `logging`, `cloudtrace`, `iam` (all `*.googleapis.com`).
5. Create Firestore (Native mode) in `asia-southeast1`, a Cloud Storage bucket `copilot-manufacturing-pramaan` in `asia-southeast1` (uniform access, not public), and a dedicated service account `pramaan-run@copilot-manufacturing.iam.gserviceaccount.com` with only: Vertex AI / Agent Platform user, Cloud Datastore user, Storage object admin on that bucket, Logging writer, Cloud Trace agent.
6. Confirm which location serves `gemini-3.8-flash` and `gemini-3.5-flash-lite` on Agent Platform before writing model calls; use `global` if they are not served in `asia-southeast1`.
7. Stop and report: billing status, enabled APIs, resources created, and the service-account roles — before deploying anything.

---

## 1. Mission

Build **Pramaan** (Hindi for "proof"): an agentic AI copilot that lets a **small steel-goods exporter** (fasteners, wire, pipes) turn **phone photos of bills, invoices and production logs** into **verifier-ready EU CBAM embedded-emissions data**, where **every number traces back to the exact region of the source document**, and that shows — in € and ₹ — **what staying on EU default values costs their EU buyer**.

Tagline: **"CBAM proof from a phone photo."**

**Why this matters (use these facts in the README and UI copy, with sources):**
- The EU CBAM entered its definitive (payment) phase on **1 Jan 2026**. EU importers now pay for emissions embedded in steel imports; exporters without verified data are priced on punitive **default values with a mark-up of 10% (2026), 20% (2027), 30% (2028+)**.
- An estimated **25,000–30,000 Indian MSMEs** are at risk; the EU takes **32–45% of India's steel exports**; exporters may need to cut prices **15–22%** (Business Standard via Vision IAS, Jan 2026).
- Per-MSME compliance cost is reported at **₹15–20 lakh**; India is working on a scheme to reimburse 90% (Indian Express, Jun 2026).
- European fastener distributors say a **verification bottleneck** is forcing importers onto default values in 2026 (EFDA via Eurometal).
- The same problem hits exporters in Vietnam, China, Korea, Indonesia — this is a JAPAC-wide product.

**Hard deadline:** prototype submitted by **18 Oct 2026**. Judging runs **19 Oct – 6 Nov 2026** on a deck, a ≤3-minute video, a **public GitHub repo** and a **live deployed URL**. The live URL must work for the entire judging window.

---

## 2. Hackathon rules the build must satisfy (non-negotiable)

1. Must use Google AI models (Gemini/Gemma) and/or Google agentic platforms (Agent Platform / ADK / AI Studio / Antigravity).
2. Must be **deployed on Google Cloud via Cloud Run** (or Firebase). We use **Cloud Run**.
3. **Fresh code only** — everything in this repo is written now.
4. Public GitHub repo, English everywhere, no secrets committed.
5. Same judging weights for all themes:

| Criterion | Weight | Where Pramaan earns it |
|---|---|---|
| Technical merit & Gen AI implementation | **40%** | ADK 2.x multi-agent workflow; Gemini 3.8 Flash multimodal extraction with bounding boxes; blind second-reader verification; File Search with page citations; deterministic engine with golden tests; eval metrics; clean Cloud Run deploy |
| Problem alignment & impact | 25% | Real regulation, real MSME pain, ₹/€ outcome per tonne, verifier-ready output |
| Innovation & creativity | 25% | Evidence Lens (pixel provenance), Precursor Lever, "Money on the table" with the *correct* formula, vernacular voice gap-closing |
| UX & solution design | 10% | 3-step flow, phone capture, local languages, agent timeline, one-click demo |

---

## 3. Who we are building for (design every screen with these people in mind)

| Audience | What they need to see | How Pramaan shows it |
|---|---|---|
| **Hackathon judges** (Google Cloud + industry experts; they skim a deck, a 3-min video, a live link, a repo) | Gen AI doing the core job; Google stack used well; proof numbers are right; APAC impact | Live **agent-activity timeline**; **Evidence Lens** on every number; **"EC example reproduced" badge**; extraction-accuracy metrics; architecture page |
| **MSME owner / accountant** (Ludhiana, Rajkot, Coimbatore; phone-first; not a carbon expert) | What to upload, what is missing, what it costs | Photo capture; progress checklist; plain-language answers in **Hindi / Tamil**; ₹ and € per tonne |
| **EU importer** (authorised CBAM declarant) | Specific embedded emissions per CN code, route, extra parameters; no confidential plant data | **Read-only buyer link** with summary only |
| **Accredited verifier** | Monitoring plan, data-flow controls, source records | **Verifier pack**: indexed evidence, control log, draft monitoring plan |
| **Shop-floor supervisor** | Simple questions in their language | **Voice answer** (Hindi/Punjabi/Tamil) transcribed and filed as evidence (stretch) |

---

## 4. Product scope

### 4.1 Core flow (3 steps — one question per screen)
1. **Capture** — "Add your documents." Phone camera / multi-file upload. Agent timeline shows progress live.
2. **Close gaps** — "What's missing?" Checklist of required data per production process; amber items need a human tap to approve; red items are missing or on default values; each item has a plain-language explanation in the selected language.
3. **Report** — "Here's your proof." Specific embedded emissions (SEE) per CN group, Evidence Lens on every number, Money-on-the-table chart, exports, buyer link.

### 4.2 Features with priority

**[MUST] — ship these first (USPs 1–5)**
- **M1. Document ingestion & classification** — images (JPG/PNG/HEIC) and PDFs; classify into: electricity bill, gas/fuel invoice, precursor purchase invoice, supplier emissions statement, production register, scrap log, export/dispatch invoice, other.
- **M2. Extraction with bounding boxes** — Gemini 3.8 Flash returns every required field with `value`, `unit`, `box_2d` = `[ymin, xmin, ymax, xmax]` normalised 0–1000, page index, and a short label.
- **M3. USP 2 — Blind two-reader check** — for each extracted field, crop the region (pad 15%), send *only the crop* to Gemini 3.5 Flash-Lite and ask it to read value + unit without seeing the first reading. Normalise and compare (numbers within 0.5%, units exact after normalisation). Match → `VERIFIED_2R` (green). Mismatch → `NEEDS_REVIEW` (amber) showing both readings. Human edit/approve → `APPROVED` (with user + timestamp).
- **M4. Cross-document control checks** (mirrors EC Guidance 2, Step 7 "control system") — e.g. precursor consumed − scrap ≈ product produced (±2%); purchases vs consumption vs stock; monthly totals vs annual; exports ≤ production. Each check is logged with pass/fail and shown in the verifier pack.
- **M5. Deterministic CBAM engine** (Section 5) — Python, `Decimal`, unit-safe, exposed to agents only as a tool. **The LLM never does arithmetic.**
- **M6. USP 1 — Evidence Lens** — click any number in the report → side panel shows the source image with the region highlighted, the formula with inputs, the two-reader result, approver and timestamp. Derived numbers show their full calculation tree, each leaf clickable.
- **M7. USP 3 — "EC example reproduced" badge** — in-app page that runs the golden tests (Section 5.6) live and shows expected vs computed with tolerance and the guidance page reference.
- **M8. USP 4 — Precursor Lever** — show the contribution split (own process vs each precursor). In the EC screw example the purchased rod is ~90% of the total. Generate a **supplier data request letter** (English + Hindi) asking the rod supplier for verified SEE, production route, verification report, SEFA, carbon price paid and the extra parameters (Section 5.5). Track status: requested / received / verified.
- **M9. USP 5 — Money on the table** — for each exported CN group: buyer's CBAM cost per tonne (€ and ₹) under (a) the exporter's actual data and (b) EU default values with mark-up, for 2026 → 2034, using the **correct formula** (Section 5.3). Include a "Myth-buster" note: *some online estimates multiply embedded emissions by 2.5% in 2026; the Commission's formula subtracts a benchmark-based free-allocation adjustment, so everything above the benchmark is payable* — demonstrate with EC Example 1 (3,690 certificates on 15,670 t embedded = 23.5%, not 5%).
- **M10. Exports** — PDF report, Excel workbook (inputs, factors, calculations, evidence index), verifier pack (zip: report, workbook, source images, evidence index CSV, control-check log, reference-data manifest).
- **M11. Buyer share link** — read-only, no login, summary only: CN codes, SEE (direct), production route, extra parameters, period, data status (actual/default per precursor), "provisional until verified" banner. No plant-level inputs.
- **M12. Demo mode** — landing page button **"Load sample factory"** that loads the fictional factory (Section 6) with pre-processed, cached results so judges see the full experience in seconds; plus a **"Process live"** button that re-runs the agents on the sample docs.
- **M13. Agent-activity timeline** — streamed events (SSE): agent name, action, input summary, output summary, duration, model, tokens. Shown during processing and saved as a run log ("receipt").

**[SHOULD] — after all MUSTs pass**
- **S1. USP 8 — Rules copilot** — chat that answers CBAM method questions using a **File Search** store built from the EC guidance PDFs and regulations, returning **page-number citations**. Scripted demo questions: "Does electricity count for my screws?", "What if my rod supplier won't share data?", "What extra parameters must I report for screws?", "When is the first declaration due?", "Is scrap counted?".
- **S2. Hindi + Tamil UI and explanations** (i18next), Vietnamese as a fourth language for JAPAC signal.
- **S3. USP 6 — Draft monitoring plan** — generate a draft monitoring plan (English + Hindi) from the project data, structured on the minimum elements in Annex II section A.5 of the Methodology Act (read EC Guidance 3 for the list); clearly marked "draft for verifier review".

**[STRETCH] — only after the Oct 15 eval run is green**
- **X1. USP 7 — Vernacular voice** — supervisor records a voice note answering a gap question ("How many tonnes of scrap in August?") in Hindi/Punjabi/Tamil → `gemini-3.5-transcribe` → value extracted → stored as evidence (audio + transcript). Optional live interview via `gemini-3.8-live`.
- **X2. Decarbonisation what-if** — switch rod supplier (BF-BOF vs scrap-EAF verified SEE), switch heat-treatment fuel; show SEE and buyer-cost change. Note on screen that for iron & steel only direct emissions count, so electric heating changes CBAM SEE.
- **X3. Data shaped like the Commission's operator emissions report summary** (Annex IV 1.1/1.2 of the Methodology Act) — label as "aligned to", verify against the official template before claiming compatibility.

**Explicitly out of scope:** user accounts beyond a simple project passcode, payments, real CBAM Registry integration, real supplier networks, any non-steel sector beyond a "coming soon" note.

---

## 5. Domain specification (CBAM definitive period) — implement exactly

**Primary sources (download into `docs/regulation/` and cite page numbers in code comments and UI):**
- EC CBAM legislation & guidance page: https://taxation-customs.ec.europa.eu/carbon-border-adjustment-mechanism/cbam-legislation-and-guidance_en
- Guidance No. 2 (quick guide for non-EU operators), No. 3 (calculation methods), No. 4 (free allocation adjustment), **No. 5d (iron and steel)** — links on the page above (published 14 Aug 2026).
- Default values (Excel, corrected, 10 Aug 2026): https://taxation-customs.ec.europa.eu/document/download/1c05d211-80cb-4aaa-8ef0-e08005a95d7e_en?filename=DV%20correcting%20act_final%20update_06.08.xlsx
- Benchmarks (Excel, 13 Feb 2026): https://taxation-customs.ec.europa.eu/document/download/9877523c-2a02-4926-a211-aefae7cf6d0d_en?filename=CBAM%20Benchmarks_20260206.xlsx
- Legal: Reg. (EU) 2023/956 (consolidated after 2025/2083); Methodology Act 2025/2547; Default Values Act 2025/2621 (+ correcting 2026/1740); Free Allocation Adjustment Act 2025/2620; Verification 2025/2546 and 2025/2551; Certificate prices 2025/2548.

> **Rule:** never hand-type a regulatory value. Every factor, default value, benchmark, price and schedule lives in `backend/refdata/` as JSON generated from the official files, with `manifest.json` recording source URL, download date, SHA-256 and the parser version. A test fails if any refdata file lacks a manifest entry. If a value is not in an official file, it must carry `"status": "assumption"` and be shown as such in the UI.

### 5.1 Scope rules
- Iron & steel goods (CN 72xx, 7301–7311, **7318**, 7326) are in aggregated category **"iron or steel products"**; precursors can be in the same category (rod → screws).
- **Only direct emissions count** for iron & steel goods (Annex II of the CBAM Regulation). Record electricity for completeness and energy balance, **exclude it from SEE**, and say so in the UI.
- For iron or steel products, emissions from **plating, cutting, welding and finishing** are excluded; precursor mass still enters before cutting.
- Scrap and cut-offs carry **zero embedded emissions**.
- Reporting period = **calendar year of production** (by default the year of import). Demo data is **Jan–Sep 2026 = provisional, year-to-date**.
- Precursor **actual** data may be used only with a valid verification report covering the precursor's production period; otherwise use the **country-specific default value** for that precursor.

### 5.2 Specific embedded emissions (per production process p, functional unit = tonnes per CN group)

```
AttrEm_p = Σ_fuels  AD_f × NCV_f × EF_f × OxF_f        (direct, t CO2; OxF default 1)
           + process emissions (if any; not in demo)
SEE_p    = AttrEm_p / AL_p  +  Σ_i ( m_i × SEE_i )
m_i      = mass of precursor i consumed in p  /  AL_p   (t/t; > 1 when there is scrap)
AL_p     = tonnes of goods produced by p in the period
```

Fuel conversions must use cited factors stored in refdata. Prefer the standard factors in **Annex II section G of the Methodology Act**; fallback to IPCC 2006 defaults (flagged): natural gas EF 56.1 t CO2/TJ, NCV 48.0 GJ/t; LPG 63.1 / 47.3; gas/diesel oil 74.1 / 43.0; residual fuel oil 77.4 / 40.4. For gas billed in MMBtu (GCV basis): 1 MMBtu = 1.055056 GJ (GCV); NCV ≈ 0.9 × GCV for natural gas (IPCC 2006 Vol. 2 Ch. 1) — store as cited assumptions.

### 5.3 Free allocation adjustment, certificates and cost

```
SEFA_g      = BM_colA(own process, CN of g)  +  Σ_i m_i × SEFA_i
              SEFA_i = supplier's actual SEFA if verified data provided,
                       else BM_colB(CN of precursor i)   (benchmarks Excel; pick period note (1) for 2026–27, (2) for 2028+)
SEFA_g,y    = CBAMfactor_y × CSCF_y × SEFA_g             (CSCF_y default 1.0 — store as assumption, cite Guidance 4)
FAA_g       = SEFA_g,y × M_g                             (M_g = tonnes imported into the EU)
EE_g        = SEE_g × M_g
Certificates = Σ_g EE_g − Σ_g FAA_g − carbon_price_paid_deduction   (floor at 0 and flag if negative)
Cost €      = Certificates × price(quarter of import)
Cost per t  = (SEE_g − SEFA_g,y) × price                 (show both actual and default paths)
Default SEE = DV(country, CN) × (1 + markup_y)            (markup: 2026 0.10 · 2027 0.20 · 2028+ 0.30)
Default SEFA uses BM_colB for the good's CN.
```

**Reference schedules (store in refdata with sources):**

| Year | CBAM factor | Default mark-up |
|---|---|---|
| 2026 | 0.975 | 10% |
| 2027 | 0.95 | 20% |
| 2028 | 0.90 | 30% |
| 2029 | 0.775 | 30% |
| 2030 | 0.515 | 30% |
| 2031 | 0.39 | 30% |
| 2032 | 0.265 | 30% |
| 2033 | 0.14 | 30% |
| 2034 | 0.00 | 30% |

Sources: ICAP (Commission package, Dec 2025); OPIS/McCloskey (committee-approved acts, Dec 2025). Verify against Guidance 4 and Reg. 2025/2620 and flag any difference.

**2026 certificate prices (quarterly; from 2027 weekly):** Q1 €75.36 (pub. 7 Apr 2026), Q2 €75.28 (6 Jul 2026), Q3 €82.32 (5 Oct 2026), Q4 *pending — published 4 Jan 2027* (use Q3 as a flagged estimate). Projections beyond 2026 use a user-adjustable price assumption (default €82.32) shown as an assumption.

**Key dates:** certificates on sale from 1 Feb 2027; first declaration & surrender due **30 Sep 2027** for 2026 imports.

### 5.4 Data-status logic per value
`VERIFIED_2R` (two readers agree) · `APPROVED` (human) · `NEEDS_REVIEW` · `MISSING` · `DEFAULT_USED` (with which default and mark-up) · `ASSUMPTION` (refdata assumption). The report header shows a readiness score = share of SEE-relevant inputs that are `VERIFIED_2R` or `APPROVED`.

### 5.5 Extra parameters for iron or steel products (required fields in the gap checklist)
Main reducing agent used in precursor production (if known); mass % of Mn, Cr, Ni, total other alloy elements; tonnes of scrap used per tonne of product; % of that scrap that is pre-consumer (EC Guidance 5d, Table 3-1).

### 5.6 Golden tests — the build is not done until these pass
All from **EC Guidance No. 5d (14 Aug 2026)**, section 4. EC tables round intermediate values to 3 decimals, so use tolerance **±0.002 t CO2/t** for SEE/SEFA and the stated tolerance for certificates. Put them in `backend/tests/test_golden_ec.py` with the page reference in each docstring.

| ID | Case | Inputs | Expected |
|---|---|---|---|
| G1 | Example 3, carbon-steel screws & nuts | AL 17,000 t; rod consumed 20,000 t (scrap 3,000 t); rod SEE 1.567; natural gas 3.5 GJ(NCV)/t product, EF 56.1 t/TJ | direct 0.196; precursor 1.843; **SEE 2.039** (full precision ≈ 2.0399) |
| G2 | Example 3, high-alloy screws & nuts | AL 8,200 t; rod 10,000 t (scrap 1,800 t); rod SEE 1.783; gas 3.5 GJ/t | precursor 2.175; **SEE 2.371** |
| G3 | Example 1, SEFA rails | BM_colA 0.057; m(crude steel) 1.042; SEFA crude steel 1.156; year 2027 (factor 0.95, CSCF 1) | **SEFA 1.261**; SEFA_2027 **1.198** |
| G4 | Example 1, certificates rails | 10,000 t; SEE direct 1.539 + indirect 0.028 (indirect from sintered-ore precursor); SEFA_2027 1.198 | EE 15,670; FAA 11,980; **3,690 certificates** (±1) |
| G5 | Example 2, certificates pipes | 100 t; SEE 1.783; SEFA 0.867 (=0.057 + 1.083×0.748); 2027 | FAA 82.4; **95.9 certificates** (±0.1) |
| G6 | Example 1, SEFA sheets & bars | 0.044 + 1.042×1.156; 0.038 + 1.042×1.156 | **1.248**; **1.242** |

**Known inconsistencies — do NOT use as tests, but log them in `docs/EC_EXAMPLE_NOTES.md`:** Example 2 Table 4-9 lists FeCr SEE 2.280 but its emissions (934,021 t for 331,213 t) imply 2.820; Table 4-10 gives pipes SEE 1.783 while 1.337 × 1.083 + 0.355 = 1.803. Pointing these out in the deck shows rigour.

---

## 6. Demo factory and synthetic documents

**"Shivalik Fasteners Pvt Ltd (SAMPLE — fictional)"**, Focal Point, Ludhiana, Punjab. Makes carbon-steel and stainless screws/bolts (CN 7318 15 xx) from purchased wire rod; heat-treats with piped natural gas; exports to **"Rhein Befestigungstechnik GmbH (SAMPLE)"**, Germany. Mirrors EC Example 3 at reduced scale so judges can check numbers against the guidance.

**Jan–Sep 2026 (provisional YTD) — keep these ratios exactly so SEE equals G1/G2:**

| Process | Product (AL) | Rod consumed | Scrap | Rod source & data status | Gas (NCV) |
|---|---|---|---|---|---|
| P1 carbon-steel screws | 1,275 t | 1,500 t | 225 t | "Northern Wire Rod Mills (SAMPLE)" — provides a **verified** statement: SEE 1.567, route BF-BOF, SEFA as per EC Example 1 bars (1.242), fictional verifier | 3.5 GJ/t × 1,275 t |
| P2 stainless screws | 615 t | 750 t | 135 t | "Indus Stainless Rods (SAMPLE)" — **no data yet** → default value for India for the rod's CN with 2026 mark-up (this is the Precursor Lever demo) | 3.5 GJ/t × 615 t |

Exports to the EU (by quarter, for cost): P1 ≈ 900 t, P2 ≈ 400 t split across Q1–Q3 2026.
Also show the "what if the stainless supplier sends verified data with SEE 1.783" toggle → SEE 2.371 (G2).

**Synthetic documents (`demo/`), 20–25 files, each with `ground_truth.json`:**
- 3–9 monthly PNG gas invoices from "Doaba City Gas (SAMPLE)": SCM, GCV, MMBtu, billing period — internally consistent with the GJ totals above.
- 3 monthly electricity bills from "Sutlej Power (SAMPLE)": kWh, MD kVA, period (recorded, not counted).
- Rod purchase invoices (both suppliers): CN code, grade, tonnes, date.
- Supplier verified emissions statement (P1 rod only).
- Production register (monthly tonnes by product) — semi-handwritten.
- Scrap log — **handwritten style with Hindi/Punjabi headings** (fonts: Noto Sans Devanagari, Noto Sans Gurmukhi, a handwriting font such as Kalam).
- Export invoices to the German buyer with CN codes and net mass.

**Generation:** HTML templates rendered to PNG/PDF with **Playwright**, then photo-like augmentation with Pillow/OpenCV (perspective skew 2–6°, shadow, JPEG noise, slight blur). Every document carries a visible **"SAMPLE — FICTIONAL"** watermark. Never use real company names, logos or utility branding. The same set is the **extraction eval dataset**.

---

## 7. Architecture

### 7.1 Stack
- **Backend:** Python 3.12, FastAPI, **google-adk 2.x** (Agent + Workflow graph + Task API human-in-the-loop), **google-genai** SDK using the **Interactions API** (`client.interactions.create`, `response_format` JSON schema, `generation_config.thinking_level`), Pillow/OpenCV, pandas + openpyxl (refdata parsing, Excel export), WeasyPrint (PDF from HTML), google-cloud-firestore, google-cloud-storage.
- **Frontend:** React + Vite + TypeScript, Tailwind CSS, Radix/shadcn components, Recharts (or visx), i18next, PWA (installable; camera capture via `accept="image/*" capture="environment"`).
- **One Cloud Run service** serving the API and the built frontend (one container → one cold start). `min-instances=1`, `cpu-boost`, region `asia-southeast1`. Gemini via **Gemini Enterprise Agent Platform** using the Cloud Run service account (no API keys in prod). Firestore (native) + Cloud Storage bucket. Secret Manager only if a secret is unavoidable. Cloud Logging + Cloud Trace.
- **CI:** GitHub Actions — lint, type-check, `pytest` (golden + unit), frontend build, `gitleaks`. Deploy with `gcloud run deploy --source .` (or Cloud Build) from `main`.

### 7.2 Models — use only these
| Use | Model |
|---|---|
| Classification, extraction, gap reasoning, explanations | `gemini-3.8-flash` |
| Blind second reader on crops, cheap classification | `gemini-3.5-flash-lite` |
| Rules copilot retrieval | File Search store with `models/gemini-embedding-2` |
| Voice notes (stretch) | `gemini-3.5-transcribe`; live interview `gemini-3.8-live` |
| Spoken summaries (stretch) | `gemini-3.8-flash-tts` |

**Forbidden:** any Gemini 2.x model, any Veo preview model (shut down 22 Oct 2026, mid-judging), `deep-research-pro-preview-12-2025` (shuts 23 Oct). **Do not set `temperature`, `top_p`, `top_k`** (deprecated 21 Jul 2026). Use high media resolution for document images (check the current parameter name in the docs).

### 7.3 ADK workflow (graph)

```
Intake ──► Classifier ──► Extractor ──► SecondReader ──► ControlChecks ──► GapFinder
                                                │                              │
                                     (mismatch) ▼                              ▼
                                       HumanReview (Task API HITL)      Calculator (tool, deterministic)
                                                                               │
                                                        Explainer (File Search citations) ──► Reporter
```

Agent contracts (all outputs are JSON validated with Pydantic; every agent emits timeline events):
- **Classifier** → `{doc_id, doc_type, language(s), period, confidence}`.
- **Extractor** → list of `Field{field_key, value_text, value_num, unit, box_2d, page, label, doc_id}` using a per-doc-type schema (e.g. gas invoice: period_start, period_end, scm, gcv_kcal_per_scm, mmbtu; rod invoice: supplier, cn_code, grade, tonnes, invoice_date; …).
- **SecondReader** → per field `{reading_value, reading_unit, agrees: bool, delta}` from the crop only.
- **ControlChecks** (code, not LLM) → list of `Check{name, formula, inputs, result, tolerance, status}`.
- **GapFinder** → required-field checklist per process and CN group; plain-language question per gap in the selected language; suggested document or person to ask.
- **Calculator** — the Section 5 engine as an ADK function tool; returns results with a full calculation tree (every node references evidence ids or refdata ids).
- **Explainer** → short narrative sections with File Search page citations; never introduces numbers that are not in the calculation tree.
- **Reporter** → PDF, Excel, verifier pack, buyer summary.

### 7.4 Evidence record (Firestore)
```
projects/{pid}
  documents/{doc_id}: {gcs_uri, doc_type, pages, uploaded_by, uploaded_at, hash}
  evidence/{eid}: {doc_id, page, field_key, value_num, unit, box_2d,
                   extractor_model, second_reader_model, second_reading, status,
                   approved_by, approved_at, notes}
  processes/{p}: {name, cn_group, al_t, precursors[...], fuels[...], period}
  runs/{run_id}: {events[...], started_at, finished_at, metrics}
  results/{run_id}: {calc_tree, see_by_process, sefa, certificates, costs_by_year, readiness}
  share_links/{token}: {summary_snapshot, created_at, expires_at}
refdata (in repo, versioned JSON + manifest; not in Firestore)
```

### 7.5 API (FastAPI)
`POST /projects` · `POST /projects/{pid}/documents` · `POST /projects/{pid}/runs` (starts workflow; returns run_id) · `GET /runs/{run_id}/events` (SSE) · `GET /projects/{pid}/evidence` · `PATCH /evidence/{eid}` (approve/edit) · `GET /projects/{pid}/results` · `GET /projects/{pid}/export/{pdf|xlsx|pack}` · `POST /projects/{pid}/share` · `GET /share/{token}` · `POST /copilot/ask` · `POST /demo/load` · `GET /golden` (runs golden tests, returns table) · `GET /healthz`.

### 7.6 Repo layout
```
backend/  app/ (main.py, api/, agents/, cbam/ engine, evidence/, exports/, i18n/)
          refdata/ (raw/, json/, manifest.json, build_refdata.py)
          tests/ (test_golden_ec.py, test_engine.py, test_units.py, test_refdata_manifest.py, test_two_reader.py)
          eval/ (run_extraction_eval.py, report.md)
frontend/ src/ (pages/, components/EvidenceLens, AgentTimeline, MoneyChart, GapChecklist, …)
demo/     templates/, generate_docs.py, out/, ground_truth.json
docs/     BUILD_BRIEF.md, regulation/, ARCHITECTURE.md, EC_EXAMPLE_NOTES.md, DEMO_SCRIPT.md, DECK_NOTES.md
Dockerfile · .github/workflows/ci.yml · README.md · LICENSE (MIT) · .env.example
```

---

## 8. UX and visual design spec

- **Feel:** calm, audit-grade, trustworthy — closer to financial software than a consumer app. Strong typography, generous white space, no stock illustrations, no emoji.
- **Colour carries status only:** green = verified by two readers, amber = needs or got human approval, red = missing / default used. Neutral ink-on-paper palette otherwise; one accent colour for primary actions.
- **Numbers:** tabular figures; units always shown; ₹ and € side by side; "per tonne" and "per year".
- **Signature components:**
  - **Evidence Lens** (side sheet): source image with animated highlight box → formula → two-reader result → approver → timestamp → "open full document".
  - **Agent Timeline**: vertical list of agent steps with icons, duration, model name, collapsible details.
  - **Money on the table**: line or bar chart of buyer cost per tonne, actual vs default, 2026–2034, with the gap labelled in € and ₹; footnote with the formula and source.
  - **Contribution bar**: own process vs each precursor (shows the ~90% precursor share).
  - **Readiness ring**: % of SEE-relevant inputs verified/approved.
- **Mobile:** capture screen and gap checklist are fully usable on a 360-px-wide Android; tap targets ≥ 44 px.
- **Language:** English default; Hindi and Tamil toggles (Vietnamese if time). Regulatory terms stay in English with a local-language explanation.
- **Empty states:** never blank — always offer "Load sample factory".
- **Accessibility:** WCAG AA contrast, keyboard navigable, alt text on images, `aria-live` for timeline updates.

---

## 9. Quality, evaluation and metrics

- **Golden tests (Section 5.6)** must pass in CI.
- **Unit tests** for unit conversions, Decimal rounding, mark-ups, schedules, floor-at-zero, precursor default fallback, refdata manifest integrity.
- **Extraction eval** (`backend/eval/run_extraction_eval.py`) on the synthetic set: field-level accuracy, two-reader agreement rate, human-review rate, mean time per document. Write results to `backend/eval/report.md` and expose them on an in-app "Metrics" page. Targets: **≥ 95% field accuracy**, **< 2 min** from 25 uploads to report on Cloud Run. Report the real numbers even if below target.
- **Agent eval:** add at least 5 `adk eval` cases (e.g. a skewed scrap log, a Hindi-headed register, a bill with two periods, a missing supplier statement, a mismatched unit).
- **Explainer guard:** a test that fails if the Explainer output contains a number not present in the calculation tree.

---

## 10. Deployment and demo safety
- Cloud Run: `min-instances=1`, concurrency tuned, request timeout ≥ 300 s for runs (use background tasks + SSE), `asia-southeast1`.
- Billing budget alert; per-project rate limit on runs; cache demo results in Firestore/GCS.
- Health check page lists model names, refdata versions and their dates.
- Before every deploy: run golden tests, run a smoke test that loads the sample factory and opens the buyer link from a logged-out browser.
- Keep the deployed version **frozen from Oct 18 to Nov 6** except for critical fixes.

---

## 11. Submission assets Claude Code must produce
- **README.md**: one-paragraph pitch, the problem with sourced numbers, demo link, 60-second "try it" steps, screenshots/GIF, architecture diagram (Mermaid), Google Cloud services used, how the two-reader check works, golden-test table, eval metrics, local setup, deploy steps, limitations and "not a substitute for an accredited verifier", license.
- **docs/ARCHITECTURE.md** with the Mermaid diagram and agent contracts.
- **docs/DEMO_SCRIPT.md**: a 3-minute video script with timestamps:
  0:00 hook (Ludhiana owner, German buyer asks for CBAM data or a price cut; 25–30k MSMEs at risk) → 0:20 capture → 0:45 Evidence Lens + two-reader + one human approval → 1:15 Precursor Lever + Money on the table + myth-buster → 1:45 verifier pack, buyer link, rules copilot with page citation → 2:10 architecture → 2:35 proof (EC example reproduced, eval metrics, timing) → 2:55 scale (downstream expansion ~180 product categories by 2028; UK CBAM 2027).
- **docs/DECK_NOTES.md**: the real numbers from eval and golden tests, ready to paste into a 10-slide deck.

---

## 12. Phased plan (today is Sun 11 Oct 2026; submit by Sun 18 Oct)

Stop at the end of each phase: report what was built, test results, open risks, and wait for `go`.

| Phase | Date | Deliverables | Exit criteria |
|---|---|---|---|
| **0 — Foundations** | Sun 11 Oct | GCP setup from 0.1 verified (billing linked, APIs, Firestore, bucket, service account); repo scaffold, CI, Dockerfile, `/healthz` deployed to Cloud Run; download EC PDFs + Excel files; `build_refdata.py` parses default values, benchmarks, schedules into JSON + manifest; golden tests written (red) | Live URL returns health JSON; refdata manifest test passes |
| **1 — Engine + demo data** | Mon 12 Oct | CBAM engine with calculation tree; golden tests green; synthetic document generator + ground truth; Firestore/GCS wiring | G1–G6 green; 20+ sample docs generated |
| **2 — Agents + Evidence Lens** | Tue 13 Oct | ADK workflow: Classifier, Extractor (box_2d), SecondReader, ControlChecks; SSE timeline; review UI; Evidence Lens | Sample docs processed end-to-end on Cloud Run; every value has a region |
| **3 — Gaps, money, outputs** | Wed 14 Oct | GapFinder; Precursor Lever + supplier letter (EN/HI); Money on the table + myth-buster; PDF/Excel/pack exports; buyer link; demo mode | Full 3-step flow works from "Load sample factory" |
| **4 — Copilot + eval** | Thu 15 Oct | File Search rules copilot with page citations; extraction eval + metrics page; `adk eval` cases; fix top failures | Eval report written; 5 scripted copilot questions cite pages |
| **5 — Polish + freeze** | Fri 16 Oct | Hindi/Tamil UI; visual polish; performance; accessibility pass; stretch X1 only if all green | Feature freeze; smoke test passes logged-out on mobile and desktop |
| **6 — Story assets** | Sat 17 Oct | README, ARCHITECTURE, DEMO_SCRIPT, DECK_NOTES, screenshots/GIF | Human records video and builds deck |
| **Submit** | Sun 18 Oct (by midday IST) | Final deploy check; gitleaks clean; tag `v1.0-submission` | All four submission links verified from a logged-out browser |

---

## 13. Working rules for Claude Code
1. **Verify before you code.** SDKs changed a lot in 2026 (Interactions API, ADK 2.x, Agent Platform naming). Check the current docs on ai.google.dev, the ADK docs and cloud.google.com before writing any SDK call; do not rely on memory.
2. **The LLM never computes a compliance number.** Numbers enter the engine only from evidence records or refdata.
3. **Never invent regulatory values.** Load from official files; anything else is an explicit, visible assumption.
4. **Keep `main` deployable.** Small commits, conventional commit messages, tests before merge.
5. **No secrets in git.** `.env.local` is gitignored; production uses the service account; run gitleaks in CI.
6. **Fictional data only.** No real companies, people, logos, bills or employer material of any kind.
7. **Ask before** changing the architecture, adding a paid service, deleting data, or anything irreversible.
8. **Report honestly.** If a test or metric misses its target, say so and propose the fix; do not hide failures.
9. When a guidance document and this brief disagree, **the guidance document wins** — note the difference in `docs/EC_EXAMPLE_NOTES.md` and tell me.
10. Optimise for the **demo path first** (sample factory, end to end, deployed), then generality.

---

## 14. Definition of done (checked on Sat 17 Oct)
- [ ] Live Cloud Run URL loads the sample factory in < 5 s and completes a live run in < 2 min.
- [ ] Golden tests G1–G6 pass in CI and on the in-app badge page.
- [ ] Every number in the report opens the Evidence Lens with a highlighted source region or a refdata citation.
- [ ] Two-reader statuses visible; at least one amber value demonstrates human approval.
- [ ] Precursor Lever shows the contribution split and generates the supplier letter in English and Hindi.
- [ ] Money on the table shows actual vs default cost per tonne in € and ₹ for 2026–2034 with the myth-buster note.
- [ ] PDF, Excel and verifier-pack exports download and open.
- [ ] Buyer link works logged-out and shows no plant-level inputs.
- [ ] Rules copilot answers the 5 scripted questions with page citations.
- [ ] Eval metrics page shows real numbers from the synthetic set.
- [ ] Hindi and Tamil UI toggles work on the main flow.
- [ ] README, ARCHITECTURE, DEMO_SCRIPT, DECK_NOTES complete; repo public; gitleaks clean.
- [ ] No Gemini 2.x / Veo preview models anywhere; no deprecated sampling parameters.