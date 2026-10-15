# Phase 3 C3D — DBC index methodology change: SEC holdings evidence

**15 October 2026 — research only; no PAPER or LIVE trading authorisation.**

## Real SEC disclosures recovered

From the [30 September 2025 DBC Form 10-Q](https://www.sec.gov/Archives/edgar/data/1328237/000119312525270307/dbc-20250930.htm),
we transcribed each **14** reported long commodity futures positions
with contract counts, delivery months and notional USD, totalling
**$1,288,934,852**. The financial statement reports shareholders'
equity of **$1,289,445,913**. The original SEC filing was accepted
after US market hours on **6 November 2025** and has an SEC
**filing date of 7 November 2025**:
[SEC filing detail](https://www.sec.gov/Archives/edgar/data/1328237/000119312525270307/0001193125-25-270307-index.htm).

We require the *next US weekday* as a conservative possible use
date: **10 November 2025**. However, the index methodology itself
**changed effective 10 November 2025**. Therefore **the old Q3
holdings cannot be treated as an investable, historically known
pre-change portfolio**. The April–November old index could only be
reconstructed using genuinely earlier data that were publicly filed
then. No new profitable historical model is claimed.

The prior [C3C dataset](dbc_sec_futures_holdings_2026_q1_q2.csv)
contains **28** futures descriptions from March and June 2026 SEC
quarterly schedules, first usable from **8 May 2026** and
**10 August 2026**, respectively. Comparisons in the new
`fund100_dbc_index_break_c3d_v1_0.py` report show actual
*filing-released sector notional fractions*, not actual investable
index weights, daily contracts, strategy returns or roll P&L.

### Verified market-universe changes

The [DBC 8-K/A effective 10 November 2025](https://www.sec.gov/Archives/edgar/data/1328237/000119312525273297/d70758d8ka.htm)
identifies the following **14 added market exposures** under the
new index: gas oil; COMEX copper; LME lead and nickel; platinum;
feeder cattle; cocoa and coffee; cotton; lean hogs and live cattle;
Kansas wheat; soybean meal and soybean oil. The 2026 actual
quarter-end positions list all 14 newly included alongside all
14 former index commodities.

These data establish a genuine **index-regime structural break**.
They do not establish futures-carry alpha, a precise intra-month
roll schedule, or whether DBC share prices would have increased
under the old rules.

## Data integrity and reproducibility

- Original 2025 source: 10-Q Schedule of Investments, September
  30, 2025 (open futures table); accession
  `0001193125-25-270307`.
- Human-transcribed complete 14-position CSV:
  `research_lab/commodities/dbc_sec_futures_holdings_2025_q3_prechange.csv`.
  Its raw SHA256 is stored in the GitHub workflow result.
- Public availability: 2025-11-07 SEC filing date; 2025-11-10
  conservative earliest research use. Never infer October 2025
  live index weights from a November filing.
- Post-change 2026 source schedule was independently validated by
  the existing C3C tests, including full 28-line coverage and a
  ~3% notional-to-equity reconciliation.
- New offline test suite enforces 14/28 composition, the exact
  issuer announced new exposures, both source metadata series,
  the 2025-11-10 effective date, and no orders or P&L.
- Source CSV is *transcribed secondary data*, not original SEC
  HTML bytes, and any error must be corrected through review.

## Immediate new work

1. Obtain dated **2025 Q1/Q2/2024 Q4** DBC holdings from actual SEC
   filings, to establish the original 14-commodity composition with
   filings available **before November 2025**.
2. Obtain at least one genuine post-change **December 2025** SEC
   snapshot from the [2025 DBC 10-K](https://www.sec.gov/Archives/edgar/data/1328237/000119312526083563/dbc-20251231.htm)
   to narrow the observational structural break, with its own
   *actual SEC public filing date*, not presumed date.
3. Keep official issuer/source distinctions: fund positions versus
   index weights, futures delivery month versus exact expiry,
   quarter-end exposure versus trade/roll execution.
4. Continue acquiring legitimate time-stamped exchange settlements
   and actual constituent/roll rules. Do not turn sparse fund
   holdings changes into historical futures contract P&L.
5. Maintain independently recorded prospective **GLD/DBC C1/C2/static**
   ETF shadow research. No promotion or editing of observed returns.

Fund-100 V5 US ETF pilot remains the only approved LIVE universe;
no additional trades, secrets, risk-budget updates, or permissions.
HIGH risk, the $130.30 LIVE ceiling, operator STOP and engaged LIVE
kill switch remain unchanged.
