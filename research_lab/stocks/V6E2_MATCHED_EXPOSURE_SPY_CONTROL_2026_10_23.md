# V6-E2 — exposure-matched SPY control for the original SEC event portfolio

**23 October 2026. Retrospective research correction only. No new strategy, signals, source cohort, price history, account instructions or trading permissions.**

## Why the previous comparison was incomplete

PR #153 constructed one capital-constrained portfolio from the original frozen 8-issuer, 23-event SEC Item 2.02 study (11 selected events). Its comparison with continuously invested SPY measures the opportunity cost of intermittent deployment, but **does not isolate whether the selected stocks beat the market during the same periods with comparable initial capital exposure**. A portfolio spending much of its time in cash will mechanically lag SPY in a rising market, even if the chosen stocks merely track SPY while held.

## Counterfactual implemented inside the existing event engine

For each *actually accepted* stock entry (after the original four-name capacity, same-issuer overlap and cash tests), an independent simulated SPY-only cash account enters on the **same third-session close** and exits on the **same tenth-session-after-entry close**. It uses the **same entry fraction of its own then-current NAV** as the accepted stock entry uses of the stock portfolio's NAV. The SPY control pays the identical 5/15/35 basis-point cost **on both entry and exit** and cannot borrow. If price drift leaves insufficient control cash, its entry is reduced to available cash and the number of such events is disclosed. Skipped stock events never create benchmark positions. All positions must close and reconcile.

The report retains the original full-window continuously invested SPY return **as a distinct economic opportunity-cost comparator** and adds:

- `net_spy_matched_schedule_return_pct` — SPY-only control following accepted stock trade times and capital fractions.
- `portfolio_minus_matched_spy_net_percentage_points` — active stock-selection result after matched trade timing, cash constraint and symmetric fees.
- Control accepted/closed counts, cash-limited entry count and maximum SPY gross exposure.

This is a **counterfactual matching the accepted trade schedule and initial allocation rule**, not an exactly equal daily-beta hedge or sector-neutral factor attribution. Stock and SPY exposures drift between trades, and independent cash accounts may have slightly different available budgets. The original cohort remains 2026-survivor-selected; source prices are retrospectively adjusted, executions at close are optimistic, and the comparison is in-sample. A favorable result would not establish investable alpha or authorize an order.

## Acceptance and promotion

Synthetic falsification must show that identical stock/SPY price paths produce zero matched alpha despite an apparently large full-investment SPY advantage, that divergent paths yield correctly signed relative results, that capacity/overlap restrictions carry through to the control, and that no-signal results remain null rather than invented. The existing original SEC+price artifact workflow and full LIVE static audit must pass before merging. No changes to the $130.30 LIVE ceiling, operator STOP, kill switch, release locks, holdings or private ledger.
