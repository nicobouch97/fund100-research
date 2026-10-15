# Phase 3 GLD / DBC first fixed-hypothesis historical review — 15 October 2026

**Decision: RESEARCH-ONLY; NOT PROMOTED TO PAPER OR LIVE.**

## Predeclared strategy and source

- Strategy: `fund100_commodity_etp_research_v1_0.py`; no training-time parameter optimisation.
- Protocol fixed before first public-data run:
  `research_lab/commodities/PHASE3_COMMODITY_PROTOCOL_V1.md`.
- GitHub code commit: `fadedcde0a59f1aea95293341a6edfd9048ff6a9`.
- Real-data run: [GitHub Actions 38708680599](https://github.com/nicobouch97/fund100-research/actions/runs/38708680599).
- Public price data: vendor auto-adjusted daily GLD/DBC/SHY/SPY
  share closes (Yahoo Finance via yfinance); revisions possible.
- Trading sessions: **4,977** through **2026-10-14**. Later chronological
  evaluation starts **2020-11-02** (not proof of prospective performance).
- Input SHA256: `8bd00d8be2f419e127e896db6012f197d5646ff4fd24867bd6dfaa7e4ff36780`.
- Reproducible price CSV + detailed JSON: GitHub artifact
  `fund100-phase3-commodity-research-38708680599` ID
  `11959277832` retained 90 days. This document preserves key findings
  beyond artifact expiry.
- Full audit on merged main: [GitHub Actions 38708680785](https://github.com/nicobouch97/fund100-research/actions/runs/38708680785):
  **714 tests passed**, LIVE static boundary passed; no broker trade path.

## Chronological later-period comparisons

The fixed rule uses prior-session 126-day absolute and SHY-relative trend,
63-session realized-volatility position-size halving above fixed limits,
monthly rebalancing, max GLD target 20%, max DBC target 15% and residual
in SHY. Buy and sell turnover charged at 5/15/35 bp per side.
`SPY` was read only for equity correlation / shock diagnostics, NOT traded.

Results show **cumulative percentage-point difference in net period
return** versus SHY buy-and-hold, NOT annualised excess returns, risk-adjusted
alpha or forecasts. Static benchmark is a monthly-rebalanced, capped
20% GLD / 15% DBC / 65% SHY share portfolio, with identical costs.

| One-way turnover cost | Trend GLD/DBC over SHY | Capped static mix over SHY | Trend shortfall to static mix |
|---|---:|---:|---:|
| 5 bp | +29.19032 pp | +39.68469 pp | -10.49437 pp |
| 15 bp | +27.91685 pp | +39.50015 pp | -11.58330 pp |
| 35 bp | +25.40372 pp | +39.13174 pp | -13.72802 pp |

Trend strategy daily return correlation with SPY on the later historical
evaluation period was approximately **0.15** at all three cost levels.
This is a descriptive measure; it does NOT establish that the commodity
strategy is a reliable equity-market hedge. Real estate, rates, currencies,
equity factor overlap and tail-risk stress need separate review.

## Interpretation and next gate

The commodity sleeve may have an interesting diversification profile, but
the tested 126-session trend strategy fails the simpler static commodity
benchmark even before accounting for data revisions and actual broker
slippage. **No PAPER/LIVE promotion is justified by these results.**

Future work should not tune parameters against the already observed later
segment and then claim an independent holdout. A different predeclared
hypothesis might separate physical-gold safe-haven behavior from DBC's
futures carry/roll and inflation regimes, with real data on futures curves,
fund turnover/liquidity and timestamped macro vintages. Such a strategy
must demonstrate prospective risk-adjusted improvement versus capped
static commodities, SHY and portfolio equity sleeve, including stress
periods and implementation costs.

Under the current Fund-100 LIVE policy, **only the 14 equity ETFs** are
eligible; GLD/DBC remain outside the approved universe, and no asset
may automatically graduate from research into brokerage trading.

**Status:** `FUND100_PHASE3_RESEARCH_ONLY_NO_BROKER`.
