# V6-S1 — real Alpaca PAPER fractional order round trip: VERIFIED

**19 October 2026; genuine PAPER-only execution on the US market open session, NOT simulated offline tests and NOT real-money stock orders.**

## Original broker execution proof

- Exact GitHub Actions run: [39269640353](https://github.com/nicobouch97/fund100-research/actions/runs/39269640353).
- Workflow: `.github/workflows/fund100-v6-s1-paper-fill-once.yml`, ID `389220712`. Event was **workflow_dispatch** on original **main**, run attempt **1**. Run HEAD `9bd34bb28096e5d5aadc5ef066c8211676cd6a24`. Started 2026-10-19T14:30:56Z and completed successfully ~14:31:14Z.
- Job ID **118118246713**, name `s1-rehearsal`, conclusion **SUCCESS**. The critical actual market-orders step **`Execute ONE genuine $2 PAPER BUY then exact-qty SELL in open US session`** concluded **SUCCESS**, and the post-order no-LIVE activation / original STOP step also succeeded.
- Original market-hours job logs `2026-10-19T14:31:11Z` explicitly print: **`S1 PAPER buy+sell exact fractional fill: PASS; baseline holdings restored.`** and **`PAPER ONLY. ZERO LIVE orders, ZERO live permissions changed.`**
- The runner's actual Python assertions require original output `status=PASS`, `mode=REAL_ALPACA_PAPER_ONLY`, `paper_buy_filled=true`, `paper_sell_filled=true`, **exactly 2** PAPER order submissions, `all_starting_paper_positions_preserved=true`, `live_orders_submitted=0`, original strategy not LIVE-authorized and no LIVE credentials. A successful run means ALL passed, rather than merely code compiling.
- Original rehearsal isolated to one previously unowned PAPER S1 ETF among **XLK, XLE, IWM**, using only a **$2** paper-money notional initial BUY and the exact acquired fractional share quantity for the matching PAPER SELL. Two unique, run-derived client order IDs were used. Any pre-existing PAPER account positions were independently reconciled before and after. Original public log intentionally does NOT reveal customer's paper cash, private order IDs, quantities, broker account identifier or incidental fill prices.
- Automated synthetic arm/risk tests: **19 and 35 passed** as part of the same run before any PAPER broker POST. These are not substitutes for the authentic broker step, which also passed.
- Run source authenticated through GitHub Actions API GET and original job logs on 19 October 2026. Evidence sources are named and fixed, not dynamically overwritten or forged from synthetic fixtures.

## Correct promotion meaning

**`S1_REAL_PAPER_MECHANICAL_ROUND_TRIP=PASS`** is a new milestone. S1 genuine PAPER fractional DAY/market BUY, quantity SELL, return-to-baseline and duplicate-client-ID protections worked *once*. It does not prove future fills, venue spreads, cash-account settlement, LIVE jurisdiction/order approval, achieved strategy alpha, low realized slippage or risk stops beyond the $2 probe.

- Do not retry the one-time October test: both sides filled and holdings were restored. A second broker POST risks duplication, and a date/attempt guard exists in the source.
- The previously rejected V6-L1 volatility overlay stays rejected. S1 exact historical 95%-target CAGR was **17.08743% at 15bp per side** on the heavily studied 2014–Sept2026 sample; NOT an expected return.
- S1 5% original daily cash minimum failed in 2,792 original-model sessions. Proposed alternative: **5% minimum immediately AFTER every new BUY with cash-ratio drift HOLD/PAUSE, no forced daily tiny selling**. This is documented in `research_lab/V6_S1_ORDER_TIME_CASH_FLOOR_WITHOUT_FORCED_CHURN_2026_10_19.md` but has NOT yet become separately approved LIVE release risk policy.
- Legacy LIVE holdings ACWI/EEM/XLE/XLV still require direct LIVE broker reauthentication, cash/settlement and risk evidence; the original live operator is STOPPED and LIVE broker kill switch last verified ENGAGED. Do not assert that only the PAPER run enables sale of original four holdings.

## Immediate next original account milestone

Refresh ALPACA LIVE **GET-only** four original endpoints on main via the **unchanged**, previously source-pinned `fund100_v6_real_live_getonly_transition_readiness_v1_0.py` and its isolated `fund100-live-broker` GitHub Actions environment. Keep exact credentials private, and never print/store balances, account identifiers or share quantities.

This evidence file is the V6-S1 milestone key triggering a fresh original LIVE GET-only inspection on merge through a **push-path-only** change to `.github/workflows/fund100-v6-real-live-getonly-transition.yml`; no changes to the GET-only Python script, kill switch, LIVE order paths, execution permissions, capital cap or strategy universe. Any test failure or environment approval block must be reported rather than guessing account availability.

**Financial controls:** original authorisation <= USD $130.30 of trial capital, risk HIGH, no leverage/margin/options/futures/crypto/live individual shares, original operator STOPPED. This milestone made no real-money orders.
