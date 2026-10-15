# Fund-100 Phase 3 C3E — five genuine DBC quarterly SEC futures holdings

**Source status: verified report sources, human-transcribed futures positions;
research-only. Recorded 15 October 2026.**

We extend the already audited C3C/C3D DBC SEC holdings work, capturing
the 14 open futures position descriptions as of **30 June 2025** and
all 28 open futures descriptions as of **31 December 2025**. These
bracket the index-methodology expansion effective **10 November 2025**
and provide a five-observation historical timeline, not tradable daily
futures positions.

| Fund statement date | Number of reported futures descriptions | SEC filing date | Conservative earliest use date | Source |
|---|---:|---|---|---|
| 30 June 2025 | 14 | 7 Aug 2025 | **8 Aug 2025** | [DBC 2025 Q2 10-Q](https://www.sec.gov/Archives/edgar/data/1328237/000095017025105193/dbc-20250630.htm), [SEC filing index](https://www.sec.gov/Archives/edgar/data/1328237/000095017025105193/0000950170-25-105193-index.htm) |
| 30 Sept 2025 | 14 | 7 Nov 2025 | **10 Nov 2025** | [DBC 2025 Q3 10-Q](https://www.sec.gov/Archives/edgar/data/1328237/000119312525270307/dbc-20250930.htm) |
| 31 Dec 2025 | 28 | 2 Mar 2026 | **3 Mar 2026** | [DBC 2025 10-K](https://www.sec.gov/Archives/edgar/data/1328237/000119312526083563/dbc-20251231.htm), [SEC filing index](https://www.sec.gov/Archives/edgar/data/1328237/0001193125-26-083563-index.html) |
| 31 Mar 2026 | 28 | 7 May 2026 | **8 May 2026** | [DBC 2026 Q1 10-Q](https://www.sec.gov/Archives/edgar/data/1328237/000119312526209724/dbc-20260331.htm) |
| 30 Jun 2026 | 28 | 7 Aug 2026 | **10 Aug 2026** | [DBC 2026 Q2 10-Q](https://www.sec.gov/Archives/edgar/data/1328237/000119312526338697/dbc-20260630.htm) |

Q2 2025 was accepted 7 Aug 2025 **after** the US market close.
The Q4 2025 Form 10-K was accepted 27 Feb 2026 **after** the
US market close but has SEC filing date 2 Mar 2026; we deliberately
use 3 Mar. Each source is only eligible to affect a research
decision on or after its conservative use date. In particular,
the 31 December 2025 positions **were not known in December or
January**; even 2 March 2026 is conservatively excluded. The
September 2025 disclosure became available on the 10 November
index reform date, so it cannot establish a contemporaneously
known before-change portfolio for a pre-reform trading backtest.

## Reconciliation and reproducibility

The official June 2025 schedule reports gross open futures notional
**$1,230,805,407** against total shareholders' equity
**$1,230,605,532**. The official December 2025 schedule reports
gross open futures notional **$1,223,550,999** against shareholders'
equity **$1,223,200,118**. Gross notionals are neither market value
of owned securities nor futures profit; the approximate 3% equity
reconciliation is a transcription plausibility check, not a
replication of accounting.

The two new dated full-position CSVs are:
- `research_lab/commodities/dbc_sec_futures_holdings_2025_q2_prechange.csv`
- `research_lab/commodities/dbc_sec_futures_holdings_2025_q4_postchange.csv`

They are normalized transcriptions of official SEC descriptions,
including minor source naming variations such as
`CME Cattle Feeder` standardized as `CME Feeder Cattle` to match
the other reports. They are **not original SEC HTML bytes**.
The C3E report records SHA256 values of each transcribed source,
audits exact complete 14/28/28/28/14 universe, stated gross
notional, filing IDs/dates, sector fractions and conservative
as-of lookup. No securities/PAPER/LIVE broker details enter
the dataset or workflow.

## What this now permits, and what it does not

We can describe historical period-end notional concentration,
the broadened post-November commodity universe, and reported
delivery-month transitions at the five actual statement dates.
We **cannot** infer individual day-to-day futures positions,
precise expiry dates, roll timing, actual futures settlements,
net profit from roll, official optimized DBIQ index weights or
an implementable backtested C3 strategy.

An SEC filing's historical quarter-end positions have been
disclosed *after* the fact. A valid date-aware research study
must use only the latest **already-filed** snapshot or preserve
an explicit `NOT_KNOWN` state. Forward decisions cannot choose
a next-quarter contract based on late-filing hindsight.

The existing independently collected commodity GLD/DBC forward
research ledger stays untouched. No new capital, data licence,
market API key or trading permissions have been used. LIVE
operator STOP and HIGH risk setting, original 14 equity ETF
whitelist and $130.30 maximum pilot exposure remain unchanged.

**Next research milestone:** acquire actual contract expiry/settlement
data and historical DBC roll-selection logic, ideally covering
the November 2025 break, then preregister a forward-testable carry
hypothesis that must compete against capped static GLD/DBC and the
original C1/C2 models. The SEC record alone cannot do this.
