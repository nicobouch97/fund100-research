# V6 — genuinely current Alpaca LIVE account transition observation

**18 October 2026. No new strategy, order, liquidation or control change.**

## Purpose and first factual distinction

As of this date Fund-100 has source-verified historical **5 October
2026** LIVE buys of ACWI, EEM, XLE and XLV. Those fills alone
do **not** tell us the positions, prices, brokerage settled cash,
open orders or market value NOW. Original Fund-100 authorisation
remains **USD130.30 total original capital**, selected risk HIGH,
operator STOPPED and kill switch ENGAGED at last audited check.
The user's **18 October delegation of conditional sale discretion**
is recognised, but the independent decision is currently HOLD
because no tested V6 replacement qualified.

A new source
`fund100_v6_real_live_getonly_transition_readiness_v1_0.py`
and CI
`.github/workflows/fund100-v6-real-live-getonly-transition.yml`
perform *exactly four* LIVE GET requests using the existing
`fund100_alpaca_live_readonly_smoke.py` authenticated read-only
client, not the order-capable bootstrap/orchestrator:

- `GET /v2/account`
- `GET /v2/positions`
- `GET /v2/orders?status=open&limit=100`
- `GET /v2/clock`

Workflow runs tests on PR without access to LIVE secrets and
automatically attempts one account check on first **main push**,
using only the existing `fund100-live-broker` environment.
No new API key, broker environment, secret or administrative
permission. The live step requires GitHub main checkout, correct
repository identity, HIGH selected profile, **ENGAGED** kill switch,
and a new live read of the operator STOP from current main.
It refuses extra/missing positions, changed fractional quantities,
unreconciled open orders, wrong account binding, incoherent
broker position quantity/price/market value or cash/equity,
and an account not ACTIVE.

## Privacy: no current account values in GitHub

The current account ID, quantity, last mark, cost basis,
market values, account equity, brokerage buying power and
cash stay in memory of the short-lived runner and are
**never printed, saved as artifacts, committed to repo,
or appended to a GitHub job summary**. Public logs contain
only boolean checks (and market open/closed state).
The algorithm evaluates whether a future price-sensitive
transition could be planned, not the price of any order.

This GET check **does not authenticate execution quotes**,
confirm sale settlement, determine tax lots, authorise any
sell or new buy, calculate investable proceeds, certify
broker buying power, or imply four historical holdings
are still present if the scan fails. No mark-to-market
cash/equity from the previous Oct14 check is reused.
A market-closed Sunday original broker mark may be the
prior US trading session. It must NOT be described as
an executable Sunday quotation.

## What a successful check does and does not mean

Successful output:
`historic_four_original_etf_quantities_reconciled: True`,
`open_order_count: 0`, `current_strategy_decision:
HOLD_EXISTING_FOUR_ETFS_NO_SELL`, and four GET with
zero order requests. It is an evidence improvement
towards eventually exiting the original V5 ETF holdings
after a chosen V6 strategy passes an economic test.
A new account check must run again immediately
before any actual future trade; Sunday's positions
cannot authorize Monday's trade.

A failure is useful and must not be bypassed:
the remediation is to examine the broker account
privately, adjust the underlying reconciliation
logic after evidence, and rerun *read-only* validation,
not infer available cash from $130.30 or send orders.

The current V5 LIVE execution policy and stop latch
remain unchanged. New strategy risk, allowed universe,
total capital and trade execution release remain
separate from the operator's permission to *decide*
whether selling would be better.
