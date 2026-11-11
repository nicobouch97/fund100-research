# V9-F6 — annual diluted EPS source coverage for the original F5 SEC class candidates

**Registered 11 November 2026 — source pilot, NOT valuation / alpha / trading.**

## Source-grounded reason for this next action

The real [F5 main run 43021601200](https://github.com/nicobouch97/fund100-research/actions/runs/43021601200)
reconciled its *original, precommitted eight* issuer CIKs after an official
SEC Inline XBRL filing-index parsing fix: **three** exact same-issuer
own 10-K Section 12(b) plain-common ticker+venue review candidates,
**four** had no structured eligible class row, and **one** did not have a
recent annual 10-K inside the predeclared lag/age window. There were
no remaining SEC filing-index source failures.

This is a much better *current issuer/security candidate-source* base
than a ticker-only OpenFIGI lookup, but none of those three issuer
disclosures independently proves the permanent SEC CIK-to-OpenFIGI
relationship. It also does not establish a defensible dollar/share value.

## Narrow first original earnings question

For **exactly those three original 10-K class review candidates from the
same eight CIKs**, is an SEC original accession-matched full-year
`us-gaap:EarningsPerShareDiluted` fact available, as reported by the
issuer in the **same own 10-K**?

The main-only source checker:

1. Reuses the unchanged deterministic F4 first-eight CIK hash
   `caa63b8763c38ae04e911ed05f7baaba086722062b5ba0d134c0b0082c21d972`.
   Any source drift away from the original **three** class-review matches
   fails closed; no successful replacement issuer is selected.
2. Fetches same issuer official SEC submissions and exact primary
   index-verified 10-K for the same source census as F5, preserving
   same CIK, latest filed own 10-K fiscal end, conservative two-weekday
   as-of availability and capped 550-day age. Uses pre-existing SEC
   P4U modern iXBRL direct-primary parser and F5 single-row
   exact common class/ticker/exchange test.
3. Only for original exact class-reviewed three, fetches one additional
   bounded official `data.sec.gov/api/xbrl/companyfacts/CIK...json`
   document, under configured SEC Fair Access User-Agent. Uses existing
   P4B original source identity checks and unchanged **P4S accession-bound
   full-year diluted EPS** extraction (USD/share, same accession, same
   filing date, same fiscal year, exact own original 10-K).
4. Counts a **positive EPS**, **nonpositive EPS** and **unavailable or
   unqualified EPS** as distinct source categories. Missing, 404,
   conflicting EPS, wrong issuer/accession/period, missing issuer CIK
   and independently blocked source remain HOLD. No fallback to
   today's revised comparative filing, made-up EPS, zero substitution,
   adjusted prices or more convenient issuer.
5. Archives only UTC source receipt, the frozen eight-CIK commitment,
   aggregate status counts (denominator eight, no issuer rows),
   a single aggregate original-document SHA256 commitment and explicit
   FALSE valuations, alpha, legal CIK-to-FIGI and LIVE authorisation flags.
   No names, CIKs, tickers, exact original accession IDs, EPS values,
   prices, original filings, broker credentials, personal account or
   per-issuer disclosure leave the source process.

## Important economic and source constraints

- **Issuer-reported diluted EPS is NOT an exact listed share-class
  valuation.** Some SEC registrants have alternative classes, preferred
  securities, two-class EPS calculations or share-count structures that
  P4S does not independently certify for the FIGI candidate.
- **No stock price is obtained or compared in F6.** A positive annual
  diluted EPS is not a cheap stock. Price/market cap denominators, exact
  class-specific issued/float shares, class rights, splits, original
  corporate actions, expected future growth, analyst revision timestamps,
  liquidity, sector suitability, taxes and costs remain unverified.
- A 2026 retrieval of `companyfacts` is an official current SEC
  publication, not proof of when every item appeared historically or
  a survivor-free listed/delisted historical universe. Only an
  independently original same-10-K filing fact is accepted as source
  review.
- Real portfolio launch policy is separate. First ACWI SELL retains
  its independently prequalified **economic NO_TRADE** source admission;
  original $130.30 pilot, $65 new BUY maximum, HIGH 6/20/35,
  5% cash floor, standing signed capital/owner proofs, STOP,
  broker kill ENGAGED, writer HARD LOCKED and no broker POST remain
  unchanged. This one-shot feasibility source does not select or trade
  any stock.

After real result, review whether any source-positive EPS covers an
independent class-specific earnings/price bridge (reuse V8 SEC100 issuer
share and completed-price source, P4S split caveats). Do not initiate
a paid data subscription or a fresh strategy-family build merely
to generate a higher passing-test count.
