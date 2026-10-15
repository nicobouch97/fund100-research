# Phase 3 C3 WTI source availability — 15 October 2026

**Operational result: BLOCKED PUBLIC DATA INGEST; no real C3
historical output, no strategy backtest, no broker activity.**

Fund-100 implemented and audited its C3 dated RCLC1/RCLC2 front-/second-
WTI futures spread research code. The implementation is careful about
contract rank, negative WTI settlements, the EIA discontinuation after
5 April 2024, assumed publication lag, and the difference between
observed term structure versus earned DBC roll P&L.

- PR: https://github.com/nicobouch97/fund100-research/pull/21
- First historical download on merged main:
  https://github.com/nicobouch97/fund100-research/actions/runs/38714742378
- **11** dedicated C3 offline tests passed.
- The live public EIA API GET attempt returned **HTTP 403 Forbidden**;
  the run correctly failed without creating fictitious quote data or a
  model-performance report.
- No data CSV or report artifact was generated. The historical data source
  is not authenticated or available to the GitHub runner at present.

**Follow-up policy**

Normal branch and main tests are offline and deterministic; no automatic
public EIA requests on every merge. An explicitly manually dispatched
`attempt_public_eia_historical` workflow is retained to retry only if
the source is demonstrably available. If it still returns 403, report
the blocker; do NOT weaken EIA date/source/provenance rules or substitute
DBC share-price changes as fictional futures carry.

Candidate alternate data must supply exchange contract identity, expiry,
a point-in-time published settlement schedule, licensing and contract
roll eligibility. CME settlement public website prices are posted with
delay and its rolling history may be limited; licensed CME DataMine or
vetted vendor contracts may be needed for complete historical term
structures. Official DBC constituent/roll data must be aligned with
the 10 November 2025 index methodology change.

This C3 **data science** milestone is not an investment winner, is not
an actionable DBC futures strategy and supplies no 2026 futures curve.
The commodity research workstream remains active; its existing daily
append-only GLD/DBC C1/C2/static research scorecard continues separately
without C3.
