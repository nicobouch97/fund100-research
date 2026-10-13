# Fund-100 V2 — Historical data diligence (2026-10-13)

**Status: PUBLIC DOCUMENTATION REVIEW ONLY. No authenticated vendor
sample, historical export, paid subscription, archived data vintage,
terminal delisting price, or provider licence has been obtained.
No claim of alpha, survivorship-free returns or LIVE readiness.**

This review supports [data acceptance gate #4](https://github.com/nicobouch97/fund100-research/issues/4).
It is not an instrument universe or a trading instruction.

## Publicly documented candidate sources

| Provider | Documented information | Missing proof / constraint |
|---|---|---|
| Nasdaq Data Link, Sharadar SEP/SFP | SEP stock OHLCV, `closeadj` for split/dividend/spinoff adjusted close, `closeunadj` for unadjusted close; actions, reference/ticker metadata and historical funds dataset | Free **SEP** sample is 2018-09-01 to 2018-12-31, 30 selected names, and the API requires a Nasdaq Data Link key. A `lastupdated` **date** is not a true intraday data-vintage archive. Adjusted historical prices may incorporate later corporate actions. The public sample cannot prove a comprehensive delisting/IPO universe, terminal cash proceeds or broad multi-regime alpha. |
| Norgate Data | US listed/delisted equities and ETFs, index constituent history, total-return adjustment options; three-week trial with two years of stock history | Data are revised as corrections occur and vendor FAQ says **no revision version history**. Point-in-time past publication snapshots cannot be inferred from a current revised export. Need stable-ID/ticker-history, full coverage and delisting outcome diligence. |
| QuantConnect US Equity Security Master | Documented splits, dividends, IPOs, delistings and ticker-change information since 1998 | **Not** the underlying price data; separate US equity price-data entitlement and LEAN integration are required. Not a verified direct portable CSV feed for V2. |

Authoritative public documentation:

- Sharadar SEP: https://data.nasdaq.com/databases/SEP/documentation
- Sharadar price table fields: https://sharadar.com/prices
- Norgate FAQ, historical revisions and trials: https://norgatedata.com/data-package-faq.php
- QuantConnect US Equity Security Master: https://www.quantconnect.com/docs/v2/writing-algorithms/datasets/quantconnect/us-equity-security-master
- NYSE closing-auction timing (2025-11-18): https://www.nyse.com/research/insights/nyse-closing-auction-timing-shifts-and-marketability-trends

## Required independent acceptance sample

Before a vendor adapter is permitted to produce **evidence-eligible** V2 backtests, acquire a reproducible, legitimately licensed and immutable *archived vintage* for a period including:

1. Stable instrument identity across ticker reuse, name changes, multiple classes, reverse splits, exchange-to-OTC transitions, merger conversion and delisting.
2. Past securities that no longer exist, not just today's active tickers; genuine at-the-time eligibility flags, with documented announcement and effective times where relevant.
3. Actual originally published daily raw close, quoted spread and volume plus separate timestamped distribution/split/corporate-action events. Adjusted total-return series must be reconstructible **as of each historical decision** without future adjustment factors; a present-day back-adjusted `closeadj` download alone is insufficient proof.
4. Version history or original file snapshots that allow comparison of at least two different acquisition vintages and their corrections.
5. Terminal proceeds for more than one delisting type (bankruptcy, acquisition cash consideration, stock-for-stock conversion) plus executable exit/no-fill constraints. If unknown, the research evaluation **must fail**, not assume cash or zero.
6. Historical release timestamps in UTC and authoritative exchange calendar (holidays, half sessions, halts). The EOD-close signal is only allowed after its actual publication; 09:00 NY next weekday is the current **conservative synthetic research cutoff**, not a proven provider delivery SLA.
7. Dataset licensing that permits research use, local automated batch validation and reproducible audit artifacts, plus cost appropriate to a $130.30 capped pilot. No procurement without operator approval.

## Current safety behavior

`data_contract.load_research_bundle` accepts *self-declared* publication timestamps strictly between that session's 16:00 New York close and the following **weekday** 09:00 New York decision cutoff, also capped by the declared historical `as_of` UTC day end. `walkforward.evaluate_decision` uses only the prior close signal, hypothetically enters at the next close and refuses to infer a free skipped trade when a security later becomes ineligible. It fails on missing delisting settlement / exit prices.

**These gates stop known categories of leakage, but cannot authenticate false timestamp declarations or back-adjusted source revisions.** The adjusted-close+next-close trade return does not represent a broker-fillable wealth path; actual closing auctions generally require orders before the official close.

## Procurement outcome

No purchase, API-key request, plugin connection or paid trial activation was performed. The Sharadar free sample still requires authenticated access; no user credentials are requested in chat. No vendor has been selected. Continue all V2 development in offline research branches only and preserve LIVE security blocker #3.
