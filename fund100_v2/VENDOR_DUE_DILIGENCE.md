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

## Public LEAN reference sample inspection (13 October 2026)

Public, read-only GitHub references (sample rows were **not copied into Fund-100**):
- https://github.com/QuantConnect/Lean/tree/master/Data/equity/usa/universes/etf/spy
- https://github.com/QuantConnect/Lean/tree/master/Data/equity/usa/map_files
- https://github.com/QuantConnect/Lean/blob/master/Data/equity/usa/readme.md

The SPY ETF constituent samples dated `20201130` and `20201201` contain **503 ticker rows each**, but only **166 distinct trailing SID tokens** per sample. In both, **eight** SID tokens map to more than one ticker, with the most reused token assigned to **309** names. This identifies an important **reference-fixture identity collision**: these tokens are not safe unique security keys as presented, and the samples cannot prove a stable issuer identity map.

The reference ETF fixture is six CSV fields: ticker, LEAN ticker-plus-SID, constituent holdings date, reported fractional weight, shares, blank trailing field. The filename's calendar date is not a certified publication timestamp; the holdings dates may precede it. The referenced map-file `20501231` marker is a future sentinel, **not** an observed delisting or cash settlement. These examples supply neither independent priced trades nor historical corporate-action vintages.

`provider_sample_inspector.py` now checks the format, dates, numeric fields, duplicate tickers and conflicting SID ownership. It emits SHA256 of supplied local text and rigidly marks all outputs `FORMAT_ONLY_NOT_HISTORICAL_EVIDENCE`. No network client, broker credentials, ETF holdings redistribution, implied LIVE eligibility or backtest-import path is exposed. The test fixtures are synthetic. Third-party sample directory states **AlgoSeek data, all rights reserved**; underlying vendor licensing must be resolved before any further reuse.

### Zero-cost candidate (platform-specific)

QuantConnect documents **free cloud access** to its historical US Equity Coarse Universe for universe-selection workflows, and free cloud use of its US Equity Security Master. Coarse history claims daily US equity membership and closing price/volume back to 1998, **but the free Cloud entitlement does not mean the local ZIP or CSV dataset may be freely downloaded or redistributed**. Local access and US equity price data can involve separate licensing. As such, QuantConnect Cloud is the leading *cost-aware feasibility environment*, **not** yet a compatible authenticated source for the existing GitHub Actions research loader. A free account and supported cloud research workflow would need separate explicit operator action and terms review before actual data access.

- https://www.quantconnect.com/data/quantconnect-us-coarse-universe-constituents
- https://www.quantconnect.com/data/quantconnect-us-equity-security-master
- https://www.quantconnect.com/docs/v2/cloud-platform/datasets/licensing

## Bounded free-Cloud coverage probe (prepared; not run in Cloud)

`qc_cloud_feasibility.py` provides a **read-only, aggregate-only** QuantBook feasibility function. It uses QuantConnect's documented current fundamental universe research API, not deprecated legacy `CoarseFundamental`: `qb.add_universe` followed by `qb.universe_history`. Default intervals are four-to-ten-day windows in September 2018, November 2020 and June 2024, with at most ten returned research subscriptions per day and a hard cap of twenty. The callback counts dated records, distinct QC symbol keys, duplicate keys and price/dollar-volume completeness. It never logs names/tickers, exports raw prices, submits broker orders, requests secrets, or calls an Alpaca endpoint. Evidence is **CLOUD_COVERAGE_ONLY_NOT_PIT_ALPHA_EVIDENCE** regardless of success.

An operator with an independently created **QuantConnect Free Cloud Research** environment can add this single pure-Python module as a source file and run the following example in a research notebook (subject to the platform's licence and quota conditions):

```python
from QuantConnect.Research import QuantBook
from fund100_v2.qc_cloud_feasibility import (
    run_cloud_coverage_probe, aggregate_report_json
)

qb = QuantBook()
report = run_cloud_coverage_probe(qb)
print(aggregate_report_json(report))  # aggregate counts and evidence flags only
```

This notebook is a **proposed workflow only** and has not been run in the QuantConnect Cloud runtime; GitHub mock tests do not demonstrate a successful Cloud API request. It will not work as-is until the module is available to the Cloud notebook environment. No user account, external plugin connection, subscription or file transfer has been completed. The free plan lists **one research node** and no live-trading nodes; licensed local data download is separate.

Beware October 2026 fundamental-data changes: legacy Coarse/Fine APIs were deprecated; Morningstar fundamentals underwent a migration with changed reporting dates and missing/renamed properties. The probe uses only price, dollar volume and source-period dates, and its timestamps are **not authenticated publication times**. QuantConnect's research universe history can support access validation but **cannot** establish archived vintages, delisting recoveries, executable spread quotes or independent alpha.

Documentation:
- https://www.quantconnect.com/docs/v2/research-environment/universes
- https://www.quantconnect.com/docs/v2/writing-algorithms/datasets/quantconnect/us-equity-coarse-universe
- https://www.quantconnect.com/docs/v2/cloud-platform/organizations/tier-features
- https://www.quantconnect.com/docs/v2/cloud-platform/datasets/licensing
- https://www.quantconnect.com/docs/v2/meta/change-log

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
