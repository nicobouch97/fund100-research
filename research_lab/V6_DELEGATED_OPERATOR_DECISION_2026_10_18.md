# Fund-100 V6 — delegated investment discretion and current decision

**18 October 2026, following the operator's explicit message at 15:46:34 UTC.**

The operator instructed Fund-100 to act autonomously, including choosing
whether to sell the original investments without asking again for
per-trade approval:

> "im happy to sell the existing if you think best, you don't need
> my approval, this is supposed to be autonomous and decided by you"

**This supersedes earlier research handover language asking again
for chat permission every time a future sell-versus-hold decision
is presented.** The user's actual delegation is now acknowledged in
`research_lab/v6_delegated_decision_scope_v1_0.json`.

## Investment decision — HOLD for now

The current live investments are **ACWI, EEM, XLE, XLV** (historically
four FILLED Alpaca LIVE buys on 5 October 2026). These investments
aren't the operator's desired V6 strategy; holding them is a
**temporary opportunity-cost decision**, not an endorsement of
the old 75%-ACWI V5 allocation as a winning active strategy.

The reason to HOLD rather than SELL on Sunday 18 October:
**none of the five frozen candidate active replacement theses passes
its own preregistered first-pass economic criteria**. Their authentic
source reviews, preserved as source-blob-identifiable evidence:

- V6-R1 fast sector ETF rotation: lost **8.33 pp/yr** vs ACWI
  at 15bps side, ~**19.69× annual turnover**.
- V6-E2 post-earnings events: negative SPY-relative median after
  costs, extremely small preselected event set.
- V6-C1 BTC/ETH trend: ~**30%** historical CAGR at 35bps, but
  much less than BTC and passive BTC/ETH reference, exceeding
  preregistered turnover limit. No customer-specific crypto
  permissions confirmed.
- C6 CFTC oil/gold × ETF trend: roughly **−22%** cumulative
  against **+1.8%** passive in reviewed May–Oct 2026 sample.
- V6-R2 12–1 quarterly concentrated ETF momentum: ~**11.55%**
  historical 2014–2026 CAGR at 15bps vs ACWI **12.30%**,
  turnover **4.02×/year** above precommitted **3×**.
  Recent 2020–2026 was better, but the same older known
  historical data isn't a true unseen holdout.

Selling the positions immediately could incur spread/cost/tax
effects and leave uninvested cash during unknown future gains.
With no credible replacement selected, an automatic sell
would be activity for its own sake rather than a reasoned
higher-return decision. HOLD is conditional and can be
reassessed when actual evidence changes. The stock market is
closed on Sunday and nothing is queued for reopening.

## Autonomy does not mean uncontrolled live order execution

The operator delegated *investment judgement and conditional
sale discretion*. We will not annoy the operator by asking
for a separate new chat message just to give that preference
again. This is NOT a request to invest more than **USD130.30**,
open margin, borrow, short, trade physical futures or override
an account or repository safety STOP.

The existing frozen V5 LIVE deployment policy and GitHub
environment-level kill switch remain unchanged by this PR.
The old source policy's `live_order_authorization_present:false`
and `fund100_live_operator_control.json`'s
`trading_enabled:false` mean actual orders are currently
technically blocked. A future autonomous live executor must
first have an evidence-backed selected instrument/strategy,
a distinct tested executable and risk-limit contract,
a fresh account GET-only holdings/cash/order reconciliation
and verified exchange/minimum/fractional access, with stops,
risk limits and cash-settlement logic. The execution release
must comply with platform-controlled approval/environment
settings; we do not falsely mark STOP false just because
strategy judgement has been delegated.

If a strategy qualifies and can run within those constraints,
the operator needn't repeat permission to *make the investment
decision*. Account platform permissions or an actual transfer
authorization may still require the user's own action. A
change in asset class, leverage or total capital is NOT
inferred from the user's conditional ETF-sale delegation.

## Automated evidence-of-decision

`fund100_v6_delegated_hold_or_switch_v1_0.py` is a
*brokerless* decision audit, **not an order dispatcher**.
It verifies exact immutable git-blob checksums of all five
original failure reports, source-hashed live bootstrap and
STOP/policy, and that the stated user delegation applies.
It yields `HOLD_EXISTING_FOUR_ETFS_NO_SELL` with zero
buy/sell orders and no invented fresh NAV. Any purported
new winning candidate or modified rejection evidence
fails closed instead of automatically promoting a strategy.
Its tests/workflow:
`test_fund100_v6_delegated_hold_or_switch_v1_0.py`,
`.github/workflows/fund100-v6-delegated-decision.yml`.

### Next research milestone

Continue research with genuinely new, official-source market
information and **micro-capital feasible execution** rather
than tweaking failed backtests. This can include validated
independent issuer revisions, a low-turnover active allocation
with an actual economic mechanism, or commodity curve data
in a broker-supported ETF expression once CME provides
FINAL source vintage. Full CME futures/margin remains
unsuitable at $130.30. Do not promise a fixed date for
first profitable trade or guaranteed alpha.

**At writing: No new orders, no liquidation, no fresh
account valuation, V5 bot STOPPED, most recently verified
broker kill switch ENGAGED, risk HIGH, original cap USD130.30.**
