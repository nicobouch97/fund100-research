# Fund-100 V7 — actual costed monthly ETF rotation result: reject this fixed rule

**26 October 2026. Empirical research only — not a funded trading strategy or a LIVE order authorization.** The model and thresholds were frozen before examining the source result. This is the **same exact original source** already captured before strategy development; do not rescue a failed model by retuning it on that history.

## Provenance and exact reproduction

- Original successful `main` research price archive, acquired 26 October: [Actions run 40358792118](https://github.com/nicobouch97/fund100-research/actions/runs/40358792118); immutable artifact ID `12665993930`, `fund100-v7-real-listed-factor-etf-evidence-40358792118`. Adjusted-close `MTUM, QUAL, SPY, ACWI` for every XNYS session between 2015-01-02 and 2026-10-23.
- The original four-ETF canonical source CSV was **SHA256 `cf44f614d211836e83c3d4f9e2e20f2d067beefed193176a630bf334689164dc`**. The study **fails closed** rather than downloading a 2026-later vendor-vintage revised price.
- Actual model research CI: [Actions run 40360554113](https://github.com/nicobouch97/fund100-research/actions/runs/40360554113). All **8 focused tests passed**. Full original return+signal JSON artifact ID `12668480621`, report SHA256 **`c321b22a590469e0c095eed048f66096428688ae90bd04887058ac851ddd3067`**.
- Model: first eligible month 2016-03-01; signal uses t−253 and t−22 closes, ranks all four tickers each month, buys top two at 47.5% each at next first NYSE session close, remaining cash 5%. Rebalance every month, charge genuine simulated 5, 15 or 35bps on BOTH BUY/SELL turnover, including same-name reweights. Passive controls start with 95% SPY/5% cash or 95% ACWI/5% cash, each charges same initial purchase-side cost and then holds. No credit for fictitious trade fees saved, no leverage or intraday hindsight.
- The history is hindsight retrieved, corporate-action/dividend adjusted and may be vendor revised; ETF set and mechanism choice are not an untouched independent holdout. No fill, spreads, fractional share, tax, account binding or real invested P&L has been verified. History is a research comparison, not forecast of future returns.

## Real recorded results

Cost: **15 basis points per traded side**. All are *observed historical scenario annualized* net costed CAGRs or differential percentage points, not gains on the $130.30 actual account.

| Fixed evaluation period | Monthly rotation CAGR | 95% SPY + cash CAGR | 95% ACWI + cash CAGR | Rotation minus SPY | Rotation minus ACWI |
|---|---:|---:|---:|---:|---:|
| 2016-03-01–2019-12-31 | 13.719168% | 15.176959% | 12.811422% | **−1.457791pp** | +0.907746pp |
| 2020-01-02–2022-12-30 | 4.971399% | 7.107074% | 3.596789% | **−2.135675pp** | +1.374610pp |
| 2023-01-03–2025-12-31 | 21.897339% | 22.656381% | 20.247840% | **−0.759042pp** | +1.649499pp |
| 2026 year to Oct 23, **not selection window** | 8.576310% | 15.062422% | 13.314776% | **−6.486112pp** | −4.738466pp |
| Overall uninterrupted 2016-03-01–2026-10-23 | **13.064699%** | **14.893113%** | **12.326160%** | **−1.828414pp** | +0.738539pp |

Across fixed three full historical eras, the strategy **lost to SPY in all 3**. In the fixed 2026 diagnostic window it also lost significantly to SPY and ACWI. At 5bps/side SPY excess rates were **−1.083425pp, −1.727537pp, −0.323859pp** in those three eras; even with unusually optimistic costs the relative conclusion did not flip. At 35bps/side: **−2.203573pp, −2.947225pp, −1.625105pp**.

The model's 15bps full-path max drawdown was **−32.960278%** versus **−32.782858%** for SPY/cash, and annual volatility **17.68656%** versus **17.127606%** for SPY/cash. Cumulative simulated trading friction was **11.1554668 per 100 starting units**, vs **0.1422972** in the SPY buy/hold control. Sum of absolute model turnover relative to contemporaneous equity was **38.8052731**, versus **0.9486482** for passive initial buy. The strategy observed **one end-of-day >50%-single-name concentration event between scheduled rebalances**; real capped-high trading cannot ignore this.

## Investment decision

**REJECT the presently specified 12−1 monthly top-two ETF rotation as a candidate for live promotion.** The expected-return hypothesis has not been substantiated after normal trading frictions, and the monthly rule can drift above the single-name cap. Surpassing ACWI in some periods does **not** establish rotation alpha: the investment universe includes U.S. equity ETFs and may express a region, sector or concentration tilt. No retrospective optimization of lookback, weights, constituent set or rebalance timing to rescue this rule on already viewed history. Future candidates need genuinely distinct causal information and independent evidence, not repetitive engineering around this unsuccessful ETF signal.

### LIVE account

User's standing intended maximum pilot principal **$130.30**, HIGH-risk policy, STOP and kill switch **ENGAGED**. No broker calls or funded orders, no altered positions, no release of the hypothetical rotation controller. User does not wish per-trade manual approvals **once autonomous trading is genuinely released**; that standing objective does not turn a rejected historical research signal into brokerage authority.
