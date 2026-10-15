# Phase 3 — C4 stress-overlay first public historical review

**Date:** 15 October 2026
**Decision: NO PROMOTION. C4 RESEARCH ONLY.**

## Reproducible fixed-hypothesis execution

- Pre-declared hypothesis:
  `research_lab/commodities/C4_STRESS_OVERLAY_PROTOCOL_2026_10_15.md`.
- Frozen implementation merged with [PR #29](https://github.com/nicobouch97/fund100-research/pull/29)
  at commit `324410976ab46b3000d795a6e56c22b6f78f4231`.
- Real adjusted ETF price run
  [38736979158](https://github.com/nicobouch97/fund100-research/actions/runs/38736979158).
- Historical public adjusted price source SHA256:
  `fe47ef3a637e5fa74b1d735ceac57a2003746ce9d28b1f4b8cadf86506dbdc17`.
- Archived source prices + research report as artifact
  `fund100-c4-stress-exploratory-38736979158`
  (artifact ID `11974392249`, 90-day retention).
- Dedicated C4 synthetic fixture tests **11 passed**.
- Post-merge static LIVE safety audit
  [38736979039](https://github.com/nicobouch97/fund100-research/actions/runs/38736979039):
  **834 tests passed**, LIVE boundary audit **36 passed**.

## Actual retrospective result

The already-examined late 30% historical segment was used only for
a descriptive comparison against the simpler monthly
20% GLD / 15% DBC / 65% SHY reference strategy.

| Per traded side cost | C4 less static net cumulative return |
|---|---:|
| 5 bps | **−1.40360 percentage points** |
| 15 bps | **−1.56678 percentage points** |
| 35 bps | **−1.89152 percentage points** |

These are **differences in cumulative net percentage-point returns**,
NOT annualized performance, future expectations, returns vs SHY,
nor a clean new independent backtest. The same later price period
had already been examined when C1, C2 and static reference were
compared. The exact C4 volatility/correlation thresholds were
fixed before the first real C4 study; do **not** tune them to
reverse this negative result.

Drawdown/shock-day diagnostics are available in the archived JSON,
but must be inspected independently before making any claim that
C4 offers a risk-adjusted advantage. A lower historical return
does not in itself establish a lower or higher drawdown. No
risk-adjusted superiority has been shown by this review.

## Scope and next steps

This hypothesis was about loss of diversification when GLD/DBC
show high equity correlation while SPY volatility is high.
It **does not test actual futures curve/carry** and cannot
substitute for date-stamped DBIQ index roll selections and
expiry-identified genuine futures settlements. Since both C1
and C2 lagged static in known history and C4 now also lags
static in cumulative net returns, treat the simple static
basket as the honest reference, not a proven standalone
LIVE-ready strategy.

The C1/C2/static append-only prospective ledger has started
and must be allowed to accumulate genuinely new sessions.
Do not revise its already written hash chain just to add
C4; if C4 later warrants prospective observation, start a
separate frozen C4 shadow ledger from the first new completed
market session *after* its code and scorecard freeze.
No automatic strategy promotion.

Continue genuine futures curve research only after permitted
issuer document access and independently verified source
publication/expiry data, or move to another asset class
in the roadmap without making unsupported claims of trading edge.

**Trading boundary:** Original Phase 1 V5 US ETFs only in
LIVE whitelist. No C4 PAPER or LIVE orders or broker access.
Operator STOPPED, LIVE kill switch engaged, HIGH risk tier
and $130.30 pilot ceiling unchanged.
