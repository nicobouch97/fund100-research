# V6-S1 — first authenticated LIVE client-ID order-ledger reconciliation (preregistered)

**19 October 2026, pre-registered before first attempt to query the three original LIVE order IDs.**

Existing real evidence: four original LIVE holdings ACWI/EEM/XLE/XLV, zero open orders and broker stop engaged; XLE under proposed 28.5% V6 S1 target. Authenticated raw risk history available; real historical funding activity had date-only cash transfers, so new V6 performance ledger starts at independent completed migration baseline. [Original broker evidence 39299643300](https://github.com/nicobouch97/fund100-research/actions/runs/39299643300); [last genuine 7-GET inspection 39303201301](https://github.com/nicobouch97/fund100-research/actions/runs/39303201301). [PR #75](https://github.com/nicobouch97/fund100-research/pull/75) built an owner-private locally persistent synthetic SQLite pre-POST journal that is **not backed by cross-run external storage**. No LIVE sell order has been authorised or placed.

## Falsifiable source questions

Does Alpaca's **actual LIVE account** already have a broker order record matching ANY of the original deterministic V6 legacy SELL client_order_ids for ACWI, EEM, XLV? This matters before safely deciding to reserve a new attempt, even though a broker 404 cannot prove that a future earlier POST was never made.

The review uses the exact existing V6 `_id(symbol)` and the genuine Alpaca API [GET order by client ID](https://docs.alpaca.markets/us/reference/getorderbyclientorderid-1). The only allowed broker transport is the source-reviewed `fund100_alpaca_live_readonly_smoke.get_json` with GET. Precisely 7 GETs on the real LIVE account, strictly sequential:
1. `GET /v2/account`
2. `GET /v2/positions`
3. `GET /v2/orders?status=open&limit=100`
4. `GET /v2/clock`
5. `GET /v2/orders:by_client_order_id?client_order_id=<deterministic ACWI ID>`
6. Same query for EEM
7. Same query for XLV.

The first four are passed in memory through the already independently source-pinned original LIVE four-held-ETF/broker-binding/zero-open-order verifier, with original HIGH tier, remotely STOPPED and ENGAGED kill. All three IDs are derived in-memory from exact immutable migration key; NO quantities/account IDs/order payloads are printed or saved.

- A valid HTTP **404** on a recognized GET lookup is categorized `NOT_OBSERVED_404` and remains **NOT a never-POSTed guarantee** and **NOT permission to trade**.
- A returned order MUST have the exact expected ID, account-original existing shares, `symbol`, SELL, market, DAY, original order quantity and a structurally valid broker receipt. Any mismatch, missing field, partial, already full-filled while original position is still held, canceled, terminal, unknown status causes `BROKER_ORDER_PRESENT_OR_INCONSISTENT_STOP` or a hard fail; no retries or order submissions.
- Broker errors other than a provider's documented 404, 401, 403, 429, timeouts, invalid JSON, missing/extra symbols, wrong original quantity, change of remote operator STOP or original account binding -> **fail closed**. No status success is produced.
- If all three IDs are absent from the source (expected prelaunch), report only `NO_MATCHING_V6_CLIENT_IDS_OBSERVED_NOT_NEVER_POST_PROOF`. Never treat this as a broker-issued guarantee that no legacy order was ever submitted.
- No direct network use in PR tests. Source module must be exact blob-SHA pinned inside existing static LIVE audit, with GET transport, source original account verifier, original V6 fractional SELL order-ID derivation, original strategy policy and STOP control all pinned. Protected environment `fund100-live-broker`, GitHub `main`, HIGH, kill ENGAGED, operator STOP false, no schedule, pull requests cannot obtain LIVE credentials.

The job only validates **broker-side original order history**, not local SQLite durability across GitHub Actions, post-fill settlement, future order POST idempotency, original cap risk 6% daily/20% peak/35% vol approval, new BUY cash eligibility or a trading release. Later execution work needs a private persistent external storage / off-host lineage record or another demonstrably crash-safe backend, and a source-reviewed operator-authorized submission boundary. Do not change the operator STOP, kill, keys or original LIVE positions.

A separate repeated PAPER $2 test attempt on 19 October around 19:28 UTC failed due to closed US market, with no orders attempted; the **original real PAPER roundtrip run 39269640353 already PASS**. No additional PAPER test is needed for this broker source question.
