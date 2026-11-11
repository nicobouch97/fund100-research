# V9-F4 — original current free FIGI reference-source qualification

**11 November 2026. Research-only, zero brokerage, zero account/owner keys, zero trade permissions.**

## Why this is a substantive candidate

Independent primary provider [OpenFIGI API v3](https://www.openfigi.com/api/documentation)
supports no-key mapping of tickers to venue `figi`, national
`compositeFIGI` and `shareClassFIGI`, with instrument type and
`includeUnlistedEquities` for unlisted/delisted records. It supplies
identity *metadata*, not price, corporate actions, issuer SEC CIK or dated
original market membership. [Allocation rules](https://www.openfigi.com/about/allocation-rules)
explain persistent identifiers after delistings, but mapping the current
ticker today is **not proof that any share was listed in 2017**. Official
[terms](https://www.openfigi.com/docs/terms-of-service) provide open-use
FIGI identifiers without paid licensing. Unauthenticated source max is
25 mapping calls/minute and 10 jobs/call. No API-key signup is required for
a deliberately tiny first cohort.

## One real-source experiment, no selection based on outcomes

The existing V9 original two Nasdaq official listing directories and one
SEC `company_tickers_exchange.json` serve as **the same fixed current
company sample**. From the existing deterministic SHA256 first 32-CIK sample,
select the *first eight*, not the eight easiest shares after checking data.
Quarantine an issuer if it has multiple current SEC ticker/venue associations,
including unqualified null or malformed aliases, or no exact explicit
common/ordinary wording link. **Never replace those prechosen missing
issuers**. At most eight original candidate symbols are submitted in
**one** HTTPS OpenFIGI V3 `POST /mapping` request with
`idType=TICKER`, `exchCode=US`, `includeUnlistedEquities=true`.
This is a public data retrieval POST, **not** a broker mutation.

Classify original response into explicit current-source missing/ambiguous,
noncommon, mismatched ticker, absent share class ID, duplicate class across
two SEC issuer jobs or a *single current symbol common-class candidate
without independently proved SEC CIK*. Unexpected responses, HTTP errors,
rate limits and broken time order fail closed. Retain only **counts**, original
cohort commitment, HTTPS provider and SEC/Nasdaq aggregate source hashes,
UTC clocks and zero-live declarations; never publish any FIGI/ticker/CIK,
other vendor rows, original SEC requester identity, raw account holdings
or orders. One protected push-to-main initial source acquisition after
credentialless CI; no added hourly watcher or trading key.

## Precise meaning of a positive result

Even a positive single-result `shareClassFIGI` is only independent
**present-day ticker-to-reference-instrument metadata**.
It does not link that instrument to the **same SEC filer** sufficiently
to use issuer-level `EntityCommonStockSharesOutstanding` as a class-specific
share-count denominator, nor prove market cap, fair valuation, bank credit,
historical as-of security listing, delisting-proceeds wealth, cashflow
alpha or tradability on the actual Alpaca account. Current ticker reuse,
IPO/merger, security-name changes, exchange MIC mismatch, local/ADR class,
rights and preferreds still require separately original-dated corroboration.

Existing [V8 SEC100 original issuer share source](../../fund100_v8_sec100_original_issuer_share_source_v1_0.py)
and [completed vendor price source](../../fund100_v8_sec100_completed_vendor_price_coverage_v1_0.py)
already exist; do NOT duplicate them. For historical cross-sectional return
research the real requirement remains timestamped active-and-delisted
security-master/class identity, class-specific shares, original returns,
corporate actions and benchmark/costed result. Previously evaluated paid
Sharadar bundle remains an **unacquired**, optional future source; this free
probe does not request its subscription.

## Strict unchanged funded boundary

No order, broker GET or POST, Alpaca credentials, live release, signed
private CAS, new principal authorization, user approvals, 6/20/35 HIGH
risk, $130.30 original pilot, $65 new BUY cap, 5% floor, original ACWI
economic NO_TRADE, operator STOP, or engaged broker kill switch changes.
Public source capture is not a LIVE security or trading whitelist.
