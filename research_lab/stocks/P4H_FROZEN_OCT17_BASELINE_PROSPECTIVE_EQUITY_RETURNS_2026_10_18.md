# Fund-100 P4H — first prospective equity-quality momentum return ledger

**Frozen 18 October 2026, before Monday 19 October first possible new trade session. Research only.**

## Original immutable baseline

- P4G original genuine price snapshot run: https://github.com/nicobouch97/fund100-research/actions/runs/39015519726
- GitHub artifact: `fund100-p4g-prospective-stock-price-evidence` (original artifact id **12094995126**, created 17 Oct 2026), with exact original observation for **Friday 16 October 2026**. This is a source fingerprint, not a buy order.
- Baseline's original 2026 SEC issuer quality source is itself dated **15 October 2026**, so the entire preceding 2025 and early 2026 price time series is LOOKBACK CONTEXT, **NOT forward strategy performance**.
- P4G frozen admissible tickers: AAPL, MSFT, GOOGL, AMZN, PG, KO. XOM and JNJ quality currently UNKNOWN, never ranked as score 0. P4G's existing rank and threshold process is reused exactly; absolutely no retraining.
- Baseline P4G output retains complete adjusted-close CSV SHA256, original SEC source SHA, snapshot acquisition time, selected watchlist, equal six-stock baseline and SPY. Each pair of old+new source files must independently match its own JSON SHA. Any conflicting prior source bar between vintages rejects the comparison as provider revisions, not silently overwrite history.

## Exact, predeclared forward payoff

1. Use the ORIGINAL 17 October fixed watchlist, selected with only data completed through **16 October**. Never rerank based on follow-up prices.
2. **Do not claim entry on Friday 16 October or the next Monday's opening price.** Hypothetical first buy occurs at the NEXT observed close strictly after baseline, at earliest **Monday 19 October**, because close on 16 October was only knowable after the fact.
3. First measured daily forward return occurs on the *second* newly completed session after the frozen 16 October baseline, earliest **Tuesday 20 October**. If only Monday 19 October is present, emit `ENTRY_SESSION_OBSERVED_NO_FORWARD_RETURN`; if there is no new session, emit `NO_POST_FREEZE_ENTRY_SESSION`. Never present 2014–2026 backfilled returns as post-freeze.
4. Equal-weight **buy-and-hold** P4G watchlist with **up to 3 names**; if empty, model 100% CASH zero interest. Nondiversified share allocations are research-only; original LIVE account allows 14 ETFs, no individual stocks.
5. Compare passive SPY and equal-weight six-company **fixed contemporaneous P4E quality reference** over the *same entry and exit close dates*, all in USD. No daily rebalance; no proceeds reinvestment, shorts, leverage or crypto. Use frozen P4G equal-weight cohort from baseline JSON.
6. Research trading cost scenarios **5, 15, 35 basis points per traded side** for one-time entry and hypothetical terminal exit applied symmetrically to watchlist, six-stock reference and SPY. No implicit execution at close verified, no spread or market impact quote, taxes and GBP FX are absent. If CASH, no fee.
7. Returns are short-window percent, with daily observations and peak-to-trough drawdown AFTER first eligible entry. Never extrapolate a handful of days to CAGR or claim statistical significance. Forward outcome might be positive or negative.
8. Repeated same-session snapshots should yield identical observation count, not new observations. The public yfinance adjusted closes can be revised retrospectively, so matching all bars common to both source snapshots is mandatory; if any mismatch occurs, `FAIL_CLOSED_SOURCE_REVISION` instead of a faked clean forward result.
9. The algorithm does NOT produce purchase/sale recommendations or account-sized orders; quarterly issuer scores cannot be assumed point-in-time in 2024–2025. No vendor analyst EPS revisions; P4F remains unlicensed/unconnected.

## Execution of research

New `fund100_stock_forward_return_ledger_p4h_v1_0.py` consumes exactly the authenticated first artifact's JSON+CSV and one later P4G price capture. The new dedicated GitHub workflow runs an explicit temporary `gh run download 39015519726` for the archived **original** 17 October artifact, then invokes existing frozen P4G fresh public market-data download. Scheduled daily Tuesday–Saturday after previous US session close; no Alpaca secret, environment, quote endpoint, order, or payment.

First Sunday 18 October run can prove baseline and return `NO_POST_FREEZE_ENTRY_SESSION`; it cannot create Tuesday's future return. Source availability and legal reuse are not guaranteed. GitHub artifact retention 90 days means source hashes and original file must be durably retained before expiry if research is continued.

Current actual LIVE four ETF positions are verified by genuine GET-only Alpaca account read on 18 October 2026 and remain HELD/STOPPED with original HIGH and $130.30 ceiling. P4H never contacts LIVE, does not promote stocks, and does not require paper-trading months before a properly disclosed future V6 live launch.
