# Fund-100: Alpaca V2 funding-source shape and pagination boundaries

9 November 2026. Pure offline source adapter. This is NOT authenticated
broker funding, NOT settled cash, NOT a funded account mandate, and NOT an
order release.

Alpaca V2 documentation describes /v2/account/activities with
category=non_trade_activity, direction=asc, page_size<=100, and page_token
equal to the final activity ID of the previous page. A full page is not
evidence of completeness. Nontrade activity date is an activity/settlement
date and must not be treated as timestamped credited buying power.

Sources (public):
- https://docs.alpaca.markets/us/docs/account-activities
- https://docs.alpaca.markets/us/reference/getaccountactivities-2

## Implemented

The fixture-only fund100_scalable_alpaca_activity_adapter_offline_v1_0.py
replays a fixed historical nontrade request plan through a local injected
callable. A first page of 100 must be followed by another exact
page_token query. At most 20 pages are accepted; unexpected types, missing
or duplicate IDs, time-order disagreements, signs, non-USD cash transfers,
missing cashflow currency, unrecognized event codes, withdrawals exceeding
observed deposits, stale dates and missing source coverage stop in-memory
inspection. It publishes ONLY predetermined category labels and observation
counts: never raw broker account IDs, amounts, or activity IDs.

The documented Alpaca response shape has optional currency and nontrade
activity date without an independently authenticated cash-settlement clock.
Therefore a source-shape pass explicitly returns
REVIEW_ONLY_DATE_NOT_SETTLEMENT. This does not mean spendable cash.

## Important limitations

This new code deliberately does NOT import Alpaca clients, touch any network,
read production secrets, use GitHub CAS, write a private funding ledger, raise
the authorised $130.30 capital ceiling, loosen the $65 new-order size, or
enable any broker order. Real account inception must be independently proved,
not assumed from the chosen 2026-09-01 page query. Live Alpaca activity rows
with absent currency or new event types are ambiguous and must HOLD.

To transition safely:
1. Qualify an authenticated LIVE GET-only, scoped same-account inception
   source, full pagination, page token continuity and public categorical
   reporting; no secret-bearing artifact publication.
2. Independently verify settlement/buying power and true USD funding; the
   activity date alone never certifies funds availability.
3. Persist exact provenance in a private signed HMAC/CAS ledger with external
   immutable anti-rollback, separate production principal and revocation.
4. Match current signed owner capital mandate and STOP, then source-qualified
   risk, brokerage holdings/FILL/order state and first ACWI release.
5. Introduce new standing-capital capacity only after explicit owner
   approval of that mandate. Future qualifying deposits inside the approved
   cap need no per-deposit approval; no per-trade approvals either.

Current first ACWI SELL remains HOLD; broker kill ENGAGED and V5/V6 STOP.
