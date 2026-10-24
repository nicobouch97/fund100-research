# Fund-100 P4Q — original-accession annual quality stability

**Scope:** Existing 16-issuer official SEC acquisition; only the 12 issuers
with source-matched industrial annual diagnostics are compared. The other
four issuer-specific bank/sector diagnostics remain separate.

## Research question

Do the 0–3 descriptive annual accounting scores change substantially
between **adjacent** eligible original 10-K filing events? High churn
would make an eventual quality screen sensitive to filing timing and
potentially expensive to rotate; stable scores could be less costly but
do not imply predictive stock returns.

## Measurement contract

- Reuse the original verified SEC raw-file hashes, ticker/CIK identity,
  same-accession current/comparative accounting and conservative
  two-weekday filing lag from P4Q. No new market-data or broker access.
- Count score observations in buckets 0/1/2/3.
- For each issuer, compare **only adjacent original annual events**
  when *both* scores exist. A missing middle year breaks the pair;
  never bridge or forward-fill a missing score.
- Count score increases, decreases, unchanged values and transitions
  across the **illustrative** score >=2 boundary, including
  score>=2 persistence. This boundary is **not** an approved trade rule.
- Reconcile pair counts against annual filing-event counts, and
  scored observations against the source replay. Preserve all
  existing no-order and no-alpha fields.

## Interpretation and limitations

The initial 24 October 2026 source acquisition reconstructed 64
descriptive annual scores. The new adjacent-pair statistics reveal
how many of those observations form directly comparable consecutive
annual filing pairs; do **not** treat 64 observations as 64
independent companies, market periods, or strategy returns.

SEC CompanyFacts is retrieved **today** and the issuer roster was
chosen with 2026 knowledge. The history is not a contemporaneously
archived, survivorship-safe investment database. Fiscal calendars,
tag comparability, sector differences, valuation, analyst revisions,
corporate actions, delistings and realistic implementation costs
are not established. Score persistence is not return predictiveness.

A subsequent investment-research stage should join causally eligible
fundamentals to historical prices and original issuer membership
with an independent holdout, then evaluate predeclared strategies
against costed passive comparators. No trading promotion follows
from this descriptive diagnostic.

**Safety:** Original USD130.30 LIVE capital ceiling, operator STOP,
environment kill switch, LIVE release locks and protected risk
controls remain untouched. No funded orders, broker requests,
holdings sales or private-state writes.
