# Fund-100 V6-S1 — genuine settlement evidence contract, no fake spendable cash

**Pre-registered 20 October 2026 BEFORE offline test or any new brokerage operation.** Last genuine LIVE account remains original ACWI/EEM/XLE/XLV with zero V6 submitted orders; this module must not claim that the legacy sales already occurred.

## External source distinction

Alpaca's brokerage FAQ: SELL updates `cash` at fill; `cash_withdrawable` and `cash_transferable` update only after **T+1** settlement: https://docs.alpaca.markets/us/v1.1/docs/broker-api-faq. However the **Trading API account** used here is not necessarily guaranteed to expose `cash_withdrawable` or `cash_transferable` (the source FAQ refers to broker accounts); nonmarginable buying power or trading buying power **is not independent settlement proof**. No invented `settled_cash` field and no fallback `cash == buying_power` or `now is T+1` allowed. If the actual Trading API lacks independently verified post-sale spendable fields, HOLD and research supported source/endpoint and/or obtain a separately reviewed confirmation. Proceeds after fill ≠ settled spending money.

The new independent V6 risk contract [PR #80](https://github.com/nicobouch97/fund100-research/pull/80) preserves original XLE and exits exactly ACWI, EEM, XLV. Original V5 >$0 invested holdings are not to be sold until real private cross-run journal and controlled LIVE sale approval. Clean V6 performance boundary follows reconciled transition.

## Strict stage-2 *synthetic* reconciliation requirements

- Only `INVENTED_SETTLEMENT_AND_ACCOUNT_FIXTURES_ONLY` mode, original HIGH/STOP/ENGAGED, same synthetic immutable account ID before/after, exact 3 original migration SELL stable client IDs, all three status `filled`, `filled_qty == original_qty`, original synthetic positions ACWI/EEM/XLV **flat**, original XLE retained and below draft V6 target (otherwise review). Unique receipt order IDs, market DAY sell, distinct time zone aware UTC fills.
- Independently supplied *invented* US equity settlement session calendar (trading days, excluding injected holidays) with a dated session strictly after each corresponding fill and no later than private account observation date. Calendar must include each fill trading date. Business-day date alone is **not** sufficient; settlement date is *necessary*, not conclusive.
- Original cash at start and current private `cash`, `cash_withdrawable`, `cash_transferable`, `non_marginable_buying_power` fields if present, measured at source-fresh after-date account snapshot and explicit original account binding. All must be finite, nonnegative and mutually consistent. No negative cash, unknown open orders, unknown nontrade activities, external funding/inflows, stale read, unexplained positions or account rebind.
- Require BOTH withdrawable and transferable broker **settled/transferable** cash source fields plus nonmarginable buying power, compare cash reserve after hypothetical BUY and projected costs using **minimum** of these sources. Comparing to the pre-sale cash withdrawal/transferability baselines blocks misleading field decreases; it still does not prove sale-credit provenance without activity history. All are independent conservative cash bounds; any missing field, including an actual Trading API source that does not expose those broker-account fields, reports `BROKER_SETTLED_FIELD_UNSUPPORTED_HOLD` and NEVER permits a LIVE BUY.
- Original planned BUY notional must be a hypothetical $1–$65 notional, 5% NAV cash reserve, ≤95% gross/≤50% name, within $130.30 pilot and no new deposits. The result reveals **no actual balance/quantity/ID** and always `live_buy_authorized=False`, `broker_requests=0`.
- Private cross-run CAS receipt and LIVE warmup 6% daily/20% drawdown/35% vol **also remain unverified**; settlement alone can never release orders.
- No CODE path to call Alpaca, no credentialed workflow, no remote private-state token or real account GET. All tests invented, meaning no claim of actual settlement or future order permission.

Acceptance: all mismatch/status/partial/holiday/weekend/withdrawable-hidden/external-flow/source-stale/over-allocated cases fail-closed; a physically plausible *invented* settled account can only report `SYNTHETIC_CASH_EVIDENCE_ENVELOPE_VALIDATED_NOT_LIVE`. Full LIVE static audit must pass with original operator STOP.

## Release dependency after this PR

For future authentic source, identify the correct **Alpaca Trading API account** settlement fields or validated broker activity settlement endpoint and independently confirm availability in this actual LIVE account. An authenticated price/account field missing at runtime is an engineering blocker, **not** a reason to remove cash-settlement controls. Do not force buys in the meantime.
