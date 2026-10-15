# Phase 4C–4D — real eight-company SEC quality coverage review

**Date:** 15 October 2026. **Status:** genuine public SEC source
audit, with ZERO individual-stock trading permission.

## Eight original issuer source records captured successfully

The [P4C real SEC GitHub run 38756477914](https://github.com/nicobouch97/fund100-research/actions/runs/38756477914)
captured all **16 original SEC JSON source files** for the eight
frozen 2026 contemporary research issuers. It completed
**2026-10-15T15:01:45Z**, and separately verified every source
file's exact SHA256, original SEC URL/CIK, annual accession,
reporting-period information and source-recomputed P4A score
against the independent audit.

- Raw SEC artifact:
  `fund100-phase4b-real-sec-snapshot-38756477914`
  (GitHub artifact ID **11983422763**; 90-day retention).
- Independent quality coverage artifact:
  `fund100-phase4c-sec-coverage-validated-38756477914`
  (artifact ID **11983907325**; 90-day retention).
- Original capture manifest SHA256:
  `bafc7a084a6d4deaf7c7b7a5e982d52a8b5ecd6fe1b70a0ebaf3e64a610b1e18`.
- Independent next prospective ledger *candidate* SHA256:
  `251026efd810c814bb56d80092f6ea42aa0e87bd764ad288e0fff22d61bb6324`.
  A candidate record is NOT an automatic append to a mutable
  GitHub file; existing first real two-company record is untouched.
- CI premerge FULL LIVE test suite: **886** passing tests and
  **36** passed LIVE audit checks.

## Observed complete-source vs usable-quality gap

| 2026 frozen issuer | Original SEC JSON obtained | Original fixed P4A score | What still blocks or limits annual quality |
|---|---|---|---|
| AAPL | Yes | **3/3** | No missing latest-year fixed tags |
| MSFT | Yes | **3/3** | No missing latest-year fixed tags |
| GOOGL | Yes | **Unavailable** | Latest 2025 original 10-K lacks an eligible row for the model's exact RevenueFromContractWithCustomerExcludingAssessedTax concept; old P4A reported stale last *complete* annual packet |
| AMZN | Yes | **Unavailable** | Latest original full-year 10-K has no eligible exact PaymentsToAcquirePropertyPlantAndEquipment capex fact |
| XOM | Yes | **Unavailable** | Latest original full-year revenue tag not matched; fixed OperatingIncomeLoss concept absent from collected US-GAAP dictionary |
| JNJ | Yes | **Unavailable** | OperatingIncomeLoss exists as a concept in archive but not in its newest original full-year 10-K records |
| PG | Yes | **Unavailable** | Fixed revenue concept absent; Revenue/SalesRevenueNet appear as different historic taxonomy concepts |
| KO | Yes | **Unavailable** | Fixed revenue concept absent; other revenue concepts exist but have not been evaluated as interchangeable |

These are factual **source-contract coverage gaps**, not
unprofitable companies, negative EPS revisions or zero earnings.
Do not treat missing fields as zero-valued company fundamentals.

## P4D improvement: latest-source gate without rewriting history

The P4A original engine uses the last two complete fixed-tag
10-K packets. It can skip the most recently filed incomplete
10-K and accidentally describe older complete financials as
the *latest*. In the real Google source, this appeared as
`LAST_ANNUAL_REPORT_TOO_STALE` because 2025 annual revenue
did not match our frozen tag while an older original packet did.

To avoid silently masking that problem for prospective
research, Phase 4D adds a SEPARATE versioned diagnostic:
compare the P4A source-linked accession to the latest
**actually filed, conservatively available** original 10-K
from SEC submissions; if they disagree, or any required
original annual source fact is missing, record
`LATEST_10K_NOT_ELIGIBLE_FOR_FROZEN_SCORE` with the missing
concept names. It does not substitute historical alternate
GAAP tags, alter past captured P4A scores, refit the original
0–3 model, or generate orders.

Potential replacement concept *names* such as `Revenues`,
`SalesRevenueNet` or `PropertyPlantAndEquipmentAdditions`
are listed only as **candidates for future accounting review**,
NOT identical-by-definition measurements. For an energy
producer, health-care conglomerate or online retailer,
accounting treatment and SEC taxonomy can be materially
different. Any future audited and timestamped equivalence
map must be preregistered separately and checked
prospectively; don't adjust this one to force 8/8 scores.

The repository's
`research_lab/stocks/prospective/p4b_actual_sec_2026_10_15.json`
is the immutable initial two-company first-capture anchor,
**not a live trading whitelist**.

No stock prices, delisted company universe, historical
survivorship-free risk comparison, analyst EPS estimate
revision feed, historical alpha or individual stock PAPER
have been validated. The original 14 US equity ETF LIVE
whitelist, HIGH risk, $130.30 ceiling, operator STOPPED and
kill switch ENGAGED remain unchanged.

## Next

Identify actual tagged SEC financial statement concepts
for each sector, document which are or are not economically
comparable, then *freeze a new P4E quality source contract
prospectively*. In parallel obtain an independent
publication-dated analyst EPS consensus/revision source
and delisting-safe historical security master before
claiming performance. The SEC source only supports
**reported** accounting metrics, not analyst EPS revisions.
