# V6-S1 — overlap-aware low-turnover migration candidate, NOT an order release

**19 October 2026. Research-stage implementation after two verified authentic broker milestones.**

## Observed milestones, not assumed performance

- The real broker's PAPER trading interface completed an actual $2 fractional BUY and exact-qty SELL, with full fill and original PAPER holdings restored. Original [run 39269640353](https://github.com/nicobouch97/fund100-research/actions/runs/39269640353), 19 October 14:30 UTC, main, workflow_dispatch, run attempt 1.
- A fresh authenticated ALPACA **LIVE GET-only** probe on [run 39272813574](https://github.com/nicobouch97/fund100-research/actions/runs/39272813574) 19 October ~14:52 UTC verified four original symbols ACWI/EEM/XLE/XLV in their original quantities, zero open orders, reconciled account cash+equity, selected HIGH risk and ENGAGED LIVE broker kill switch; 4 GETs, zero LIVE orders. Private share quantities and balances were deliberately not printed/persisted.
- Both facts make further transition engineering concrete, but neither implies real-money strategy readiness or an independent active-alpha edge.

## Investment choice: avoid a pointless same-ETF round trip

S1's tentative **whole-account** allocation remains XLK **47.5%**, XLE **28.5%**, IWM **19%**, cash **5% target at entry**, with minimum **5% cash after every new BUY** once all-in costs are conservatively included; natural portfolio gains can lower that percentage between trades without triggering an automatic micro sale. This is the source-faithful proposed S1 risk-premium basket, not a new market-beating active algorithm.

**XLE already sits among V5 LIVE assets and in S1.** An initial hypothetical transition should therefore plan to **retain XLE**, so long as fresh broker valuation proves it is no more than the proposed 28.5%-NAV S1 target and satisfies the 50% absolute single-ETF risk ceiling. Target-only initial exits are **ACWI, EEM and XLV**, not the overlapping XLE. Avoiding an XLE sell followed by buying back the same fund reduces unnecessary turnover, taxes/spreads and T+1 settlement mechanics. This is a design preference conditional on real source evidence, not an issued sell direction or order request.

An XLE overweight position, existing open LIVE orders, unexpected new LIVE holdings, missing/malformed account fields, or any original stop triggers **review / HOLD**, not a forced XLE trim. No paper test certifies the size or current mark of LIVE XLE.

## Future transition execution order (requirements for a DIFFERENT actual LIVE release)

1. Current original V5 controller must be exclusively inactive. A newly versioned **LIVE order executor** and combined portfolio risk guard must be independently reviewed and pinned to its LIVE environment before any order exists. This document does not start such a writer.
2. Authenticate fresh GET account identity, balances, orders and four original positions immediately before acting. Privately reconcile all actual original quantities and account loss/volatility, factor exposure, maximum contribution <= **$130.30**, and no leverage, shorts or outside asset permission.
3. A future risk-cleared, idempotent SELL phase could eliminate ACWI, EEM and XLV while **retaining a non-overweight XLE**, with each executed fill reconciled by client ID and actual position quantity; no blind retries, no concurrent old V5 controller, and no new buys until all legacy unwanted holdings are confirmed flat.
4. Re-authenticate **actual settled, spendable** cash after US cash-equity settlement, considering broker buying power, capital restrictions and fees; a caller boolean or paper balance is not settlement proof. XLE held through transition must remain included in total risk and allocation.
5. A fresh risk-cleared BUY phase could then target XLK, IWM and any permitted XLE top-up, but only if each separate purchase passes the now-correct **5% post-buy account cash floor**, broker min $1 notional, conservative all-in fee/spread buffer, $65 per new buy ceiling, <=50% symbol concentration, <=95% gross and daily-loss 6% / drawdown 20% / annual volatility 35% stop evidence. Actual small final allocations may remain slightly under target if rounding or conservative cash headroom prevents a compliant buy; do not break cash policy simply to hit model weights.
6. Reconcile every fill and positions before claiming the new strategy started. Store only privacy-safe status evidence publicly. No additional deposit or higher risk authorisation follows automatically from paper execution. User delegated portfolio choices, but broker technical permissions and STOP cannot be overridden by a research model.

## What is *implemented* by this PR

- Versioned machine-readable **DRAFT** at `research_lab/v6_s1_low_churn_migration_candidate_v2_2026_10_19.json`, referencing the genuine specific S1 PAPER and LIVE GET-only run IDs, explicitly forbidding orders.
- Pure `fund100_v6_s1_low_churn_migration_v2_0.py` accepts **synthetic/caller-invented examples only**, verifies source/frozen policy and loss-control definitions, and returns **a text stage**, not a notional order, share quantity or executable broker payload.
- Tests `test_fund100_v6_s1_low_churn_migration_v2_0.py` include original 4 holdings, XLE at/over target, residual/open orders, missing settlement, mixed-account failure, stale/bad balances, no broker clients and no trades.
- No change whatsoever to original V5 REAL holdings, LIVE operator STOP, broker kill switch, whitelisted universe, S1 historical-cost model or existing proposed v1 source. No new strategy permissions.

**Decision:** Prefer an eventual low-turnover reuse-XLE transition over an unnecessary sell/rebuy-all scenario, but remain at **`DRAFT_UNRELEASED_NO_BROKER_ORDERS`** until the real LIVE writer, source-authenticated settlement, risk and an actual separate versioned release exist. No months-long PAPER return experiment is required.

**Alpha caveat:** Although exact S1 95% exposure historical 2014–Sept2026 CAGR at 15bps was approximately 17.08743%, that was an extensively studied retrospective sector mix. This shows potential concentrated beta/risk-premium exposure, NOT an independently validated active trading edge. Genuine stock-quality/valuation, commodity carry and crypto/network thesis research continues separately.
