# Fund-100: entry-cash policy scenarios, not a permanent 95% exposure ceiling

**21 October 2026. Research-only amendment to the V6 cross-asset capital arbiter.**

## Motivation

The initial central research arbiter used a 95%-invested cap and a 5%-cash floor. That was an illustrative V6-S1 entry assumption, not a demonstrated optimum and not a sensible *continuous* fund-wide rule. Historical fixed-mix modeling already showed 2,792 sessions below 5% cash when invested holdings appreciated between rebalances. Forcing the fund back to 95% gross whenever prices rise would require extra turnover and could defeat the investment goal.

A liquidity buffer should depend on order sizing, settlement, actual execution costs, cash needs, and risk tier; **nothing in the research proves a universally optimal 5% strategic cash allocation**.

## Version 1 offline comparison

The original fund cap stays USD 130.30 in all **synthetic** scenarios. One explicit `cash_policy` value selects the assumed entry budget; the named choices are not LIVE-authorized policies:

| Research scenario | Max intended gross at entry | Minimum planned entry cash | Exact max example deployment |
| --- | ---: | ---: | ---: |
| `BASELINE_95` | 95% | 5% | $123.78 invested; $6.52 cash |
| `LOW_BUFFER_98` | 98% | 2% | $127.69 invested; $2.61 cash |
| `FULLY_ALLOCATED_100` | 100% | 0% | $130.30 invested; $0.00 cash |

100% is a **ceiling**, not a direction to use all money. Shared instrument, factor, and per-asset-class hypothetical limits may leave significantly more idle funds. No borrowing, margin, shorts, FX funding, derivatives, or separate bot capital pools are introduced.

The default for old code stays `BASELINE_95` to avoid quietly changing archived research assumptions. Explicit selection is required to compare the 98/100 alternatives.

These calculations describe a possible **point-in-time entry**. Holdings can move above or below that initial percentage with market prices; this research module does not monitor markets, force a SELL to maintain a daily floor, calculate volatility, certify affordable orders, or check brokerage-settled cash. Mark-to-market rebalancing and order-time liquidity remain separate designs.

## Critical separation from LIVE

- Original V6-S1 high-risk proposal still explicitly uses XLK 47.5% / XLE 28.5% / IWM 19% / cash 5%, with a proposed maximum gross exposure of 95%. This amendment **does not** rewrite that frozen manifest or claim it is presently released.
- Actual operator `trading_enabled=false`; broker kill switch stays engaged. No existing holdings sold.
- None of `BASELINE_95`, `LOW_BUFFER_98`, `FULLY_ALLOCATED_100` has LIVE order authority. The new module has no broker or GitHub private-state transport.
- The broker's live cash fields and settled sale proceeds have not been independently resolved for the initial migration. A hypothetical zero-cash allocation does not authorize a zero-liquidation-buffer purchase.
- Per-class and factor caps in the current cross-asset prototype are **illustrative**, not approved permanent fund rules or forecasts.

## Next tests and engineering

Use independent, time-stamped returns, actual spreads, gross/net risk, overlapping ETF look-through, settlement and broker route evidence to choose a strategic cash posture. Compare results after execution costs, include an at-order cash affordability check, and distinguish normal price drift from a real risk breach. A future approved policy version may choose other values; changing this prototype never silently expands V6-S1 or any broker authority.
