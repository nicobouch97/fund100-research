# Phase 3 C3G — first issuer-indexed 28-contract basket snapshot

**15 October 2026 — web-indexed source transcription, NOT independently
timestamped market data, NOT a profitable strategy, NOT trade eligible.**

The official Deutsche Bank
[DBIQ Optimum Yield Diversified Commodity Index Excess Return](https://index.db.com/dbiq-web/indices/95400)
(Bloomberg ticker `DBLCDBCE`) has an *Index Constituents* table indexed
by public web search. It lists **28 futures contract codes**, issuer
displayed contract-month calendar dates and issuer-stated **index
weights**. The weight cells as indexed sum to **99.99%** (display
rounding). This is a different, more specific research input than
DBC's lagged SEC quarter-end futures reported notional exposure.

Our 28-entry hand-transcribed research file:
`research_lab/commodities/dbiq_diversified_index_web_indexed_28_constituents_2026_10_15.csv`.
The issuer names have been linked to 28 corresponding actual DBC
commodity markets in our already vetted SEC June 2026 schedule,
without assuming identical weights at separate observation dates.

| Issuer-listed commodity | Futures code | Issuer displayed calendar date | Listed index weight |
|---|---|---|---:|
| Brent crude | LCOZ6 | 2026-10-30 | 17.85% |
| Light crude | CLX26 | 2026-10-20 | 15.07% |
| Gold | GCZ26 | 2026-12-29 | 8.95% |
| Heating oil | HOM27 | 2027-05-28 | 5.42% |
| Gasoil | LGOZ6 | 2026-12-10 | 9.06% |
| COMEX copper | HGK27 | 2027-05-26 | 2.70% |
| LME copper | MCUH27 | 2027-03-17 | 2.86% |

(The dataset and report contain all 28, not just these examples.)

Issuer-listed aggregate **index** weights by sector, after
mapping exact market names to the SEC sector classification:

| Sector | Indexed DBIQ basket weight |
|---|---:|
| Energy | 53.27% |
| Agriculture | 17.14% |
| Industrial metals | 11.29% |
| Precious metals | 11.76% |
| Livestock | 6.53% |
| **Sum** | **99.99%** |

These represent the public web-indexed issuer basket, **not DBC's
actual contemporaneous ETF positions**. DBC's 30 June 2026 SEC
notional weights were measured on a different date; subtracting
one from the other does not show implementation slippage or
how the index was rebalanced.

## Important source-time limitations

- The official site is a client-side JavaScript application.
  Public search indexed the table and its contract IDs; the
  **original dynamic response/HTML or downloadable source PDF
  bytes were NOT fetched/archived**.
- The web search was performed on **15 October 2026**, but the
  search index did not provide an exact original index effective
  or capture timestamp. Therefore this file is a **web-retrieved
  reference snapshot with unverified as-of**, not a truth-certified
  daily basket available to a historical algorithm on that date.
- The original page names the date column **'Contract Month'**,
  although its values are calendar dates. We DO NOT claim those
  dates are exchange-verified last trade or expiry dates, so the
  C3B strict identified-expiry importer must not accept them
  without additional exchange-source evidence.
- The website's narrative description still refers to 14
  commodities while its displayed table contains 28. That
  appears to reflect stale page narrative after a known
  November 2025 index methodology redesign. The 2026 SEC
  filings also list 28 reported futures descriptions; however
  they alone do not verify the website table's exact capture
  time or concurrent index weights.
- We have not reconstructed even one actual monthly roll trade,
  verified historical signed price/vintage, issuer selection
  PDF content, or futures trading cost.

## Next action

Seek a reproducibly captured **official raw issuer table**, ideally
with a direct authenticated index REST or issuer export including
provider timestamps. Independently obtain the 2025 index
methodology PDF and November 2025 index weights PDF, then the
12 dated monthly contract-selection PDFs. Verify report contents
and rights before computing index-relative futures roll choices
or using them in prospective research. Genuine exchange per-contract
settlement prices, liquidity and collateral information remain
required for historical carry P&L.

The immutable C1/C2/static daily public ETF shadow comparison runs
independently and its past returns must NOT be retroactively
modified. The V5 ETF genuine PAPER workflow, original 14 ETF LIVE
whitelist, STOPPED operator, engaged kill switch, HIGH risk tier
and $130.30 pilot ceiling remain unchanged.

**C3G is substantive market-source discovery, not a C3 strategy
backtest, PAPER trade, LIVE permission or investment gain.**
