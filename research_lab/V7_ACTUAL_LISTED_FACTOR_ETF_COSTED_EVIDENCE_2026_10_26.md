# Fund-100 V7 — Real listed momentum / quality ETFs versus U.S. and global benchmarks

**Evidence captured 26 October 2026 at 16:15:18Z, research only; no brokerage trades or signal promotion.**

This is an actual ETF-vehicle comparison, distinct from (a) rejected hypothetical 252-session ACWI trend extrapolation, (b) retrospective survivor-selected original SEC quality score, and (c) blocked original Kenneth French academic-download investigation (PR #279, original university HTTP 406). Avoid taking historical factor ETF return strength as a ready-to-execute replacement order.

## Immutable source links and reproducibility

- Source-acquisition CI: [successful original 4-ETF evidence run #40357205585](https://github.com/nicobouch97/fund100-research/actions/runs/40357205585), PR #281 head `daf9f05ebf0ba6e247d71df80f769d024cfbbcfa` at original capture. **12 focused tests passed**.
- Archived original vendor-adjusted daily price source and complete JSON result: artifact `fund100-v7-real-listed-factor-etf-evidence-40357205585` (artifact ID `12665513585`, retention 90 days).
- Source: date-fixed Yahoo/yfinance *adjusted ETF closing prices*, acquired at `2026-10-26T16:15:18Z`, four symbols `MTUM, QUAL, SPY, ACWI`, complete NYSE session calendar from `2015-01-02` through fixed last `2026-10-23`. Original canonical source CSV SHA256 **`98b10182a64025228d8203fade547afa8f392ba75aba379e25ef70ea0e330c7e`**.
- ETFS: MTUM iShares USA momentum fund launched April 2013; QUAL iShares USA quality fund launched July 2013. Exact factor/index methodology, fund exposure, regional beta and concentration evolve; MTUM changed benchmark index version around November 2020.
- Model: buy ETF at first complete window close and liquidate at final window close; **15bps per side for every factor AND benchmark**, dividends embedded in *revisable adjusted closes*. This is not an actual fill, does not charge additional recurring switch turnover, and is not a fund-wide HIGH risk allocation simulation. ETF internal fees are already reflected in market prices; spreads, taxes, and broker/fractional micro-account access are **not verified**.

## Actual same-period after-cost observed CAGR, 15bps per traded side

| Fixed period | MTUM % | QUAL % | SPY % | ACWI % | MTUM - SPY pp | QUAL - SPY pp | MTUM - ACWI pp |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2015–2019 | 14.4803 | 12.0352 | 11.5203 | 8.6778 | **+2.9600** | +0.5149 | +5.8025 |
| 2020–2022 | 6.1516 | 5.3075 | 7.1965 | 3.6045 | **−1.0448** | −1.8889 | +2.5471 |
| 2023–2025 | 21.5911 | 21.7626 | 22.9837 | 20.6166 | **−1.3926** | −1.2211 | +0.9746 |
| 2026 YTD through Oct 23, **excluded from era screen** | 18.5062 | 15.3822 | 14.8308 | 13.1119 | +3.6754 | +0.5514 | +5.3943 |

These are period-specific annualized rates (2026 YTD is annualized over less than a year), **not actual cumulative returns** or independently validated future forecasts. The original JSON report includes 5/15/35bps cost scenarios and volatility/drawdown. Negative years and periods are retained, not refitted or deleted.

## Actual investment research decision

1. **MTUM**: Costed U.S.-benchmark excess return positive in **1 of 3** predeclared multiyear eras; **QUAL** also positive in **1 of 3**. Neither factor vehicle supports an unconditional US-equity sector/style rotation from existing diversified holdings on demonstrated net excess returns.
2. **ACWI contrast is positive for MTUM in 3/3 eras** but is not an apples-to-apples factor-alpha estimate: it also changes US versus global exposure, country risk, sector concentration, market beta and portfolio diversification. Do not call ACWI outperformance evidence of a successfully timed momentum strategy.
3. The 2026 partial-year observation is explicitly *outside the fixed three-era decision*, is not untouched independent out-of-sample evidence, and cannot cure poor earlier stability by post-hoc cherry-picking.
4. Do not promote MTUM or QUAL into the existing autonomous switching research candidate set or the LIVE ETF universe from this study alone. A truly **causal rebalancing** rule needs an unchanged ex-ante signal, suitable US-market benchmark and backtest/walkforward that honors market timing, cash settlement, round-trip turnover, micro-notional, and portfolio-wide limits. Testing the two vehicles as *inputs* to future candidate-generating strategies remains reasonable. Do not refit these periods repeatedly until a favourable outcome appears.
5. The historical return evidence may be economically useful as an **instrument feasibility lead** if the real broker confirms permitted fractional exposure, current quotes/spread and risk concentration; broker readiness is not asserted here.

## System state unchanged

Original maximum-authorized HIGH-risk pilot principal **$130.30**, trading STOP and ENGAGED kill switch; no real broker HTTP, no funded orders, no operator permissions, no automatic instrument release, no claim of validated alpha. The user's standing preference is future **autonomous** cost-aware partial swaps without per-trade manual approval once an independently qualified, fully fenced controller is genuinely released; this pure research study does not make that release.
