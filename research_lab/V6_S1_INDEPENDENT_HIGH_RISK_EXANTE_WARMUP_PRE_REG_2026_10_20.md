# Fund-100 V6-S1 — independent HIGH risk policy, XLE preservation, warm-up volatility protocol

**Pre-registered 20 October 2026 before implementing the policy or running its tests. Original LIVE STOP preserved.**

## Critical discovered inconsistency

The source-pinned original `research_lab/v6_s1_high_risk_micro_pilot_proposed_manifest.json` says `legacy_holdings_must_be_reconciled_and_exited_before_any_buy = ["ACWI","EEM","XLE","XLV"]`. That V6 exploratory proposal predates the source-authenticated [original XLE-overlap preservation decision](https://github.com/nicobouch97/fund100-research/pull/64): actual [Alpaca LIVE account check](https://github.com/nicobouch97/fund100-research/actions/runs/39299643300) confirmed original XLE within draft V6 target, so a needless XLE SELL then BUY is not justified. The original immutable manifest must NOT be silently altered because `source_controls()` and pinned safety source depend on it. This **new, independent** versioned policy exclusively specifies **ACWI, EEM, XLV** for staged exits and **XLE** preserved when <=28.5% draft allocation. If original XLE exceeds permitted cap at a future time, STOP and separately review rebalancing; do not silently liquidate.

V5 HIGH portfolio risk has `max_satellite_weight = .25`; V6 sector proposal targets XLK .475 and XLE .285, so V5 policy **cannot be reused** as risk authorization. V6 separate limits: pilot cap **$130.30**, no extra funding/leverage/shorting, invested gross **<=95%**, each new symbol **<=50%**, available cash **>=5%** after any future BUY, per BUY **$1–$65**, loss stop **6% daily**, drawdown **20% rolling/launch peak**, annual realized volatility stop **35%**, market DAY and fractional order shape. Target draft XLK **47.5%**, XLE **28.5%**, IWM **19%**, 5% residual cash. No proved active alpha.

## Risk evidence and short LIVE warm-up

Original historically funded V5 account had cashflows with **date-only** transfers; its prior raw account equity/return series is NOT verified as cashflow adjusted (real [7-GET evidence 39303201301](https://github.com/nicobouch97/fund100-research/actions/runs/39303201301)). Do NOT pretend historical V5 volatility satisfies the V6 35% stop. Begin genuine V6 performance ledger only at authenticated new V6 strategy boundary after migration, as documented in [PR #73](https://github.com/nicobouch97/fund100-research/pull/73).

This research-only `V6_S1_INDEPENDENT_HIGH_EX_ANTE_RISK_V1` computes an **illustrative annualized ex-ante volatility of the planned 47.5/28.5/19 weighted sleeve plus 5% zero-volatility cash**, using **at least 61 common observed daily ETF close points**, >=60 daily aligned returns, and sample standard deviation times sqrt(252). All three series must share exact dates, chronological order and finite positive market-adjusted closes, a common source timestamp not in the future or stale, no missing/repeated values, and an explicit synthetic-only declaration. A **30% ex-ante planning threshold** gives 5 percentage points of headroom below the hard 35% actual realized cap. It is an engineering *planning estimate* and NOT a verified future account risk guarantee; price gaps/tails and regime changes can bypass any cap.

For an actual LIVE future execution release, risk must include continuously source-authenticated 6% daily return and <=20% peak drawdown relative to a funded/flow-reconciled opening account basis. The first few V6 strategy closes cannot yield a statistical realized 35% vol: the separate reviewed release must either apply the independently authenticated aligned ETF ex-ante volatility bound **as a conservative provisional proxy**, for a predefined limited warm-up, **alongside** actual daily loss/drawdown, or refuse new BUY until enough V6 closes. Once >=6 actual clean daily closes, require actual realized <=35% and keep ex-ante guard (don't forget it). No source proof -> NO release. Original legacy SELL exit phase independently requires real-broker positions/order ledger, migration loss/tax/cost suitability and valid operator release. This module NEVER uses historic unadjusted V5 NAV as V6 actual risk.

## Engineering scope and acceptance

- Immutable original source read-only: original V6 manifest, original HIGH V5 risks and original operator STOP all unchanged.
- Separate **pure, credentialless offline** strict policy loader and estimate with invented price fixtures, exact 61-aligned-price minimum, V6 risk controls, XLE preservation, stale/price-drop/sector stress tests and no trading permit. **Never** accepts `mode=LIVE`, `broker_authenticated=True`, any Alpaca credentials or HTTP transport.
- Negative tests demonstrate original manifest XLE contradiction is detected and corrected only in separately versioned **V6-policy view**. If original manifest changes, freeze and STOP rather than reinterpret.
- No new PAPER tests; original [genuine $2 PAPER roundtrip passed 39269640353](https://github.com/nicobouch97/fund100-research/actions/runs/39269640353) and was permanently retired.
- Private remote state repo GET token added by user, but no approved LIVE Actions use yet; this independent policy must not touch the token or connect storage.
- Full repository audit pass before merge; original operator `trading_enabled=false`, kill ENGAGED, **zero actual LIVE orders**.

This risk specification is NOT actual trading approval and does NOT switch on LIVE strategy or change the funded legacy portfolio.
