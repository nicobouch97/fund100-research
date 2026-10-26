# P4V — original 2017 XBRL evidence from index-verified primary-only filings

**26 October 2026. Research only. No historical investable security or return claim.**

## Investment-research problem

P4U's bounded 64-filing original 2017 SEC audit sometimes cannot retrieve the
complete submission because the source exceeds 12 MB. It then verifies and
captures the primary 10-K through the original filing-detail index, but marks
the original EX-101.INS issuer ticker as *not evaluated*. This discards a
potentially valuable source of filing-vintage identity evidence even where
the SEC filing-detail index names a separately retrievable XBRL instance.

## P4V source rule

For an index-verified primary 10-K fallback only, locate **exactly one**
original EX-101.INS XML row in the **same original SEC filing-detail index**.
Accept only a safe XML basename and the exact canonical same-accession link.
Fetch at most 12 MB, reject redirected/non-200/oversized/empty sources, and
record the exact original XML bytes, SHA-256, URL, filename and capture state.
Reuse the original conservative issuer-level TradingSymbol parser.

A missing, ambiguous, blocked or conflicting exhibit **abstains**. Failure
to retrieve XBRL does not discard a separately verified primary 10-K.
Keep the primary-only original submission's `original_xbrl_ticker_state`
unchanged at `NOT_EVALUATED_PRIMARY_10K_ONLY`; P4V records separately
named `primary_xbrl_*` fields and aggregate
`index_verified_primary_xbrl_*` counters. Existing original-submission
ticker and same-submission class-association counts retain their prior
meaning and the existing research workflow assertions remain valid.

## Evidence and limitations

P4V expands the possible historical **issuer ticker hints**, not a verified
security master. An XBRL issuer ticker may not identify a particular common
share class or prove an exchange listing. The original 2017 filing sample
is diagnostic and stratified using today's registry; it is not an
independent historical listing or delisting census. No historical
total-return, corporate-action, tradability or alpha inference is allowed.

Offline regression covers same-accession validation, missing/duplicate
exhibits, unsafe links, redirected or oversized HTTP responses, original
byte/hash preservation, and abstention when XBRL is unavailable. The
main-only original SEC workflow can report any genuinely recovered
P4V observations after merge; no outcome count is pre-assumed.

The USD 130.30 LIVE capital ceiling, operator STOP, ENGAGED environment
kill switch and every LIVE release lock remain unchanged. No broker access,
funded orders, holdings sales, risk-control modifications or private-state
writes are part of this work.
