# Fund-100 P4 historical stock-universe source decision — 2 November 2026

**Status: source qualification / acquisition blocker; no dataset acquired, no backtest run, no alpha, no broker access.** This is a concrete decision on how to close the largest remaining stock-research evidence gap, not another synthetic stock universe or a request to wait for months of paper performance.

## Decision

**First qualified candidate: Sharadar Direct US Equities Bundle (fundamentals + stocks + tickers/metadata + corporate actions).** Its official documentation describes:

- **As-reported** fundamentals (ARQ/ARY/ART) dated by the SEC filing date, versus **most-recent/restated** MRQ/MRY/MRT indexed to report period. Only AR dimensions are eligible for a historical *as-of* signal.
- End-of-day prices for **active and delisted** US equities, with distinct unadjusted, split-adjusted and split/dividend/spinoff-adjusted close fields, extending back to 1997/1998.
- A security-reference table and corporate-action events, including ticker changes, delistings, mergers, dividends and splits. The vendor's ticker suffix convention for reused symbols must be mapped to a stable security identifier; ticker strings alone cannot be used as identity.
- Nearly 18,000 covered companies in fundamentals and about 21,000 price tickers **as vendor-described coverage**, not independently measured by Fund-100.

**Why this is different from completed P4T/P4U/P4Z:** The SEC 2017 original filing population is not an exchange-listed security master, P4U's 64 filing covers do not prove historical trading eligibility, and P4Z's four retrospectively selected listings cannot establish cross-sectional returns. A joined historical *security-level* price/action/filing dataset is necessary to estimate whether a quality + momentum strategy survives delistings and costs.

The free Sharadar sample is limited to current Dow-30 companies and recent history; **it cannot close the historical delisting/survivorship gap**. Do not use a sample-only result as independent stock alpha. Sharadar's own coverage/survivorship marketing percentages are **claims to audit**, not accepted research outcomes.

## Actual acquisition and licensing boundary

The full bundle is **paid**; no entitlement, current price, license, API token or bulk data has been established. **Do not purchase a subscription or request a paid API automatically.** Sharadar Direct's published terms restrict personal subscriptions to a natural person's personal use, exclude organizations/funds, and restrict redistribution. Confirm that the eventual Fund-100 operating arrangement and automated use qualify *before* any paid acquisition. If the strategy is operated for a legal entity, fund or clients, obtain a suitable commercial license instead.

Do **not** commit vendor raw rows, bulk archives, sample extracts, API tokens, or reconstructible derivatives to the public `fund100-research` repository. The existing signed private execution-state repository is **not** a substitute for a properly permissioned research-data store. Source bytes, license metadata and SHA256 manifests belong in a separately access-controlled data environment, with only non-reconstructible aggregate test outcomes published if licensed.

Official source links, checked 2 November 2026:
- https://sharadar.com/docs/fundamentals — AR vs MR timing and reporting dimensions
- https://sharadar.com/docs/stocks — active/delisted prices and adjustment fields
- https://sharadar.com/docs/actions — corporate actions and delisting records
- https://sharadar.com/bundle — included datasets and paid status
- https://sharadar.com/terms — personal-use / redistribution restrictions
- https://sharadar.com/ — free sample scope

**Fallback, not an equal substitute:** QUODD documents inactive US securities after September 2010 and an `IdentifierAsOfDate` to resolve reused symbols (https://www.quodd.com/faqs/does-quodd-support-survivorship-bias-in-your-historical-stock-data-api). Its historical price capability does not itself establish an integrated, as-reported SEC fundamental panel or terminal distribution treatment. Do not splice vendors without an explicit security/action and coverage reconciliation.

## Data admission tests — required on actual licensed bytes, not synthetic fixtures

1. **Complete vintage and immutable source manifest.** Record vendor dataset/version, UTC retrieval time, contract/license scope, raw file SHA256, schema, row counts and date coverage. No silently overwritten historical archive. Keep raw data outside public Git.
2. **Security identity and as-of membership.** Resolve each historical common-share class using vendor security identifiers, original listing/delisting dates, exchange/security type, ticker changes and reused tickers. Exclude ETFs, preferreds, ADRs or non-US shares only under *predeclared* policy, never because they later disappear. Audit 2017 cohorts against P4T original 10-K CIKs and P4U filing covers; a CIK alone is not a share class.
3. **Causal fundamentals.** Use ARQ/ARY/ART only, and make a filing usable **after** its dated publication (conservative next-session entry if intraday release time unknown). Report period/calendar date must never substitute for filing availability. Reject lookahead through MR dimensions, current constituents, revised values or current ticker mapping.
4. **Prices, returns and corporate actions.** Use only price/volume observations actually present at each decision date for selection and liquidity. Reconcile raw, split-adjusted and total-return-adjusted fields to dated action records; no future-adjusted price level for historical entry eligibility. Treat stock splits, special dividends, spin-offs, cash/stock mergers, bankruptcies, trading halts and delisting proceeds explicitly. **A disappearing price series is an unresolved terminal wealth state, not zero return, free liquidation or a drop from the portfolio.**
5. **Cross-source adversarial checks.** Independently cross-check known historical changes (e.g., TWTR 2022-10-27 last trading close versus original SEC merger contractual $54.20 right in P4Z, without claiming actual settlement); test a reused ticker, split, cash dividend, merger, bankruptcy, halted security, and a 2017 issuer absent from today's ticker registry. Publish pass/fail counts and unresolved cases, never vendor rows.
6. **Coverage/selection diagnostics.** By each year, report historical eligible and delisted counts, missing-price/fundamental rates, action reconciliation, sector/size distribution, survivor versus non-survivor retention, and all exclusions. A vendor assertion of 99% survivorship coverage is not a measured Fund-100 result.
7. **Independent performance test.** Predeclare a quality + medium-term momentum hypothesis and controls *before* inspecting return outcomes. Use purged chronological train/selection/holdout eras and sector/size matched and passive benchmarks, multiple one-way costs (5/15/35bps plus realistic spreads/slippage), minimum liquidity and execution delay, delisting wealth outcomes, turnover/capacity, and crisis drawdown. No retuning on previously inspected 2026-survivor or ETF histories. Report confidence and failure conditions; do not equate a favorable retrospective Sharpe with established alpha.

## Decision / next action

**Source qualification completed; actual source acquisition remains blocked by paid entitlement and appropriate license/storage.** The next high-value implementation is a single real-data ingestion + coverage audit **after** legal data access exists, reusing P4T/P4U/P4Z independent SEC/action checks. Avoid building additional invented historical panels, repeating survivor-only stock backtests or creating a mock data adapter that cannot be exercised on authentic historical bytes.

This research decision does not change the launch-first small ETF pilot priority, the $130.30 cumulative LIVE ceiling, $65 routine ticket cap, HIGH policy, operator STOP, environment kill switch, signed private-state locks or LIVE writer permissions. No funded order, sale, private-state write or broker request is authorized.
