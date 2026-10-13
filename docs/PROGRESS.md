# Progress log (for the team and for resuming work)

_Last updated: 2026-10-13 IST, night (10 judging/improvement iterations in progress; fixes pushed, **not deployed yet**)._

## 2026-10-13 (night) — 10 judging/improvement iterations

Plan (each: judge against the rubric → build → test → push, CI green): 1 supplier loop · 2 report-aware
copilot · 3 energy-efficiency insights (theme: industrial efficiency) · 4 guided tour for judges ·
5 phone flow · 6 i18n + cost receipt · 7 live-run robustness · 8 accessibility/performance · 9 docs
and visuals · 10 final judging.

### Iteration 23 — no layout jumps (the report page was CLS 0.99 on a phone)
* Judge: Lighthouse mobile on the pages judges actually land on, not just the landing: report **56** (CLS
  0.99), /try 63 (CLS 0.51). Found with a layout-shift observer on a 412 px phone: the company name wrapped onto
  a second line when IBM Plex replaced the fallback font; the run badge and tour chip arrived with the results
  and wrapped the chip row (+30 px); the footer showed inside the first screen while the page loaded and was
  then pushed away; /try's replay note and sample cards arrived late above the picker; /proof's notes were
  pushed down when the eight cases replaced two placeholders.
* Fixed: the header chips come from the project bundle; `main` is at least a screen tall; /try draws its
  samples at once with the note below them; /proof shows one placeholder per case; a project page opened
  directly starts its code and data together at boot. (A font wait tried first proved unnecessary and was
  removed.) Every page's CLS is now 0–0.017; Lighthouse mobile **report 80–86, /try 80–84, landing 95, proof
  90** (accessibility and best practices 100; project pages are no-index on purpose).

### Iterations 19–22 — trust, the live result up front, and speed
* **Screens from the live run**: README screenshots/GIFs and the deck's images regenerated from the merged build
  (they showed "Replay of bundled sample (Gemini not used)" and `replay:ground-truth` under the readers); they
  now show "Live Gemini run · 13 Oct", the field-named review card and both Gemini models.
* **Delete my project** (privacy): `DELETE /api/projects/{pid}` behind the passcode removes the photos (Cloud
  Storage prefix), Firestore documents, evidence, runs, results and the buyer and supplier links (Firestore kept
  those before); not the sample, not mid-run. "Delete this project" ends the set-up card (four languages). Tests:
  API (owner-only, photos and links gone), the Firestore emulator test run locally (its stale 213 fixed to 222),
  the UI smoke test deletes the project it creates; axe 0.
* **Landing**: a chip beside "8/8 EC worked examples" shows the latest live evaluation on the deployment
  ("222/222 fields read live by Gemini, 97 s", links to Metrics; hidden when there is none).
* **Speed**: Lighthouse mobile measured side by side with the iteration-8 build (same machine, alternating):
  91/92/90 then; preloading the first paint's three latin fonts gives 95/92/93, FCP 2.3 → 2.0 s, no duplicate
  downloads.

### Iterations 15–18 — the merged product, judged with the live run as the sample
* **Tour**: an eighth stop lights up **Call** after Ask (judges explore through the tour, and it skipped the
  voice agent); the landing's "Built with" names Gemini 3.8 Live; DEMO_SCRIPT's proof line carries the live
  result and suggests /try as an optional ten-second live moment.
* **Live-run wording**: with the captured live run as the sample, the review card read "Confirm this corrected
  value: स्टेनलेस स्क्रैप (t)" in the English UI (the label as printed on the Hindi scrap log); it is now titled
  by the field and its line in the reader's language ("Scrap · Stainless hexagon bolts"), printed label as the
  fallback. The run receipt summed 24 documents up by the last one ("10 values, 10 with regions"); the
  Classifier and Extractor rows now total their documents ("222 values from 24 documents, 222 with regions").
  Metrics: ten runs on one day all read "10/13/2026"; each now shows its time in the reader's locale.
* **Cost safety**: a visitor leaving /try mid-reading still paid for up to 40 second reads (tasks outlived the
  stream); they are cancelled with it (the test fails on the old code: all 8 reads finished).
* **Accessibility**: axe over the merged pages (landing, report with the call panel open, gaps, capture; light
  and dark; desktop and 360 px): one violation, the call panel's Start button in dark mode (2.59:1); fixed with
  the theme's ink for strong fills. Now 0 everywhere.

### Iteration 14 — Gemini you can watch: try one photo
* Judge: on the sample, the Gen AI is a recording; the only live path was a full 24-document run (a
  minute or more and ~370k tokens). A judge with two minutes, or an exporter deciding whether to trust
  Pramaan, had no quick way to see the models work on a page of their own.
* Built: **`/try`** runs the Classifier, Extractor and blind SecondReader of a full run on one page and
  streams each step (SSE over a POST, not gzipped): boxes appear on the photo as reader 1 returns them and
  turn green or amber as the blind re-reads land; selecting a value unfolds **the exact crop reader 2 saw**
  (the struck-out 13.4 next to 15.4). Three fictional samples or the visitor's own photo (camera on a
  phone; HEIC/PDF shown as read); read in memory, never stored; 40 second reads per photo, 20 live tries
  per address and hour; without live Gemini the samples replay, labelled. Entry points on the landing hero
  and the "What happens to one photo" strip; in the in-app architecture page and the README. Also: a
  live run's badge says when it ran ("Live Gemini run · 13 Oct, 02:13 pm"), and unknown `/api/` paths are a
  JSON 404 instead of the app page.
* Merged the team's **Call Pramaan** (voice agent on Gemini 3.8 Live, five languages) and the ten-live-run
  reader fixes (**222/222 fields, 96.8 s** on the 13 Oct live run, now what the sample shows). Conflicts were
  additive (routers, per-address caps, locale sections, the README diagram); one interaction fixed: the new
  "untagged" re-read no longer fires for a page read without product lines (it would have cost /try an extra
  extraction on every register or scrap log).
* Deck: a slide for Call Pramaan and /try; slide 12 now carries the live result (222/222, 96.8 s, 98.6 % of
  boxes on target) instead of the placeholder.
* Tests: 7 for /try (replay stream, live path with the scripted Gemini, own photo without product lines, not
  a CBAM document, a failed read, the per-address cap), the re-read rule, the API 404; UI smoke covers /try on
  desktop and 360 px; axe 0 violations on /try (light/dark, desktop/phone).
* Team: **redeploy main** so `/try` is live (the service runs 6c6df4e, which has Call Pramaan but not /try).

### Iteration 13 — the deck, and the demo's key photo
* Judge: the deck is one of the four submission items and did not exist; the notes did. And the demo's key
  moment had a flaw: on the scrap log, the struck-out 13.4 read as **43.4** (a level line through a
  handwritten 1 makes a 4), while the story and the review card say 13.4.
* Built: a 14-slide pitch deck from the product's own screens and numbers (problem with sources, the data
  chain, three steps, the ADK workflow with the model per agent, Evidence Lens, blind second reading, the
  money, the supplier loop, Plant pulse, proof, Google Cloud architecture, scale, a close with the live
  link and a QR code), speaker notes from DEMO_SCRIPT; it downloads as PDF or PowerPoint. One placeholder
  to fill after the redeploy: the final live-run accuracy and time (slide 11). The correction stroke now
  runs through the lower half of the old figure (only that photo changes; ground truth byte-identical);
  hero images and every README screenshot/GIF regenerated.

### Iteration 12 — the PDF answers first
* Judge: the PDF is what an exporter mails to the buyer and the verifier, but page 1 opened with tables;
  the money, the next step and the Plant pulse were only in the app, and the "Control checks" heading sat
  alone at the foot of page 3 (whole tables were kept together, so the table jumped to page 4).
* Built: page 1 now leads with **what the data saves the buyer** (€ and ₹ a year) and **what is within
  reach** with verified rod data, then **What to do next** (ask the named supplier, approve the open
  value, send the verified data); the precursor column names the verifier and the verification report;
  a **Plant pulse** table (GJ per tonne by month, the hot month highlighted, ₹ above the median month);
  long tables now break between rows and repeat their header row; headings stay with their table.
* Tests: `test_pdf_leads_with_the_answer` (verdict, next steps, verifier, pulse, a header on every table);
  rendered and checked by eye before and after the supplier sends data (5 pages, no orphaned headings).

### Iteration 11 — trust and explainability
* Judge: the Evidence Lens showed *how* a number is made (formula, inputs, photo) but not *what it means*;
  the buyer link said "actual, verified" without saying by whom.
* Built: **Explain in plain words** in the Evidence Lens: the number, its formula and its direct inputs
  (with where each was read) go to *Ask about this report* as the first facts; Gemini explains the formula
  step by step under the same numbers guard; the lens steps aside and the answer's chips reopen it. The
  buyer link now names the verifier and the verification report of the supplier's data (from the
  statement's own two-reader values, no plant data). Unlock attempts were already capped (20/h/address).
* Tests: lens explanation (focus first, cited, prompt), buyer link verifier before/after the supplier upload.

### Iteration 10 — judging pass after nine iterations
* Sweep of every page (desktop light/dark, 390 px phone; landing, report, gaps, capture, plan, proof,
  metrics, architecture, copilot, buyer link, supplier link): no page errors, no failed API calls, no
  sideways scroll. Fixed: the Metrics page showed a stale per-type table (63 gas fields, from before the
  rate field) and "25 uploads"; the eval now writes the table of the run it shows and keeps **every
  evaluation** (`history`), seeded with the first live run on Cloud Run (83.6 % before the clean-up →
  98.1 % re-scored) — the page lists them with a note.
* Scorecard (if the team redeploys main, captures the live run, records the video and makes the deck):
  Technical & Gen AI 9 (grounded report Q&A with a numbers guard, supplier loop on the same agents,
  clean-up proven on real Gemini output, runs that survive Cloud Run, eval history, ~170 tests + e2e incl.
  the tour) · Problem & impact 9 (three parties in one data chain, phone first, WhatsApp, four languages
  end to end, Plant pulse for the operations theme) · Innovation 9.5 · UX 9.5 (tour, folds, handoff QR,
  Lighthouse 91/100/100/100 mobile) → **about 92/100**. The live link as deployed today is the old build.
* Team, in order: pull → `MIN_INSTANCES=0 scripts/deploy.sh` → one live re-run (< 2 min, €409,545, 1 of 2
  lines), the supplier link on a phone, one "Ask about this report" question → `run_extraction_eval.py
  --mode live --capture` → redeploy → `scripts/readme_shots.py <URL>` → before 19 Oct plain
  `scripts/deploy.sh` (min-instances 1; check the idle cost against the budget) → video + deck → tag.

### Iteration 9 — the story in pictures (README, architecture, GIFs)
* Judge: the README is the first thing many judges read; its pictures predated iterations 1–8 and the
  strongest moment (the supplier's upload moving the money) had no picture at all.
* Built: `scripts/readme_shots.py [URL]` (in the repo, re-runnable against the deployed URL): all README
  stills, `evidence-lens.gif`, and the new `money-moves.gif` (supplier's phone + exporter's report side by
  side, €409,545 → €572,546). README diagram and the in-app Architecture page show Normalize, the supplier
  link, Ask about this report and Plant pulse. DECK_NOTES lists the visuals.
* Not captured on purpose: an "Ask" screenshot with a Gemini answer (only possible on the live service; a
  scripted answer would misrepresent it) — capture after the redeploy.

### Iteration 8 — fast on a phone (and Lighthouse 91/100/100/100 mobile)
* Judge: Lighthouse mobile 87/100/100/92 on the landing page: all four languages in the first bundle
  (189 KB gzip), the page fade and a fade-in on the headline delayed the largest paint, robots.txt was the
  SPA page, hero photos were 100 KB JPEGs, public files had no cache policy.
* Built: hi/ta/vi load on demand (`setLanguage`; a returning Hindi reader gets Hindi before the first
  paint; the WhatsApp text loads the letter's language) → main bundle 189 → 151 KB gzip. No page fade on
  the first load; headline and lead render at once. `index.html` paints a static English copy of the
  header + hero text (landing only, removed on any other route or language; CI checks it matches
  `landing.*`) and applies the stored theme before the first paint (no light flash in dark mode).
  `scripts/build_hero.py` rebuilds the hero assets from the current sample (WebP, half the bytes; JPEG
  fallback). `robots.txt` keeps private projects, buyer and supplier links out of search; public files
  cached a day.
* Lighthouse, landing, local production build: mobile **91 · 100 · 100 · 100** (FCP 2.3 s, LCP 3.1 s,
  CLS 0), desktop **99 · 100 · 100 · 100**.

### Iteration 7 — runs that survive the platform
* Judge: three ways a judge's run could go wrong on Cloud Run: (1) an instance restarts mid-run and the
  run stays "running" forever (the project refuses new runs, the UI spins); (2) the browser closed the
  timeline stream on its first error and never reconnected (a phone on mobile data would see a spinner
  after the run finished); (3) live runs were capped per project, but every visitor gets a private sample
  copy, so a script could run many live runs on the team's bill.
* Built: `runs_settled()` marks a run still "running" 30 min after it started (and not executing on this
  instance) as *interrupted*; the bundle, `start_run` and supplier uploads use it. The timeline reconnects
  with backoff (history replayed, de-duplicated by seq) and Capture settles a run from the project state.
  Live runs capped per address (12/h; replays uncapped). ARCHITECTURE: how runs keep CPU on Cloud Run.
* Tests: `tests/test_runs_robust.py` (3).

### Iteration 6 — the report in the reader's language, all of it
* Judge: in Hindi/Tamil/Vietnamese the checks, the explanations and the period label were still English
  (server text); a Ludhiana owner reading Hindi hit English paragraphs.
* Built: checks are localized in the browser by their stable ids and phrases (`lib/checks.ts`; numbers,
  units and names stay as computed; unknown text falls back to the stored English). Explanations:
  deterministic templates in en/hi/ta/vi (`explainer.TEMPLATES`) served by `GET /explanations?lang=` with
  the numbers guard applied to every language (English keeps the run's own, Gemini-written text). The
  period label is formatted from the project's months in the reader's locale. Scan of the Hindi report:
  only company and place names remain in Latin script.
* Cost receipt per run: not built — needs verified Gemini prices for these models; tokens per agent are
  already on the run receipt.
* Tests: explanations in 4 languages carry exactly the same figures (`test_api.py`); UI smoke.

### Iteration 5 — phone first (handoff QR, folds, WhatsApp)
* Judge: owners live on their phones and the documents are on the shop floor; the report was 9,614 px on a
  390 px phone and there was no way from the laptop to the phone camera.
* Built: `QrCode` (qrcode-generator 1.4.4, MIT, lazy 8 KB chunk; drawn as one SVG path, dark on white).
  Capture (laptop): *Continue on your phone* QR; for private projects the passcode rides in `#k=` (never
  sent to a server) and the phone unlocks with it, then drops it from the address bar (verified: QR
  decoded with OpenCV, a fresh phone opens the project without the passcode form). Supplier link: QR, so a
  judge can play the supplier on a real phone. Phone folds (`PhoneFold`, `CardDetails`): product cards lead
  with SEE + buyer cost, breakdown behind *Details*; levers and explanations behind one line each →
  sample report 9,614 → 7,399 px. WhatsApp button on the buyer link. en/hi/ta/vi.
* Checks: tests, UI smoke (incl. tour), axe 0 (phone report folded/open, capture + handoff, letter + QR;
  light/dark).

### Iteration 4 — a 90-second guided tour for people with two minutes
* Judge: the best parts (Evidence Lens, two readers, supplier loop, Ask, Plant pulse, EC proof) are spread
  over a long report and two pages; a judge with two minutes would see the verdict and leave.
* Built: `components/Tour.tsx` — seven stops (verdict, SEE number, two-reader comparison on Gaps, request
  letter, Plant pulse, Ask, proof), spotlight with a moving hole (one element, huge shadow; the lit part
  stays clickable), card placed below/above the target, step dots, Back/Next/Skip, arrow keys, Esc,
  focus on Next, reduced motion = cuts. Layered under the Ask panel and the Evidence Lens so what it points
  at can be opened over it. Starts from the landing ("Take the 90-second tour", loads the sample) or the
  workspace chip "Take the tour" on the sample. en/hi/ta/vi.
* Tests: `scripts/ui_smoke.py` now runs the tour end to end (CI e2e); axe 0 on landing + tour (light/dark,
  1440/360).

### Iteration 3 — Plant pulse (theme: intelligent operations & industrial efficiency)
* Judge: the theme is manufacturing operations; Pramaan read the operational data (gas bills, register)
  only for compliance. And the sample's months were perfectly flat (3.500 GJ/t, 15.0 % scrap every
  month), which looks synthetic.
* Sample data: gas per tonne now moves month to month around EC Example 3's 3.5 GJ/t (June +16.5 %,
  April −7 %); September balances to the meter so the period's gas (6,966.553 vs 6,966.542 MMBtu) and
  every golden number are unchanged (SEE 2.0399, €409,545). January and March bills are unchanged
  (screenshots, GIF, OG card). The gas rate (₹/SCM) is now a ground-truth field: 222 fields (was 213);
  replay cache and eval report regenerated (replay self-check 100 %).
* Engine: `_gas_pulse` — monthly GJ/t nodes, median month, hot months (≥ +10 %) with excess GJ, SCM (via
  the bill's GCV), ₹ (the bill's rate) and t CO2, all calculation nodes (lens down to the June bill).
* UI: Plant pulse section (nav "Plant pulse"): bars from zero, dashed median, hot month in warn with its
  label, best month in green, readout line (no tooltip leaving the card on a phone), insight cards with
  lens numbers. Ask about this report: gas facts + "Where is my plant wasting gas?" (4 languages).
* Tests: `tests/test_plant_pulse.py` (3); all 158 + UI smoke; axe 0 on the full report (light/dark,
  1440/360).

### Iteration 2 — "Ask about this report" (grounded in the engine's own figures)
* Judge: the rules copilot answered method questions but not "why is *my* stainless line on the default?"
  or "which default applies to my bolts?", the first thing a judge types. Gen AI (40 %) rewards exactly
  grounded, verifiable answers about the user's data.
* Built: `app/copilot/report.py` + `POST /api/projects/{pid}/ask` (passcode-protected, rate-capped):
  ~50 facts from the result (calc-tree ids, official default values, buyer costs, what-if, readiness,
  open items) + 4 guidance pages → Gemini 3.8 Flash cites `[F:id]` / `[Guidance N, p. X]`; the Explainer's
  numbers guard withholds answers with numbers not in the report; timeouts and no-Gemini fall back to
  the relevant facts (keyword + intent ranking). UI: a non-modal "Ask about this report" panel (button on
  the verdict + floating *Ask*), suggestion chips, answers with lens chips after each number, a "Figures
  from your report" list; the Evidence Lens opens over it and the conversation stays. en/hi/ta/vi.
* Tests: `tests/test_report_copilot.py` (5: no-Gemini facts, grounded with cited lens nodes, invented
  number withheld, timeout, passcode). axe 0 (light/dark, 1440/360, grounded + facts modes).

### Iteration 1 — close the Precursor Lever's loop (supplier upload link)
* Judge: the biggest lever (rod data ≈ 90 % of SEE) ended in a letter; nothing in the product showed the
  data coming back. Impact and innovation both hinge on that loop.
* Built: one upload link per product line (`ShareLink` kind `supplier`), carried in the EN/HI letter,
  copy / WhatsApp / *Open as the supplier* (sample). Public phone-first page `/supplier/:token`: what is
  asked and why, upload (camera/PDF), a sample statement for the fictional factory, progress (sent →
  received → read by two AI readers → verified), what was read with two-reader badges, privacy note.
  The upload runs the same agents on the new document only, then marks the request verified when the
  line uses the supplier's verified data. The exporter's open report polls while a link is out, says
  so in a toast and the verdict tweens with a "+€163,002" badge.
* Sample supplier pack: `demo/generate_supplier_pack.py` → `demo/supplier/stmt-ISR-2026.jpg` (fictional
  Indus Stainless Rods, SEE 1.783 / SEFA 0.919 = EC Example 2 / Table 4-14), replayed like the sample,
  outside the 24-document eval set.
* Result on the sample: stainless bolts €402 → €97/t; verdict €409,545 → €572,546 a year; 2 of 2 lines
  ready; readiness 100 %. Tests: `tests/test_supplier.py` (6). axe: 0 violations (light/dark, 1440/360).

## 2026-10-13 (early morning) — third mock judging, on the live deployment

Judged the live URL like a judge would (desktop + phone, logged out) and pressed **Re-run agents** on a
private copy of the sample once: the **first real Gemini run of the workflow** (24 photos, ~407k tokens).

* It works end to end (no errors) but took **392 s**: classifier 31 s, extractor 254 s (one call
  stalled for ~200 s), second reader 83 s for 213 crops, explainer 21 s.
* It changed the headline: **€78,613 instead of €409,545, "0 of 2 lines ready", 8 red gaps.**
  Scored against the ground truth: 83.6 % field accuracy, but the readings were nearly all right:
  supplier-statement values had no product line (→ default precursor, P1 SEE 5.722), a junk-suffixed
  number dropped the stainless rod tonnes, documents had month/quarter tags on document-level fields,
  CN code inside a description, reference with a date appended, and the classifier wrote model notes
  into every period date ("2026-05-01Bytes"), which would have reached the verifier Excel.
* Gemini read the hand-corrected scrap figure right (15.4, both readers), so the live run had **no**
  value for a person to approve: the two-reader catch and the *Approved* stamp would vanish from a
  live capture.
* Cold start with min-instances 0: **9.1 s** to the first byte. First copilot answer on a new
  instance: **17.6 s** (the EC PDFs were parsed on the first question). "What default value applies
  to my stainless bolts from India?" → "the pages do not state it" (the copilot does not see refdata).

Fixed (tests: 143 passed + 1 skipped; UI smoke desktop + 360 px; Docker image builds):
* `app/agents/normalize.py`: schema-driven clean-up before the second read (scope of every field,
  one product line per single-material document from its CN code / tags / supplier, salvaged
  numbers, CN codes as `dddd dd dd`, references without dates, ISO dates, document period from its
  own values). Offline re-score of the live readings: **98.1 %**, golden SEE 2.040 and €409,545 again.
* Per-call time limits + retry; Flash and Flash-Lite in separate concurrency lanes (12 / 24).
* Second reader reports a crossed-out figure; a hand correction is always a human tap ("Confirm this
  corrected value", ✎ badge, "13.4 crossed out on the page"); text agrees if a line of the padded crop
  matches.
* Copilot pages parsed at image build time (first answer in a fresh container: 0.07 s); copilot falls
  back to cited pages if Gemini times out; Gemini-backed endpoints capped per address/hour.
* Link previews (`og:image` card, absolute URLs filled in by the server), HEAD on the SPA, hashed
  assets cached for a year, run timer ticks during a run.

**Team, next (in order):** pull → `MIN_INSTANCES=0 scripts/deploy.sh` → on the live URL load the
sample, **Re-run agents** once and check: < 2 min, €409,545, 1 of 2 lines ready, a corrected-value card
→ `backend/eval/run_extraction_eval.py --mode live --capture` → redeploy → before judging plain
`scripts/deploy.sh` (min-instances 1: check the idle cost against the ₹2,000 budget).

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

Done: gcloud sign-in, billing + budget alert, public GitHub repo, `scripts/gcp_setup.sh`, first deploy, ten
live runs and the captured live run (222/222, 96.8 s; the sample serves it), Call Pramaan deployed (6c6df4e),
a 15-slide deck draft (link in DECK_NOTES; private until shared).

1. `git pull`, then `MIN_INSTANCES=0 scripts/deploy.sh`: the service runs 6c6df4e, which lacks **/try** (try one
   photo), the PDF that answers first and the API 404 fix. Then on the live link: one sample photo on /try (a few
   cheap calls) to see the boxes turn green live.
2. Before judging (and before recording the video): plain `scripts/deploy.sh` → min-instances 1, no cold start.
3. Record the video (DEMO_SCRIPT; /try makes a good 10-second live moment), share the deck from its Share menu,
   check it, export the PDF, and tag `v1.0-submission`.

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
