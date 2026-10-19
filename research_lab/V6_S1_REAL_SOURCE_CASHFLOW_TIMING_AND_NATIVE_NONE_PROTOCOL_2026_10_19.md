# V6-S1 — original Alpaca cash-flow timing and native NONE portfolio-history validation

**19 October 2026. Precommitted before new authenticated LIVE API inspection. No broker order, no S1 release.**

## Real reason

Actual original Alpaca LIVE [run 39299643300](https://github.com/nicobouch97/fund100-research/actions/runs/39299643300) verified nontrade external activity type(s), original four V5 ETF holdings, and original XLE market weight below proposed S1 target. [PR 71](https://github.com/nicobouch97/fund100-research/pull/71) then implemented a strictly offline **approximate Modified Dietz** return estimator that requires timestamped, signed CASH contribution/withdrawal activity. It has never received or processed authenticated customer funding amounts. Do not disguise LIVE values as SYNTHETIC fixtures.

**Provider documentation nuance:** original [Alpaca account activities](https://docs.alpaca.markets/us/docs/account-activities) distinguishes trade `transaction_time` from nontrade `date`; provider SDK describes nontrade `date` as occurrence **or settlement**. Some nontrade records may omit the intraday `transaction_time` that an independently adjusted precise daily return requires. [Alpaca daily portfolio history](https://docs.alpaca.markets/us/reference/getaccountportfoliohistory-1) supports `cashflow_types=NONE`, but its optional cashflow setting must NOT be assumed to turn the resulting `equity` or `profit_loss_pct` into exact investment returns without source reconciliation.

## Original provider queries and outputs

Only existing source-reviewed, SHA-pinned, main-only, HIGH, STOPPED, kill-engaged `fund100-live-broker` environment is permitted, and only after full static audit. The new exact-read script is approved separately with a SHA pin and negative-mutation tests. Original seven GETs, strictly in this order:

1. `GET /v2/account`
2. `GET /v2/positions`
3. `GET /v2/orders?status=open&limit=100`
4. `GET /v2/clock`
5. `GET /v2/account/portfolio/history?period=1M&timeframe=1D`
6. `GET /v2/account/activities?category=non_trade_activity&after=2026-09-01&direction=asc&page_size=100`
7. `GET /v2/account/portfolio/history?period=1M&timeframe=1D&cashflow_types=NONE`

The first six are routed through **already independently reviewed source binding / raw HIGH history validation / original XLE reuse and external-source categorization** and any account identity, quantity, open order or operator STOP mismatch halts. Activity classes and `net_amount` source-field eligibility are verified **only in private memory**, with zero public values.

Precommitted privacy-safe outcomes:
- For CASH `CSD` and `CSW`, reject missing/nonfinite/wrongly signed `net_amount` as `CASH_AMOUNT_SOURCE_INVALID`; no assumption about customer activity counts in public logs.
- For cash transfer types with valid signed amounts but nontrade `date` **and no offset-aware `transaction_time`**, return `CASH_TRANSFER_SOURCE_DATE_ONLY_NO_DIETZ` rather than applying settlement date as performance time.
- For cash transfers with valid offset-aware `transaction_time`, classify `CASH_TRANSFER_AMOUNT_AND_TRANSACTION_TIME_FIELDS_PRESENT_UNRECONCILED` (not yet verifying portfolio-close alignment and funding completeness).
- If only noncash journals/security transfers/unknown transfer types exist, `NONCASH_OR_UNKNOWN_TRANSFER_REQUIRES_VALUATION_REVIEW`—never an invented USD cash adjustment.
- No relevant transfers in window: `NO_EXTERNAL_TRANSFER_DETECTED_IN_WINDOW`, never "whole history has no transfers."
- Exactly 100 returned activities implies `PAGINATION_INCOMPLETE` and no return computations.
- Daily portfolio history with `cashflow_types=NONE` must have *exact identical* original UTC epoch timestamps and same `1D` timeframe to compare fields. Original monetary P&L series may be unavailable; return `BROKER_NATIVE_NONE_PNL_SERIES_MISSING_OR_UNCOMPARABLE`, `...DIFFERS`, or `...SAME`—these are observational categories only. No external transfer amount, return, account number, XLE market value or P&L array in logs.

**Absolutely no** correct cashflow-adjusted 6%/20%/35% LIVE risk release, no T+1 settled spendable sale proceeds, new live authorisation, orders, writer, margin/leverage, change of $130.30 HIGH cap or the original live operator/broker STOP. First prove original actual data shape. If missing timing, choose robust brokerage-native verified reporting or explicit market-close cash flow accounting with independent dated broker original source later. Avoid expensive fake "progress" from merely adding test layers or months of PAPER profit backtests.
