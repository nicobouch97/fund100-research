# V6-L1 — aggressive sector-risk premium with volatility-dependent exposure

**Research hypothesis and all model parameters registered 18 October 2026 BEFORE first L1 real historical result.**

## Purpose and economic distinction

The operator correctly objected to waiting months for forward P&L before a USD130.30 real-money experiment. Historical research, economic logic and an operational rehearsal should be the launch-selection tools; genuine forward observations belong to **ongoing live learning**, not a prelaunch calendar gate.

The first economically distinct rapid-launch candidate is **volatility-conditioned long-only equity risk-premium exposure**. Unlike the rejected V6-R1 and R2 which frequently re-rank and rotate sector momentum winners, this strategy **NEVER selects winners using past returns**. The exposure selection is frozen in advance and changes only for a statistically motivated RISK state. Long-run equity risk premium and high risk sector factor exposures are the return source, not claimed prediction of tomorrow's prices.

Related economic background: Moreira and Muir (2017), "Volatility-Managed Portfolios", Journal of Finance DOI 10.1111/jofi.12513, finds meaningful benefits for several volatility-managed factor portfolios. However later broad critiques report volatility scaling is not universally helpful; this study of concentrated sector ETFs is **NOT** a reproduced or proven implication of that paper. No one has demonstrated net alpha for this exact Fund-100 model.

## Full frozen V6-L1 trading logic — no after-the-fact retuning

- Research instruments only from current whitelisted ETF universe, avoiding untradeable CME CL/crypto/individual stocks: **XLK tech 50%, XLE energy 30%, IWM small caps 20%**, gross maximum 100%. No borrowed cash, derivative, short, futures or margin, and no new assets.
- When SPY annualised realised volatility over **20 previously completed daily returns** exceeds **30%** (strictly greater), reduce every sector weight by **50%**, leave other 50% as unremunerated cash. Else hold full prescribed risk portfolio. The exact volatility formula is sample standard deviation times sqrt(252).
- Only decide on the last available completed US trading session of each calendar month, using the SPY return series **through the previous session (t−1)**, trade at the decision day's close, and receive returns no earlier than the following session. This end-of-day fill is a favourable modelling assumption, not an authentic auction fill.
- Monthly rebalancing: if ANY sector allocation differs from its target by >= **10 percentage points** after day's price moves, trade ALL differences; otherwise retain natural drift. Sum absolute difference is gross turnover, bid/ask and friction applied on EACH side.
- Original SHA256 locked historical `research_lab/frozen_history_v2.csv`, exactly `acc2c8c08953b895ca5062b3cfba287efb97143b10e108e8ce4bd8b82ffb0d28`. It has been studied in prior Fund-100 research, therefore 2014–Sep2026 and 2020–Sep2026 results are **exploratory** and NOT independent validation.
- Model 5, 15 and 35 basis points per traded unit, all costs as NAV reductions; zero cash return, no dividend double-counting, no financing, no GBP tax/FX, fractional-share / minimum order fills unverified. If no current prices, abort.
- Compare annualised historical return, maximum drawdown, volatility, annual turnover, number of actual rebalances and risk-off sessions with passive ACWI. Historical 2020-onward must be shown separately to expose regime dependence. DO NOT optimise allocations, volatility threshold or band against these historical results.
- Research-only micro-pilot *plausibility* screen (different from alpha certification): turnover <= **4x NAV/year**; historical drawdown >= **−60%**; no leverage; correct original source; at 35bps/side annual return above **−5%**, avoiding a historically destructive active strategy; volatility conditional rule exercised at least once. A passed screen does NOT assert market-beating returns, even if retrospectively true. A failed screen rejects the candidate. Do not lower thresholds afterwards.
- Even a passed L1 PLAUSIBILITY screen cannot create an order. **The existing V5 HIGH profile maximum single sector ETF weight is 25%**. L1 50% XLK therefore requires an entirely separate versioned concentrated HIGH risk definition and tested combined-portfolio drawdown/volatility stops, active SELL/BUY settlement-aware execution, fractional notional verification and an operator-level live release aligned with GitHub environment permissions. Current operator remains STOPPED/kill switch engaged.
- This is an *unproven high-risk experiment*, not a recommendation or profit guarantee. $130.30 is the existing authorisation ceiling not necessarily account buying power. Four LIVE ETF holdings were independently checked 18 October and remain HELD until an approved replacement is operational.
- PAPER rehearsal should validate the actual request types, minimum notional, order state transitions and no-double-order logic, **not earn a specified number of days of paper P&L**. Forward monitoring measures LIVE learning and can trigger a halt/strategy version review, not on-the-fly self-optimisation that leaks future data.

## Initial release process (supersedes forward-profit prerequisite)

1. Specify one economically distinct fixed strategy, cost assumptions and historical loss scenario BEFORE first actual research run.
2. Test existing historical data now (including periods where losses occur) with true chronology and one prespecified plausibility screen; no infinite benchmark-beating parameter search.
3. Verify small-account broker asset support, no leverage/margin, capital ceiling, fresh LIVE cash/positions; test orders in PAPER quickly for mechanics only.
4. Install a separately reviewed LIVE concentrated-risk manifest and one execution engine with stop/cash/market-order controls. Only then release an experimental LIVE allocation using **existing** capital. Explicit client brokerage/environment permissions still apply.
5. Track forward LIVE returns and transaction costs to decide whether to revise future separately versioned strategies; avoid fitting to noise.

Published background: https://doi.org/10.1111/jofi.12513 .
