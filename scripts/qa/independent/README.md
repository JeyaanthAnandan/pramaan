# Independent test factory

A second fictional factory, never shown to the app before 14 Oct 2026, to test that Pramaan's
numbers and reports are right for any exporter and not just the bundled sample. Its expected
results come from a separate calculator, not from the app's engine.

**Kaveri Precision Fasteners (TEST, fictional)** in Coimbatore, Jan–Jun 2026:

| Line | Good (CN) | Rod (CN) | Rod data |
|---|---|---|---|
| P1 | Carbon-steel hexagon nuts (7318 16 92) | Carbon wire rod (7213 91 49) | none: India default + 10 % |
| P2 | Stainless hexagon nuts (7318 16 39) | Stainless wire rod (7221 00 10) | verified statement (SEE 2.150, SEFA 0.880) |

There are 16 documents in new layouts:
- 6 gas bills
- 1 electricity bill
- 4 rod invoices
- the supplier statement
- the production register
- a handwritten scrap log in Tamil, with one figure struck out
- 2 export invoices

The data has deliberate faults:
- The carbon scrap log is 5 t off in March and in May, though the six-month totals balance.
- March gas runs 21 % hot.

| File | What it does |
|---|---|
| `factory.py` | Ground truth: every number printed on the documents |
| `oracle.py` | Independent calculator: reads the Commission's default-value and benchmark files in `backend/refdata/raw/`, applies Guidance 3/4/5d and reproduces EC Examples 1–3 |
| `expected.py` | Builds `expected.json`: SEE, SEFA, costs, savings, pulse and checks per line, plus 162 field values |
| `generate.py` | Renders the documents and adds phone-photo effects (seeded, so the output is the same every run) |
| `run_live.py` | Runs the photos through a deployed service with live Gemini (paid) |
| `compare_fields.py` | Scores each reading against the ground truth |
| `make_fixture.py` | Turns a live run into `backend/tests/fixtures/independent_factory.json` |

```
cd scripts/qa/independent
../../../backend/.venv/bin/python expected.py            # expected.json
../../../backend/.venv/bin/python generate.py out        # 16 photos
../../../backend/.venv/bin/python run_live.py https://<service>.run.app   # live Gemini, about 6 min
../../../backend/.venv/bin/python compare_fields.py      # reading accuracy
```

`backend/tests/test_independent_factory.py` runs in CI. It replays the live readings through the
engine and checks the oracle's numbers, the checks, the PDF, the supplier letter, the monitoring plan
and the verifier pack. The results of 14 Oct 2026 are in `docs/TEST_REPORT.md`, under "Independent
new-factory test".
