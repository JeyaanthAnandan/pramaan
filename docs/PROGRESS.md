# Progress log (for the team and for resuming work)

_Last updated: 2026-10-12 IST, night (deployed to Cloud Run: https://pramaan-646454690406.asia-southeast1.run.app; `main` pushed to https://github.com/JeyaanthAnandan/pramaan (public))._

## 2026-10-12 (night) — deployed to Cloud Run

* **Live:** https://pramaan-646454690406.asia-southeast1.run.app (service `pramaan`, asia-southeast1, revision `pramaan-00002-shx`, git `3e1edf9` + the
  health fix below). Billing linked to `copilot-manufacturing`; budget **₹2,000/month** on this project
  with e-mail alerts at 50 / 90 / 100 % of actual spend and 100 % of forecast.
* `scripts/gcp_setup.sh` done: APIs, Firestore (Native, asia-southeast1), private bucket
  `copilot-manufacturing-pramaan`, service account `pramaan-run` (aiplatform.user, datastore.user,
  logging.logWriter, cloudtrace.agent + objectAdmin on the bucket). Both models answer at `global`
  (`gemini-3.8-flash`, `gemini-3.5-flash-lite`: HTTP 200).
* **Running with `min-instances 0`** to keep idle cost near zero until judging; the first request after a
  quiet spell has a cold start. Before judging run plain `scripts/deploy.sh` (default 1 keeps it warm).
* **Bug fixed on the way:** Cloud Run's front end reserves some paths ending in `z`, so `GET /healthz`
  returned 404 on the live service: the deploy smoke test failed and the SPA's health query (Gemini status
  on Capture, Setup, Voice, Architecture) never loaded. Added `/api/health` (same handler); SPA and
  `deploy.sh` use it; `/healthz` stays for local runs and CI.
* `scripts/deploy.sh` smoke test passes on the live service: health (store `firestore`,
  `gemini_configured: true`), sample load, buyer link, golden `all_pass: true`, and `scripts/ui_smoke.py`
  logged-out on desktop + 360 px phone (sample 2.0–2.2 s, approval, buyer link, proof + copilot, own project +
  passcode on a second device). This is the first run of the **Firestore store** outside the emulator.
* **Rules copilot, live:** the 5 scripted questions were answered by Gemini 3.8 Flash (`grounded`) in
  2.6–3.6 s; 4 of 5 carry validated page citations, none invalid. "Does electricity count for my screws?"
  came back **without a citation** and with a hedged answer (retrieval did not surface the page that says
  only direct emissions count for iron & steel) — worth a look.
* Not done yet: the live extraction eval / demo capture (`--mode live --capture`), so "Load sample
  factory" still replays the bundled ground truth and says "Gemini not used".


## 2026-10-12 (evening) — UI and motion pass (second mock judging, UX focus)

* **Answer-first report**: a verdict panel opens the report (your data saves the buyer €409,545 a
  year; +€163,002 within reach if Indus sends data; 1 of 2 product lines ready), with the provisional
  notice as its footer; a sticky "on this page" bar follows the section in view; product cards draw
  the buyer's two costs to scale and mark the one the buyer pays.
* **Motion with meaning** (`motion` 12.43.0, `src/lib/motion.tsx`): numbers count up the first time
  they are seen and tween when inputs change; reader 1 → reader 2 → verdict (✓ or ≠, the mass balance
  lights up the reading it supports); the photo glides to the value, the page around it dims and a
  reading beam sweeps the box; approving presses an *Approved* stamp, folds the card away and a toast
  confirms; the lens slides forward and back with a path trail; steps and segmented controls have a
  sliding highlight; the agent timeline fills as agents finish and documents show a scanner line while
  they are read; the money chart draws 2026 → 2034 and morphs when the product or what-if changes; the
  levers chart adds the scenario line only once something changed; landing hero tells the two-reader
  story with pause / step controls, and a pipeline strip shows one photo's path; EC proof checks tick
  in turn on every run; skeletons instead of spinners; theme switch cross-fades.
* Reduced motion: numbers appear final, nothing slides (MotionConfig `reducedMotion="user"` + CSS).
* Fixes found on the way: long supplier names pushed the phone layout sideways in Tamil and Vietnamese
  (badges now wrap); buyer-page list markup, monitoring-plan contrast and the letter dialog's scroll
  area (keyboard) — all axe findings on screens not scanned before.
* Judging robustness: sample loads per address raised from 40 to 120 an hour (a room of judges can
  share one office address); if the limit is ever hit, the landing page reopens the visitor's earlier
  sample copy instead of showing an error.
* Dependencies: `react-router-dom` 6.30.6, `vite` 5.4.21, `postcss` 8.5.28 (security fixes, patch
  level). Remaining `npm audit` items are dev tooling that needs a major upgrade (Tailwind 4, Vite 8).
  First-load JS is 175 KB gzip (+46 KB for `motion`).

Checks: backend 127 passed + 1 opt-in skipped; ruff, mypy clean; frontend `npm ci`, `check:i18n` and
build clean; `scripts/ui_smoke.py` passes (desktop + 360 px); axe: 0 WCAG 2.1 A/AA violations on every
page, the Evidence Lens and the letter dialog, light and dark, and on the phone; no horizontal scroll
at 360 px in EN/HI/TA/VI; README screenshots and the Evidence Lens GIF regenerated.


## 2026-10-12 — fixes from a mock judging against the official rubric

A mock judging against the official rubric (aibuildercup.com: Technical merit & Gen AI 40 %,
Problem & impact 25 %, Innovation 25 %, UX 10 %) put the build at about 68/100 *if submitted
as it was*, mainly because nothing is deployed and every screen said "Gemini not used". Done since,
without credentials:

* **One buyer cost everywhere.** The engine also costs the 2026 imports on EU default values and
  records the cheaper path; report cards, Precursor Lever, "What to do next", levers, PDF and Excel
  agree (stainless bolts: the buyer uses the EU default, €402/t, until the rod data arrives).
* **"What to do next"** at the top of the report (deterministic, with € attached), in-page nav,
  passed checks collapsed, plain-language text clamped.
* **Readiness per product line**: "1 of 2 product lines can be declared on actual data" next to
  the 99 % input score.
* **Operations levers**: scrap rate and gas per tonne next to supplier data and electric heating,
  with rod and gas saved per year and an honest note that SEFA falls with the rod too.
* **Own factory set-up**: product lines typed with live CN checks, or proposed by the new
  **ProductLines** ADK node / `POST /product-lines/suggest` (Gemini 3.8 Flash over export and
  rod invoices; every code validated against refdata; owner confirms). Reporting period and
  country editable. Tested with a scripted model (`tests/test_setup_and_access.py`).
* **Private projects**: passcode (hash only), project-scoped HttpOnly cookie, unlock screen,
  rate-limited unlock; samples stay open.
* Translations complete for hi, ta and vi (`npm run check:i18n`, in CI); plural forms fixed.
* Bug found by the extended smoke test and fixed: opening the supplier letter from "What to do
  next" unmounted the dialog.
* README / ARCHITECTURE / DEMO_SCRIPT / DECK_NOTES and screenshots + GIF refreshed for the
  "Mill Certificate" theme.

Checks: backend 126 passed + 1 opt-in skipped; ruff, ruff format, mypy clean; frontend build
clean; `scripts/ui_smoke.py` passes (desktop + 360 px phone, incl. own project + passcode on a
second device); axe: 0 WCAG A/AA violations on report, gaps, capture, own-project capture (light
and dark).

Still needs the team (in order): gcloud sign-in as sudarssan73@gmail.com + billing → setup,
live eval (`--mode live --capture`), deploy; record the video and build the deck from the live
run; one conversation with a real exporter, consultant or verifier for a quote; photograph ~10
printed sample documents on a phone (crumpled, bad light) as a "hard" eval set.

## Status by phase

| Phase | State | Notes |
|---|---|---|
| 0 Foundations | **Done** | Repo, CI, Dockerfile, health check, EC PDFs + Excel downloaded, refdata pipeline + manifest test green. GCP: billing + budget, APIs, Firestore, bucket, service account, Cloud Run deploy with smoke test (2026-10-12 night). |
| 1 Engine + demo data | **Done** | Decimal engine with calculation tree; golden tests G1–G8 green; 24 synthetic photographed documents + `ground_truth.json` (213 fields with exact regions). |
| 2 Agents + Evidence Lens | **Done (replay-verified)** | ADK 2.11 workflow (Classifier, Extractor, SecondReader, HumanReview branch, ControlChecks, GapFinder + Calculator tool, Explainer, Reporter), SSE timeline, review UI, Evidence Lens. Live Gemini path is exercised in CI with a scripted stand-in (`tests/test_agent_scenarios.py`) but **has not yet run against real Gemini** (no credentials). |
| 3 Gaps, money, outputs | **Done** | GapFinder, Precursor Lever + EN/HI letter + status tracking, Money on the table 2026–2034 with what-if and myth-buster, PDF/Excel/verifier pack, buyer link, demo mode. |
| 4 Copilot + eval | **Done; live eval pending** | Copilot with page citations (retrieval works offline; grounded Gemini answers verified live on Cloud Run). Eval harness + metrics page + 5 agent scenarios (CI) + 5 `adk eval` cases. **Live eval not run** (needs Gemini). |
| 5 Polish | **Done** | Hindi, Tamil and Vietnamese UI (complete, CI-checked), light/dark, 360 px mobile without overflow, accessibility basics (labels, focus, aria-live, keyboard chart). |
| 6 Story assets | **Done (drafts)** | README, ARCHITECTURE, DEMO_SCRIPT, DECK_NOTES, EC_EXAMPLE_NOTES, screenshots. Fill live eval numbers after the live run. |

Tests: backend `pytest` 127 passed (golden, refdata manifest, engine, two-reader, API end-to-end, agent scenarios) + 1 opt-in Firestore-emulator test (passes against the local emulator); ruff + mypy clean; frontend `tsc` + Vite build clean; gitleaks clean. The Docker image (amd64) passes `scripts/ui_smoke.py` end to end in a logged-out browser on desktop and a 360 px phone: sample load 0.1-0.2 s, Evidence Lens to photo, approval, Hindi supplier letter, buyer link without plant data, EC proof 8/8, copilot citations.

Robustness for judging: "Load sample factory" gives every visitor a **private copy** of the sample (stale copies are cleaned up), restored from a captured run snapshot (`demo/cache/replay_run.json` now; `live_run.json` takes precedence once captured with Gemini).

## What the team needs to do next

Done: gcloud sign-in, billing + budget alert, public GitHub repo, `scripts/gcp_setup.sh`, first deploy.

1. `backend/eval/run_extraction_eval.py --mode live --capture` (real Gemini metrics + live demo cache; paid
   Gemini calls), then `MIN_INSTANCES=0 scripts/deploy.sh` so "Load sample factory" serves the live run, and
   fill the live row in README / DECK_NOTES / DEMO_SCRIPT from `backend/eval/report.md`.
2. Before judging (and before recording the video): plain `scripts/deploy.sh` → min-instances 1, no cold start.
3. Record the video and build the deck from the live service.

## Decisions needed from the team

* **File Search store** (brief S1) works only with a Gemini Developer API key (google-genai: file-search stores are not available in Agent Platform mode). Current copilot: page-level retrieval + Gemini on Agent Platform with validated page citations (no keys). Option: add a Gemini API key in Secret Manager and switch the copilot to a File Search store. Adding a secret/paid service needs your approval (brief rule 7).
* **CSCF 2026–2030 is official = 1.0** (Decision (EU) 2026/1862), not an assumption as the brief said — implemented per the official source (docs/EC_EXAMPLE_NOTES.md §2a).

## Known gaps / next steps

* Run live Gemini once; inspect extraction misses in `backend/eval/report.md`; tune prompts if field accuracy < 95 %.
* Firestore store: exercised on the deployment by the smoke tests (sample copies, approval, buyer link, passcode); local runs use the in-memory store.
* Copilot retrieval misses the page for "Does electricity count for my screws?" (answer has no citation).
* Stretch X1 (vernacular voice) is implemented: mic button on monthly gap rows → `gemini-3.5-transcribe` (Hindi/Punjabi/English; Tamil via Gemini 3.8 Flash audio) → Gemini reads the stated quantity → evidence with audio + transcript, amber until a person confirms. Tested with a scripted model in CI; **needs live Gemini to try for real**. Stretch X2 (decarbonisation what-if) is implemented: rod supplier SEE/SEFA (EC example presets) and gas vs electric heat treatment, computed by the engine (`POST /api/projects/{pid}/whatif`). X3 (Annex IV operator-report alignment) is **not done on purpose**: the official Annex IV text/template could not be retrieved (EUR-Lex blocks automated access) and the brief forbids claiming alignment without verifying it.
* Freeze the deployed version from 18 Oct; tag `v1.0-submission`.

## Definition of done (brief section 14)

| Item | State |
|---|---|
| Live Cloud Run URL: sample < 5 s, live run < 2 min | **Live:** https://pramaan-646454690406.asia-southeast1.run.app. Sample 2.0–2.2 s end to end in the browser (warm); live run timing pending (live eval not captured) |
| Golden tests G1–G6 in CI and on the badge page | Done (G1–G8) |
| Every number opens the Evidence Lens (region or refdata citation) | Done (API test asserts every leaf has a source; evidence leaves have regions) |
| Two-reader statuses visible; an amber value shows human approval | Done |
| Precursor Lever: contribution split + supplier letter EN/HI | Done |
| Money on the table € and ₹ 2026–2034 + myth-buster | Done |
| PDF, Excel, verifier pack download and open | Done (PDF rendered, XLSX opened in LibreOffice, pack contents tested) |
| Buyer link logged-out, no plant-level inputs | Done (API test + UI smoke) |
| Rules copilot: 5 scripted questions with page citations | Live on Cloud Run: 5/5 answered by Gemini 3.8 Flash (grounded, 2.6–3.6 s); 4/5 with validated page citations, 1 without |
| Eval metrics page with real numbers | Harness + page done; **live Gemini numbers pending** (replay self-check shown, labelled) |
| Hindi and Tamil UI on the main flow | Done (hi, ta, vi complete; checked in CI) |
| README, ARCHITECTURE, DEMO_SCRIPT, DECK_NOTES; repo public; gitleaks clean | Done (public: https://github.com/JeyaanthAnandan/pramaan) |
| No Gemini 2.x / Veo preview; no deprecated sampling params | Done (tests/test_compliance.py) |

## Useful commands

```bash
cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/pytest -q          # all tests
cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/uvicorn app.main:app --port 8080   # app on :8080
cd frontend && npm run build                                                              # SPA → frontend/dist
backend/.venv/bin/python demo/generate_docs.py                                            # regenerate sample docs
cd backend && .venv/bin/python -I refdata/build_refdata.py                                # rebuild refdata + manifest
docker build -t pramaan:local . && docker run -p 8080:8080 -e GEMINI_VERTEX_READY=0 pramaan:local
```
