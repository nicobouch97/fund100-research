# C3F — Verified issuer publishing trail for commodity futures selection

**15 October 2026.** Fund-100 Phase 3. Source discovery complete; **document
content acquisition and contract extraction NOT complete**. Research only,
no PAPER or LIVE approvals, no futures strategy backtest.

## Why this matters

Our C3C–C3E research transcribed actual quarter-end DBC open futures
positions from SEC 10-Q/10-K reports but those arrive many weeks after
the quarter. We need independently dated disclosures for **index
contract selection and weights**, not retrospective assumptions about
daily rolls.

Deutsche Bank's official DBIQ web index page:
https://index.db.com/dbiq-web/indices/95400
identifies the **DBIQ Optimum Yield Diversified Commodity Index Excess
Return**, official Bloomberg identifier **DBLCDBCE**, and lists:

- `DBIQ Optimum Yield Diversified Commodity Index Guide 2025.pdf`
- `Diversified Commodity Index Weights for November 2025.pdf`

Its official issuer [publications catalogue](https://dbindex.db.com/dbiq-web/publications)
also lists the **'DBIQ Optimum Yield indices Selection Report'**
each month, dated November 2025 through October 2026 (12 issue
records). Deutsche Bank's single-commodity indices likewise link
to those monthly reports; *that alone does not demonstrate the PDF
selects the same futures maturities or weights actually held by
DBC*. We need PDF review and a mapping to DBLCDBCE.

**This is new evidence that official monthly selection-report documents
exist. It is NOT evidence that we downloaded their contents or that
actual daily DBC rolls can already be reconstructed.** The accessible
issuer page is a JavaScript web app, and the public search text only
provided publication metadata, not direct verifiable PDF bytes/URL.
No unauthorized scraper, market-data credential or source forgery was used.

## Official catalogued publication dates

Below are the site-listed **dates and clock text** (the catalogue does
not disclose the displayed clock's timezone in search results; do
not convert it to UTC or assume before/after the US close):

| Report month | Site-listed issue date | Site-listed clock |
|---|---|---|
| Nov 2025 | 2025-11-03 | 18:52 |
| Dec 2025 | 2025-12-01 | 18:59 |
| Jan 2026 | 2026-01-02 | 17:02 |
| Feb 2026 | 2026-02-02 | 17:11 |
| Mar 2026 | 2026-03-02 | 17:07 |
| Apr 2026 | 2026-04-01 | 17:21 |
| May 2026 | 2026-05-01 | 16:24 |
| Jun 2026 | 2026-06-01 | 17:01 |
| Jul 2026 | 2026-07-01 | 16:57 |
| Aug 2026 | 2026-08-03 | 17:03 |
| Sep 2026 | 2026-09-01 | 16:57 |
| Oct 2026 | 2026-10-01 | 17:48 |

Source-linked dataset:
`research_lab/commodities/dbiq_official_selection_report_registry_2025_2026.csv`.

To reduce timestamp look-ahead risk, the research catalogue assigns
the **second subsequent weekday** as a conservative earliest
candidate *calendar* date for source visibility. This is NOT
exchange-holiday-calibrated or independent source publication-time
verification. It is not yet a trading-decision availability
certificate. Actual PDF publication timestamps/timezones and
market hours need independent verification before making signals.

Official issuer context: [DBIQ index page](https://index.db.com/dbiq-web/indices/95400),
[DBIQ publications](https://dbindex.db.com/dbiq-web/publications),
[Deutsche Bank index notice, 2025-04-15](https://index.db.com/dbiq-web/indices/97353),
[Invesco issuer/SEC index reform 2025-11-10](https://www.sec.gov/Archives/edgar/data/1328237/000119312525273297/d70758d8ka.htm).

## What the issuer announced about selection

April 2025 issuer notice stated that for November 2025:
commodity eligibility gets annual review, liquidity and production
weights become formula-driven, per-sector and commodity concentration
caps apply, intra-year rebalance controls are introduced, and the
index moves to **Modified Optimum Yield** contract selection.
The listed methodology guide is the authoritative next document for
precise eligible tenors, liquidity screens, contract rolls, selection
date, weighting, holiday exceptions, and implementation details.

Crucially, **index selected expiry ≠ actual DBC fund position ≠
future rolling P&L**. Historical SEC holdings are separate,
sparse observations. Current index webpage constituent weights can
change and cannot be used as historical weights at another date.

## Source intake and promotion gate

The offline `fund100_dbiq_publication_registry_c3f_v1_0.py`
provides:
- exact 12-month source list/issue date/title/provenance validation;
- earliest conservative visible-catalogue date, rejecting premature
  historic source access;
- SHA256 and provenance contract for any *legitimately acquired*
  original PDF (document month, title, issuer URL, direct HTTPS
  source URL, genuine acquisition UTC, permission to store/analyse);
- **no falsely extracted contracts**, contract expiry data, PDF
  text, daily issuer weights, eligible investment strategy or
  brokerage orders.

Once actual original PDFs are available through an authorized
export, retain their SHA256 and issuer path, review each PDF
(and visually inspect tables), record full date/time precision and
publisher timezone, and compare selected months and weights against
DBC issuer filings and the old/new index methodology.

**Before a carry-based C3 strategy:** require expiry-identified
historical settlement curves at the appropriate as-of time,
actual commodity index basket weights and release-dated contract
selection results, market trading frictions, collateral returns,
and documented paper reproducibility. The existing C1/C2/static
commodity forward scorecard remains unchanged, with no promotion.

The Fund-100 equity ETF V5 PAPER runner is still the only active
execution strategy; original 14-US-ETF LIVE whitelist, HIGH risk,
$130.30 pilot ceiling, operator STOPPED and ENGAGED kill switch
are unchanged.
