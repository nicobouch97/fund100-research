# V6-S1 — point-in-time funding-aware account risk research, locked before implementation

Date: 19 October 2026. **Do not enable LIVE or PAPER orders.** Finance inputs are ONLY deliberately invented fixture data for this initial phase. A separate independently reviewed LIVE read-only reader must qualify and pass original brokerage activity details before actual account data can be used.

## Real evidence and research problem

Original genuine LIVE [six GET run 39299643300](https://github.com/nicobouch97/fund100-research/actions/runs/39299643300) observed six GET/zero orders, original ACWI/EEM/XLE/XLV quantities, original XLE not overweight under proposed 28.5% S1 target, cash below new 5% buy-time floor, raw HIGH account-equity history PASS, and **nontrade external transfer-type activities present**. It intentionally withheld original cash amounts/dates/IDs. Therefore the current 1D broker account-equity percent changes cannot be presented as investment returns nor valid cash-flow-adjusted 6%/20%/35% S1 portfolio risk evidence.

Primary provider documentation:
- https://docs.alpaca.markets/us/reference/getaccountportfoliohistory-1 — brokerage `1D` equity timestamps, values, `cashflow_types` optional query.
- https://docs.alpaca.markets/us/reference/getaccountactivities-2 — paginated original account nontrade activity source, `transaction_time`, `activity_type`, `net_amount`; `date` and transaction time have different interpretations. Do not substitute settlement date for the actual transaction timestamp.

## First invariant calculation (pure offline; independent economic source qualification pending)

For each successive original *end-of-session* brokerage equity observation E_{i-1}, E_i and the signed **external cash** transfers F_j strictly after the previous timestamp and at/before the current observation:

- Raw change = E_i / E_{i-1} - 1 (known cash-flow contaminated if deposits/withdrawals occur).
- Simple endpoint flow removal = (E_i - E_{i-1} - sum F_j) / E_{i-1}. This is a diagnostic, **not** an exact money-weighted or true time-weighted trading return.
- For a more refined original-account diagnostic use **Modified Dietz approximation**: (E_i - E_{i-1} - sum F_j) / (E_{i-1} + sum w_j F_j), where w_j is the fraction of the interval between when each cash transfer occurred and E_i. This remains an approximation when deposits are intraday, and can differ from actual daily time-weighted returns if the market fluctuated between the transfer and close. Report it as an ESTIMATE. For flows at the *end* observation, w=0; no in-day performance can be inferred.
- Unitize from index 1 by compounding estimated daily returns only for **exploratory** drawdown, risk-stop comparisons and volatility. This can help us quantify the difference between raw and funding-corrected proxies, but **does not certify LIVE S1 risk protection** without proper trade/transfer timing, account valuation fixes, daily account / fill history and independent cashflow evidence.
- Never treat the full account account-value change, raw Alpaca P&L, dividends or broker fees as external contributions. Dividends, financing costs and fees are part of investment economics.
- Only CASH deposits `CSD` with signed positive `net_amount` and CASH withdrawals `CSW` with signed negative `net_amount` are eligible for numerical adjustment. Noncash journals, ACAT security transfers or unfamiliar activity types have economic valuation effects that cannot be backed out from a simple USD cash entry: **FAIL CLOSED**.
- Every external event must have unique original activity ID, explicit offset-aware `transaction_time`, finite signed `net_amount` and a single unambiguous session interval. Missing transaction time (broker sometimes supplies only settlement `date`), a 100-entry unpaged response, overlapping/missing 1D history or uncovered activity date = **FAIL CLOSED**. A nontrade activity scan covers only events after a fixed date; prove the scan starts before the *first* portfolio history value.

## Preregistered tests and limits

Synthetic fixtures include: $100 initial equity / +$100 contributed before the next close / $200 ending equity => raw +100%, adjusted 0%; withdrawals; prices rising alongside deposits; intraday Modified Dietz weights; fees/dividends NOT corrected; unknown event; ACAT/JNL/security transfer; missing signed cash/transaction time; off-window flows; duplicated ID; pagination 100; stale history; negative equity; negative/zero denominator; implausible >25% adjusted return; and 6%-daily loss, 20%-drawdown and 35%-annual vol diagnostic breaches.

Outputs never contain account IDs, USD balances, activity IDs/dates/amounts, actual investment-return arrays, privately sourced equity or executable intents. A boolean broker history status and a diagnostic source label only. It must NOT connect to brokerage credentials, the new LIVE writer or enable operator trading. $130.30 authorization, HIGH risk, 5% cash-after-new-BUY, existing portfolio and broker STOP unchanged.

**Acceptance:** PASS means a tested *offline accounting method*, not a validated investment strategy, production stop release, spendable T+1 funds or authentic broker-adjusted risk report. Future live source work requires separately audited original activity data and account closed-session alignment. Do not spend weeks obtaining PAPER profit curves.
