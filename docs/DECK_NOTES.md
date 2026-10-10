# Deck notes — real numbers, ready to paste (10 slides)

All numbers come from the running app on the fictional sample factory (Jan–Sep 2026,
provisional) and from the golden tests. Re-check the eval slide after the live Gemini run.

## 1. Title
**Pramaan — CBAM proof from a phone photo.** Agentic AI copilot that turns photos of bills,
invoices and production logs into verifier-ready EU CBAM data for small steel-goods exporters.
Team Innovative Warriors · Google Cloud AI Builder Cup 2026 · Manufacturing.

## 2. Problem
* EU CBAM definitive phase since **1 Jan 2026**: importers pay for embedded emissions; without
  verified data they pay on **default values + 10 % (2026), 20 % (2027), 30 % (2028+)** mark-up
  (EC Guidance No. 3, p. 115).
* **25,000–30,000** Indian MSMEs at risk; EU = **32–45 %** of India's steel exports; price cuts of
  **15–22 %** may be needed (Business Standard via Vision IAS, 29 Jan 2026).
* Compliance ≈ **₹15–20 lakh per MSME**; Centre working on a 90 % reimbursement scheme
  (The Indian Express, Jun 2026).
* Verification bottleneck is pushing importers onto defaults (EFDA via Eurometal).

## 3. Who
Owner/accountant in Ludhiana (phone-first, Hindi/Punjabi), EU importer (declarant), accredited
verifier, shop-floor supervisor.

## 4. Solution — 3 steps
Capture → Close gaps → Report. 24 photos (gas bills, rod invoices, handwritten Hindi/Punjabi
register and scrap log, export invoices) → 213 values, each with its region on the page.

## 5. Gen AI core (40 % of the score)
* **ADK 2.11 Workflow** graph: Intake → Classifier → Extractor → SecondReader → (mismatch →
  HumanReview) → ControlChecks → GapFinder (+ Calculator FunctionTool) → Explainer → Reporter.
* **Gemini 3.8 Flash** (Interactions API, JSON schema, high media resolution) extracts every value
  with `box_2d`; **Gemini 3.5 Flash-Lite** re-reads **only the crop**, blind.
* **The LLM never does arithmetic**: Decimal engine; Explainer guard rejects numbers that are not in
  the calculation tree.
* Rules copilot answers with **page citations** from the EC guidance.

## 6. USP 1–2: Evidence Lens + two readers
* SEE 2.040 → formula → **38 values from 12 documents** → the highlighted region on the photo,
  both readings, approver and timestamp.
* Replay of the sample: **212 / 213 values agree**; the 1 disagreement is a handwritten correction
  (13.4 struck out, 15.4 written) — the monthly mass balance (rod 85.4 − produced 70.0 = 15.4)
  supports reader 1; the owner approves it.

## 7. USP 4–5: Precursor Lever + Money on the table (sample factory)
| | Carbon-steel bolts (CN 7318 15 82) | Stainless bolts (CN 7318 15 75) |
|---|---|---|
| SEE (t CO2/t) | **2.040** (full precision 2.0399 = EC Example 3) | **8.889** (rod on India default 6.480 + 10 %) |
| Rod share of SEE | 90 % | 98 % |
| SEFA / SEFA 2026 | 1.499 / 1.462 | 1.532 / 1.494 |
| Certificates for Q1–Q3 2026 imports | 520.4 for 900 t | 2,958.2 for 400 t |
| Buyer cost 2026 (€/t), actual data | **€45** | €576 |
| Buyer cost 2026 (€/t), EU defaults | **€386** | **€402** |
| Money on the table 2026 | **€341/t = ₹36,994/t** (≈ €409,545/yr at current volumes) | actual data worse than default → buyer declares defaults |
| If the rod supplier sends verified data | — | SEE **2.371** (= EC G2), cost **€97/t** (−€306/t vs defaults) |
* 2026 price = Q1 €75.36, Q2 €75.28, Q3 €82.32 weighted by export quarters = €77.85.
* **Myth-buster**: "2.5 % in 2026" is wrong — EC Example 1: 3,690 certificates on 15,670 t
  embedded = **23.5 %**, not 5 %.

## 8. Proof
* **Golden tests G1–G8 pass** (EC Guidance 5d, 14 Aug 2026): Example 3 SEE 2.039 / 2.371;
  Example 1 SEFA 1.261 → 1.198 (2027) and **3,690 certificates**; Example 2 **95.9
  certificates**; SEFA sheets/bars 1.248/1.242; screws 1.499/1.159; benchmarks re-read from
  the official file. Runs live on the "EC proof" page.
* Inconsistencies found in the EC examples: FeCr SEE 2.280 vs implied 2.820; pipes 1.783 vs
  1.803 (docs/EC_EXAMPLE_NOTES.md).
* Official data, not hand-typed: 7 refdata files parsed from EC files with SHA-256 manifest;
  CSCF = 100 % for 2026–2030 is official (Decision (EU) 2026/1862).
* **Extraction eval (24 docs, 213 fields)**: live Gemini numbers → fill from
  `backend/eval/report.md` after the live run (field accuracy target ≥ 95 %, < 2 min).
  Harness self-check (replay): 100 % / 1.3 s — not a model score.
* 102 backend tests (golden, refdata manifest, engine, two-reader, API, agent scenarios) + Firestore-emulator test + logged-out UI smoke (desktop + 360 px phone) in CI; ruff + mypy clean; gitleaks clean.

## 9. Architecture (Google Cloud)
Cloud Run (asia-southeast1, one container, min-instances 1) · Gemini on Agent Platform (global)
· ADK 2.x · Firestore · Cloud Storage · Cloud Logging/Trace · GitHub Actions CI with gitleaks.
Sample factory loads in **0.1–0.3 s** (snapshot restore; Firestore emulator), each visitor gets a private copy (target < 5 s).

## 10. Impact & scale
Built for JAPAC (Vietnam, China, Korea, Indonesia face the same defaults); Commission proposal to
extend CBAM downstream (~180 product categories from 2028); UK CBAM from 2027. Pramaan is not a
substitute for an accredited verifier — it makes verification fast and cheap.
