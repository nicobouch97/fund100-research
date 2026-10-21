# V6 95% vs 98% vs 100% nominal entry exposure — 21 October 2026

**Result is descriptive in-sample research, NOT independent alpha, risk-optimal selection, or a LIVE order release.**

## Verified execution

- [Original successful offline history run 39583900182](https://github.com/nicobouch97/fund100-research/actions/runs/39583900182): 4 tests passed; original 95%/100% NAV and turnover regression checked; report generated from original source only.
- Research protocol pre-registered BEFORE the result: `research_lab/V6_CASH_BUFFER_COSTED_COMPARISON_PRE_REG_2026_10_21.md`.
- Verified source SHA256: `acc2c8c08953b895ca5062b3cfba287efb97143b10e108e8ce4bd8b82ffb0d28`.
- Same existing XLK/XLE/IWM 50/30/20 sector basket, prorated to nominal 95%, 98%, or 100% exposure at rebalance. Same monthly check and >=10 percentage-point drift band. Cash yield assumed zero.
- Original fixed-cost scenarios: 5 / 15 / 35 basis points per transaction side. Simplified costed NAV model is not true fractional-order settlement accounting.

## 2014–16 September 2026, original already-examined history

| Transaction costs per side | Entry gross target | Historical CAGR | Maximum drawdown | Realised annual volatility |
| ---: | ---: | ---: | ---: | ---: |
| 5 bp | 95% | 17.09900% | −32.85421% | 21.44238% |
| 5 bp | 98% | 17.60181% | −33.39029% | 22.04412% |
| 5 bp | 100% | 17.90503% | −34.27389% | 22.51822% |
| 15 bp | 95% | 17.08743% | −32.86853% | 21.44249% |
| 15 bp | 98% | 17.58987% | −33.39029% | 22.04447% |
| 15 bp | 100% | 17.89297% | −34.28854% | 22.51836% |
| 35 bp | 95% | 17.06428% | −32.89717% | 21.44274% |
| 35 bp | 98% | 17.56598% | −33.39029% | 22.04520% |
| 35 bp | 100% | 17.86885% | −34.31783% | 22.51868% |

At 15bp, 98% rather than 95% increased historical CAGR by **0.50244 percentage points**; 100% rather than 95% increased it by **0.80554 points**. The 100% comparator suffered a **1.42001 percentage point deeper** maximum drawdown than 95%, and higher realised volatility. This is expected from higher historical exposure to the *same* volatile holdings; it does not prove any excess investment skill.

## 2020–September 2026, previously examined, NOT untouched validation

| Entry gross target | 15bp CAGR | 15bp maximum drawdown | 15bp annual volatility |
| ---: | ---: | ---: | ---: |
| 95% | 19.10518% | −32.86853% | 24.95665% |
| 98% | 19.76361% | −33.39029% | 25.67226% |
| 100% | 20.08392% | −34.28854% | 26.26220% |

## Investment/engineering conclusion

1. Keeping 5% in cash did not maximize historical CAGR in the previously examined bullish sector basket; some cash drag was observed. This alone cannot choose the correct *future* reserve.
2. Higher equity investment increased realized risk, so an operator HIGH risk profile must include gross portfolio risk budgeting rather than just funds invested.
3. A 100% nominal investment target is NOT an operational authorization. Real broker affordability, spread/slippage, unsettled proceeds, open orders and execution precision can require a positive transaction buffer. The favorable simplified cost model cannot prove a true zero-cash order path is viable.
4. The tested 95% / 98% / 100% are **entry/rebalance targets** and drift between monthly decisions. None is a continuous portfolio cash minimum.
5. Do not select the best-performing backtest row as a new signal or retroactively change V6-S1's frozen proposed 95% manifest. Existing LIVE STOP and holdings remain unchanged; broker orders **zero**.
6. The central allocator now permits research scenario comparisons independent of eventual approved cross-asset risk limits, but it still does not have validated performance-ranking inputs.
