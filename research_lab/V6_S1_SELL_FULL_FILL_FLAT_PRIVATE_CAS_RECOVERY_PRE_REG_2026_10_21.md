# Fund-100 V6-S1 — private CAS staged SELL completion and recovery protocol

**Pre-registered 21 October 2026 before introducing the new checker or running its tests.**

## Why this blocks first LIVE launch today

Actual [original V5 BUY broker receipts and FILLs matched six GET, 21 October](https://github.com/nicobouch97/fund100-research/actions/runs/39573160640). All original ACWI, EEM, XLE, XLV holdings intact and original LIVE operator STOPPED/HIGH/kill ENGAGED. Existing [PR #78](https://github.com/nicobouch97/fund100-research/pull/78) sealed private GitHub SHA compare-and-swap planner permits only `RESERVED_NO_RETRY` and `POST_MAY_HAVE_BEEN_SENT` transitions, while NEXT original EEM/XLV reservation requires the preceding original sale in `SIM_FULL_FILL_AND_FLAT`. **There is no safely validated transition to completion yet.** The code here implements that missing *pure synthetic* transition.

## Proposed exact account source acceptance

A CAS document can move one original SELL from `POST_MAY_HAVE_BEEN_SENT` to `SIM_FULL_FILL_AND_FLAT` **only if all of the following synthetic fixtures reconcile**:
- Correct HMAC-sealed source document/immutable genesis/original account binding and exact stable legacy client ID and SHA-commitment to original fractional qty; original strict order ACWI, then EEM, then XLV; XLE is **never an exit**.
- Authenticated-looking (but in reality **invented**) single Alpaca receipt `status=filled`, `side=sell`, `type=market`, `time_in_force=day`, exact order id, original `client_order_id`, original exact `qty`/`filled_qty`, `filled_at` and `submitted_at` chronological UTC; do not infer absence of a previous POST from order lookup 404.
- Nonempty **fully paginated invented FILL** activity ledger, unique activity IDs and exact broker order-ID match, original symbol/side SELL, positive exact qty and price, monotonic cum_qty and nonnegative leaves_qty, intermediate `partial_fill` permitted but the final `fill` must reach exact original quantity with zero leaves, activity timestamps between submitted and completed order times. Sum all activity qty equals actual receipt qty exactly; overfill and unseen events STOP.
- Synthetic fresh original bound LIVE-looking position snapshot, zero open orders and a fully paginated open-order list, exit symbol actually flat, all **other** original holdings unchanged (including XLE original quantity), each prior legacy symbol already fully completed in signed CAS document. Unknown positions/funding activity => HOLD. No value or account identifier may leave private validation.
- Proposed **atomic GitHub Contents expected-blob-SHA** state update in the separate PRIVATE state repo, including monotonic document sequence, prior SHA, keyed HMAC. Two competing runners at the same SHA may not both win; a timed-out CAS response requires independent remote re-read of the new exact SHA, **never retry broker POST**.
- After confirmed prior CAS update, allow a new (NON-EXECUTABLE) reservation for the next legacy symbol, never an automatic brokerage submission.

Crucially, this module does not create/authenticate LIVE snapshots. It allows **only explicit** `INVENTED_ACCOUNT_ORDER_FILL_FIXTURES_ONLY` and `source_authenticated_live=False`; every returned result must say `actual_broker_sale_verified=False`, `cross_run_private_state_verified=False`, `live_order_authorized=False`, `broker_requests=0`. The transient in-memory CAS plan contains only HMAC share commitments, source status and original deterministic client IDs (already visible in strategy code), never raw account/share values. It must never commit a trading order or touch account credentials.

## User goal and next verified dependency

The Fund-100 HIGH $130.30 pilot targets exit ACWI/EEM/XLV and preserve XLE, then 47.5% XLK, 28.5% XLE, 19% IWM with 5% cash. This synthetically completes SELL-stage recovery, **not** Trading API post-SALE settled cash; actual Trading account lacks `cash_withdrawable`/`cash_transferable` [four GET result](https://github.com/nicobouch97/fund100-research/actions/runs/39489743795). Original [BUY order FILL source](https://github.com/nicobouch97/fund100-research/actions/runs/39573160640) can be generalized to future genuine migration SELL receipts, but not until approved V6 LIVE write release and private CAS durability are proven.

Private state repo [fund100-state-private](https://github.com/nicobouch97/fund100-state-private) exists PRIVATE, but the protected Actions read token and CAS writes are still **untested** owing to security controls on the credentialed workflow; do not represent synthetic CAS as authentic storage. No new token/account data in public repo. No change to source-pinned old V5 risk, original LIVE auth, kill, STOP, SELL writer or actual Alpaca account. No new PAPER trades. Full static LIVE safety audit required before merge.
