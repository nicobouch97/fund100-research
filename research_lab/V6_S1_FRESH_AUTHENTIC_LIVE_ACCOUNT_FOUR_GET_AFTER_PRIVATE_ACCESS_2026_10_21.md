# Fund-100 V6-S1 — one fresh authentic LIVE four-GET recheck after private state access

**21 October 2026, pre-registered before triggering the main-branch LIVE read-only workflow.** This is a dated account observation, never a trade release.

## Original evidence sequence

1. Actual protected private READ under Actions identity: [run 39600082142](https://github.com/nicobouch97/fund100-research/actions/runs/39600082142), two exact GETs, no state mutations.
2. Separate protected private SANDBOX write/independent GET/stale 409: [run 39618444064](https://github.com/nicobouch97/fund100-research/actions/runs/39618444064), one synthetic file only; no production account/order data.
3. Actual protected production state three-GET inspection: [run 39620212136](https://github.com/nicobouch97/fund100-research/actions/runs/39620212136), `MISSING_OR_UNAVAILABLE_PRODUCTION_LEDGER_STOP`; no production HMAC/genesis anchor and zero writes.
4. **Now** independently revalidate the authentic Alpaca LIVE account and original legacy ETF holdings before planning any production genesis, using the pre-existing unchanged `fund100_v6_real_live_getonly_transition_readiness_v1_0.py` source and `.github/workflows/fund100-v6-real-live-getonly-transition.yml`.

## Narrow acceptance

The workflow requires protected `fund100-live-broker`, main, original operator `trading_enabled=false`, `FUND100_BROKER_KILL_SWITCH=ENGAGED`, HIGH, original V5 policy account binding; exactly four Alpaca GETs (account, positions, open orders, clock) through the original read-only implementation. Real response must validate: account ACTIVE/not blocked; original exact `ACWI/EEM/XLE/XLV` position quantities as originally recorded; total value/cash consistency; no open orders. The source prints categorical booleans only and no account IDs, share quantities, actual cash/equity or order references. A failure DOES NOT authorize liquidating or buying to repair the situation.

New evidence is a **fresh observation at that moment**, NOT a current broker fill history, settled sale proceeds, HMAC key, private production ledger or durable external anchor. A successful run leaves `HOLD_EXISTING_FOUR_ETFS_NO_SELL`, no new broker orders; the user HIGH $130.30 ceiling and unmodified V6-S1 47.5% XLK / 28.5% XLE / 19% IWM / 5% cash proposal remain unchanged. The corrected S1 transition policy would retain the original XLE instead of selling/rebuying it. No automated migration.

## Engineering scope

Change only the original read-only workflow `push.paths` trigger to include this specific non-executable evidence protocol, so a reviewed merge performs one protected LIVE four-GET main run without asking the operator for yet another manual run. DO NOT alter its protected job content, credential scope, method or source script, or install any brokerage write path. Existing full LIVE static audit must pass before merge. If the source's real GET fails, report honestly and stop.

This new observation will be paired manually with the already successful private-production-ledger NOT PROVEN report. Even if the account recheck passes, the next critical step is a separately protected HMAC-and-genesis-anchored production state initialisation procedure (with real account binding), *not* a LIVE SELL. No new trading permissions.


---

## 22 October 2026 — controlled current-account recheck after verified signed genesis

This is a **new dated append-only observation request**, NOT a change to the original 21 October preregistration or an invitation to create the already-existing production genesis twice.

The previous signed private production genesis was **actually created** in [protected run 39637082911](https://github.com/nicobouch97/fund100-research/actions/runs/39637082911) and its exact HMAC + public comment were independently recovered in [protected run 39638576563](https://github.com/nicobouch97/fund100-research/actions/runs/39638576563); both protected jobs passed. An independently repeated GitHub private Contents GET on 22 October found the *same* original Git blob and the structured original sequence=0/zero entries; this remote read alone does not reverify the HMAC. The old paragraph that describes the production ledger as missing is a historical observation, **no longer the current project state**.

Purpose of this reviewed docs-only trigger: request **one more authentic original Alpaca LIVE four-GET account/positions/open-orders/clock snapshot**, now that the ledger exists and V6-S1 original fractional SELL shape/reconciliation is implemented but still hard locked. The pre-existing workflow explicitly allowlists this document path for main-branch push, so no workflow or sensitive code/credential changes are needed. On the PR only its credentialless tests run; after merge the existing main-only protected READ-only broker job is eligible. No operator-triggered funded order.

Expected result on success: the source attests its *own live broker state at that time only*. It is NOT permission to reserve original ACWI seq1, unlock any of the six reviewed writer locks, sell an ETF, or spend proceeds. Subsequent release still needs independently reviewed live account risk and durable signed HEAD/external watermark integration plus explicit funded-order authorisation. Keep original four ETF positions unchanged, $130.30 cap, HIGH risk, operator trading_enabled=false and ENGAGED broker kill switch.
