# Fund-100 | Sequenced multi-asset build plan

Status: engineering plan, 14 October 2026. This document is **not**
authority to trade or expand LIVE permissions.

## Mission

One operator-selected LOW / MEDIUM / HIGH risk level governs the
*combined* portfolio; one STOP control blocks all strategy engines.
Strategies compete for capital on forward-tested, cost-adjusted evidence,
not number of markets, backtest return, or how often a bot trades.

## Phase order and acceptance gates

| Sequence | Scope | Distinct investment thesis | Progress and promotion rule |
|---|---|---|---|
| **1: ETF pilot** | US-listed global/sector equity ETFs (V5-002) | ACWI benchmark core plus relative momentum satellite, threshold-based rebalance, constrained exposure | **CURRENT:** synthetic end-to-end paper acceptance passes; next is broker-connected paper rehearsal, then explicit small LIVE activation only if approved |
| **2: Bond ETFs** | TLT, IEF, SHY, TIP, LQD (research universe, not LIVE-whitelisted) | Duration / yield-curve regimes, inflation surprise and credit-spread compensation; protect capital when equities struggle | Research-specific data, duration and correlation checks; independent out-of-sample and paper performance before allowlisting |
| **3: Commodity ETPs** | GLD, DBC (research universe, not LIVE-whitelisted) | Trend / inflation regimes / curve carry where applicable; ETF tracking, roll costs and concentration matter | Distinguish futures-backed from physically held products; ETF-specific costs, liquidity, volatility and regime validation |
| **4: Individual US stocks** | Liquid unlevered shares | Quality and earnings revision trends plus medium-term momentum; fundamental and corporate-action filters | Point-in-time fundamentals, delisting/survivorship-safe history, realistic turnover, diversification, corporate actions |
| **5: Crypto** | Existing **separate** BTC/GBP synthetic paper bot | Slow momentum and long-run trend in a 24/7 market with high gap/liquidity/custody risk | Continue prospective forward paper; demonstrate improvement versus simple buy-and-hold net of costs, integrate 24/7 monitoring and exchange-specific API before any LIVE enablement |
| **6: Direct FX** | Major liquid pairs, contingent on brokerage access | Rate differential/carry conditioned on economic regime and trend; account for overnight financing | Dedicated broker/API, realistic spreads/slippage, timezone/event calendar and leverage/margin prohibition or explicit risk model |
| **7: Options/futures** | Only if later justified by independent tests | Structural hedges, carry or volatility opportunities, not naked directional bets | Derivatives account permissions, Greeks, margin, expiry/assignment/roll, stress and capital controls; separate human release decision |

This sequence is subject to empirical evidence and broker permissions.
An asset class may remain paper-only indefinitely if no durable edge appears.

## Non-negotiable shared contracts

1. Risk-level budgets are TOTAL portfolio budgets, not a complete
   budget for each bot. Aggregate asset, sector, factor, currency and
   broker exposures, including overlapping ETF look-through where known.
2. Existing Fund-100 pilot ceiling **USD 130.30** remains a separate
   hard LIVE boundary. No additional deposits enlarge it automatically.
3. No shorting, leverage or options in the current pilot.
4. No bot may self-promote a new strategy/asset universe to LIVE from
   a backtest; it may automatically test and rank research candidates.
5. A single operator STOP must halt new execution across all engines.
   Existing fills/positions require an explicit separate response policy.
6. Each new market must pass: clean point-in-time research, walk-forward
   testing, multiple cost scenarios, independent prospective paper
   operation, end-to-end failure testing and capital/broker reconciliation.
7. Risk monitor must account for each market's actual trading session:
   equities/bonds trading hours; crypto 24/7; FX across time zones.
8. Keep model-selection data separate from evaluation data and preserve
   immutable experiment records. Backtest outperformance alone is not
   proof of an exploitable edge.

## Current milestone evidence

- V5-002 LIVE policy permits only 14 US-listed broad/sector equity ETFs;
  direct crypto, options, FX, bond and commodity orders are not approved.
- The standalone BTC/GBP bot is an independent **imaginary-money**
  experiment with no live-order keys.
- `fund100_etf_paper_rehearsal_v1_0.py` exercises the production
  strategy parser, sizing, risk guards, SELL/BUY orchestrator, cap
  proof, synthetic fills, restart idempotence and STOP response.
  It **does not** connect to Alpaca's paper trading account.
- Until explicit launch authorization, operator control stays STOPPED
  and broker kill switch remains ENGAGED.
