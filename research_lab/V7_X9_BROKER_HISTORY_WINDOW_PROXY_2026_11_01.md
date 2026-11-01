# V7-X9 — account-risk window semantics, fixed retrospective sensitivity (1 November 2026)

**Research-only. No change to LIVE risk controls, capital ceiling, STOP, kill switch, signed state, broker transport or permitted asset universe.**

## Why this matters

The original X9 after-cost next-close risk-maintenance study applies an **inception-to-date equity peak** for its 20% drawdown STOP and waits for **63 daily returns** before testing its 35% annualized-volatility STOP. It uses inclusive daily-loss/drawdown comparisons. The existing broker-history portfolio risk guard instead considers up to **70 equity closes** (69 return intervals), accepts at least six funded equity closes for sample volatility, uses strict loss/drawdown threshold comparisons and conservatively considers an additional zero return when the current account mark could duplicate the last history mark. These differences can change the **first STOP date** and hence the actual time spent invested and after-cost returns.

The original X9 is **preserved exactly** as the default. An explicitly selected `BROKER_70_CLOSE_69_RETURN_WINDOW_PROXY` mode replays the **same source-frozen adjusted-close S1 path**, existing $1 modeled routine SELL minimum, next-close-only fixed share exits, 5/15/35bp per-side costs, predeclared 2014/2020/2023 windows and $130.30 pilot-sized hypothetical capital. It changes only the account-history window interpretation, **not** the 6% daily loss, 20% drawdown or 35% volatility ceilings.

The comparison is reported for all registered costs and historical cohorts, including first STOP signal and after-cost full-window CAGR. **Do not select whichever risk-history mode produces better historical returns.** The original is a preserved study; the proxy is a semantic reconciliation diagnostic.

## Limitations and decision

The proxy is **not** the production risk monitor, does not authenticate real Alpaca account history or cashflows, and cannot determine whether a current equity mark has a genuinely distinct timestamp. It deliberately chooses the larger volatility from observed returns and a zero-appended alternative, but does not model the production reader's 25% daily equity discontinuity rejection, actual account funding adjustments, intraday losses, current broker order state, real fills or settlement. The model's immediate $1 risk-repair tickets and fractional full-exit exceptions remain hypothetical. Cash-floor and concentration breaches still receive the original X9 SELL-only maintenance response, not a waiver.

This study uses repeatedly inspected retrospective data; neither scenario establishes independent alpha or permits a funded trade. An eventual authenticated, signed, restart-safe controller must apply the **actual approved risk contract**, not pick the most favorable research approximation. LIVE STOP, capital and release locks remain intact.

CI evidence and source-frozen results are produced by the existing `fund100-v7-x9-delayed-risk-maintenance.yml` workflow; do not claim them passed until the final-head run completes.
