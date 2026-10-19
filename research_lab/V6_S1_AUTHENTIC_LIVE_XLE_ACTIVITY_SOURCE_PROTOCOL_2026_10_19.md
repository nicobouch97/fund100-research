# V6-S1 — original protected LIVE cash-flow activity and existing XLE weight study

**Precommitted 2026-10-19 18:00 UTC (design stage), BEFORE accessing any actual new account activities or XLE private percentages.**

The source facts previously verified remain frozen:

- Authentic $2 Alpaca PAPER fractional BUY and acquired-qty SELL both filled: [39269640353](https://github.com/nicobouch97/fund100-research/actions/runs/39269640353).
- Original four LIVE holdings ACWI, EEM, XLE, XLV and zero open orders: [39272813574](https://github.com/nicobouch97/fund100-research/actions/runs/39272813574).
- Authenticated original LIVE 1D raw equity history passed prior HIGH raw-history validator: [39297690493](https://github.com/nicobouch97/fund100-research/actions/runs/39297690493). This raw history is **NOT cash-flow-adjusted strategy returns** and does not clear a 6% daily-loss/20% drawdown/35% realized vol LIVE risk policy.

## New private, read-only, falsifiable questions

**Q1. Is the currently held XLE position below S1's intended 28.5% target, measured against the lesser of original USD 130.30 authorized pilot capital and LIVE observed current account equity?** This determines whether the existing XLE can be *considered* for reuse through the draft V6 transition. An overweight XLE does NOT automatically cause a SELL. An in-target XLE does NOT authorize a BUY/SELL.

**Q2. Which cash-flow activity classes exist on the actual account over the source horizon?** Because the existing raw account equity return study does not adjust for account deposits/withdrawals or incoming/outgoing security transfers, fetch the source broker's **non-trade account activities** after 2026-09-01, with `category=non_trade_activity`, ascending, maximum 100 activities. Distinguish direct transfer types `CSD`, `CSW`, `ACATC`, `ACATS`, `JNL`, `JNLC`, `JNLS` and broker `TRANS` from dividend/fee/interest/other events. Unknown types are **UNKNOWN**, not ignored.

The API is documented by original provider Alpaca:
- [Get account activities](https://docs.alpaca.markets/us/reference/getaccountactivities-2), including `category=non_trade_activity`, `after`, `direction`, `page_size`, pagination.
- [Daily portfolio history](https://docs.alpaca.markets/us/reference/getaccountportfoliohistory-1), including `cashflow_types` flag. The existing default 1D history does not justify pretending recorded deposits are investment gains.

A 100-row activity response is deliberately **inconclusive**, since pagination may hide additional events. Any invalid response, blank/missing type, conflicting types, stale account check, unapproved holdings/identity or live operator enabled must fail. Public GitHub logs expose only categorical strings and booleans — **no account IDs, cash/equity, XLE market values, timestamps of user transactions, financial-event amounts or client-order IDs**.

## Exact authenticated data run

Protected existing `fund100-live-broker` environment, `main` only, operator STOPPED, broker kill `ENGAGED`, HIGH risk; original source-aware 2026 account binding; read-only arm. Exactly SIX GET requests in this order:

1. `GET /v2/account`;
2. `GET /v2/positions`;
3. `GET /v2/orders?status=open&limit=100`;
4. `GET /v2/clock`;
5. `GET /v2/account/portfolio/history?period=1M&timeframe=1D`;
6. `GET /v2/account/activities?category=non_trade_activity&after=2026-09-01&direction=asc&page_size=100`.

The first five are read with the original reviewed code only; the new sixth endpoint is a **source-qualifying one-time inspection**, not an assertion that all historical cashflows are identified or a method to create adjusted fund returns. **The response and account valuations must never be written to disk, artifacts or printed**. A new command is credential-eligible only through a newly scoped, exact-Git-blob-pinned security gate, not by widening the global interpreter allowlist. Any dependency, source hash, environment, STOP, HIGH, new workflow or branch change denies broker credentials.

## Decision and failure semantics

- `XLE_BELOW_OR_AT_DRAFT_TARGET` or `XLE_ABOVE_DRAFT_TARGET_REVIEW` are **observations only**.
- `NO_EXTERNAL_TRANSFER_TYPES_SEEN_IN_OBSERVED_WINDOW`, `EXTERNAL_TRANSFER_TYPES_SEEN_REQUIRES_CASHFLOW_ADJUSTMENT`, `UNKNOWN_NONTRADE_TYPE_REVIEW` and `ACTIVITIES_PAGINATION_INCOMPLETE` are **observed source categories**, not investment returns.
- Available original CASH and broker buying power do **not** prove T+1 settled sale proceeds or spendable buying power. Any absent account cashflow evidence makes later production risk **not proven**, never “pass”.
- **No orders** or release of S1, no change to existing four original ETFs, no deposit, no live writer, no extra financial or asset permission; original cap USD 130.30/HIGH and remote operator + broker STOP unchanged.

The objective is to make the next LIVE migration choice (retain XLE or manual review, and how to normalize account risk) from authenticated *private* account data, instead of synthetic assumptions or repeatedly waiting for PAPER returns.
