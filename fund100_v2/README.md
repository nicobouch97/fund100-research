# Fund-100 V2: isolated research universe screen

Status: **research-only, disconnected from execution**. This directory must not read Alpaca credentials, access a trading account, create orders, change the V5 baseline, or define LIVE risk permissions.

## First deliverable

`universe.py` accepts a caller-supplied sequence of dated instrument observations and returns:
- a reproducible and liquidity-ranked set of equity/ETF **research candidates**
- explicit rejection reasons for non-tradable, insufficient-history, stale, future-dated, low-liquidity, low-price, and wide-spread observations
- a deterministic SHA256 audit fingerprint of the selection and research policy

No ticker list is frozen. The caller supplies candidate assets; the code applies the policy on each call. The default screen is equities and ETFs **only**, excluding crypto, options, futures, shorts, and non-equity spot assets. An asset's `tradable` research input is not proof of availability in the specific live Alpaca account or jurisdiction.

## Offline historical bar adapter

`market_data.py` adds a local CSV reader for **symbol, date, unadjusted daily close, same-day share volume and quoted spread**. It rejects future-dated, duplicate, non-finite, unknown-symbol or malformed bars, and requires at least 20 recent trading sessions to estimate trailing dollar liquidity.

`observations_from_history()` takes an independently supplied **as-of catalog** and bar history and creates `AssetObservation` inputs for the universe screen; each input's history length and latest observed date remain checkable. It aborts an incomplete batch rather than silently excluding missing names. It does not fetch vendor data or validate that vendor's historical catalog is survivorship-bias-free.

The adapter deliberately uses **close × same-day volume** to estimate liquidity, not split-adjusted prices mixed with raw volumes. It is not a return engine or a performance backtest. Source timestamp provenance, trading calendars, corporate actions, delistings and survivorship-aware snapshots are still future dependencies.

## Point-in-time bundle contract (new)

`data_contract.py` creates a **research-only** `ResearchPanel` from three local files: `manifest.json`, `prices.csv` and `membership.csv`. It is intentionally **not** a network downloader or an Alpaca data client.

Each price CSV row must provide `session,symbol,total_return_close,spread_bps,price_known_at_utc`. Each membership CSV row must provide `session,symbol,eligible,membership_known_at_utc` with uppercase `TRUE` or `FALSE`. The bundle manifest declares the provider, snapshot ID, source evidence reference, SHA256 of each CSV, `price_basis=SPLIT_AND_DIVIDEND_ADJUSTED_TOTAL_RETURN`, `membership_basis=HISTORICAL_POINT_IN_TIME`, and `includes_delisted_instrument_history=true`. The loader requires complete historical **membership** grids. Historical **price** grids may have explicitly ineligible leading/trailing gaps, but not unexplained interior gaps. Future-dated or late-known membership, stale-vintage prices, duplicated records, eligible symbols with missing prices, incomplete hashes and malformed values are all rejected.

A price observation must be declared available after the regular 16:00 New York close but before 23:59 UTC on that same session; membership must be declared known by that close. This conservative cut-off does not model exchange holidays or early closes, which still need a verified trading calendar. A source with historically restated prices or present-day membership snapshots cannot pass simply by relabeling them: it needs **genuine archived as-of records**, including delisted instruments.

**Important proof limit:** the SHA256 binds file bytes to a manifest; it does not authenticate the vendor or prove that the declared publication time, split/dividend adjustment, past membership or delisting coverage is truthful. `BundleEvidence.source_verification` is always `SELF_ATTESTED_NOT_INDEPENDENTLY_VERIFIED`. Current unit tests use explicitly synthetic data. Passing those tests **does not** constitute a verified provider, tradable prices, unbiased historical performance or alpha evidence.

## Ragged historical IPO and delisting support

The research data contract can now represent **real absence of historical prices** as `None` in the synchronized research panel: before an instrument begins trading or after its final genuinely observed session. The membership CSV still needs an explicit historical `TRUE`/`FALSE` row for *every* date and symbol. A missing price is permitted only while historical eligibility is `FALSE`, and cannot appear as an unexplained interior hole within an observed price lifetime. Price and spread gaps must always agree. The screen excludes instruments whose 60-session lookback is incomplete instead of filling nonexistent prices or leaking later price data.

**Delisting exits are intentionally fail-closed.** If a hypothetical holding entered at `t+1` has no real observed exit at `t+2`, `walkforward.py` raises an error. It does not assume cash, zero loss, last-observed-price liquidation, or a synthetic return. To model a delisting credibly we still need separately sourced and adjusted last-trade/terminal settlement outcomes, including stock-for-stock acquisitions, bankruptcies and forced liquidation timing. A vendor claim that it includes delisted instruments is not proof of those proceeds.

`test_fund100_v2_ragged_history.py` verifies historical IPO absence, insufficient new-issue history, post-delisting gaps, missing-exit failures, missing benchmarks, interior gaps and reproducibility. This removes a structural survivorship-bias trap but does **not** certify independent historical universe completeness or establish an investable backtest.

## Corrected publication time and entry-eligibility gate

A bar dated `t` is not permitted to influence a trade instruction at the same `t` market close if the vendor publishes that bar afterward. The research-only bundle now requires its declared `price_known_at_utc` to be **after the 16:00 New York session close and no later than 09:00 New York on the next weekday**, and never later than 23:59 UTC of the requested `as_of` date. Thus a signal from session `t` is **formed after publication, by the next weekday's 09:00 New York cutoff**, and the simplistic hypothetical fill is the subsequent session's close `t+1`, with exit at `t+2`. Historical membership remains required by its own session close.

This timing cutoff is a conservative **weekday approximation, not an NYSE trading calendar**: public holidays, early closes and trading halts need a dedicated, independently verified calendar and venue-aware fill model. The CSV timestamps are still vendor-self-declared; no complete historical publication archives have been authenticated.

The evaluator also **refuses a free hindsight cancellation**: if the selected candidate becomes ineligible by `t+1` according to subsequently observed membership, it stops rather than assuming a zero-return skipped fill. A genuine pre-fill eligibility notice and broker/auction no-fill evidence would be required to model such a scenario. Real MOC/LOC orders can face earlier cutoff times than the 16:00 close, so the next-close assumption is **not** a guaranteed achievable price. No production orders or portfolio weights are constructed.

## Three signal families + offline walk-forward diagnostics

`signals.py` defines three fixed, transparent hypotheses, independently scored with prices **available at the signal session close**:
- **Medium-term momentum:** 60-session return excluding the latest five sessions
- **Short-term reversal:** inverse of the previous five-session return
- **Risk-scaled trend:** 20-session return divided by 20-session daily return volatility

All signals operate on a caller-supplied **corporate-action-adjusted return price panel** and **historically recorded per-session eligible symbols**. This differs from `market_data.DailyBar.close_usd`, which is currently unadjusted and MUST NOT be fed directly to return calculations without corporate-action and distribution adjustment. There is no authenticated price or constituent provider yet, so these components **do not establish historical alpha**.

`walkforward.py` tests the three hypotheses using **expanding-window training**, a predeclared cash baseline, explicit embargo sessions and disjoint out-of-sample blocks. Each hypothetical decision uses **session `t` prices after their declared publication time, by the following weekday's 09:00 New York cutoff**, assumes an illustrative fill at **next session close `t+1`**, and measures performance from that close to close `t+2`. It applies both sides' explicit fees, illustrative slippage and half the recorded quote spread on entry and exit. Test outcomes are never used to choose that same fold's family. All scores, fold choices, OOS diagnostics and research data are hashed for reproducibility.

These are **single-symbol, one-day, fully exited hypothetical independent trials**, not a replicable implementation, real transaction history, or operator-authorized portfolio. The benchmark is a passive and uncosted daily reference, with different turnover economics. Actual V2 portfolio construction, multi-asset risk management, bid/ask fills, market impact, financing, exposure limits, delayed corporate actions and serial order reconciliation **do not exist here**. The reported compound fraction is purely a diagnostic based on these simplified independent trials, never observed NAV.

`test_fund100_v2_signals.py` and `test_fund100_v2_walkforward.py` include no-future-data mutation, embargo/purging, failed market-eligibility, excessive-cost cash fallback and reproducibility tests. The V2 CI workflow exercises all tests offline without LIVE credentials or brokerage network clients.

## Research-only default screens

Minimum 252 historical sessions, USD price at least $5, average 20-day dollar volume at least $5 million, quoted spread at most 40 basis points, observed snapshot at most five **calendar** days old, and the top 250 passing symbols by dollar volume. These are *exploratory universe defaults*, not LIVE exposure, risk or order bounds.

## Public-source format inspection only

`provider_sample_inspector.py` accepts local LEAN ETF constituent examples or ticker map-file text and returns strict **format-only** audit reports. It checks security identifier reuse, date/format anomalies, unique symbols and file SHA256, and explicitly returns `FORMAT_ONLY_NOT_HISTORICAL_EVIDENCE`. It cannot emit a `ResearchPanel` or convert ETF holdings into historical price/alpha evidence.

QuantConnect's public LEAN sample ETF constituent files have repeated SID tokens (503 tickers but only 166 distinct SID tokens in each of two inspected dates); the public sample directory includes a third-party rights notice. No vendor sample rows were republished here. For sources and affordable Cloud data feasibility, see `VENDOR_DUE_DILIGENCE.md` and open historical-data gate #4.

## Cost-controlled QuantConnect Cloud research feasibility

`qc_cloud_feasibility.py` provides a tightly bounded **QuantBook research-only** feasibility probe. It checks aggregate historical US-equity Fundamental universe coverage over three short windows (2018, 2020 and 2024), reports source-period dates, missing price/liquidity counts and duplicate QC symbol keys, and takes at most ten temporary research subscriptions per period/day. It does **not** export provider price rows or identifiers, create trading orders, use Alpaca, certify a source vintage, validate dividends or calculate alpha. Every report is marked `CLOUD_COVERAGE_ONLY_NOT_PIT_ALPHA_EVIDENCE`.

The function must be passed a QuantBook instance from the QuantConnect **Cloud Research** environment. GitHub CI tests only its mocked interface; **it has not been executed against Cloud data**. The documentation at `VENDOR_DUE_DILIGENCE.md` explains the optional Cloud execution path, Free-tier resource limits, data licensing and required source-independent verification. Cloud research access is separate from paid data downloads, and no account has been connected or created.

## Critical data and risk limitations

1. **No network data provider implemented.** This module receives observations, not a broker-feed request. To avoid survivorship and lookahead bias, V2 needs a historical point-in-time constituent/eligibility data source, delisting records, date-aligned volume/spreads, and adjusted OHLCV data. Merely setting `observed_on` cannot make a present-day asset catalog historically unbiased.
2. **No validated alpha.** Three exploratory signal hypotheses and a synthetic purged walk-forward diagnostic now exist, but no verified point-in-time adjusted dataset, realistic market-impact calibration, model-selection robustness or independent holdout supports profitability. No portfolio backtest is claimed.
3. **No execution.** No trading permissions, portfolio weights, position sizing, stop losses, or orders are emitted. Any future LIVE eligibility must be checked with contemporaneous broker asset permissions and operator-approved risk bounds.
4. **Crypto remains a separate research workstream.** Venue, session/calendar, min notional and spread/market-depth semantics are different; 24/7 crypto is not supported by the current equity scheduler.
5. **No V5 coupling.** V5 production, its kill switch, locked capital ceiling and release process remain entirely unchanged.

## Next build gates

Source verified point-in-time US-equity/ETF membership, delisted names and corporate-action-adjusted total-return prices; build a read-only vendor adapter with data-provenance logs; quantify missingness and adjusted spread/depth quality; perform genuine survivorship-aware multi-regime and independent-holdout walk-forward comparisons and calibrated fill models; then design the Master Risk Engine and shadow comparisons. Paper and LIVE are separate later approval gates.
