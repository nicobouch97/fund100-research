# Fund-100 V9 — official current US listing discovery, prospective only

**Registered 10 November 2026. NO historical backtest, trade, investment
recommendation, portfolio selection, qualified common-stock universe, or
license for unrestricted republication.**

## Why this is different, and why it is limited

The owner wants the eventual five-pillar stock opportunity engine to explore
thousands of potential names, not just the 8 / 24 / 100 preselected contemporary
survivors. The complete as-of historical listed-and-delisted security master,
corporate actions, SEC filing vintages, share classes, prices and analyst
revisions are **not acquired**, as explicitly documented in
\`P4_HISTORICAL_DELISTED_DATA_SOURCE_DECISION_2026_11_02.md\`.

This step starts an **authentic prospective current listing-source clock**,
using two official NASDAQ Trader publicly accessible symbol directories:

- https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt
- https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt
- Official field specification: https://www.nasdaqtrader.com/trader.aspx?id=symboldirdefs
- Official symbol files refresh intraday and next-day issuance can be delayed;
  Nasdaq's 2026 directory publication note:
  https://www.nasdaqtrader.com/TraderNews.aspx?id=ETA2026-64

Current-venue listing records are **not** a dataset of US-domiciled common
shares. A non-ETF, non-test flag can include ordinary shares, preferreds,
depositary receipts, warrants, rights, units, trusts and other economically
different securities. An ACT/CQS/Nasdaq ticker is also **not** a permanent
security/share-class identifier. No sector, financial statements, valuation,
liquidity or earnings expectations are inferred from names or ticker strings.

## Source capture, no user action or paid data

- Source-specific official host and two literal HTTPS GETs (no redirects),
  bounded at 4 MB each and 20-second timeout, only when source capture runs
  on protected default **main**, or in a credential-free local research test.
- Validate official original headers, every row/flag, field widths, symbol
  uniqueness *within each file*, complete file-creation footer and freshness
  against the actual New York clock; files older than **96 hours**, future
  files, malformed rows or changed schemas STOP rather than supply a fake
  dated universe. Source file-creation time is **publisher metadata**, not a
  separately independently signed creation timestamp.
- Publish **only aggregate rows by exchange code and flags, the original
  byte-length, original raw-file SHA-256 and real UTC capture timestamp**,
  under one dated observation in
  \`research_lab/stocks/prospective/official_listings/\`. No issuer names,
  tickers, source tables, raw bytes, bank/account identifiers or broker data
  are stored in the public repository. A hash is useful for detecting revisions
  against preserved independently obtained source bytes later; **without
  the original bytes archived under appropriate rights it cannot replay a
  complete 2026 listing universe after the vendor changes it**.
- No overwriting an existing daily observation to hide intraday revisions.
  Git main-only source publishing uses fast-forward pushes, at most three
  reconstructions if a concurrent legitimate main writer advances first.
  An uncertain push/changed branch ancestry STOPs; no force push. A later
  failed run is **not** proof of complete source coverage for that date.
- Weekday research capture: 02:30 UTC Tuesday–Saturday (after prior US
  evening directory refresh), plus first merged-main push and controlled
  workflow dispatch. Overnight file contents may include next-day changes;
  the capture timestamp is the only claimed as-of source time. Never
  interpret this as same-day prior-market-close stock eligibility.
- Offline pull-request CI exercises stale/missing/corrupt/unknown-field,
  duplicate-symbol and no-raw-issuer-leak cases. Pull-request workflows
  neither fetch live directories nor carry mutation permissions.

## What a genuine report would and would not prove

A source-backed total of, e.g., several thousand **non-ETF/non-test listing
rows** would prove only the breadth of this *unqualified discovery pool*, NOT
that several thousand viable stock ideas have been screened. The first
predeclared US common-share target remains **>=1,000 truly eligible distinct
security classes in >=10 sectors**, including point-in-time and delisted
evidence for historical performance claims. The report does NOT certify
that threshold. No historical constituent membership, issuer fundamentals,
SEC CIK-to-share-class join, ticker reuse, current broker eligibility, genuine
point-in-time valuation, backtested return, 5-pillar score or alpha.

## Next useful independent admission step

After a real first capture, inspect **aggregate counts and row-class
coverage**, then separately authenticate SEC/company CIK and legal common
share / ADR / preferred / warrant / unit classification. Do not treat
security-name heuristics as point-in-time security-master evidence. The first
true historical backtest still needs delisted security identities, raw
corporate-action adjusted wealth paths, as-reported filing dates and a
legally usable complete data source. A contemporary prospective roster is
useful in parallel but not a substitute.

All existing Fund-100 USD130.30 original funded pilot, $65 new-order limit,
HIGH risk, STOP/ENGAGED kill switch, broker and signed journal permissions,
V6 first ACWI sale HOLD, and approved ETF whitelist remain **unchanged**.
This code has ZERO brokerage requests, private CAS, trading decisions or
LIVE releases. Real-money launch remains separate from this research.
