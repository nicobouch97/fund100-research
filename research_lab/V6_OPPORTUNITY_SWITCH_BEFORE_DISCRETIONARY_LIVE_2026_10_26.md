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


## 26 October original-source 21-session result: do not promote the 252d forecast

The original frozen adjusted-price dataset (SHA256 `acc2c8c08953b895ca5062b3cfba287efb97143b10e108e8ce4bd8b82ffb0d28`) was tested in the post-merge [original-source CI run 40321421773](https://github.com/nicobouch97/fund100-research/actions/runs/40321421773). This is **previously examined historical data**, not an independent holdout. The non-overlapping episodes use signals ending the session before a hypothetical decision, with realized returns measured over the subsequent 21 sessions. Every episode resets to the same synthetic $100 ACWI-50/cash-50 baseline; these are NOT a compounded track record or executable fills.

- **151** completed 21-session windows, 2014–September 2026; **zero** hypothetical switches cleared the existing cost-plus-uncertainty hurdle. The strategy's *actual hurdle-qualified realized alpha is therefore unobserved*, not zero or positive.
- The 252-session extrapolation's mean absolute 21-session forecast error was **393.8157bp** across the ETF observations versus **394.6361bp** for a zero-return forecast: only **0.8204bp** better on this already studied dataset. This tiny descriptive difference does not establish skill.
- Hypothetical candidate allocations, **whether or not they cleared the hurdle**, underperformed a matched 95% ACWI/5% cash portfolio after 35bp each-side switching friction by an average **37.5496bp per candidate episode**. The same diagnostic was **−53.4588bp** (2014–19), **+1.8759bp** (2020–22), and **−44.2882bp** (2023 onward). These are NOT the returns of a live or approved strategy.
- The apparently positive **+26.2374bp** mean candidate edge versus *50% ACWI/50% cash* is not evidence of selection skill: that baseline has substantially less equity exposure. Use the 95%-invested ACWI comparator for the relevant economic contrast.

**Decision: reject the present 252-day trend extrapolation as a qualified switching signal.** It has no cost/uncertainty-qualified events in this study, weak descriptive forecast improvement versus naive zero, and negative overall matched-equity selection economics. Do **not** relax the uncertainty buffer, cost assumptions, historical windows, or the existing protected LIVE risk limits to manufacture trades. No strategy is promoted. Future opportunity research should use genuinely different economic mechanisms and source vintages or independent prospective evidence, with precommitted tests, rather than retuning this already inspected sample. Keep the operator STOP, engaged environment kill switch, original $130.30 ceiling, one-time ACWI release locks and all broker-order permissions unchanged.
