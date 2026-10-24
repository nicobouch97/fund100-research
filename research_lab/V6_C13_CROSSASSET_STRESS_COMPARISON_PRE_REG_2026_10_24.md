# V6-C13: equal-equity-risk cross-asset diversification diagnostic

**Research-only, predeclared 24 October 2026, before the first real source run.**

## Why this is worth testing

Fund-100's four existing V6 equity strategies share substantial market exposure, while prior isolated bond and commodity *trading strategies* did not beat their own passive controls. That does **not** establish whether static, diversified gold and short-Treasury ETF exposures reduce downside in the proposed sector basket. A clean comparison must distinguish diversification from merely selling equities to hold cash. This is a costed historical **risk diagnostic**, not a new signal, optimizer or candidate for automatic LIVE promotion.

## Fixed inputs before inspecting source results

Use the six public, vendor-auto-adjusted ETF closes `XLK`, `XLE`, `IWM`, `GLD`, `SHY`, `SPY` on common completed sessions from **2 January 2014** onward. These are revisable vendor closes, not archived execution prices or verified historical fund-constituent snapshots. `SPY` is an untraded risk reference; nominal cash return is assumed zero. `SHY` is **not cash**: it has interest-rate and ETF price risk. The gold ETF's historical expense/tracking is embedded in adjusted prices.

Three **monthly close-rebalanced** counterfactuals, with trades effective next session:

| Hypothetical basket | XLK | XLE | IWM | GLD | SHY | Cash |
|---|---:|---:|---:|---:|---:|---:|
| S1 sector risk baseline | 47.5% | 28.5% | 19% | 0% | 0% | 5% |
| Equity-matched cash control | 37.5% | 22.5% | 15% | 0% | 0% | 25% |
| Equity-matched diversified | 37.5% | 22.5% | 15% | 10% | 10% | 5% |

The second and third have exactly the same **75% equity allocation**, with the identical 50:30:20 relative sector composition. Thus the incremental GLD/SHY comparison cannot be explained merely by lowering equity exposure. The 95%-equity baseline is for context, not the original S1 execution rule: this experiment **does not** replay S1's 10pp trade band or LIVE risk controller. We charge initial buy costs and each later monthly buy/sell at fixed **5, 15, 35 basis points per traded side**. No dividends are double-counted. We do not model spread spikes, market impact, tax, borrowing, margin, broker share constraints or cash interest.

Predeclared outputs: total net return, CAGR, maximum peak-to-trough drawdown, annualized realized volatility, same-session SPY beta and correlation, mean daily portfolio return conditional on SPY losing at least 2%, and return/drawdown in two well-known already-observed crises: **19 Feb–23 Mar 2020** and **3 Jan–14 Oct 2022**. The historical windows are not untouched holdouts. Report the diversified-minus-cash-control CAGR, drawdown and stressed-day return; no fitted thresholds, ranking or new trading instructions.

## Falsification and guardrails

- Missing or suspicious source bars, incomplete source sessions, inconsistent dates, stale/current-day data and nonpositive prices fail closed; a SHA256 fingerprints the exact canonical vendor price series.
- No same-close look-ahead: a rebalance executed after the close changes **following-session** exposure. Tests alter the final bar to prove earlier NAV does not change.
- The two 75%-equity scenarios must retain identical equity allocations; test no future leakage, cost monotonicity, positive GLD/SHY contribution and strict no-broker boundaries.
- Source downloads occur only in the research workflow, never in the LIVE audit or production runtime. Do not use LIVE/PAPER secrets, private-state write principals or the brokerage.
- Even if diversification appears helpful historically, results do **not** establish future alpha, verified gold crash-hedge reliability or current account suitability. 2026-selected weights applied retrospectively and data-vintage corrections preclude causal strategy claims. Independent current ETF look-through, actual spreads, and realistic portfolio-level risk controls remain future gates.

**No change to the USD 130.30 pilot capital ceiling, operator STOP, ENGAGED environment kill switch, original V5/V6 risk limits, release locks, holdings or broker permissions. No orders.**
