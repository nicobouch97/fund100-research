# V9-F7: completed vendor-price source coverage for the exact first three SEC earning-review issuers

**Registered 11 November 2026. Strictly non-executable, no buy/sell suggestion.**

## Real source motivation

The actual protected main-only SEC original own-10K [V9-F6 run
43026350533](https://github.com/nicobouch97/fund100-research/actions/runs/43026350533)
completed successfully on 11 November 2026 13:08 UTC. It returned
**3/3** same-own-10-K issuer-declared common class review candidates
with positive source-provenance `us-gaap:EarningsPerShareDiluted`, plus
**4** issuers lacking structured 12(b) common rows and **1** without
an eligible 550-day recent own original 10-K. The first eight original
CIK sample is committed as
`caa63b8763c38ae04e911ed05f7baaba086722062b5ba0d134c0b0082c21d972`.
F6 additionally committed the precise three CIK identity subset as
`a2fe180b71fc46d818c015f76bc608f9bc59c72ab7c92caab7cfe17581b75a59`.

This supports testing the next narrow source feasibility question:
does the existing public Yahoo/yfinance research provider have a
**complete last 21 earlier finished XNYS-session unadjusted close,
adjusted close and exchange-volume series** for those same original
three precommitted issuer candidates, *before* considering market
capitalisation, a margin of safety, future expectations or any BUY?

## Exact scope

1. Reuse unchanged current official Nasdaq and SEC symbol/venue/CIK
   sources, original F5 same-issuer filing-index-verified 10-K 12(b)
   parser, original **eight-CIK cohort fingerprint**, and exact **three-CIK
   current 10-K class-reviewed subset fingerprint** from F6. Abort
   and publish no source result if those predeclared identities drift.
   Do not substitute a ticker or an issuer to get a more attractive
   close, original EPS or liquidity.
2. Reuse V8 SEC100's existing public price-source normalization code
   (`fund100_v8_sec100_completed_vendor_price_coverage_v1_0._download`).
   This is a single public vendor capture, **not** an exchange,
   brokerage order quote, time-of-trade midpoint or independently
   verified exchange trade tape. The provider may retrospectively
   revise corporate-action adjustments.
3. For each fixed candidate, count complete coverage only when there
   is one original prior completed-session research price row for
   **each of the 21 latest XNYS sessions strictly before the UTC
   source-acquisition date**, with canonical day ordering, finite
   positive unadjusted and adjusted close and bounded share volume.
   No same-day partially completed NYSE close is eligible. Missing
   any source day or invalid/zero last-day volume is HOLD; do not
   fill missing rows or infer intraday execution.
4. Publish only a full-eight issuer denominator, exact first 3-subset
   SHA256, SEC source-document hash, vendor snapshot SHA256, UTC
   receipt, fixed provider name, original source status counts and
   explicit **no legal CIK→FIGI link / no class-specific EPS, price
   entitlement / no price×class share market-cap validation / no alpha
   / no BUY** flags. Not a public 3-ticker watchlist: no CIK, issuer
   names, tickers, EPS numeric values, actual price, volume,
   class identifiers, filers, shareholder records or account data
   leave the source process; suppress library diagnostics.
5. Keep the current separate real-account market-open
   **14:39 UK read-only eight-GET** source, authentic broker clock,
   original LIVE STOP/engaged kill, first ACWI NO_TRADE economic
   preclaim, and all signed original state and capital gates
   unaffected. The F7 workflow contains **zero broker GET/POST,
   funded or private-state mutation**.

## Interpretation and next decision

Positive vendor coverage would mean only that a current ticker
associated by issuer's original 10-K appears in a public vendor's
completed *historical research price* feed for 21 sessions. It would
not independently certify which exchange instrument or share class
the provider priced, or the current ticker→FIGI→SEC CIK legal relationship.
Historical GAAP diluted EPS can be issuer- or capital-structure-specific:
do not divide it by a vendor price and call the result a reliably
class-specific P/E, earnings yield, intrinsic value, or expected alpha
until independent issuer class rights, corporate actions, reporting
share denominator, split adjustments, trade eligibility and
as-of timestamp/price provenance are checked. This does not
purchase historical survivorship-free licensing, and does not
start long-horizon forward waiting.

The original owner $130.30 pilot, $65 new BUY order ceiling, HIGH
6/20/35, 5% cash floor, signed funding attribution, STOP,
broker KILL ENGAGED, economic NO_TRADE and all writer HARD LOCKED
remain unchanged.
