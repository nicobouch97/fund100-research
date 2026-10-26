# P4W — indexed primary 10-K / original XBRL class crosscheck

**26 October 2026 — offline historical source research; no trading authority.**

## Research objective

P4V recovered 28 separately indexed original 2017 EX-101.INS exhibits from
oversized submissions and found 11 unambiguous issuer-level ticker hints.
Previously the same-filing class crosscheck examined only complete
submissions, leaving recovered primary-only XBRL and structured 12(b)
common-share rows unassociated.

P4W reuses the existing conservative class/ticker crosscheck **only after**
the original primary 10-K and original EX-101.INS were independently
captured from canonical links in the **same verified SEC accession index**.
The output is a separate `indexed_primary_ticker_class_*` research category.
It preserves all prior `same_filing_*` and `original_xbrl_*` counters and
keeps the existing V5 JSON schema backward-compatible through additive fields.

A review candidate requires exactly one structured common-share/recognised
exchange row, exactly one valid original XBRL issuer ticker, original
primary/index/XBRL SHA-256 provenance, and no disagreement with an explicit
ticker in the 10-K row. Conflicting symbols, missing/invalid source hashes,
unavailable XBRL, ambiguous classes and absent rows all abstain. Each
candidate records its three original-source hashes, an evidence-level label
distinguishing indexed documents from full submissions, and whether an
explicit class symbol agreed. A missing explicit class symbol stays null
in the original row; an issuer ticker is **not** filled into it.

The sample remains 64 deterministically selected original 2017 filings
stratified by **current** registry membership. Neither a review association
nor the number of observations establishes historical exchange listing,
share-class identity, investability, delisting, corporate actions,
total-return prices or alpha. Do not use these hints as an investable
universe or trading signal.

## Evidence and follow-up

The existing P4T main-only SEC source workflow can capture the original
documents and report observed new associations. Offline regression covers
concordance, disagreement, multiple/absent classes, invalid/missing XBRL
and provenance, no mixing with complete submissions, and preservation of
source hashes. No numerical outcome is presumed before source CI runs.

The next genuinely investment-relevant blocker is **independent historical
security-master/listing verification and delisting-inclusive total-return
prices**, not further expansion of issuer ticker hints. After those sources
are acquired, test stock selection out-of-sample against investable controls
and multiple cost scenarios.

Original USD 130.30 LIVE capital ceiling, operator STOP, ENGAGED kill
switch and all release locks are unchanged. No funded orders, holdings
sales, private-state mutation, or broker credentials are involved.
