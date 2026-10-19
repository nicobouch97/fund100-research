# V6-S1 — one-time PAPER $2 fractional order-mechanics test

**Scheduled for Monday 19 October 2026, earliest intended 13:43 UTC / 9:43 AM EDT, and no other date.**

The operator wants a small LIVE investment experiment without waiting for
months of profitable forward paper trading. This strictly limited PAPER test
checks order compatibility and lifecycle, **not future return or predictive
alpha**.

## First source proof already complete

Original authenticated Alpaca PAPER GET-only [run 39227661735](https://github.com/nicobouch97/fund100-research/actions/runs/39227661735)
confirmed **XLK, XLE, IWM are each active, tradable and fractionable**
in the PAPER broker; zero real or PAPER orders at that stage.
The linked V6-S1 manifest proposes a separately versioned HIGH
concentrated risk contract with 95% gross investment / 5% cash reserve
and the original $130.30 maximum pilot budget, NOT permission to switch LIVE.

## This one-time experiment

- Test implementation:
  `fund100_v6_s1_one_time_paper_fill_probe_v1_0.py`.
- [Alpaca PAPER base URL](https://docs.alpaca.markets/us/docs/paper-trading)
  is hard-fixed to `https://paper-api.alpaca.markets`; only
  `ALPACA_PAPER_KEY` and `ALPACA_PAPER_SECRET` are injected.
  Original LIVE credentials are not present, are expressly forbidden,
  and LIVE original STOP and broker kill switch remain ENGAGED.
- A single GitHub Actions schedule for **19 Oct 2026 13:43 UTC** runs
  synthetic negative unit tests first, and attempts actual order
  creation only if the account is active, market is in a strictly
  limited 9:35 AM–2:00 PM ET regular window, date is exactly
  19 Oct, initial account open orders are zero, and repository
  remote LIVE operator STOP remains active.
- Select FIRST S1 ETF with **no current PAPER shares** from
  XLK, XLE, IWM. Existing PAPER positions in any symbols,
  even non-S1, remain untouched. If all S1 ETFs are held,
  the test aborts without an order.
- Confirm the selected asset itself is ACTIVE, TRADABLE
  and FRACTIONABLE, and PAPER cash is at least $4.
- Create a unique SHA-derived `client_order_id` for
  `buy` and `sell` based on GitHub run ID. No duplicate
  client ID is allowed. GitHub rerun attempt 2+ always
  refuses to submit orders.
- Submit exactly **ONE $2 notional BUY** with market+DAY,
  no extended-hours. Wait for filled receipt and compare
  actual position delta to exact `filled_qty`.
- Only then submit a **SELL of exactly the acquired
  fractional quantity**, market+DAY, to restore original
  holdings, verifying the entire original PAPER holdings
  set and no residual open orders.
- A timeout is not counted as no fill; attempt cancellation
  only by own order ID, and flag any un-restored paper
  shares as an explicit manual clean-up condition.
- Expected two total PAPER POSTs, zero LIVE POSTs.
  No real-money liquidation or new LIVE allocations.
- If workflow is delayed past safe market hours, it
  must FAIL rather than quietly retry in later sessions.
  No unattended perpetual workflow; no claimed fill
  until the broker actually returns a terminal filled
  order.

Unlike the failed R1/R2/commodity strategy variations,
this work has **no extra parameter tuning or historical
return assumptions**. Success verifies that our broker
can execute a fractional, cash-sized, day-only ETF
PAPER buy/sell loop; it does NOT prove that S1's
50/30/20 fixed sector investment earns risk-adjusted
alpha, nor that the real LIVE account's buying power,
fractional eligibility and cash settlement are verified.

The next valid release engineering after a successful
PAPER fill is a separate versioned LIVE S1 risk and
execution policy that explicitly handles original
ACWI/EEM/XLE/XLV investment sale, T+1 settlement,
stale quotes, current account positions and own-order
idempotency. User delegated investment discretion,
but GitHub LIVE environment release/stop still applies.
