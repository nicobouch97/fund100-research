# Phase 2 bond ETFs — first real-data holdout decision

**Reviewed:** 14 October 2026

**Outcome: KEEP RESEARCH ONLY — DO NOT PROMOTE.**

## Reproducibility

- Source: public historical auto-adjusted ETF closes via Yahoo Finance / `yfinance`. Historical data may be vendor-revised and is not truly point-in-time macro information.
- Universe: TLT, IEF, SHY, TIP, LQD. No bond ETF is allowed in current Fund-100 LIVE policy.
- Study: [GitHub Actions 38623102500](https://github.com/nicobouch97/fund100-research/actions/runs/38623102500), code commit `c43f79b46f18f05ec85604ac30a82c8c7d4d43a3`.
- Observations: 4,725 trading sessions; last date 2026-10-13.
- Dataset SHA256: `7fd146db0b049f84f60c1a9a684f32a34bf63e77c2b7760547b98e2d9a311eac`.
- The data CSV and detailed JSON are retained as the workflow artifact (90 days). This log preserves the decision beyond artifact expiry.
- Results pass 12 isolated research tests and repository audit: 691 tests, static LIVE boundary PASS.

## Predeclared research and holdout procedure

Train over the earliest 70% of sessions and choose one lagged relative-price trend candidate based only on the training period. Evaluate on the most recent 30% chronological holdout, without refitting. Signals use prior-session prices and rebalance next-session exposure after monthly close; estimate both sides' turnover at 5, 15 and 35 basis points.

Training selected momentum lookback **126 sessions** and maximum satellite target **25%** (TLT remains independently capped at 15%). Comparison benchmark: SHY buy-and-hold adjusted close, which is a short-duration ETF and is not equivalent to cash.

| Cost per traded side | Cumulative net excess return over SHY in holdout |
|---|---:|
| 5 bp | -7.86688 percentage points |
| 15 bp | -9.977167 percentage points |
| 35 bp | -14.070787 percentage points |

These are DIFFERENCES in cumulative period returns, **not annualised excess returns**, forecast returns, or investment advice. The separate holdout underperformed SHY across all three friction settings.

## Decision and next experiment

This candidate is NOT allocated funds, not approved to trade PAPER or LIVE, not admitted to any common asset allocator, and not a demonstrated inflation hedge or risk-off diversifier. Do not tune these same candidates to the holdout or retrospectively describe it as independent validation again.

A new preregistered hypothesis may subsequently use timestamped Treasury curve, real yields, breakeven inflation, investment-grade credit spreads and equity correlation/stress regimes. Reserve later observations for genuinely prospective evaluation; evaluate net of costs, liquidity and ETF tracking. A future pass must be independently earned and cannot override the existing operator STOP, US-equity pilot whitelist or USD 130.30 LIVE ceiling.

**Status:** `RESEARCH_CANDIDATE_NOT_PROMOTED`; no broker credentials or orders involved.
