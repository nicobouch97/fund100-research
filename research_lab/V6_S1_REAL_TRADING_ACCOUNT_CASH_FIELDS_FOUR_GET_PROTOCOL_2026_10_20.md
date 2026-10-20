# V6-S1 actual Alpaca Trading LIVE account cash FIELD INVENTORY — preregistered 20 October 2026

Original source-frozen account/holdings verified genuine 4 GET on 18 October, genuine original 7 GET funding source [39303201301](https://github.com/nicobouch97/fund100-research/actions/runs/39303201301) and genuine original V6 client IDs [39317938514](https://github.com/nicobouch97/fund100-research/actions/runs/39317938514) with no matching orders. The original HIGH $130.30 LIVE pilot **operator STOPPED**, environment kill `ENGAGED`. Date-only original external transfer activities invalidate naive original V5 historical realized-risk claims. The V6 settlement-gate PR #81 is deliberately synthetic and prevents repurchase without authenticated proof. The Trading API field model PR #82 does NOT inspect the genuine account.

## Genuine falsifiable question BEFORE future SELL/BUY

On the *actual Trading API* `GET /v2/account` associated with the original LIVE funded account, does the source expose `cash_withdrawable` and `cash_transferable`? Does it expose pending transfer and nonmarginable purchasing capability? These are **presence-only flags**, not cash amount, spendability or proof that a SELL has settled. Alpaca separate Broker API FAQ field descriptions should not be attributed to this Trading API account until verified.

## Original authenticated STOP chain, GET scope

Reuse original SHA-pinned `fund100_v6_real_live_getonly_transition_readiness_v1_0.check_account`, which demands exactly four legacy original positions ACWI/EEM/XLE/XLV, matching original fill shares, original frozen account binding, ACTIVE status, zero open orders and original cash/equity/position reconciliation. Reuse exact original immutable `fund100_alpaca_live_readonly_smoke.get_json` for **exactly four GETs**:
1. `GET /v2/account`
2. `GET /v2/positions`
3. `GET /v2/orders?status=open&limit=100`
4. `GET /v2/clock`

The new reader is source-pinned independently with the original source, original proposed policy, LIVE operator and GET transport all pinned. Its protected LIVE job is only on `main`, exact `fund100-live-broker` environment, HIGH, engaged kill, readonly arm, operator remotely stopped; PR tests use **invented synthetic source-shaped fixture** only. **No additional endpoints, http writes, actions artifacts, secrets in stdout or external transfer checks**.

## Pre-registered result semantics

Only categorical/boolean flags leave the protected runner:
- Both direct broker-style fields present: `BOTH_BROKER_STYLE_FIELDS_PRESENT_SEMANTICS_UNVERIFIED`.
- Neither present: `DIRECT_BROKER_STYLE_SETTLED_FIELDS_ABSENT`. This makes the PR #81 direct-field positive path unsupported for the actual Trading account; **STOP**, research a supported cash-settlement source rather than pretend buying power/cash equivalent.
- Exactly one present: `PARTIAL_BROKER_STYLE_FIELDS_AMBIGUOUS_HOLD`.
- `cash`, `non_marginable_buying_power`, `buying_power`, `pending_transfer_in`, `pending_transfer_out`, `accrued_fees` present/absent, and `multiplier` categorized into 1/other/missing, only. The original account verifies actual cash and equity internally but NEVER outputs values. Missing optional fields are not misclassified as account failure when original four-GET verification passes.

No account ID, account number, share quantities, cash amounts, order details, raw account JSON, exact equities/returns or credential values appear in output. If source original four GET fails, report STOP with no numeric details; no HTML artifacts. Always `actual_original_sale_proceeds_settled=False`, `real_buy_sell_authorized=False`, `broker_non_get_requests=0`. Under no circumstances is BUY permission granted from field presence.

## Acceptance criteria

Negative synthetic tests: wrong original broker binding/holdings, non-stopped operator, malformed response shapes, missing or partial candidate fields, present positive fake fields (must still NOT authorize), source fields redacted, exact four-GET log, original pinned transport/reader, injected invalid pins and workflow eligibility. Full repository LIVE static audit PASS before merge; on `main` genuine protected four-GET source run; status based on actual run not expected outcome. Keep original $130.30 pilot, V6 staged sale permissions and all LIVE switches unchanged.
