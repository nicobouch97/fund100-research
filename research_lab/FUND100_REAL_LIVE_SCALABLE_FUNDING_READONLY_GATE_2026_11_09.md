# Fund-100 real Alpaca funding-source provenance: protected GET-only gate

9 November 2026. Protected source qualification; NOT capital mandate change.

## Implemented

The separate main-only source fund100_scalable_live_funding_history_getonly_v1_0.py
requires broker kill ENGAGED, original operator STOP, account/policy binding,
risk HIGH and LIVE write mode DISABLED. A protected Actions job can
perform at most SEVEN actual Alpaca GETs: original account snapshot,
up to five 100-row non_trade_activity pages and final account snapshot.
It uses exact page_token = previous page last activity ID, retains all
raw account data in memory, and prints only categorical HOLD/review labels
and nonidentifying record counts.

Source exact Git blob SHA is pinned in the full LIVE safety audit.
Credentialed job is main-only, never PR/head; it requires pre-credential
no-network tests, exact source audit, GitHub Environment protection,
read-only arm and account owner STOP. No private ledger mutation principal
or broker write method is used.

## Reading the status

- OBSERVED_GROSS_FUNDING_ABOVE_ORIGINAL_PILOT_HOLD means visible deposits
  exceed original USD130.30, NOT that new money has become authorised,
  settled, attributed or spendable.
- HOLD_CURRENCY_UNSPECIFIED_ON_CASHFLOW means at least one relevant row
  lacked independently usable USD currency metadata.
- OBSERVED_FUNDING_WITHIN_ORIGINAL_CAP_REVIEW_ONLY is a shape-only
  review, not a settlement or approved capital release.
- Missing pages, duplicate IDs, unsupported transfers, wrong signs,
  wrong account or changed cash across snapshots all HOLD.
- The revised query obtains account created_at directly from the same
  authenticated original Alpaca account. Its after date is the calendar
  day BEFORE creation, rather than a fixed 2026-08-01 start. That is a
  conservative account-inception-relative lower bound for activity
  creation time, as described in the API docs. A complete bounded
  nontrade page chain can set account_creation_query_window_covered=true.
  It does NOT independently certify provider history completeness across
  other categories, cash settlement, transfers, or the private ledger.
  The older fixed_after_filter_inception_coverage_proved flag stays false
  because a fixed after-date is no longer the source of coverage.
- A nontrade activity date is NOT proof of order-time settled cash.
  Even a green run is NOT a real trade permission.

Alpaca V2 documentation:
https://docs.alpaca.markets/us/reference/getaccountactivities-2

page_token uses last activity ID, and after filters activity
creation time; the activity date may refer to a different booking
or settlement day. The Alpaca account.created_at field comes from
the existing original account GET, not an additional endpoint.

## Remaining critical path

1. Authenticate full account inception and all foreign-currency/stock
   transfers and cashflows (the current date bound is only a hypothesis).
2. Verify actual settled USD cash and FX conversions, independent of
   date-only cashflow records and hypothetical account buying power.
3. Persist exact source in a private HMAC/CAS signed funding ledger with
   provider-immutable anti-rollback history.
4. Obtain one-time explicit bounded standing capital approval before
   changing $130.30. Within it, later qualified deposits require no
   per-deposit or per-order owner confirmations.
5. Join true broker risk, fills, holdings, STOP, at-most-once signed
   event CAS and recovery before any live SELL or BUY.

Existing $130.30 pilot and $65 order limit, ENGAGED broker kill and
V5/V6 STOP stay unchanged. ZERO orders or live state writes by this module.

## 9 November 2026: cash code attribution correction

Alpaca's current Account Activities API documents that **CSD also includes
returned withdrawals** and **CSW also includes returned deposits**. Therefore
a brokerage-observed CSD credit is **NOT independently proven owner-
contributed capital**, and a CSW debit is not necessarily an owner
withdrawal. Earlier statuses claiming *gross deposits/funding above $130.30*
were overinterpreted: the verified narrower fact is that the observed
**gross CSD cash credits exceed $130.30**, subject to the historical
read-only source coverage and currency checks. No settled cash or owner
capital mandate was ever approved by that status.

The corrected protected diagnostic now returns
CSD_CREDITS_ABOVE_PILOT_OWNER_ATTRIBUTION_HOLD or
CSD_CREDITS_WITHIN_PILOT_OWNER_ATTRIBUTION_HOLD, and always sets
owner_contributed_principal_authenticated=false. It requires independent
bank/transfer provenance (and return linkage, corporate actions, FX and
settlement) before any owner contribution can enter a production
principal ledger. The pilot $130.30 ceiling, $65 ticket and STOP remain.

Authoritative Alpaca account activity types:
https://docs.alpaca.markets/us/reference/getaccountactivities
