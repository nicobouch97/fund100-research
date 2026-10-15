# Fund-100 V6-R1 — first aggressive concentrated rotation exploratory result

**15 October 2026 — strategy REJECTED for LIVE migration.**
Implementation: \`fund100_v6_aggressive_rotation_research_v1_0.py\`.
Immutable preregistered rule: \`V6_ACTIVE_AGGRESSIVE_RESET_2026_10_15.md\`.
Original frozen history: \`research_lab/frozen_history_v2.csv\`, SHA256
\`acc2c8c08953b895ca5062b3cfba287efb97143b10e108e8ce4bd8b82ffb0d28\`.
Original user goal: replace 75%-ACWI largely passive V5 with a more active, concentrated strategy — not necessarily to own fewer ETFs regardless of achieved performance.

## Actual historical review

[GitHub Actions V6 test and data run 38772847954](https://github.com/nicobouch97/fund100-research/actions/runs/38772847954) **SUCCESS**.
16 synthetic risk/lag/source tests passed. The code deliberately cannot use a broker, sell any live position or produce trade permits.

Comparison period beginning **2014-01-01**, ending **2026-09-16**; includes years already explored by prior Fund-100 research. These are **exploratory differences in annualised percentage-point returns against passive ACWI**, NOT out-of-sample evidence, future forecasts, or absolute strategy returns.

| One-way transaction-cost assumption | V6-R1 minus ACWI annualised return | V6 max drawdown (exploratory) |
| --- | ---: | ---: |
| 5 bps | −6.2656 percentage points | −20.2234% |
| 15 bps | −8.3343 percentage points | −23.4907% |
| 35 bps | −12.3557 percentage points | −32.7175% |

Annual **gross weight turnover sum** was **19.68715 x NAV** (reported for cost scenarios), a major reason friction compounds against this weekly concentrated method. Actual execution spreads, market impact, latency, and GBP/USD FX frictions were not independently verified. An apparently smaller historical drawdown at the 5 bp cost does not rescue the large opportunity cost versus ACWI.

**Decision: DO NOT PROMOTE V6-R1 TO REAL MONEY.** It supplies useful negative research evidence that trading more aggressively and concentrating capital is not automatically a strategy with positive expected alpha. It would also exceed current HIGH live satellite concentration of 25%, requiring a separately approved risk-profile change even if it had passed economic comparison.

## Next strategy-development direction

Do not tune the same 63/126-day coefficients, 35/35/30 slots, 200-day regime threshold, and Friday rotation on this already used history to fabricate a new 'holdout winner'. Instead pursue **economically separate** hypotheses and datasets:
1. Authentic quality/analyst-earnings revision + event/catalyst strategy on individual stocks once the P4F source and proper security/total-return master can support genuine source-timed decisions.
2. Actual dated commodity futures term-structure/carry and gold risk-hedging signals, not inference from sparse DBC quarter-end filings. Historical C1/C2/C4 ETF price candidates also failed static references.
3. Broader low-turnover momentum evidence and cross-market regime methods under an *explicit separate preregistration*, assessed with a fresh period, spread-aware costs, and non-leveraged microaccount constraints; not simply a V6-R1 rescue optimisation.
4. Broker/exchange requirements and custody/market limits before crypto and FX LIVE.

The V5 real portfolio has **not** been liquidated or modified, all old automation remains STOPPED and kill switch ENGAGED. V6-R1 is a research rejection, not a replacement allocation.

No automatic LIVE promotion. After a genuinely promising and implementable V6 winner is selected, issue a specific fresh holdings/sale/transition plan for user's **explicit** permission; no trades just because this study exists.
