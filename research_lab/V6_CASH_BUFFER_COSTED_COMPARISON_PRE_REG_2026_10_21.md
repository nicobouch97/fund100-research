# Fund-100: registered historical cash reserve comparison (21 October 2026)

**Written before running new 98% comparison. No LIVE promotion.**

Question: what changes economically between 95% / 98% / 100% nominally invested at entry, holding the **same original frozen XLK/XLE/IWM 50/30/20 underlying mix**?

## Frozen scenarios and controls

- Baseline: 47.5% XLK, 28.5% XLE, 19.0% IWM, 5.0% cash.
- Lower buffer: 49.0% XLK, 29.4% XLE, 19.6% IWM, 2.0% cash. This comes from exactly 98% times ORIGINAL sector 50/30/20; it is not backtest-fitted.
- Fully invested: 50.0% XLK, 30.0% XLE, 20.0% IWM, 0% cash, as in the existing original L1 fixed sector comparator.
- Same original source **SHA256** `acc2c8c08953b895ca5062b3cfba287efb97143b10e108e8ce4bd8b82ffb0d28` for `research_lab/frozen_history_v2.csv`.
- Original monthly session check, rebalance only after 10 percentage-point absolute sector-weight drift, *zero* cash yield; cost sensitivities exactly 5, 15, 35 bps per BUY/SELL side.
- Same original 2014-onward window and separately reported 2020-onward *descriptive* window. Use daily NAV changes, CAGR, drawdown and volatility from the existing original L1 metrics function. Compare each cash variant against the original ACWI benchmark. No external fresh historical source or revised source after observing this result.
- Verify exact numerical parity with the existing S1 95% model and original 100% L1 comparator at each cost level. Reject unknown weight sets, data sources or new risk toggles.

## Interpretation

All these data were examined previously when developing the ETF strategy. They are **in sample**, descriptive, not independent expected-return estimates, not strategy-selection proof. Rising equity markets can reward higher exposure while amplifying declines. Do not select among 95/98/100 from this historical winner alone; use market-specific risk and cash/liquidity requirements independently.

No account funding, broker fields, settled-cash verification, positions or orders involved. Do not change the original frozen proposed V6-S1 manifest, operator STOP, $130.30 original capital cap, or active LIVE permissions.

The historical simulator does NOT enforce continuous target cash after prices drift; the reported initial percentages are nominal **rebalancing targets**, not daily hard ceilings. An actual future trading policy must separately handle order-time costs, cash settlement, open orders and volatility.
