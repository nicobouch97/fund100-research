# V6-S1 — authentic Alpaca LIVE Trading cash field inventory and next supported settlement route

**Observed on 20 October 2026, 20:10:59 UTC.** Authenticated protected [LIVE four GET run 39489743795](https://github.com/nicobouch97/fund100-research/actions/runs/39489743795), resulting from reviewed [PR #83](https://github.com/nicobouch97/fund100-research/pull/83). Protected `main`, environment `fund100-live-broker`, HIGH, operator STOPPED and kill ENGAGED; exactly 4 broker GET and **0 broker writes / 0 orders**.

## GENUINE field-presence results (amounts and IDs are private and NOT persisted)

| Trading account field | Present on actual LIVE account? |
|---|---|
| `cash` | YES |
| `buying_power` | YES |
| `non_marginable_buying_power` | YES |
| `cash_withdrawable` | **NO** |
| `cash_transferable` | **NO** |
| `pending_transfer_in` | **NO** |
| `pending_transfer_out` | **NO** |
| `accrued_fees` | YES |
| `multiplier` | 1X, **NOT** settlement certificate |

Original authentic account binding and four original ETF holdings ACWI/EEM/XLE/XLV were verified again. Zero open orders. The actual requested V6 transition has **NOT** begun. No past or future settlement status is established for absent sales.

**Architecture decision:** The original synthetic [PR #81](https://github.com/nicobouch97/fund100-research/pull/81) required **both** `cash_withdrawable` and `cash_transferable`. Their absence is now **proven for this actual Alpaca Trading LIVE account**; the PR #81 *positive* direct-field path is therefore unsupported on this account. DO NOT alias `cash`, `buying_power` or `non_marginable_buying_power` to those missing settled fields. See [Trading Account object](https://docs.alpaca.markets/us/v1.1/docs/account-plans) describing `multiplier=1` as standard limited margin with buying power equal to cash, not a settlement certificate; [Broker API FAQ](https://docs.alpaca.markets/us/v1.1/docs/broker-api-faq) for Broker-specific withdrawable/transferable fields. The two account APIs have separate schema/semantics.

The source-only offline capability classifier `fund100_v6_s1_trading_account_cash_capability_v1_0.py` was initially written assuming the `pending_transfer_in/out` values are always present. This genuine source **disproves that assumption**. Amend it to accept their absence while classifying `PENDING_TRANSFER_FIELDS_ABSENT_HISTORY_REQUIRED`, **never** converting missing to a verified 0; financial nontrade activity pagination and external deposits remain source requirements.

## Practical Trading API-only alternative to research and test (not yet authorised)

1. An authenticated pre-S1 migration account, position and zero-open-order snapshot and independent durable private state reservation, with source-identifiable original ACWI/EEM/XLV position and individual order client IDs. Source-verified XLE retained.
2. Every actual LIVE original SELL must have matching Alpaca order-by-client-ID receipt, matching individual fractional `FILL` activities (documented with `transaction_time`, `order_id`, `qty`, `side`), exact cumulative quantity, flat position, zero open orders; activity history must be **fully paginated** and checked for cancellations, corrections, deposits, withdrawals, journals, fees and dividends in the transition window. Source: [Trading API Account Activities](https://docs.alpaca.markets/us/v1.4.2/docs/account-activities), [Trading account activity list](https://docs.alpaca.markets/us/reference/getaccountactivities-2).
3. Standard US ETF T+1 after a valid completed stock exchange settlement session is a **necessary** timing gate; propose **one additional completed session buffer** (T+2) as a conservative design, not a substitute for failed-settlement or broker error proof. Verify actual date sequence from a supported exchange calendar and activity trade timestamps; weekends/holidays can delay.
4. Fresh genuine account `cash`, `non_marginable_buying_power` and `buying_power`, account multiplier and blocked flags, consistent original sale proceeds, original holdings residual XLE, no other unexpected transfers or open orders; allow only a separate explicitly reviewed **source-specific provisional spendability policy** if brokerage execution accepts the spend and all original HIGH risk/5% NAV cash reserve conditions pass. Account-only buying power does NOT prove legally settled withdrawal balance.
5. If a source amount/timing cannot be independently reconciled, stop and require broker-supported settlement confirmation rather than force a BUY. Do not use old V5 unadjusted equity returns as genuine V6 6/20/35 risk proof.
6. Private read-only token stored by user in protected environment but **an approved protected cross-repository Actions job remains blocked by tool safety constraints**. Remote private CAS writes and replay-proof independent state still not verified; no LIVE SELL release until that is resolved separately.

**This result note does not create orders, authorize any LIVE action, alter original protected source pins or expose customer financial amounts.** Starting REAL $130.30 HIGH pilot remains invested as originally; user delegated V6 S1 strategy objective, but no alpha guarantee and no extra deposits.

Next concrete source step is a separately reviewed, main-only **authentic GET of original Trading API FILL activity schema/order linkage**, not months of PAPER testing. Then prepare private cross-run state access and the first staged original SELL with operator and risk release. 
