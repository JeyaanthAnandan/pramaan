# EC example notes and differences from the brief

Working rule 9 of the brief: when a guidance document and the brief disagree, the guidance wins,
the difference is logged here, and the team is told. Page numbers refer to the PDFs in
`docs/regulation/` (EC guidance documents of 14 Aug 2026).

## 1. Inconsistencies inside the EC worked examples (not used as tests)

| # | Where | What the guidance prints | What its own inputs imply | Effect |
|---|---|---|---|---|
| 1 | Guidance 5d, Example 2, Table 4-9 (p. 49) | FeCr (52 % Cr) SEE **2.280** t CO2/t | 934,021 t CO2 ÷ 331,213 t = **2.820** | Digits transposed; the slab SEE 1.337 is computed with the emissions column, so the total is unaffected. |
| 2 | Guidance 5d, Example 2, Table 4-10 (p. 50) | Pipes SEE **1.783** | 1.337 × 1.083 + 0.355 = **1.803** (the text itself says 1.337 × 1.083 = 1.448) | Example 2 certificates (G5) use 1.783 as printed; we reproduce the printed figure. |
| 3 | Guidance 5d, Example 3, Table 4-12 (p. 53) | Carbon-steel rod "SEE direct" **1.567** | Example 1 (Table 4-5, p. 42): 1.567 is *total* = 1.539 direct + 0.028 indirect (sintered-ore precursor) | G1 uses 1.567 as printed. |
| 4 | Guidance 5d, Example 3, Table 4-14 (p. 54) | Stainless rod SEFA **0.919** "calculated in Example 2 (bars and rods)" | Not shown in Table 4-11; equals 0.109 (BM col. A, CN 7221/7222) + 1.083 × 0.748 = 0.919 | Consistent; derivation added for transparency (golden test G7). |
| 5 | Guidance 4, Table 2-1 (p. 13) | Caption: "CSCF values have not yet been calculated … preliminary" | Footnote 10 on the same page: CSCF 2026-2030 published in Implementing Decision (EU) 2026/1862 | We treat 2026-2030 as official (see 2a). |

## 2. Where the official sources differ from the brief

**2a. CSCF is official for 2026-2030, not an assumption.** The brief says "CSCF_y default 1.0 —
store as assumption". Commission Implementing Decision (EU) 2026/1862 of 23 July 2026, Article 1
(OJ L, 24.7.2026) sets the uniform cross-sectoral correction factor at **100 % for every year
2026-2030**. `refdata/json/cbam_schedule.json` marks 2026-2030 `official` (parsed from the OJ text)
and 2031-2034 `preliminary` (Guidance 4 Table 2-1). EUR-Lex blocks automated downloads, so the
equally authentic Spanish-language OJ copy served by BOE is the parsed source (`sources.json`).

**2b. Benchmark period code (2) covers 2028-30, not "2028+".** Guidance 4 Table 2-2 (p. 14):
"(1) production years 2026-27; (2) production years 2028-30". For the 2031-2034 projection we
keep (2) and flag the benchmark `preliminary`.

**2c. Fuel factors are official CBAM values, not an IPCC fallback.** Methodology Act Annex II
section G Table 1 (reproduced in Guidance 3 Annex D, p. 139) *is* the IPCC 2006 table (natural gas
56.1 t CO2/TJ, NCV 48.0 TJ/Gg; LPG 63.1/47.3; gas/diesel oil 74.1/43.0; residual fuel oil
77.4/40.4). They are parsed from that page and marked official.

**2d. Gemini location.** `gemini-3.8-flash` and `gemini-3.5-flash-lite` are GA on Gemini
Enterprise Agent Platform but served only from `global`, `us` and `eu` (model pages, Oct 2026), not
`asia-southeast1`. `GEMINI_LOCATION=global`, as the brief anticipated. 3.8 Flash rejects
`thinking_level=minimal`; Flash-Lite defaults to minimal.

**2e. File Search stores are Gemini Developer API only.** In google-genai 2.29 every
`file_search_stores` method raises "only supported in Gemini Developer API mode, not in Gemini
Enterprise Agent Platform mode". Production uses the service account (no API keys), so the rules
copilot uses page-level retrieval over the official PDFs plus Gemini 3.8 Flash grounded on the
retrieved pages, with validated `[Guidance N, p. X]` citations. Switching to a File Search store
needs a Gemini API key in Secret Manager — **a decision for the team** (brief rule 7).

**2f. Default-value Excel is informational.** Both Commission Excel files state that only the OJ
text is legally valid. Values are parsed from the Excel files (as the brief specifies) and the
manifest records this caveat.

## 3. Findings worth showing in the deck

* **A defaulted precursor can make actual data worse than the default.** India's default for
  stainless wire rod (CN 7221, 6.480 t CO2/t) is higher than the default for the finished screws
  (CN 7318 15, 5.720). With the 2026 mark-up the sample's stainless bolts come out at SEE 8.889 on
  actual data with a defaulted rod, versus 6.292 on the good's own default — so the importer would
  simply declare defaults (€402/t). With the supplier's verified data (SEE 1.783, as in EC
  Example 2) the same bolts are 2.371 (= golden test G2) and the buyer's cost falls to €97/t.
  This is the Precursor Lever.
* **The "2.5 % in 2026" myth.** Payable emissions are SEE − SEFA_y, not 2.5 % of SEE. EC Example 1:
  3,690 certificates on 15,670 t embedded = 23.5 % (2027), not 5 %.
* **Example 1's rail certificates include 0.028 t/t of indirect emissions** from the
  sintered-ore precursor even though only direct emissions count for iron and steel goods; we
  reproduce the example as printed (G4).
* **Rounding.** The sample's carbon-steel SEE is 2.0399 at full precision; EC Table 4-13 prints
  2.039 because it adds rounded intermediates (0.196 + 1.843). Pramaan computes in full precision
  and rounds only for display; tests allow ±0.002 t CO2/t.

## 4. Source caveats for the facts in the UI and README

* "25,000-30,000 MSMEs at risk", "EU takes 32-45 % of India's steel exports" and "price cuts of
  15-22 %": Vision IAS summary of a Business Standard article (29 Jan 2026). The summary attributes
  only the export-volume point to ICRA; another summary attributes the 15-22 % figure to GTRI.
* "₹15-20 lakh per MSME" and "90 % reimbursement scheme": reported from The Indian Express
  (30 Jun 2026) by secondary outlets; the scheme was "being worked on", not final.
* EFDA's verification-bottleneck statements are advocacy by a trade association.
