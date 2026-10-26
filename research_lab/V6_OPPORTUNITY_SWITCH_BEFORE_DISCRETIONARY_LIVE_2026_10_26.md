# Fund-100 V6 — opportunity-driven rebalancing BEFORE discretionary live rotation

**26 October 2026 | PRIORITY: before first discretionary allocation | STATUS: research-only, no live trading.**

## Owner requirement

Fund-100 must autonomously decide what investments to own, and may partially
or completely rotate existing holdings into more compelling opportunities.
It should not require human approval for each subsequent trade once the
initial standing HIGH-risk pilot mandate has been explicitly activated.
A fixed basket allocation is a fallback candidate, **not** an unconditional
instruction to liquidate existing ETFs.

**Sequencing: implement and qualify opportunity-aware HOLD / SWITCH first,
then commit to discretionary live portfolio changes.** The isolated first
original ACWI inventory-sale technical chain exists for migration, not proof
that selling ACWI today is economically best. Do not unlock even that initial
one-time sale merely to complete an engineering milestone. Exception:
independent account-risk reduction may justify a sale regardless of alpha,
but requires the same live-risk/authorization checks and an appropriate,
independently released live risk-reduction order path (NOT currently active).

## Completed first decision layer (this PR)

Pure `fund100_v6_opportunity_rebalance_economics_v1_0.py` now compares
observed synthetic current dollar exposures against a proposed new target:
- Gains/losses over **one shared predeclared forecast horizon** (5/21/63
  sessions) for ALL affected holdings, with no look-ahead assumption.
- Charges a conservative bps cost on both gross sale AND purchase notional,
  plus a separate turnover-weighted forecast-error buffer and a minimum
  improvement/hysteresis threshold, to prevent habitual churn.
- Supports partial reductions and retained overlap, not just all-or-nothing
  liquidation. Rejects unidentified assets and unsupported forecasts.
- Enforces original USD130.30 maximum deployable pilot capital, 95% max gross,
  5% undeployed reserve, 50% individual-symbol exposure, USD65 single-order
  notional, minimum USD1 meaningful trade, and no negative/leveraged target.
  Growing portfolio equity does not increase permitted invested principal.
- A hypothetical purchase needing sale proceeds is **not** marked executable
  from proceeds that have not independently settled. Broker open orders and
  unreconciled account values reject the comparison.
- All output explicitly says forecasts, signal, mandate and broker snapshot
  are **UNAUTHENTICATED**, live trades not authorised. No signal is selected
  or promoted and there is NO Alpaca GET/POST, no credential or order code.

## Required before any opportunity trade is authorised

1. Develop independent, point-in-time estimates and empirical forecast-error
   uncertainty for eligible candidates. Do not use backtest returns as
   expected live returns. Track calibrated superiority vs HOLD and transaction
   cost benchmarks on untouched validation periods.
2. Join authenticated, versioned deployed-strategy provenance to current
   exact broker cash, positions, open orders, historical fills, risk
   6% daily / 20% account drawdown / 35% realised volatility, liquidity,
   tax/account restrictions and current operator GO/kill switch. Those
   validations are not accomplished by this economic calculator.
3. Compare the *actual* position-aware net impact, including ETF overlap
   and any staged sell/settle/buy, before selecting a portfolio transition.
   Only issue an event if projected **net advantage convincingly exceeds
   friction + uncertainty**; otherwise HOLD.
4. Add a separately reviewed recurring execution controller with standing
   HIGH mandate, verified per-event immutable journal and genuinely
   idempotent broker order IDs, fills and settlement. No manual per-trade
   approval, no resend after ambiguous order responses, no reuse of
   original ACWI first-migration signed seq1/owner fence.
5. Finally, stage one-time funded pilot activation with user authorisation,
   independent V6 GO and broker kill transition. No source flags, permissions
   or real orders are released by this PR.

The goal is **superior long-run net compound returns**, not maximising
the number of trades. Historical model comparisons are exploratory and
cannot establish that a new investment's expected return is better.
