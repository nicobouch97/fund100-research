# V6-S1 first exact 95%-invested costed study — 19 October 2026

**Decision: S1 economic plausibility remains exploratory; original 5% HARD MINIMUM cash rule is NOT satisfied. No LIVE promotion.** This study follows the frozen protocol written before the first actual review run:
`research_lab/V6_S1_EXACT95_COST_AND_CASH_FLOOR_PROTOCOL_2026_10_19.md`.

## Original-source execution evidence

- [GitHub Actions original-costed result run 39249437572](https://github.com/nicobouch97/fund100-research/actions/runs/39249437572) — success.
- **17 synthetic tests passed**, including original full-ETF parity, negative data/source guards, no broker/order capability and drifting cash requirement.
- Exact pre-existing price source: `research_lab/frozen_history_v2.csv`, SHA256 `acc2c8c08953b895ca5062b3cfba287efb97143b10e108e8ce4bd8b82ffb0d28`; existing revised-vendor research dates already studied by earlier Fund-100 experiments.
- Immutable targets: **XLK 47.5%, XLE 28.5%, IWM 19%, cash 5%**. No L1 vol switch. Month-end 10 percentage-point rebalance band; cash earns 0%.
- Trading costs fixed **5 / 15 / 35 bps per BUY/SELL side** using the original L1 attribution convention, which is *optimistic* about precise expense debits from the cash buffer.
- Original detailed full results retained as 90-day GitHub Actions artifact `fund100-v6-s1-exact95-original-frozen-history`.

## Actual exploratory historical results (2014–16 September 2026)

| Cost per side | S1 exact 95%-deployed CAGR | Old 100%-invested static basket CAGR | ACWI CAGR | S1 maximum drawdown |
| ---: | ---: | ---: | ---: | ---: |
| 5 bps | **17.09900%** | 17.90503% | 12.29808% | −32.85421% |
| 15 bps | **17.08743%** | 17.89297% | 12.29808% | −32.86853% |
| 35 bps | **17.06428%** | 17.86885% | 12.29808% | −32.89717% |

At 15bps, S1 underperformed the original 100%-invested basket by **0.80554 percentage points per year**. This is expected for an historically rising concentrated risk exposure with separate cash, but does NOT guarantee the same relative result in future down markets.

**Critical implementation finding:** under unchanged monthly 10pp maintenance,
S1's post-entry modeled cash fraction dropped **BELOW the specified 5% minimum on 2,792 sessions** during the 2014-onward period. Its smallest modeled cash fraction was **2.337138%**, despite every rebalance initially targeting 5% cash. This is the mathematical consequence of long ETF holdings appreciating relative to fixed idle cash while the monthly 10pp relative-weight band often does not trade. The source's simplified expense accounting is favourable to the cash floor; genuine brokerage transaction costs could worsen available reserves.

**Therefore the existing proposed contract's '5% minimum cash buffer' is NOT implementable by the as-studied monthly rule.** It can be a *target* but not a guaranteed invariant without a different, separately versioned account cash-replenishment/position-sizing policy and an appropriate realistic broker-cash test. This is a real release blocker for **this** exact S1 implementation, not a need to wait several months for PAPER profitability.

## Descriptive 2020–16 September 2026 (NOT independent validation)

| Cost per side | Exact S1 CAGR | Old 100%-invested static CAGR | ACWI CAGR | S1 worst drawdown |
| ---: | ---: | ---: | ---: | ---: |
| 5 bps | 19.11974% | 20.09957% | 12.18279% | −32.85421% |
| 15 bps | 19.10518% | 20.08392% | 12.18279% | −32.86853% |
| 35 bps | 19.07607% | 20.05259% | 12.18279% | −32.89717% |

The 2020-onward cash fraction breached 5% on **1,524** modeled sessions and reached a minimum **2.982567%**. This recent period was previously examined and cannot be called an untouched forward holdout. Historic S1/ACWI difference mostly describes exposures selected after examining years where technology and energy did well, **not** a proven market-beating strategy.

## What this changes in the Fund-100 decision

- Keep original four LIVE **ACWI/EEM/XLE/XLV** holdings as the conditional HOLD position while a credible replacement is engineered. No automated liquidation.
- Today's 19 October S1 **$2 PAPER** buy/fractional-sell rehearsal remains a **separate mechanical experiment**, not an economic validation or proof of S1 continuous cash reserves.
- Do not misstate S1 historical 95% CAGR as the 100% portfolio result; do not treat a favourable exploratory comparison as independent alpha.
- Before S1 order release either (a) create and separately test a precisely implemented minimum-cash account risk contract including cost/cash settlement and small-account feasible daily trim, or (b) replace the 'minimum' claim with a clearly disclosed target under a newly reviewed version. **No post-hoc performance parameter optimisation is authorised.**
- Continue genuinely differentiated active stock and commodity research as the route toward the operator's requested actively managed experiment. The sector basket remains a possible **risk-premium capital deployment experiment**, not the final multi-asset alpha strategy.
- Original $130.30 capital ceiling, HIGH tier, STOPPED operator, ENGAGED kill switch, non-leveraged ETF-only LIVE allowlist remain unchanged. This run made **ZERO broker calls / orders**.
