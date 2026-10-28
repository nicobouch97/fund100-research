# Fund-100 V7 T1 — First actual source-backed cross-asset trend verdict (28 Oct 2026)

**Status: REJECT this exact T1 historical 12-minus-1 trend rule for funded strategy promotion.** This is a research-only verdict, not an independently observed future alpha measurement, a trade instruction, or a new live permission. Record this finding without retrospectively changing weights, instruments, signal lookbacks or historical selection dates to make it pass.

## Original source and completed reproducible run

- The preregistration is `research_lab/V7_T1_PREDECLARED_CROSS_ASSET_TREND_2026_10_27.md` (27 October, before initial original-source acquisition).
- The first successful **merged-main, corrected fee-inclusive** evaluation is [GitHub Actions run 40734397501](https://github.com/nicobouch97/fund100-research/actions/runs/40734397501) from 28 October. Its original public adjusted-price CSV and full 5/15/35bps-per-side report are preserved in artifact ID **12837290834**, name `fund100-v7-t1-crossasset-real-12minus1-40734397501` (90-day retention). The run completed successfully; its focused suite reported **9 passed**. The exact code merge was [PR #369](https://github.com/nicobouch97/fund100-research/pull/369), commit `8030390f470879a943d55fab774677511bd261ff`.
- Model: SPY / TLT / GLD / DBC, positive preclose 12-minus-1 momentum ranking, at most two selected names at 47.5% postfee NAV each; remainder cash, minimum 5%; monthly first-close hypothetical rebalance; long-only, no borrowing. Each synthetic alternative starts at 100 units, and costs entry, actual turnover and terminal liquidation. The exact investment comparator is a static 23.75% each of those four ETFs plus 5% cash, without subsequent rebalancing. The 95%-SPY/5%-cash control has **different exposure and risk**.
- The corrected session risk path includes entry fees and terminal-sale fees on the **actual first and last observed sessions**, not on an invented extra day. It is used for simulated volatility, drawdown, worst-modeled-session return and 6% daily-loss-breach counting. Full static audit v1.17/v1.18 passed for the PR and later merged-main commit.

## Predeclared costed return screen

Literal original GitHub Actions output, **historical net annualised model return percent**, using **15 basis points per traded side** and 5% synthetic cash reservation:

| Fixed historical era | T1 active 12-minus-1 | Static same-four ETF mix | Passive SPY + cash | T1 beats matched passive? |
| --- | ---: | ---: | ---: | --- |
| 2014–2016 | 1.934091% | 0.809847% | 8.607211% | Yes |
| 2017–2020 | 6.542729% | 9.308038% | 14.971420% | **No** |
| 2021–2025 | 17.136549% | 9.923687% | 14.044612% | Yes |

**Frozen rule:** beat the static *same-four-ETF* benchmark **in all three** historical eras at 15bps/side merely to qualify for further independent research. **Observed result: FALSE (two of three, not three of three)**. The 2017–2020 failure is retained. Do not select the best era or loosen costs to claim success. The 2026 YTD window is descriptive only, excluded from the original gate.

## Investment and execution decision

**NO PROMOTION / NO LIVE SWITCH.** T1 is not an evidence-qualified reason to sell existing Fund-100 holdings or divert shared investment capital. Preserve this exact model as a historical control if needed, but do not repeatedly optimise its already inspected source periods. Prior established-literature momentum evidence does not independently establish alpha for this long-only four-ETF implementation. Synthetic 15bp fills are not authentic quotes, trades, tax costs, fractionals, bid/ask spreads or cash-settlement outcomes; Yahoo retrospective adjusted closes can revise, and DBC's index methodology changed in 2025. Cross-asset risk diversification can be useful in principle, but this result is not a forward-return prediction.

Separately, V7 F1's 47.5%-MTUM/47.5%-QUAL/5%-cash quarterly reference was already judged **HOLD / DO NOT PROMOTE** in `research_lab/results/V7_F1_FIRST_ORIGINAL_LISTED_FACTOR_BASKET_VERDICT_2026_10_27.md`. Avoid duplicating or rerunning that already completed baseline merely to generate a stronger-looking historical result.

**P0 launch path remains separate:** original signed private order/owner evidence, independently authorised private-write capability, current authenticated Alpaca account and order/fill/cash reconciliation, account-wide HIGH policy, reviewed standing mandate and protected execution release. Keep the operator STOP and broker kill switch ENGAGED. Original $130.30 cumulative pilot principal ceiling and $65 single-order limit unchanged. No LIVE broker GET/POST/order, private signed-state mutation or portfolio reallocation is authorised by this research result.
