# Pramaan: test report

Overnight QA pass, 14 Oct 2026, 01:55–08:00 IST. Every feature was tested as a user and through the
API, on two targets:

* **main**: the current code (`main` at the commit that adds this report), on a local server with in-memory
  storage and again on the Firestore emulator. Gemini is not available locally, so live AI paths run
  as recorded replays here.
* **live**: the deployed service https://pramaan-646454690406.asia-southeast1.run.app, running
  **6c6df4e** (13 Oct). It has live Gemini, so all the AI features were exercised there for real.

**Bottom line:** every feature works on main. Testing found 15 problems; all of them are fixed, tested and pushed
(CI green). **The live link does not have the fixes or the newest features yet: it needs a redeploy**
(see *Do next*).

**Afternoon, 14 Oct: a factory the app had never seen.** Its inputs and expected outputs were made
independently of the app (*Independent new-factory test* below). Pramaan's numbers matched an
independent calculator to 6 decimals, and the AI read 158 of 162 values right (none wrong). The reports
for a non-sample factory were incomplete in 9 ways, for example:
* no supplier lever;
* months out of balance were not named;
* the text said "bolts" for a nut maker.

All 9 are fixed in 45dd60c. Two more failures came from live Gemini:
* A supplier's reply was read without its verification section, so the report silently stayed on the
  default.
* A correct Tamil answer was withheld by the number guard.

Both are fixed in the commit after 93e95c4.

Legend: ✅ works · ⚠️ works with a caveat (see notes) · ⏳ on main, not on live until the redeploy · – not run on live

## Do next (team)

1. **Redeploy main**: `git pull && MIN_INSTANCES=0 scripts/deploy.sh`; before judging, plain `scripts/deploy.sh`
   (min-instances 1).
2. **Run the API check against live** after the deploy:
   `backend/.venv/bin/python scripts/qa/make_fixtures.py && backend/.venv/bin/python scripts/qa/api_check.py https://pramaan-646454690406.asia-southeast1.run.app --live`
   (expect `0 failed`).
3. **Check the per-address caps once** (cannot be checked from here). From one network, send 21 wrong passcodes to a
   test project, then one more with the header `X-Forwarded-For: 203.0.113.1`. The extra one must also answer
   429. If it answers 401, set `CLIENT_IP_HOPS=0` on the service. Then a wrong passcode from a second network
   (a phone on mobile data) must still answer 401.
4. **Delete the QA projects** left on live (fictional sample photos only). The live build has no Delete
   button yet. After the redeploy, open each one and use **Delete this project** (the passcodes are in the
   session notes, not here): `prj_d09f4fac3c5c` and `prj_2c3d9eac9d4c`. Three more have no recorded
   passcode; remove them in the Firestore console, or leave them:
   * `prj_67753707f825` (a rate-limit probe)
   * a project named with 120 "x"
   * one named "QA call"
   * `prj_baa99ca68fcc`, "Kaveri QA run (TEST)", the independent new-factory test (passcode in the session notes)

   Visitor copies of the sample expire by themselves.
5. **Demo video**: at 0:45 the captured live run shows *both* readers reading 15.4, with the second reader
   flagging the crossed-out 13.4, but the voice-over says "reader two sees 13.4". Say "a hand correction
   goes to a person" instead. On live, the supplier's statement can leave one value for review, so "2 of 2
   lines ready" may need one approval; the money moves either way.

## Feature status

| # | Feature | main | live | Notes |
|---|---|---|---|---|
| 1 | Landing: hero, CTAs, live chips, sources, language, theme, nav, phone menu | ✅ | ✅ | One dead source link (kotakneo, 404) replaced with Business Standard 30 Jun 2026 (e8f8cab) |
| 2 | Load sample factory (a private copy per visitor) | ✅ | ✅ | 0.1–0.5 s; 24 documents, cached live Gemini run |
| 3 | 90-second tour (8 stops, ends on EC proof) | ✅ | ✅ | Desktop and phone; cards stay on screen |
| 4 | Process live / Re-run agents: agent timeline, run receipt | ✅ | ✅ | Live: 24 docs in **122 s**, 442,490 tokens; laptop run 97 s |
| 5 | Two Gemini readers, blind second read, human review | ✅ | ✅ | Live re-run: **222/222 fields right (100 %)**, 3 sent for review |
| 6 | Uploads: JPG, PNG, WebP, HEIC, multi-page PDF, EXIF rotation, CMYK, alpha | ✅ | ✅ | Bad files refused with the file name and reason (corrupt, 16 MB, text, GIF, HTML-as-PNG, 900 MP bomb) |
| 7 | Own private project: passcode, set-up, product lines (manual, CN checked) | ✅ | ✅ | Live: Gemini proposed both product lines with the right CN codes from 6 photos (67 s) |
| 8 | Phone handoff QR (#k= passcode), unlock screen, wrong passcode message | ✅ | ✅ | |
| 9 | Delete my project (photos, readings, links) | ✅ | ⏳ | Other devices then see "project not found" |
| 10 | Close gaps: review card (approve / edit), mass-balance hint, checklist | ✅ | ⚠️ | Edit now refuses typos with a message and reads "15,4" as 15.4 (on live a typo still closes the form silently until the redeploy) |
| 11 | Answer a gap by voice (Hindi) | ✅ | ✅ | Live API: Hindi clip → "15.4 t", NEEDS_REVIEW, 4.5 s. Browser mic path works; the reading depends on audio quality |
| 12 | Report: verdict, next steps, products, contribution bar | ✅ | ✅ | Figures cross-checked: screen = PDF = Excel = buyer link |
| 13 | Money on the table: chart/table, CN tabs, what-if line, INR and price inputs | ✅ | ⚠️ | Bad inputs now show a message (silent on live until the redeploy) |
| 14 | Plant pulse (gas per tonne by month) | ✅ | ✅ | June +18.5 % hot, ₹2,00,905 |
| 15 | Operations levers (rod data, EC example chips, scrap, electric, reset) | ✅ | ✅ | EC Ex. 1 rod gives stainless SEE 2.107 (checked by hand) |
| 16 | Evidence Lens: every number (33 on the report) to the photo and both readers | ✅ | ✅ | Focus now returns to the number on close |
| 17 | Explain in plain words, Ask about this report (Gemini, cited, numbers-guarded) | ✅ | ✅ | Live: EN 2.9 s, HI 3.6 s, figures correct; without Gemini the figures still answer |
| 18 | Rules copilot (EC guidance, page citations) | ✅ | ✅ | Live: grounded answer with page citations, 10.5 s |
| 19 | Call Pramaan (Gemini 3.8 Live voice agent, 5 languages) | ✅ | ✅ | Live, English and Hindi: greeting, spoken question transcribed, figures verified, opens the Evidence Lens by itself, barge-in, hang-up |
| 20 | Supplier letter (EN/HI), WhatsApp, upload link, supplier page | ✅ | ✅ | |
| 21 | Supplier sends statement → report updates | ✅ | ⚠️ | Live: read in 48 s, stainless SEE 8.889 → 2.371 (= EC G2); one value (report number) left for review |
| 22 | Buyer link (read-only, no plant data), copy, WhatsApp | ✅ | ✅ | Dates now unambiguous (14 Oct 2026, not 10/14/2026) |
| 23 | Exports: PDF, Excel, verifier pack ZIP, monitoring plan (EN/HI, print) | ✅ | ✅ | PDF in English only (EU buyer document) |
| 24 | Verifier spot-check (12 values by weight, marks, notes, print, CSV in pack) | ✅ | ⏳ | |
| 25 | /try: watch two Gemini models read one photo | ✅ | ⏳ | Replay locally; live reading of own photos only after the redeploy |
| 26 | EC proof: 8/8 worked examples reproduced live | ✅ | ✅ | |
| 27 | Metrics page (live eval + history) | ✅ | ✅ | |
| 28 | Architecture page | ✅ | ✅ | |
| 29 | Languages: English, हिंदी, தமிழ், Tiếng Việt | ✅ | ⚠️ | Tamil/Hindi phone layout fixes not live yet. Server error messages stay English |
| 30 | Dark mode | ✅ | ✅ | |
| 31 | Phones and tablets (320/360/390/768 px) | ✅ | ⚠️ | Several squeezed or clipped layouts fixed (not live yet) |
| 32 | Accessibility (axe all rules, keyboard) | ✅ | ⚠️ | main: 0 violations in 247 page views; live has the old issues |
| 33 | Browsers: Chrome, Firefox, Safari (WebKit) | ✅ | – | Full UI smoke test passes in all three on main; live was tested in Chrome |
| 34 | Speed (Lighthouse, mobile) | ✅ | ✅ | main: landing 94, report 83 (SEO 63 by design: private pages are no-index). Live: landing 88, proof 95 |
| 35 | Privacy and access control | ✅ | ✅ | A stranger gets 401 on all 20 project routes and on photos |
| 36 | Robustness: bad input, server errors, a page that fails to load | ✅ | ⏳ | 500s, silent failures and blank-page cases fixed (below) |
| 37 | Storage: in-memory, Firestore emulator, live Firestore + Cloud Storage | ✅ | ✅ | API check: 224 checks, 0 failed on both local stores |

## Independent new-factory test (14 Oct, afternoon)

**Question:** are the numbers and the reports right for an exporter the app was never tuned on? This
test does not use the bundled sample.

**The test factory.** Kaveri Precision Fasteners (TEST, fictional) in Coimbatore makes carbon and
stainless hexagon **nuts** (CN 7318 16 92 and 7318 16 39), Jan–Jun 2026:
* the carbon rod has no supplier data (India default + 10 %);
* the stainless rod comes with a verified statement (SEE 2.150, SEFA 0.880).

Every input differs from the sample: the region, suppliers, document layouts, period and handwriting
(a Tamil scrap log with one figure struck out). There are two planted faults:
* the carbon scrap log is 5 t off in March and in May, though the six-month totals balance;
* March gas runs hot.

**How the answer was checked.** `scripts/qa/independent/oracle.py` computes the expected results. It
does not use the app's engine. It reads the Commission's own default-value and benchmark files, and it
reproduces EC Examples 1–3 before anything else is trusted. The 16 photographed documents went through
the live service with real Gemini (6c6df4e, an own private project). The live readings are now a CI
test (`backend/tests/test_independent_factory.py`).

| Checked | Expected (independent) | Pramaan | |
|---|---|---|---|
| Values read from the 16 photos | 162 on the documents | 158 right, **0 wrong**, 4 missed (Mn/Cr/Ni/other % on one stainless invoice) | ⚠️ |
| Values sent to a person | 1: the struck-out Tamil scrap figure (5.9 → 5.6) | that one + 4 false alarms (fixed, below) | ✅ |
| Product lines proposed by Gemini from the documents | 2 CNs, 2 rods, 2 suppliers | all right | ✅ |
| SEE, carbon / stainless nuts | 5.642014 / 2.624069 t CO2/t | 5.642014 / 2.624069 | ✅ |
| Own process (gas), rod per tonne (m) | 0.185013; 1.161806 / 1.134444 | same | ✅ |
| SEFA; SEFA 2026 | 1.622703 / 1.036311; 1.582135 / 1.010403 | same | ✅ |
| Buyer cost per t, own data vs EU default | €305.78 vs €325.68; €121.54 vs €341.10 | same | ✅ |
| Certificates; buyer cost 2026 | 1,583.4 / 250.1; €119,253 / €18,838 | same | ✅ |
| Saving a year for the buyer | €15,522 + €68,064 = **€83,586** | €83,586 | ✅ |
| Years 2027–2034 (mark-up, CBAM factor) | e.g. 2027 €378 vs €401 | same (2027, 2030, 2034 checked) | ✅ |
| If the carbon rod supplier sends verified data | €42.30/t, +€205,512 a year | missing before the fix; now same | ✅ |
| Alloy content (Guidance 5d Table 3-1) | tonnes-weighted: Ni 8.07, Mn 0.43 | plain mean before the fix (8.08, 0.44); now same | ✅ |
| Plant pulse | March +20.7 %, 118.8 GJ, ₹1,76,194; best April | same | ✅ |
| Control checks | monthly balance off in Mar and May; supplier data missing for the carbon rod | warns on both; the months were not named before the fix | ✅ |
| Live run time | under 2 min target | **345 s**: two Gemini calls stalled (167 s, 260 s) and were retried | ⚠️ |
| Supplier replies through its upload link (live): verified statement for the carbon rod, BF-BOF, SEE 1.567, SEFA 1.242 | carbon nuts SEE 2.005563, €42.30/t, €221,035 a year on that line (€289,099 in all), 2 of 2 lines ready | read in 61 s, but **only 6 of 13 values** (no SEFA, verifier or report number): the line stayed on the default, and the checklist still said "no verified data" | ❌ → fixed |
| The same statement read in full (engine, CI test) | as above | SEE 2.005563, SEFA 1.480963, €42.30/t, €221,035, 2 of 2 lines | ✅ |
| Ask about this report (live Gemini) | €305.78 and €121.54 per t; why carbon is higher | English: right figures with citations, 5.2 s. **Tamil: withheld** by the number guard for "70", from the product name "A2-70" | ⚠️ → fixed |
| Buyer link, Excel, operations levers (local) | SEE 5.642 / 2.624, no plant data; levers from first principles | all match (rod EC Ex. 1 €42.30/t; electric 5.4570; gas 3.0 GJ/t 5.6253; scrap 10 % €292.92/t) | ✅ |

**Found and fixed** (45dd60c, CI green):

| Problem on the new factory | Fix |
|---|---|
| **No supplier lever.** The "if the rod supplier sends verified data" figures existed only for the sample, so there was no "More within reach", no "Ask … for verified data" step and no what-if row | A rod on its default value gets the Commission's worked example (Guidance 5d Example 1; Example 2 / Table 4-14 for stainless) unless the owner sets a scenario |
| **Monthly mass balance** said "4/6 months" and "Missing months:" with nothing after it; the scrap line in the checklist said OK | Names "2026-03 (125.0 vs 130.0 t), 2026-05 (120.0 vs 115.0 t)" and links the 6 values; the checklist flags the scrap line with "Mar 2026, May 2026". Shown on screen, in the PDF and in the pack's CSV |
| The PDF did not print check notes or the rod's own SEE (only m × SEE) | Printed |
| Alloy % was a plain mean across invoices | Weighted by the tonnes on each invoice |
| **"Bolts" for a nut maker**: the explanations (4 languages), the supplier letter (EN/HI), the monitoring plan (also "Two production processes" whatever the count), "Rod per t of bolts", the pulse caption, a call suggestion | Product-neutral |
| Assumptions said "none is claimed for the sample factory" and cited 3.5 GJ/t of gas (this plant's bills give 3.30) | Reworded |
| PDF: "Mode: None · run None" after a recalculation; "-0 %" in the pulse | Fixed |
| Second reader: "53.15 per SCM" vs INR/SCM, and the buyer's name vs name + address, sent 4 correctly read values to a person | Unit aliases; a leading part of the second reading may match |
| A next step called a hand-corrected value one that "the two AI readers could not settle" | Reworded |
| **Live supplier reply read in part** (SEE but no SEFA, verifier or report number): the line stayed on the default with no reason given | A page missing an essential value (statement: SEE, SEFA, verifier, report number; gas bill: MMBtu; rod invoice: tonnes) is read again for just those values. The first reading's values are kept. The checklist says when a statement arrived without a verification report number (4 languages) |
| A correct **Tamil** answer was withheld: "A2-70" in the product name read as an invented 70 | Numbers printed inside the report's own facts (names included) are allowed; a figure the model works out itself is still withheld |

**How the fixes were checked:**
* 11 tests in `tests/test_independent_factory.py`, including the supplier reply, plus 5 more: 2 in
  `test_two_reader.py`, 2 for the re-read in `test_normalize.py`, and 1 for the guard in
  `test_report_copilot.py`. The tests that cover these fixes fail on the previous code; the
  engine-accuracy tests pass on both.
* The full suite (233 tests), the Firestore emulator test, ruff, mypy and the refdata rebuild.
* i18n, `check:format`, the build, the UI smoke test, and `api_check.py` (224 checks, 0 failed).
* The factory in a browser on a local server: 25 of 25 checks with no console errors. This covered the
  report, the checklist with the Tamil crop on the review card, Hindi, Tamil and Vietnamese, a 390 px
  phone, the PDF (every page looked at, figures recomputed by hand) and the verifier pack.

**Still open:**
* The 4 alloy values Gemini missed on one invoice are not flagged. The average then uses the invoices
  that have them. Alloy % is not on the re-read list, because many rod invoices do not print it.
* Gemini sometimes returns only part of a page; the same layout was read in full an hour earlier. The
  re-read covers the values the engine cannot do without, not every field.
* Live run time depends on Gemini's slowest call. Each call times out at 75 s, has a hedge at 30 s and
  gets 3 attempts.
* The live service has none of these fixes until the redeploy.

## Problems found and fixed (all pushed, CI green)

| Severity | Problem (as found) | Fix |
|---|---|---|
| High | A page whose code could not be fetched turned the whole app into a **blank white page**. This happens to any judge with a tab open during a redeploy, and on a flaky phone network | 1d77f67: "This page could not load" with Reload; reloads by itself once when a newer version is out |
| High | **Per-address limits could be dodged** on live with a made-up `X-Forwarded-For` header, including the passcode attempts and every Gemini cost cap (runs, copilot, voice, calls) | 484ee51 + d76f0c8: the caller's address is counted from the right (verify after deploy, step 3) |
| High | Phones: **Tamil landing page cut off** at the right edge; **"Money on the table" squeezed to one word per line** (every language); Hindi gaps legend squeezed; Tamil tablet next steps squeezed | 40752d8 |
| Medium | **Edit on the review card closed silently** on a typo ("abc"), and **"15,4" was saved as 154** | 40752d8 (message + parser; `npm run check:format` in CI) |
| Medium | **Excel formula injection**: a value read from a document (a supplier can upload one) that starts with "=" became a live formula in the workbook and the pack's CSVs | 6e51282 |
| Medium | Report said **"Start a run"** when its data failed to load (on the live sample a click starts a paid run); /proof and /metrics showed only their titles | 3abda53 (Retry card) |
| Medium | Own project on a phone: the set-up card was wider than the screen (the page scrolled sideways) | 66f43e0 |
| Medium | API answered **500** for a NaN/Infinity value (and kept it), an FX "NaN", an unknown run mode, and ids Firestore cannot hold (`__x__`, 1,500+ bytes); an upload with one bad file stored half the batch | 484ee51 (422/404 before anything is stored) |
| Low | Money inputs, buyer link, letter, request status, /start: failures were silent | 40752d8 |
| Low | Keyboard focus fell to the top of the page after closing the Evidence Lens, Ask or Call | 9a64aba |
| Low | Accessibility: an unnamed copilot button on phones, tables not scrollable from the keyboard, heading order, missing h1, list roles; untranslated metrics headers | 40752d8 |
| Low | A mistyped step (`/p/<id>/foo`) showed an empty page | 40752d8 (opens the report) |
| Low | Sample chip "Live Gemini run · 02:13 pm" vs Metrics "02:15 pm" for the same run | 40752d8 (dated by finish) |
| Low | Wording: "1 need review", "1 official values" | 484ee51, 40752d8 |
| Low | Source link 404 (landing + README) | e8f8cab |
| Low | Landing: the hero demo's pause and step buttons could not be clicked | c54c02a |

## Known limitations (not changed)

* The PDF report is always in English (it is written for the EU buyer); the monitoring plan is English or Hindi.
* Server error messages ("wrong passcode", "project not found") are English in every language. A few
  screen-reader labels and placeholders are English.
* A PDF over 12 pages keeps its first 12, and one upload keeps its first 40 files; neither says so.
* The Excel workbook shows full-precision numbers (2.0398…) in the General format.
* No Content-Security-Policy header (nosniff, X-Frame-Options and Referrer-Policy are set); `/api/docs` is public.
* The supplier's page says "Thank you… verified" even when one of its values still waits for the owner.
* On Cloud Run a full live run took 122 s against the Metrics page's 120 s target (the laptop run: 97 s).
* The voice agent once said "across all product lines" about a saving that is one line's. The figure it
  showed was the verified one.

## Load: several judges at once (live, no Gemini calls)

Each simulated visitor opens the landing page, loads the sample, opens its report data and downloads the PDF.

| Visitors at once | Load sample (p50) | PDF (p50) | Errors |
|---|---|---|---|
| 1 (warm) | 2.5 s | 1.9 s | 0 |
| 5 | 9.8 s | 8.6 s | 0 |
| 15 (instance was cold) | 22 s (max 32 s) | 37 s | 0 |

Nothing fails, but CPU-heavy requests queue. The container runs one uvicorn worker (one Python process,
so effectively one of the two vCPUs), and Cloud Run sends up to 60 requests to one instance before it starts
another. The cold start added about 8 s to the first page, so keep min-instances at 1 while judges visit.
If a group demo is likely, the team could try `--concurrency 10` in `scripts/deploy.sh` (bursts spread over
the 3 instances) or `--workers 2` in the Dockerfile. The app already follows runs across instances through
Firestore. Both change cost and behaviour on Cloud Run, so neither was changed blind.

## How it was tested

* **Automated**, all green:
  * backend pytest: 218 tests, 17 of them new regression tests in `tests/test_input_hardening.py` that reproduce the bugs found
  * Firestore emulator test (now also covers the invalid ids)
  * ruff, mypy
  * i18n coverage, `check:format`, build
  * UI smoke test on desktop and 360 px, in Chromium, Firefox and WebKit
* **API, black box** (`scripts/qa/api_check.py`, fixtures from `scripts/qa/make_fixtures.py`; load: `scripts/qa/load_check.py`): 224 checks
  of every endpoint with valid, invalid, hostile and unauthorised input. Run on the in-memory store, the
  Firestore emulator and live.
* **UI sweeps**:
  * 19 pages × desktop/phone × light/dark × 4 languages (247 page views): console errors, failed requests,
    overflow, raw keys, broken images, axe (all rules).
  * A clipped/squeezed-text check of 14 pages × 4 languages × 4 widths, plus own-project pages and WebKit.
  * Every page's screenshot was looked at.
* **Flows by hand in the browser**:
  * tour; Process live; Evidence Lens (all 33 numbers); review approve/edit/typos; money inputs; levers; exports
  * buyer link; supplier statement; spot-check (12 marks, a difference, print, CSV); Ask; Call; /try
  * own project (uploads, handoff, passcode, delete); back/forward/reload; keyboard
  * simulated server errors and missing page code
* **Live with real Gemini**:
  * copilot; report Q&A in English and Hindi; Hindi voice note
  * voice calls (English and Hindi, typed and spoken; in the browser with a fake microphone)
  * a full re-run (222/222)
  * an own project from 6 photos
  * the supplier statement
  * one product-line proposal

  About 0.6 M Gemini tokens in all, plus about two minutes of Live audio.
