# First-ACWI protected 8-GET research-only classification and risk parity

**11 November 2026 — reviewed original-only safety diagnostic; no trading release**

After #625 the real original active first-ACWI SELL risk evaluator stopped
rejecting a positive broker CSD solely for exceeding the original pilot
$130.30 cap, because a liquidation of original owned inventory does not
deploy new funds. The protected 8-GET observer still mapped the removed
exception to a misleading pilot-capital-ceiling HOLD but did not recognise
the evaluator's current `Original cash-credit direction/count unqualified`
exception. A real in-session rejection would have been reported as unknown.

This change replaces the stale category with
`ACTIVE_FUNDING_SOURCE_SHAPE_HOLD` for the actual credit source-shape
failure. The observer does **not** treat a gross credit as authenticated
owner principal.

The observer's `ACTIVE_PURE_SOURCE_MATCH_RESEARCH_ONLY` classification
now verifies the **complete** reviewed first-sale risk invariants, including
`unattributed_credit_or_new_principal_spend_authorized=False`,
`original_acwi_sell_only_no_additional_principal_deployment=True`,
original $130.30 capital ceiling, $65 new-order cap, entire original share
inventory boundary, real broker-open/no pending orders, and zero broker
mutations. Negatives and missing fields return HOLD, never a MATCH.

Adversarial offline tests assert every literal code-owned evaluator stop
reason has a redacted fixed diagnostic and mutate/remove every critical
source field in the synthetic purported PASS. The protected source file's
exact Git blob hash is repinned in the LIVE credential-scope auditor,
protected test, and **both** pre-credential workflow checks.
Original 8 GET endpoints, main-only restricted credentials, schedule
09:39 weekdays America/New_York, original 3M data, signed HMAC, STOP,
no-POST and no new BUY capital remain unchanged.

The next open-market protected run is the first meaningful live-data
readiness result under the updated source contract. Even a MATCH
cannot make an order, certify principal, release the signed owner fence
or independently authorize trading.
