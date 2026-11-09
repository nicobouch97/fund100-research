# Fund-100 scalable capital: standing-mandate integrity and paginated funding research

9 November 2026. Engineering checkpoint, research-only. Not a release or an owner-approved capital increase.

## Objective and unchanged authority

The owner wants additional funding (possibly GBP 10,000 soon) and eventual scalable, autonomous investment with LOW/MEDIUM/HIGH risk and emergency STOP as the only routine controls. This must avoid arbitrary fixed-cap technical limitations once a separately approved standing authority exists. It must not infer authority from merely discussing or depositing new funds.

The present LIVE mandate remains USD $130.30 cumulative pilot with $65 maximum new-buy / partial-sale ticket, broker kill ENGAGED, V5 and V6 operator STOP, separate signed ACWI order reservation and no live first SELL or BUY release. The protected 9 November eight-GET source reported ACTIVE_PILOT_CAPITAL_CEILING_HOLD. This code does not waive or resolve that blocker.

## Implemented here (synthetic only)

- Strict HMAC-SHA256 draft-mandate integrity: unapproved/dormant schema, USD-only exact capital, account-binding digest, risk tier list, revision/parent digest, issue/expiry UTC, JSON duplicate detection, MAC validation. Synthetic fixture keys are NOT evidence of owner approval, production key custody or independent immutable anchoring.
- Paginated hypothetical funding completeness: bounded pages/rows, stable source IDs, ascending activity dates, exact continuation token chain, full-page ambiguity, source account binding, as-of freshness and inception coverage. No live API client.
- Signed USD CSD deposits and CSW withdrawals. Dividends, fees and interest are not deposits. Missing/duplicated/unsettled/unsupported events, asset transfers including ACAT, GBP records, bad money signs, incomplete paging and impossible withdrawals HOLD.
- Conservative two capital checks: both NET contributed principal and GROSS lifetime deposits must remain within the draft ceiling. A withdrawal followed by redeposit cannot silently recycle a cumulative pilot limit.
- Public stages do not include private cash amounts, source activity IDs or account binding values. All results force live_order_authorized false; no broker credentials, GET/POST, real ledger CAS or private signed writes exist.

## Not implemented: remaining production critical path

1. Explicit owner-approved new capital scope in an independently controlled versioned standing mandate, signed with production key and separately provider-immutable anchored. No changed USD cap can be inferred from a possible GBP 10k deposit.
2. Authentic, complete broker cash/FX activity history from account inception, pages and source timestamps, withdrawals, settlements, foreign currency conversion and duplicate detection. Existing Alpaca date-only activity records are not proof of intraday settlement.
3. Durable private funding ledger with HMAC/CAS, independently verified immutable rolling heads and authenticated broker source; this change is offline only.
4. Real omnibus account attribution: excess funds mixed in the same account cannot be declared segregated by a virtual sleeve or original filled-order value alone.
5. Production order-time strategy source, safe risk levels, settled cash, current holdings/FILL/STOP, broker single writer, pre-order signed reservation, at-most-once POST and nonblind ambiguity recovery. Current capital/ticket locks remain.
6. FX: only actual settled USD credited to Alpaca is potentially eligible, after authentic conversion and costs; new trading capacity and liquidity need independent verification.

Within a valid future standing mandate, funding, trade selection and reconciliation should not require a recurring owner approval. Owner controls remain selected risk LOW/MEDIUM/HIGH and emergency STOP.

CURRENT RESULT: RESEARCH ONLY, live ACWI first sale and all live new buying remain stopped.
