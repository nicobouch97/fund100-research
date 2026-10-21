# V6-S1 ACWI fractional SELL HTTP adapter — locked transport design, 21 October 2026

**Review-only PURE protocol. No live broker credentials in any new workflow. No executable new HTTP POST, no funded Alpaca order, no real private ledger head change.** The real production ledger remains HMAC-signed empty genesis sequence 0. Existing separately-reviewed source-pinned manual ACWI intent-only workflow has not been dispatched; do not strand a reservation before execution release.

## Actual reviewed execution boundary — no additional standalone POST

The original LIVE static safety audit correctly **rejected** an earlier draft of this PR which introduced a new `Request(method="POST")` outside the existing reviewed broker-writer modules. That draft is **not merged**. We have **removed the entire new HTTP Request/urlopen path**, not suppressed the audit or hidden its detection. The approved original hard-locked writer boundary remains the only place where executable LIVE Alpaca POST code may exist. Integrating V6 fractional quantity SELL into that allowlist is a **future separately reviewed versioned change**, not an environment unlock.

This PR instead source-pins a complete and useful **pure protocol**:
- HMAC-validate original signed private seq1 ACWI `RESERVED_NO_RETRY` and successor seq2 `POST_MAY_HAVE_BEEN_SENT`, exact stable deterministic client ID and original fractional share quantity MAC, successor parent Git SHA, genesis witness and both original issue-8 bot SHA256 head comments.
- Construct the precise **data-only** fractional qty ACWI market DAY SELL JSON shape: exactly `symbol,qty,side,type,time_in_force,extended_hours,client_order_id`; forbid XLE, BUY, shorts, notional, leverage and unsupported decimal quantities.
- Validate a supplied **FAKE** Alpaca response in-memory: unique broker UUID and stable client ID, qty, side, market/DAY shape, no notional, valid state classification, no resubmission after terminal/ambiguous responses, and no claim that an apparent filled receipt proves position flat or settled cash.
- An explicitly named live submission entrypoint is **permanently disconnected**: checks three hard-coded FALSE release flags first, then unconditionally raises a rejection even if malicious tests temporarily patch those flags. No `main()`, no broker/HTTP imports, no new GitHub secrets or schedule.
- Neither the JSON payload builder nor the fake receipt review creates an HTTP request; they do not source a real broker snapshot or actual signed production state. The original production ledger stays seq0 and LIVE execution stays STOPPED.

## Further release dependencies

Only after authentic fresh broker account/positions/client-ID/history checks, a durable signed pre-POST private CAS with independent readback and separately trusted current-head watermark, order-time <= $65/6-20-35 risk, current operator/kill-switch state and a versioned independent LIVE release could the **already-reviewed** broker writer be extended for this fractional-SELL shape. A future first real SELL is one bounded order at a time with immediate receipt/flat/FILL reconciliation, no automatic retries after ambiguous outcomes and no buys until independent settlement.


## Threat and regression checks
Offline unit fixtures test accurate fractional SELL request and headers to Alpaca LIVE hostname, missing/invalid HMAC, old/new signed state broken, extra EEM/XLE entries, wrong original quantity/id, private SHA mismatch, public bot edited/forged, wrong previous comment/run link, wrong account binding, 404 not proof of never posted, duplicate invocation, broker timeout, HTTP non-2xx, filled/active/terminal/ambiguous/malformed receipts, explicit hard lock first. Network adapter cannot run by GitHub PR / push / workflow dispatch. Full original LIVE static audit must pass before merge. This is an executable *code candidate* for review, **not** an authenticated production writer or a SELL release.
