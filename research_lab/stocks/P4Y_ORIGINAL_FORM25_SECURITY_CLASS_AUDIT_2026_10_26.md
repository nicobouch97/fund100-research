# P4Y — original 2017 Form 25 document/class evidence (26 October 2026)

**Research only; no trading or delisting-inclusive return claims.**

## Problem corrected

P4X identified 1,624 original SEC Form 25-family index rows and 461
same-CIK 2017 10-K associations. Those are **filing-index associations**,
not 461 delisted issuers. Form 25 is issuer-filed; Form 25-NSE is
exchange-filed. The index CIK does not independently identify the
affected security, and an exchange-filed submission is not an
issuer-filed voluntary exit. The P4X report now separately counts both
filing families and their historical 10-K CIK overlaps, preserving the
original fields for compatibility.

## Original-source acquisition

P4Y adds a bounded **16-document** diagnostic to the already scheduled
P4T main-only original SEC research workflow, with no workflow YAML
changes. It preselects up to eight unamended issuer-filed `25` and
eight unamended exchange-filed `25-NSE` accessions from the original
2017 quarterly indexes using a fixed SHA256 ranking. The selection is
independent of the contemporary ticker registry and excludes amendments
from this *document sample* (amendments remain in the full P4X census).

For each selected accession, only its exact original SEC complete
submission text URL is requested, with a 3 MB ceiling, approved SEC
archive path, redirect/status rejection, and a configured SEC contact
User-Agent. The original SGML accession and submission type must agree
with the indexed accession. Original bytes, length and SHA256 are
preserved in the existing P4T research artifact.

The parser extracts only the original structured
`descriptionClassSecurity` XML element when exactly one short,
unambiguous instance is present. A plain common-stock description is
labelled **POSSIBLE_COMMON_EQUITY_REVIEW_ONLY**; mixed instruments,
warrants, notes, rights, preferred securities and ambiguous descriptions
cannot become common-stock exits. Missing/unavailable documents remain
explicitly unavailable or abstained, never silently classified.

## Interpretation and blockers

- Original source content may confirm a **security-class description**,
  not the historical ticker, exchange listing, issuer linkage, corporate
  action, or effective delisting date.
- The original filing date is not the effective delisting date.
- The fixed 16-document sample is not representative and its common-class
  fraction must not be extrapolated to the 1,624 filing index rows.
- The existing P4T 10-K census and P4U annual-report audit remain intact.
  Source failure in a P4Y sample does not invalidate independently
  verified 10-K census evidence.
- Before a historical stock backtest: verify security-level issuer,
  class, exchange, effective date, all delisting/merger outcomes, and
  independent total-return series including disappeared securities.
- No current tickers, broker requests, funded orders, private-state
  mutations, strategy promotion, capital changes or risk-control changes.

Original $130.30 LIVE ceiling, operator STOP, ENGAGED environment kill
switch and all release locks remain unchanged.

## P4Z — original issuer-filed cover captions (26 October 2026)

The first **post-merge P4Y** original-source artifact (run 40306356524)
verified all 16 source submissions, but the initial XML-only parser
abstained on **all eight issuer-filed Form 25** documents because they
used HTML or plain-text cover captions rather than
`descriptionClassSecurity` XML. The same source artifact had three
possible common-equity review candidates among eight exchange-filed
Form 25-NSE documents. This is a *source-format blind spot*, not evidence
that the eight issuer filings concerned no common shares.

P4Z now reads the exact primary issuer-filed `25` document and requires
**one address caption followed by one class-of-securities caption** before
accepting a short cover description. Original XML remains preferred when
present, and conflicting/multiple structured tags still abstain. The
exchange-filed `25-NSE` extraction is unchanged. Ordinary shares may be
possible common equity; fund/ETF beneficial interests are conservatively
excluded from corporate common-equity candidates. Source format is
recorded per recovered class.

No accession selection, original-source bytes, source hashes, security
identity assumptions, delisting effective dates, trading logic, risk
controls or broker capabilities change. The fixed sample remains
nonrepresentative; possible common equity is **not** proof of an
independently identified historical listed security or delisting.
Independent security-master, corporate-action and delisting-inclusive
total-return evidence remains the central backtest blocker.
