# C7: original CME Section 61 daily futures settlement bulletin intake

**Preregistered 17 October 2026. Research-source acquisition only.**

## Why this advances the Fund-100 commodity bottleneck

US EIA RCLC1 etc WTI futures prices ceased April 2024. CFTC C5
genuinely sourced managed-money positioning for October 2026 but
does not provide contract expiry settlement prices. The C6
positioning + ETF price strategy failed its 2026 cost test.

CME **Daily Bulletin Section 61, Energy Futures Products** contains
individual **CL NYMEX CRUDE OIL (PHYSICAL)** expiry-named contract
month settlement prices, volume and open interest. Original link:
https://www.cmegroup.com/market-data/daily-bulletin.html
Rotating Section 61 PDF:
https://www.cmegroup.com/daily_bulletin/current/Section61_Energy_Futures_Products.pdf

## Critical original-source admission requirements

1. Rotating public PDF URL is **not** an immutable record. Web
   inspection of this same URL returned discrepant captures:
   a 16 October 2026 *PRELIMINARY* text extraction versus an
   8 October 2026 *FINAL* PDF screenshot. CDN/cached versions can
   differ. Independently store original PDF bytes + SHA256,
   direct extraction from THOSE same bytes, acquisition UTC, and
   the document's actual printed dated status; never infer its
   date from URL, web search or filename.
2. Reject anything PRELIMINARY, future-dated, impossibly stale,
   duplicate contract months, missing settlement, price/volume/OI
   errors, source block ambiguities or failed CL total open-interest
   reconciliation. Reject a source without the literal physical
   NYMEX CL product identity and an exact FINAL marker. One GET
   only; bounded original PDF and no broker credentials.
3. At least 12 unique named CL delivery months, positive finite
   USD/barrel settlements and non-negative open interest.
   Require a valid first two consecutive month contracts to
   compute a descriptive nearby spread; do not relabel missing
   contracts as near month. Validate full CL OI total equals
   the bulletin's published total if no missing contract rows.
4. Bulletin settlement prices can be nominal marks in thin
   far expiries and do not establish *executable fill prices*.
   The actual third party pages may supply discussion, but
   ORIGINAL exchange PDF is required for admission.
5. Mark publication UTC as NOT independently verified (CME page
   indicates preliminary after midnight Central and final later).
   The date in a PDF is trade date, not publication time.
6. Do not invent contract LAST TRADE / expiration dates merely
   to satisfy the existing stricter C3B intake. Named delivery
   months are a step toward futures curve structure, not a
   completed C3B source, DBC index, authenticated roll or
   traded returns.
7. No historical alpha/backtest from ONE cross-sectional snapshot.
   The next viable economic test needs multiple actual final dated
   snapshots, instrument-specific expiry/roll rules, tradability,
   fees and original market-source timestamps.

## Rights and microcapital costs

CME's public website offers delayed/reference final settlements,
but licence, website terms, redistribution and automated reuse
remain subject to CME's rights. One manual Github source probe;
NO automated repeated scraping, and no paid CME DataMine order.
CME official documentation:
https://www.cmegroup.com/articles/faqs/access-to-cme-group-settlement-data-faq.html
https://www.cmegroup.com/market-data/cme-group-continuous-price-series.html
https://dataservices.cmegroup.com/pages/fo-api-websites

CME delayed OAuth API requires entitlement, and deep dated
history on DataMine may have licence fees that are unjustifiable
relative to the current USD 130.30 pilot budget.

## Operator/broker boundary

Research only; no futures, margin, leverage, Alpaca GET or POST,
or trading permits. Four existing V5 ETFs have **not** been sold;
operator STOPPED and broker kill switch ENGAGED. Selected risk
HIGH, authorised USD130.30 ceiling and existing 14 ETF-only
LIVE whitelist are unchanged.
