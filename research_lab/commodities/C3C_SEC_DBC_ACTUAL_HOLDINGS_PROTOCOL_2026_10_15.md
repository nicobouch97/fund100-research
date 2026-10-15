# Fund-100 Phase 3 C3C — actual DBC futures portfolio disclosures

**Recorded 15 October 2026. Research only; no trading permission.**

## What can now be verified, for free

DBC's official SEC Form 10-Q **Schedule of Investments** lists
open futures for each disclosed commodity at the quarter-end statement
date. Unlike WTI-only EIA nearby quotes, this is the **fund's actual
reported holdings**, with market/exchange labels, specific **delivery
months**, number of futures contracts and USD notional exposure.

This public filings-based dataset covers **ALL 28 listed long futures
commodity descriptions** in both 2026 SEC quarterly schedules:

| SEC statement date | Public filing date | Conservative earliest use | SEC filing | Reported futures gross notional |
|---|---|---|---|---:|
| 2026-03-31 | 2026-05-07 | 2026-05-08 | [March DBC 10-Q](https://www.sec.gov/Archives/edgar/data/1328237/000119312526209724/dbc-20260331.htm) | $1,689,474,972 |
| 2026-06-30 | 2026-08-07 | 2026-08-10 | [June DBC 10-Q](https://www.sec.gov/Archives/edgar/data/1328237/000119312526338697/dbc-20260630.htm) | $1,576,215,941 |

The public SEC filing dates are evidenced by [March filing index](https://www.sec.gov/Archives/edgar/data/1328237/0001193125-26-209724-index.htm)
and [June filing index](https://www.sec.gov/Archives/edgar/data/1328237/0001193125-26-338697-index.htm).
For modelling, use the *NEXT business day after the public filing date*
rather than use the quarter-end snapshot as if it was published the
same day. The March 31 holdings cannot influence an April 1 trading
decision; the June 30 holdings cannot influence a July 1 decision.

The publicly transcribed dataset
`research_lab/commodities/dbc_sec_futures_holdings_2026_q1_q2.csv`
is version-controlled, source-linked, SHA256-hashed and tests its
28-line coverage, source identities and an approximate 3% reconciliation
between aggregate reported futures notionals and each SEC balance sheet
reported shareholders' equity. The raw dataset is a **human-transcribed
representation**, not original SEC HTML bytes or a licensed market feed;
spot-check source lines and record any corrections through a new reviewed
commit. These USD notionals reflect futures exposures, NOT owned
security market values or realized profit.

For example, COMEX Copper is reported as July 2026 in March and
May 2027 in June; ICE-UK Brent moves April 2026 to August 2026.
This confirms **different delivery months at the two reporting dates**,
not the date/price of an executed roll, and not the number or sequence
of trades between reports.

## Key before/after index-methodology discovery

The official [30 September 2025 DBC 10-Q](https://www.sec.gov/Archives/edgar/data/1328237/000119312525270307/dbc-20250930.htm)
documents the **pre-November-2025 index** as 14 commodities and annual
November rebalancing based on the former fixed weighting convention.
The issuer's [8-K/A](https://www.sec.gov/Archives/edgar/data/1328237/000119312525273297/d70758d8ka.htm)
confirms the **10 November 2025 methodology change**: broadened universe,
liquidity screens, annual rules-based commodity base weights, sector and
single-commodity limits, plus potential intra-year rebalances. The
March/June 2026 futures schedules contain 28 positions, materially
broader than the old methodology. This observation is useful for
index-regime validation, but does NOT by itself prove actual weight
formula or full day-by-day index tracking.

## What we cannot claim

- The 10-Q reports are sparse quarter-end *point-in-time positions as
  later filed*, NOT continuous daily contract holdings.
- Contract delivery months are NOT exact exchange last-trading dates.
- The fund's reported positions are not necessarily the precise
  DBIQ index theoretical weights: derivatives, futures margins,
  collateral, tracking and index adjustments can differ.
- Changes in USD notional combine price movement, contract count,
  subscriptions/redemptions and maturities. Never call a notional
  difference **roll profit** or a commodity futures strategy return.
- No intraperiod spot/forward curves, actual trade dates/prices,
  collateral yield decomposition, or 2026 signal-ready carry was
  obtained. No C3C strategy backtest can currently be justified.

## Next research stage

1. Compare 2025 pre-methodology and 2026 post-methodology disclosures
   with an explicitly *filing-date-safe* availability model. Extend
   the quarter-end coverage only from verified SEC filings.
2. For separately sourced identical contract-expiry snapshots, use
   the strict C3B expiry/settlement importer. Never manufacture
   missing near/far quotes from the DBC notional schedule.
3. Seek actual index roll calendars/constituent weighting logic
   available from issuer/Deutsche Bank as date-stamped public
   material. Preserve rights and provenance.
4. Freeze a futures-carry hypothesis and evaluate future independent
   evidence versus the existing capped static GLD/DBC baseline.
   C1/C2/static prospective daily public ETF research runs on its
   existing clock. C3C is **not** added to PAPER or LIVE.

The US ETF V5 genuine PAPER pilot remains the only trading strategy
track. The LIVE whitelist, user HIGH risk selection, $130.30 pilot
ceiling, operator STOP and kill switch remain unchanged.
