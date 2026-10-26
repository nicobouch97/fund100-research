# Fund-100 V7-X1 — fixed Bitcoin sleeve, cross-asset diversification and costs

**Pre-registration, 26 October 2026. RESEARCH ONLY.** This is a distinct asset-allocation thesis, **not** a refit of the rejected high-turnover BTC/ETH trend bot, C13 gold-cash timer or failed equity-only momentum rotation. Neither the overlapping matched-source prices nor the outcomes of this proposed new combination have been inspected during model design. Both underlying source histories have been used in earlier unrelated research, therefore **the joint historical period is not a clean independent holdout**.

## Immutable, original sources already available

1. Original V6-C1 crypto price archive from successful public main-style research workflow **39027912139**, GitHub artifact **12099261808**, file `fund100-v6c1-original-crypto-price.csv`, SHA256 **`ae796a3141a4fe52453af8aa83e879b95841dc28b11b4294b1e0f43077e9f22f`**. Yahoo spot `BTC-USD` and `ETH-USD` 24/7 vendor daily bars 2018-01-01 to **2026-10-16**.
2. Original V6-C13 six-ETF + `^IRX` archive from *main* **40298967469**, GitHub artifact **12638779034** (the existing V5 long original C13 source), ETF file `fund100-c13-price-source.csv` SHA256 **`0e7fb648bea2c9cb199000f1a4f7603a1cdd037ca50ed0e50456d318ccf63b8b`** and original `fund100-c13-yahoo-irx-source.csv` SHA256 **`3016a658b633ed9e1eea6635f46f392f41168a0b42c029738ee2b321515743fa`**. `XLK/XLE/IWM/GLD/SHY/SPY`, XNYS daily ETF adjusted closes 2014-01-02 through 2026-10-23, and quoted `^IRX` rate histories back through December 2013. The issuer-adjusted stock/gold price sources and vendor BTC spot bars remain revisable; no real brokerage ticks or cash rates have been verified. Source artifact archive may expire and must be hash-verified while available.
3. Treat crypto bar labelled a UTC calendar date as **not contemporaneously available** at the US stock close of the same date. For ETF trading session `t`, use Bitcoin's calendar-day bar labelled **t−1 day**, which precedes that US market session. Do not interpolate missing weekends, crypto days, ETF trading days or exchange holidays. Only joint complete NYSE dates **2020-01-02 through 2026-10-16** are considered. No new vendor download or refreshed selection of profitable dates is permitted.

## Fixed portfolio comparison before seeing results

All listed basket weights are target allocations at prior completed monthly closing rebalance and initial start. Every candidate retains an **identical 75% listed U.S. equity mix** (`XLK 37.5%, XLE 22.5%, IWM 15%`) so any Bitcoin or gold incremental outcomes do **not** come from buying more US equities or de-risking the equity sleeve:

| Basket | Equity total | GLD | BTC | Interest-bearing cash proxy |
| --- | ---: | ---: | ---: | ---: |
| CASH_CONTROL_75 | 75% | 0% | 0% | 25% |
| GOLD_10 | 75% | 10% | 0% | 15% |
| BTC_5 | 75% | 0% | 5% | 20% |
| BTC_10 | 75% | 0% | 10% | 15% |
| BTC_5_GOLD_5 | 75% | 5% | 5% | 15% |

The crypto capital concentration is **never above a 10% target** and no shorting, futures, leverage, borrowed capital, margin or BTC/ETH timing signal is permitted. Cash is *not* SHY. Cash-rate base scenario is C13's **pre-existing conservative three-weekday-lagged Yahoo `^IRX` 13-week US Treasury-bill proxy minus fixed 50 basis points**, floored at zero. Also calculate existing gross bill-proxy rate and cash-returns-zero bounds; these are **scenarios, not obtainable account yields or verified first-publication vintages**.

**Trading:** monthly last-completed XNYS close target rebalance, effective only from next source session, including initial buy. Charge ETF purchases and sales **15bp per traded side**, and BTC purchases/sales **35bp per traded side**; repeat with conservative BTC **60bp per side**. Cash accounting is not charged as a traded instrument. Mark interim wealth daily using source-correct BTC previous-UTC-day quote and adjusted ETF prices. Rebalance even unchanged selected names if their weights drift. Compare realized CAGR, maximum drawdown, annual volatility, cumulative relative wealth and total turnover, and segment returns in fixed **2020–2022** and **2023–2025** eras, with **2026 YTD** held separate descriptively. Report individual calendar-year relative log-return contributions so one bull year cannot masquerade as robust alpha, but no fitted break date, largest-year exclusion trading model, or out-of-sample claim. Benchmark matched cash control and static GOLD_10, not only raw SPY.

## Falsifiability

- If exact archive file SHA changes or full original-source validators fail, **ABSTAIN**; do not reread live prices from an updated vendor or use made-up data.
- If a crypto weekend or NYSE session is missing, **ABSTAIN**; a missing BTC trade date must not be filled silently.
- Every position cost is charged, including both legs of BTC/ETF swaps. Verify cost monotonicity, no future crypto quotes and equal equity weights.
- A retrospectively positive BTC total return or comparison in several regimes does **not** establish an investable strategy, an independent causal expected return, a fill at the backtest close, sufficient BTC liquidity, an eligible UK retail Alpaca crypto account, tax/spread/currency-adjusted net P&L or that volatility caps hold between rebalances.
- Do not promote a strategy from this already historically inspected single-period study. Real LIVE brokerage instrument qualification, 24/7 controls, after-tax fee capacity and a valid future holdout would be additional necessary evidence; **no per-order approval requirement** is imposed by this offline study.

**LIVE risk/account stays unchanged:** original maximum authorised investment capital $130.30, user-selected HIGH risk, trading STOP and ENGAGED kill switch, no live crypto or new instruments, no private-state writes, no Alpaca HTTP and no real-money orders.
