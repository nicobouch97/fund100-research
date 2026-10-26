# P4X — original 2017 SEC Form 25 index-event evidence (26 October 2026)

**Research only. Not a common-stock delisting census, historical security master, or trading strategy.**

## Why this is the next evidence step

P4T reconstructed 7,074 distinct issuer CIKs filing 2017 10-Ks, without
selecting only surviving current tickers. P4U/P4W reviewed 64 original
annual reports and their ticker/class hints. However, *today's absence from
a ticker registry is not evidence of delisting*, and neither issuer tickers
nor a 10-K cover establishes the security's complete return history.

The already captured four original SEC 2017 quarterly **master.idx**
sources also contain Forms 25, 25/A, 25-NSE and 25-NSE/A. Extract their
original filing-date/accession/CIK evidence, without downloading more data
or expanding the existing 64-report diagnostic sample. Preserve every
filing, including amendments, and cross-reference the CIK against the
original full-year 2017 10-K filer population. Record separately whether
the issuer's 10-K had **already been filed by the Form 25 filing date**;
a later 10-K cannot be presented as prior evidence.

## What can and cannot be inferred

- A Form 25 **index row** is evidence of a filing entry in the original
  SEC master index. It is **not** the underlying Form 25 document.
- The filing date is **not** the effective delisting date.
- Form 25 / 25-NSE can concern **debt, preferred, or other securities**,
  not necessarily an issuer's common stock. An exchange-filed Form 25-NSE
  and its amendments are separate index entries, **not independent exits**.
- Matching the CIK of a 2017 10-K filer does not identify the relevant
  share class, prove its delisting, or provide a corporate-action-adjusted
  terminal price. The issuer may continue trading another security.
- The full-year cohort join is **retrospective**. Only the separately
  marked earlier/same-day 10-K evidence can be treated as filed by the
  Form 25 date; neither measure creates a point-in-time investable universe.
- Today's ticker registry is not consulted in this index-event extraction.
  No performance, alpha, investment universe, or trading authority is inferred.

## Source contract and reproducibility

Reuse P4T's four raw original 2017 SEC master indexes, verified with
the existing original-quarter parser and SHA256. Fail closed on malformed
Form 25 rows, mismatched CIK/archive paths, out-of-quarter dates, unsafe
paths, or repeated accessions. Preserve an accession-level sorted JSONL
manifest and a source-hash-bound JSON report in the same read-only
P4T GitHub Actions artifact. Preserve P4T's original census schema and
all previous 10-K outputs unchanged.

Synthetic tests must verify date-aware CIK matching, amendments, exchange
filings, issuer-independent rows, duplicate/malformed rejection, registry
independence, hashes and captured output. Run the focused P4T workflow and
the full pytest + LIVE static audit v1.17/v1.18 on the exact PR head before
merge. Post-merge, inspect actual original-source counts and safety audit.

**Next blocker:** inspect original Form 25 document content and independently
resolve its *security class, exchange and effective date*; then obtain
delisting-inclusive corporate-action-adjusted total-return prices and
historically investable membership. Index-only evidence cannot validate
quality/value/momentum stock-selection alpha.

No broker network access, funded orders, private-state writes, holding
sales, risk-control edits, new LIVE universe or promotion. Preserve the
$130.30 pilot ceiling, operator STOP, ENGAGED environment kill switch and
all LIVE release locks.
