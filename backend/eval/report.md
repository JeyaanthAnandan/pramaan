# Extraction evaluation

Synthetic set: 24 photographed SAMPLE documents (demo/), 213 ground-truth fields.

## replay run - 2026-10-12T19:24:06+00:00

Models: extraction `replay`, second reader `replay` (replay of ground truth: harness self-check, not a model score)

| Metric | Value | Target |
|---|---|---|
| Document type accuracy | 100.0% | - |
| Field accuracy | 100.0% (222/222) | >= 95 % (met) |
| Region hit rate (IoU >= 0.5, of correct fields) | 100.0% | - |
| Two-reader agreement | 99.5% | - |
| Human-review rate | 0.5% | - |
| Total time, 24 documents -> report | 1.2 s | < 120 s (met) |
| Time per document | 0.05 s | - |
| Tokens | 0 | - |

