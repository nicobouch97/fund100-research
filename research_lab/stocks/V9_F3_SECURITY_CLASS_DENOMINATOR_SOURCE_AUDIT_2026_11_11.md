# V9-F3 — current issuer-vs-traded-share-class denominator audit (11 Nov 2026)

**RESEARCH ONLY. No price, valuation, stock buy, broker or original ACWI exit authorisation.**

## Source boundary and purpose

The existing protected three-source acquisition uses original official Nasdaq Trader
`nasdaqlisted.txt` and `otherlisted.txt` plus original SEC
`company_tickers_exchange.json`, sourced within one short-lived main-only run.
The publication receipt includes source timestamps and SHA-256 fingerprints.
The SEC CIK is a **filer/issuer** identity, not a particular traded equity
class, unique economic share count, historical stock symbol, or legal proof
of an eligible U.S. common share. Nasdaq security-name wording is only a
review hint, as the official field definitions allow security type and class
information inside the name, not a machine-certified universal security master.

This increment reuses those **same three already-authenticated source reads**
without any broker or added market-data GET. It produces **mutually exclusive
counts across distinct SEC CIKs with an exact present-day ticker+venue match**:

1. Multiple SEC mapped ticker+venue associations or multiple exact matched
   current listing symbols: quarantine issuer for any single-class denominator,
   even if one ticker's listing name says `Common Stock`.
2. Only one association and exact matched name with explicit common/ordinary
   wording: **research candidate only**, never verified class eligibility.
3. Only one association and name with explicit alternative-security wording:
   quarantine (including preferred, ADR/ADS, units or warrant-like instruments).
4. Only one association and name without explicit class wording: quarantine.

Only aggregate issuer counts and constant false capability declarations leave
the process. No CIK, issuer name, ticker, raw SEC value, class count by issuer,
market cap, quote, stock rank or securities order is exported.

## Required to compute a genuine value signal

Before any model compares economic market valuation to original filed earnings,
cash flow or equity, independently prove:

- **Identity:** exact independently sourced security identifier (ideally a
  class-specific permanent identifier) and tradable venue/share-class mapping,
  ticker changes, ADR ratios, splits, multiple classes and corporate events.
  These current association counts **do not** establish those facts.
- **Denominator:** original effective-dated *class-specific* free/issued and
  outstanding shares as appropriate to the chosen numerator/valuation theory.
  Do not use a generic issuer-level SEC `EntityCommonStockSharesOutstanding`
  fact as if it were always a particular publicly traded class.
- **Price:** independent, actually available source for as-of executable close
  or tradable quote, price units and currency, session clock, security identity,
  split/corporate-action adjustments, stale/absent quotes and realistic costs.
  A recently retrieved revised historical chart is **not** proof of original
  market-time vintage.
- **Backtest:** original point-in-time filed financials, current and delisted
  eligible historical shares, audited corporate-action history, exposure and
  fair cost/turnover comparison vs retaining ACWI and exposure-matched SPY,
  using prior-registered tests and including all rejected/no-signal cases.

No open/paid historical security master or price provider with source-consistent
class-specific original vintages has yet been independently validated for
this project. Until it exists, a missing share-class denominator is
`UNAVAILABLE`, **not cheap, expensive or uninvestable by performance**.

## Release/operational constraints

This only adds aggregate original **current** issuer-to-listed-symbol source
status to the existing recurring public, main-only V9 capture, using no extra
HTTP requests. It changes no original 32-CIK precommitted sample, original
financial diagnostics, sampled outcomes, account permissions, $130.30 pilot,
$65 new BUY ceiling, HIGH 6/20/35 risk controls, operator STOP, engaged broker
kill, signed private owner claim, original ACWI economic NO_TRADE gate or
broker writer locks. No manual per-order approval is introduced.
