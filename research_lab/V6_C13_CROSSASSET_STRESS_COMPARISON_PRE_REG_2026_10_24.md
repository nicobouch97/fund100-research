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


## Post-run implementation correction — 24 October 2026 UTC

The original pre-registration above is preserved unchanged. A source-code
review **after** the first historical run found that the initial C13 simulator
calculated monthly turnover as the L1 distance across all six weights,
including the untraded CASH accounting leg. This incorrectly charged
transaction costs to both an ETF cash transfer and its offsetting cash entry.
The corrected cost convention charges each actual ETF buy and sell once,
using the L1 distance over the five ETF positions **only**. For an ETF-to-ETF
switch both security legs still incur their respective per-side costs; for
an ETF-to-cash transfer only the security leg incurs costs. Inception ETF
buys remain charged. The output schema is advanced to V2 so previous
C13 V1 historical reports are not silently treated as cost-comparable.

The correction changes **only historical cost attribution**, not the
fixed allocations, 5/15/35 bp assumptions, data window, signal thresholds,
crisis intervals or LIVE controls. New historical output must be rerun on
original-source prices and interpreted as a corrected retrospective
risk diagnostic, not a new holdout or a strategy promotion.

## C13-V3 cash-carry sensitivity extension — predeclared 25 October 2026 UTC

The corrected V2 study held nominal cash at zero return. This structurally
disadvantages the 25%-cash control relative to the 5%-cash GLD/SHY basket
when short-term rates are positive. **Before running V3 on original sources**,
freeze all previous ETF weights, study dates, monthly rebalance convention,
5/15/35bp ETF-only trading costs and crisis windows. Compare exactly three
cash-rate scenarios for **every** existing basket and cost assumption:

1. `ZERO`: original zero-interest cash; exact V2 result parity required.
2. `DFF_MINUS_50BP`: max(0, FRED effective federal funds rate minus a fixed
   50 basis points) as a deliberately haircut cash-yield sensitivity.
3. `DFF_GROSS`: unhaircut effective federal funds rate, an illustrative
   upper-yield proxy, **not an obtainable bank-deposit rate**.

Use the public Federal Reserve Bank of St. Louis FRED **DFF** daily effective
federal funds series, downloaded without API credentials from the official
FRED CSV endpoint. Rates are percentages per year; for each historical
market close, use only the rate observed on or before **three weekdays
earlier**, then apply the *prior session's* lagged rate to the subsequent
cash interval with actual calendar days / 365.25 exponential accrual.
Three weekdays is a conservative approximation, **not a verified FRED
release-vintage or holiday-calendar guarantee**. Any missing, stale,
nonnumeric, duplicate, negative or implausible rate observations stop
the study rather than being silently replaced by zero. Both original
ETF prices and DFF observations must be SHA256-fingerprinted and archived
in the research workflow; vendor data may be revised after the fact.

Primary contrast: diversified-minus-equity-matched-cash-control annualized
net return at 15bp, comparing ZERO, haircut and gross cash. Also report
the original downside/drawdown metrics in all scenarios and both 5/35bp
cost sensitivities. No thresholds, assets or weights may be optimized
using these results. The 50bp haircut is a **scenario assumption**, not
a measured 2014–2026 cash account spread. The federal funds rate is an
interbank benchmark; the calculation omits retail product eligibility,
taxes, cash sweep limits, settlement and broker-specific interest terms.

This is a **retrospective descriptive comparison**, not out-of-sample
investment alpha or a LIVE candidate. Do not change protected execution
policy, holdings, the USD 130.30 capital ceiling, operator STOP, the
ENGAGED kill switch or any LIVE release lock. No broker requests,
private-state writes or orders are authorized.
