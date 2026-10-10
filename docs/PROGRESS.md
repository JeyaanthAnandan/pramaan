# Progress log (for the team and for resuming work)

_Last updated: 2026-10-11 (overnight autonomous build session)._

## Status by phase

| Phase | State | Notes |
|---|---|---|
| 0 Foundations | **Done locally; GCP blocked** | Repo, CI, Dockerfile, `/healthz`, EC PDFs + Excel downloaded, refdata pipeline + manifest test green. gcloud SDK 588 installed; project/region set. **Blocked:** no signed-in gcloud account and billing status unknown → APIs, Firestore, bucket, service account, deploy not done. |
| 1 Engine + demo data | **Done** | Decimal engine with calculation tree; golden tests G1–G8 green; 24 synthetic photographed documents + `ground_truth.json` (213 fields with exact regions). |
| 2 Agents + Evidence Lens | **Done (replay-verified)** | ADK 2.11 workflow (Classifier, Extractor, SecondReader, HumanReview branch, ControlChecks, GapFinder + Calculator tool, Explainer, Reporter), SSE timeline, review UI, Evidence Lens. Live Gemini path is exercised in CI with a scripted stand-in (`tests/test_agent_scenarios.py`) but **has not yet run against real Gemini** (no credentials). |
| 3 Gaps, money, outputs | **Done** | GapFinder, Precursor Lever + EN/HI letter + status tracking, Money on the table 2026–2034 with what-if and myth-buster, PDF/Excel/verifier pack, buyer link, demo mode. |
| 4 Copilot + eval | **Done; live numbers pending** | Copilot with page citations (retrieval works offline; grounded Gemini answer when configured). Eval harness + metrics page + 5 agent scenarios (CI) + 5 `adk eval` cases. **Live eval not run** (needs Gemini). |
| 5 Polish | **Mostly done** | Hindi + Tamil + partial Vietnamese UI, light/dark, 360 px mobile without overflow, accessibility basics (labels, focus, aria-live, keyboard chart). |
| 6 Story assets | **Done (drafts)** | README, ARCHITECTURE, DEMO_SCRIPT, DECK_NOTES, EC_EXAMPLE_NOTES, screenshots. Fill live eval numbers after the live run. |

Tests: backend `pytest` (golden, refdata manifest, engine, two-reader, API end-to-end, agent scenarios) all green; ruff + mypy clean; frontend `tsc` + Vite build clean; Docker image builds and passes a container smoke test (health, sample load ≈ 2.4 s under emulation, PDF, verifier pack, golden, SPA, copilot).

## What the human needs to do (morning checklist)

1. **Sign in to gcloud as `sudarssan73@gmail.com`** (browser): in this terminal run
   `! gcloud auth login` and `! gcloud auth application-default login`
   (the SDK is at `/opt/homebrew/share/google-cloud-sdk/bin` — add it to PATH or use the full path).
2. **Link billing + budget alert** on `copilot-manufacturing` (Console → Billing; budget e.g. ₹2,000 with 50/90/100 % alerts).
3. **GitHub:** create the **public** repo (e.g. `pramaan`) and push — I did not publish anything. Suggested:
   `gh repo create <owner>/pramaan --public --source . --push` (review first; CI runs gitleaks).
4. Then say "gcloud ready" and the next session will run:
   * `scripts/gcp_setup.sh` (APIs, Firestore asia-southeast1, private bucket, `pramaan-run` SA with 5 roles, model availability check at `global`)
   * `backend/eval/run_extraction_eval.py --mode live --capture` (real Gemini metrics + live demo cache)
   * `scripts/deploy.sh` (golden gate → Cloud Run → smoke test) and update README/DECK_NOTES with the live URL and real metrics.

## Decisions needed from the team

* **File Search store** (brief S1) works only with a Gemini Developer API key (google-genai: file-search stores are not available in Agent Platform mode). Current copilot: page-level retrieval + Gemini on Agent Platform with validated page citations (no keys). Option: add a Gemini API key in Secret Manager and switch the copilot to a File Search store. Adding a secret/paid service needs your approval (brief rule 7).
* **CSCF 2026–2030 is official = 1.0** (Decision (EU) 2026/1862), not an assumption as the brief said — implemented per the official source (docs/EC_EXAMPLE_NOTES.md §2a).

## Known gaps / next steps

* Run live Gemini once; inspect extraction misses in `backend/eval/report.md`; tune prompts if field accuracy < 95 %.
* Firestore store implementation is written against the documented schema but only exercised once deployed (local runs use the in-memory store).
* Vietnamese UI is partial (falls back to English); Tamil covers the main flow.
* Stretch items not started: vernacular voice notes (X1), decarbonisation what-if beyond the supplier toggle (X2), Annex IV operator-report alignment (X3).
* Freeze the deployed version from 18 Oct; tag `v1.0-submission`.

## Useful commands

```bash
cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/pytest -q          # all tests
cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/uvicorn app.main:app --port 8080   # app on :8080
cd frontend && npm run build                                                              # SPA → frontend/dist
backend/.venv/bin/python demo/generate_docs.py                                            # regenerate sample docs
cd backend && .venv/bin/python -I refdata/build_refdata.py                                # rebuild refdata + manifest
docker build -t pramaan:local . && docker run -p 8080:8080 -e GEMINI_VERTEX_READY=0 pramaan:local
```
