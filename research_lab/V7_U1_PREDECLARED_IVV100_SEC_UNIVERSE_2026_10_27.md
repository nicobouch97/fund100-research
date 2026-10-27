# V7 U1 — One genuinely prospective broader US listed-issuer surveillance sample

**Registered 27 October 2026 before original U1 source acquisition.**
The goal is to increase *future sample coverage* of an investment thesis,
not improve a historical backtest by adding future survivors.

## Exact independent issuer sources and pre-fixed roster design

- Official BlackRock iShares **IVV** S&P 500 ETF current issuer/holdings
  public CSV:
  https://www.ishares.com/us/products/239726/ishares-core-sp-500-etf/1467271812596.ajax?fileType=csv&fileName=IVV_holdings&dataType=fund
- Original US SEC official EDGAR company ticker + CIK mapping:
  https://www.sec.gov/files/company_tickers.json
  (the SEC warns its ticker/CIK association files are periodically
  updated and not guaranteed complete; they are **not** proof
  of a currently tradable common-share class).
- Both sources acquired during the SAME source-run after original
  registration; record actual UTC acquisition, IVV provider as-of
  date (must not be future or older than seven calendar days),
  and original SHA256 of both exact source byte strings.
- Require IVV source reports at least **400 equities**, roughly
  95–102% of fund weight across equity rows, original provider
  date/columns/asset-class/weight. Exclude cash, futures, non-equity
  rows and any ticker absent from SEC original mapping.
- Rank solely by **original provider's reported fund weight**
  descending (ticker alphabetical for ties), then choose first
  **100 distinct SEC CIK issuers** whose symbol matches original
  SEC ticker map. Multiple share classes from same issuer never
  count as two independent company observations. Do not replace
  absent issuer data with a guess or a later convenience sample.
- Preserve original raw source as 90-day research-only Actions
  artifact along with the derived SHA/roster, for source replay.
  The first successful completed main-branch original roster
  serves as *the only* future event-registration authority; do
  not roll IVV membership with market winners.
  Raw fund holdings are provider information, not Fund-100-generated
  public domain data; no redistribution or retail investment advice.

## Separate from existing 24-company experiment

The original M1 24-company portfolio, originally selected and
captured on 26 October, is a distinct one-selection 21-session
prospective investment test. Its original 27 October entry, exit,
SPY and sector controls, and Yahoo source-vintage pinning DO NOT
change. The new IVV/SEC 100-issuer cohort is a different
**surveillance population** for future SEC earnings and
possibly other events. It cannot be used to retrofit prior
earnings-event studies or to claim that 2017/2020 historical
companies had been known/tradable at that time.

Once U1 authentic 100-name original sources are captured, the next
substantive step is a **single bounded original SEC first-receipt
calendar for these 100 CIKs** (filing accession, SEC original
source capture, no backdated release). Only earnings filings first
received AFTER the original U1 capture could enter prospectively
dated measurements. Later real post-observation market marks must
be costed and compared against passive SPY and sector-matched
controls with enough independent events to support inference.
An earnings report is NOT a predictable return forecast.

## Current fund authority

2026 IVV fund membership selected today carries all known
contemporary-index bias; cannot establish long historical
survivorship-safe alpha or actual broker instrument eligibility.
The existing original LIVE trial ceiling is **USD 130.30**,
HIGH profile, original ACWI/EEM/XLE/XLV positions, and both
operator STOP and environment kill remain engaged. U1 creates
**zero broker GET/POST/orders** and no activation, rebalance,
new capital, share purchase or financial forecast.
