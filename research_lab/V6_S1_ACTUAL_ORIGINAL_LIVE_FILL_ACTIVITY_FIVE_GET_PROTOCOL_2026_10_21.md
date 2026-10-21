# V6-S1 — first authentic original LIVE FILL activity source, preregistered 21 Oct 2026

Existing genuine Alpaca Trading account evidence: [2026-10-20 exact 4 GET source](https://github.com/nicobouch97/fund100-research/actions/runs/39489743795) verifies original ACWI/EEM/XLE/XLV holdings, no open orders, and that direct `cash_withdrawable`/`cash_transferable` fields are **absent**. Existing [live seven GET nontrade source](https://github.com/nicobouch97/fund100-research/actions/runs/39303201301) sees date-only cash transfers; historic V5 raw equity returns are NOT V6 clean returns. Original operator STOPPED, HIGH and broker kill ENGAGED, $130.30 capital limit, 0 V6 migration orders.

## Source question

Will the actual **Trading API** GET `/v2/account/activities/FILL?after=2026-10-01&direction=asc&page_size=100` yield structurally valid original LIVE BUY fill events with `activity_type=FILL`, unique `id`, `order_id`, `symbol`, `side`, `qty`, `cum_qty`, `leaves_qty`, `price`, `transaction_time` and `type`? Docs: [Trading Account Activities](https://docs.alpaca.markets/us/docs/account-activities), [specific type endpoint](https://docs.alpaca.markets/us/reference/getaccountactivitiesbyactivitytype-1). This is a SOURCE-SHAPE qualification only; it does NOT reconstruct historical order receipts or certify T+1 settled spendable cash, and transaction_time is execution timestamp **not settlement time**.

## Precisely five authenticated GETs, no order POST

1. `GET /v2/account`
2. `GET /v2/positions`
3. `GET /v2/orders?status=open&limit=100`
4. `GET /v2/clock`
5. `GET /v2/account/activities/FILL?after=2026-10-01&direction=asc&page_size=100`.

First four must pass previously source-pinned original LIVE account full 4-position, original-fill quantities, zero OPEN orders, account identity and cash/equity reconciliation. Fifth read uses original unchanged pinned GET-only transport. The endpoint is explicitly selected by exact literal path and params; no pagination token from LIVE activity is printed or used to form an extra URL. Fully populated page of 100 is **PAGINATION_INCOMPLETE_HOLD**, not completed history. Empty page is `NO_HISTORIC_FILLS_SEEN_HOLD`. Unknown/original SELL activity/extra symbol, malformed JSON/row, duplicate ID, future/bad timestamp, nonpositive qty/price or invalid order ID causes fail-closed stop / conditional HOLD. Source-qualified BUY FILL activity rows for original ACWI/EEM/XLE/XLV yield `ORIGINAL_FILLS_STRUCTURE_SEEN_ORDER_LINKAGE_UNVERIFIED` but **not** original order receipt linkage: the original bootstrap does not include unique broker order IDs; matching each requires a new separately reviewed GET of past order receipts and complete pagination/cashflow activity history.

Do not print, persist or artifact any actual: account or activity ID, share qty, price, cash, equity, exact trade timestamps, broker order ID, raw activity JSON, source page token or auth key. Print only schema labels, bool flags, conservative event-source status, and five GET/zero non-GET counters. Source identity is matched with the immutable original account binding. Original operator and HIGH/ENGAGED state must be checked before and after GETs.

**Explicit non-goals:** no private state token, no remote CAS read/write, no live sell/buy permission, no changed operator state, no actual settlement certificate, no account return computation, no new PAPER trade. A subsequent fully paginated authenticated source scan can independently match original orders to FILL receipts, then develop a cash/settlement-specific Trading API rule with a full verified nontrade activity window. For this first source, any 100-row result is held; do not claim exhaustiveness.

Workflow: synthetic PR tests with NO credentials; protected main-only `fund100-live-broker` original LIVE secrets scoped solely to the exact new reader blob SHA, unchanged 4-GET checker, original transport/STOP/first strategy source deps SHA pinned by static audit. Pre-merge full static audit and negative pin mutation tests mandatory; authenticated main run only after merge.
