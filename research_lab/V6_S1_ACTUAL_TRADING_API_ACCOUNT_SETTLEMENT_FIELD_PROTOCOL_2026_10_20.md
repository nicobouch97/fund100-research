# V6-S1 Trading API — settle-source capability qualification (pre-registered 20 Oct 2026)

## Important distinction from PR #81

PR #81 implemented an **offline** BUY cash safety envelope but assumed access to `cash_withdrawable` and `cash_transferable` fields, with a hard HOLD if absent. The source for that distinction is [Alpaca Broker API FAQ](https://docs.alpaca.markets/us/v1.1/docs/broker-api-faq), **not** necessarily the Trading API used by the actual privately funded Fund-100 account. Source reference for the Trading API [Trading Account object](https://docs.alpaca.markets/us/v1.1/docs/account-plans) lists `cash`, `buying_power`, `non_marginable_buying_power`, `multiplier`, `pending_transfer_in`, `pending_transfer_out`, and `accrued_fees`. It does NOT document withdrawable/transferable in that account object. Trading API [account activities](https://docs.alpaca.markets/us/reference/getaccountactivities-2) are separate read-only evidence for exact fills; activity `date` is an activity creation date, **not proof of stock settlement date**. Neither field names nor fund source shapes justify treating `non_marginable_buying_power` or `buying_power` as settled cash.

**Source hypothesis**: a genuine `GET /v2/account` in the user's LIVE Trading account may expose buying power but not direct settled/transferable cash. Existing authentic V6 four/seven-GET account readers do not disclose a positive or negative field-presence result; therefore **we have not checked the real account's field inventory**. Do not cite public docs as if they were actual authenticated field inventory.

## Separate versioned pure capability classifier

The new module `fund100_v6_s1_trading_account_cash_capability_v1_0.py` accepts source-shaped account data from a hypothetical future authenticated reader with an expected **original SHA256 account binding**, and reports only **field presence and supported/requires-review labels**. No amount, ID, cash balance, HMAC or private quantity is ever output. The function cannot manufacture authentication: `source_authenticated_by_this_module=False` and `actual_live_account_inspected_by_this_module=False` in every result. It implements **NO HTTP**, gets **NO Alpaca key or GitHub PRIVATE repo token**, opens **NO LIVE route**, authorizes **NO order**.

The following outcomes are pre-registered:
1. If both `cash_withdrawable` and `cash_transferable` absent, return `TRADING_API_SETTLED_FIELDS_NOT_EXPOSED_IN_SUPPLIED_SNAPSHOT` and **NO verified settled cash**, even if `multiplier=1` and all buying-power fields are positive.
2. If both present and finite, label `POSSIBLE_WITHDRAWABLE_FIELDS_REQUIRE_ENDPOINT_SEMANTICS_VERIFICATION`; still **NO** settlement clearance until the source is independently verified for *this* actual API credential/account.
3. If either present without the other, label `PARTIAL_SETTLED_FIELDS_AMBIGUOUS_HOLD`. Malformed values, negative transfers, non-USD/nonactive/blocked account, mismatched original account binding or invalid leverage multiplier fail closed.
4. A margin-multiplier of 2/4 is distinguished from 1; `multiplier=1` is **not** the same as cash-account settled spendable proof. `non_marginable_buying_power` and `buying_power` may not release the BUY step.
5. Explicit `pending_transfer_in`, `pending_transfer_out`, `accrued_fees` values must be complete and valid. Positive pending transfers are a further source hold, not a guaranteed cashflow reconciliation.
6. Source must remain directly testable via synthetic negative cases; **no archived old source pins altered**.

## Genuine LIVE next step

Only a **separately approved, exact blob-pinned, main-only** authenticated read-only source adapter (with no changes to existing immutable Alpaca transport) may call the classifier on a fresh actual account and print one privacy-safe categorical label. Previous attempt to create a workflow directly consuming `FUND100_PRIVATE_STATE_READ_TOKEN` was blocked by connector safety controls; DO NOT bypass by moving the secret to an unprotected workflow. The new classifier *does not require* that token; the two credentials have unrelated scopes.

A true LIVE BUY release needs a verified cash/sale-proceeds mechanism compatible with the **Trading API account**, full private cross-run attempt persistence and idempotency, authentic legacy-sale fills, T+1 calendar/activity provenance, V6 6% daily/20% drawdown/35% volatility HIGH gates, risk and order transport review. If actual Trading API lacks certified settled spendability, require a separately documented supported endpoint or brokerage confirmation; do not weaken PR #81 on inference alone.

Original V6 intent is ACWI/EEM/XLV SELL, original XLE retain when within cap, then XLK/IWM/XLE allocation 47.5/19/28.5 with 5% cash. Trading remains STOPPED, pilot $130.30, **zero LIVE trades**.
