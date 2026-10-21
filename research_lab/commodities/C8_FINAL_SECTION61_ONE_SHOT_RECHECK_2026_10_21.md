# C8 — one authentic final-source WTI bulletin recheck, 21 October 2026

**Pre-registered BEFORE this PR's public-source workflow runs. Research-only. No broker, paid market-data, or orders.**

## Why now

The original 17 October source test [39039186006](https://github.com/nicobouch97/fund100-research/actions/runs/39039186006) retrieved a real CME Section 61 energy PDF for 16 October, but its printed status was PRELIMINARY. The strict C7/C8 parser correctly refused any settlement-derived output. This rejection remains part of the evidence and is NOT a reason to loosen parsing.

The official [CME daily bulletin page](https://www.cmegroup.com/market-data/daily-bulletin.html) publishes delayed preliminary and next-business-day FINAL issues. CME's [Settlement Data FAQ](https://www.cmegroup.com/articles/faqs/access-to-cme-group-settlement-data-faq.html) says bulletin/website settlements become publicly available, while earlier channels or other datasets may require licensing. The official [DataMine API documentation](https://www.cmegroup.com/datamine/datamine-api.html) describes credentialed access; no DataMine entitlement is inferred.

## Authorised exact experiment

The existing unchanged `.github/workflows/fund100-c8-cme-source-status.yml` fires once on this C8 protocol PR and exercises the original C7/C8 tests plus **one bounded official HTTP GET** of `https://www.cmegroup.com/daily_bulletin/current/Section61_Energy_Futures_Products.pdf`. No repeated poll/schedule, no custom hostname, no terms bypass and no paid access.

A valid source must declare the official CME dated **FINAL** issue, be at most 14 days old, contain physical-delivery NYMEX CL contracts with at least 12 unique consecutive deliveries, and reconcile the printed `TOTAL CL FUT` open interest. Only a valid FINAL source can become a **single dated cross-section**. A PRELIMINARY, stale, unreadable, or misparsed issue will retain truthful rejection metadata without vendor contract prices or original PDF redistribution.

If accepted, record the original document date, SHA256, source status, first two CL contract month identifiers, their settlement difference and provenance within the workflow's original protected 90-day artifact. This is only a single *price level / term-structure* snapshot. **Do not** interpret positive or negative spread as an earned roll return or available trading edge.

## Why this is NOT a futures trading plan

- CME historical futures carry requires at least two original dated FINAL strips, real expiry/roll mechanics and contract P&L accounting, not a single cross-section.
- Our capital ceiling is only **$130.30**. Existing C9 evidence identifies even micro WTI futures as requiring considerably more broker margin and derivatives are excluded by the current LIVE policy.
- Commodity ETF symbols (GLD, USO, DBC) are not direct reproductions of the futures term structure; their historical adjusted NAV can include underlying roll, fund costs and tracking errors.
- If the fetched source is rejected, preserve that failure and move on; do not choose substitute dates or fabricate price curves.

**No change** to the original V6-S1 proposed 95% entry target, fund risk tier HIGH, stop switch, current original LIVE holdings, broker asset permissions, or private ledger. The experiment adds no executable strategy or automated API scraping schedule.
