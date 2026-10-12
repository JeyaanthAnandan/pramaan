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
* Theme fit (Manufacturing: Intelligent Operations & Industrial Efficiency): operational data
  (bills, registers, scrap logs) → insights (SEE per product, where it comes from) →
  recommendations ("What to do next", with € attached) → actions (supplier letter EN/HI, buyer
  link, operations levers).
* Own factory: product lines typed (CN codes checked live against the official files) or
  proposed by the ProductLines agent from export and rod invoices; private project with a
  passcode (hash only stored).
* Design (UX 10 % and the Best UI/UX award): the report answers first (€409,545 a year saved for the
  buyer, +€163,002 within reach, 1 of 2 lines ready); motion only where it explains — numbers settle
  into place, reader 1 → reader 2 → verdict, a reading beam on the photo, an *Approved* stamp, the
  agent timeline filling as agents finish; reduced-motion safe, 360 px, light/dark, 4 languages,
  axe 0 WCAG A/AA violations.

## 5. Gen AI core (40 % of the score)
* **ADK 2.11 Workflow** graph: Intake → Classifier → **ProductLines** → Extractor → SecondReader →
  (mismatch → HumanReview) → ControlChecks → GapFinder (+ Calculator FunctionTool) → Explainer →
  Reporter.
* **ProductLines agent**: Gemini 3.8 Flash reads export and steel-input invoices and proposes the
  product lines (one per exported CN code, linked to its rod); code rejects any code that is not
  an iron & steel good with a default value and benchmarks; the owner confirms.
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
| **What the buyer pays** (the cheaper path) | **€45** on your data | **€402** on the EU default |
| Buyer's cost, Q1–Q3 2026 imports | €40,489 (vs €347,482 on defaults) | €161,090 on defaults (€230,572 on your data) |
| Money on the table 2026 | **€341/t = ₹36,994/t** (≈ €409,545/yr at current volumes) | actual data worse than default → buyer uses the default |
| If the rod supplier sends verified data | — | SEE **2.371** (= EC G2), cost **€97/t** (−€306/t, ≈ €163,000/yr) |
* "What to do next" (top of the report): (1) ask Indus Stainless Rods for verified data, (2)
  approve one value, (3) send the carbon-steel data to the buyer.
* **Operations levers** (same engine): stainless with EC Example 2 rod data + electric heat
  treatment → SEE 8.889 → 2.174, buyer €402 → **€81/t**, 2,870 GJ gas a year no longer burned.
  Carbon bolts, scrap 15 % → 10 % of rod → SEE 2.040 → 1.937 and **111 t of rod saved a year**,
  but the 2026 buyer cost moves only €45.0 → €43.2/t because SEFA falls with the rod too (2034:
  €167.9 → €159.5/t). Gas 3.5 → 3.0 GJ/t → 850 GJ a year saved.
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
* 126 backend tests (golden, refdata manifest, engine, two-reader, API, agent scenarios, product-line set-up with a scripted ProductLines model, privacy, one buyer cost, levers) + Firestore-emulator test + logged-out UI smoke (desktop + 360 px phone, incl. own project + passcode unlock) in CI; ruff + mypy clean; gitleaks clean; axe: 0 WCAG A/AA violations (light + dark); translations hi/ta/vi complete (checked in CI).

## 9. Architecture (Google Cloud)
Cloud Run (asia-southeast1, one container, min-instances 1) · Gemini on Agent Platform (global)
· ADK 2.x · Firestore · Cloud Storage · Cloud Logging/Trace · GitHub Actions CI with gitleaks.
Live: https://pramaan-646454690406.asia-southeast1.run.app
Sample factory loads in **0.1–0.3 s** locally (snapshot restore; Firestore emulator) and **2.0–2.2 s** end to end in a
browser on the live service (warm instance), each visitor gets a private copy (target < 5 s).

## 10. Impact & scale
Built for JAPAC (Vietnam, China, Korea, Indonesia face the same defaults); Commission proposal to
extend CBAM downstream (~180 product categories from 2028); UK CBAM from 2027. Pramaan is not a
substitute for an accredited verifier — it makes verification fast and cheap.
