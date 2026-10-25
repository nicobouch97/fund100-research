# V6-C13: causal gold-versus-cash trend challenger (25 October 2026)

**Frozen research specification before any original-source run. Not an independent holdout. No trading authority.**

## Decision worth testing

C13 V5 found that a 10% fixed GLD allocation, funded from interest-bearing cash while holding 75% in the identical XLK/XLE/IWM mix, had a positive but 2025-concentrated historical advantage. Test whether a *simple, economically interpretable* lagged gold-versus-cash trend filter improves robustness, **rather than** repeatedly describing static-gold results or fitting a threshold to 2025. The separate C1 commodity trend compares gold/DBC to SHY in a commodity-only sleeve; this experiment instead asks whether a small GLD allocation belongs in the **whole equity-matched portfolio**, with realistic cash carry and fixed portfolio costs.

## Exactly one candidate, no optimization

- Retain C13's identical 75% equity weights (XLK 37.5%, XLE 22.5%, IWM 15%) and monthly-close rebalance convention.
- The other 25% is either **25% cash** or **10% GLD plus 15% cash**. No SHY allocation, leverage, derivatives or shorting.
- At each completed month-end close, compute the GLD total-return proxy for the **126 trading sessions ending at the PREVIOUS trading session close**. Compare to the cash-rate proxy compounded over the same 126 intervals, using only C13's three-weekday-lagged 13-week Treasury bill discount-rate observations. If GLD's trailing gross return **strictly exceeds** compounded cash, target 10% GLD; otherwise target 0%. First 126 sessions default to cash. No volatility filter, fitted threshold, stop loss or optimizer.
- Execute the *hypothetical* month-end close rebalance with the target effective next session; charge ETF buy/sell legs at 5, 15 and 35 bp per traded side, including initial equity purchases, but never charge the offsetting cash ledger leg. No broker access.
- Evaluate exactly the existing C13 scenarios: ZERO, IRX_MINUS_50BP, IRX_GROSS. Compare net CAGR and max drawdown with both the **fixed 10% GLD** and **25% cash** portfolios at identical equity exposure. Report turnover, number of gold/cash switches and every dated decision for reproducibility.
- Show descriptive 2014–2019 and 2020-onward subperiods with no fitting or post-period strategy selection. These periods and all of 2014–2026 are **already inspected**. There is **no clean out-of-sample claim** and no promotion from this backtest.
- Reuse the *same invocation's* C13 original vendor-adjusted ETF price and Yahoo ^IRX quote files, with exact C13 report schema, acquisition timestamp, completed session and SHA256 checks. These are revisable prices and an **illustrative**, not executable, Treasury-bill cash-yield proxy. No look-ahead: signals stop at t-1 and cannot depend on t or later.
- Do not infer an investable cash sweep, execution at exact ETF closing price, account suitability, spread/market-impact sufficiency or future alpha from any favourable result.

## Acceptance / rejection

1. Unit tests prove 126-session previous-close causality, positive GLD vs higher-yield cash rejection, no future-data leakage, ETF-only cost monotonicity, source mismatch rejection and unmodified equity mix.
2. Real-source GitHub Actions run must pass these tests, verify exact C13 price/rate hashes and preserve a standalone JSON report alongside the C13 original source files.
3. The full LIVE static audit v1.17 and v1.18 must pass on the PR's exact head **before** merging. Post-merge audit must also pass.
4. Any result is exploratory because the rule was proposed after observing static gold performance and the historical data. No model promotion, no trading intent, no funded orders, no private-state mutations.

**Existing capital ceiling $130.30, operator STOP, ENGAGED kill switch, 14-ETF LIVE whitelist, protected risk controls and every LIVE release lock remain untouched.**
