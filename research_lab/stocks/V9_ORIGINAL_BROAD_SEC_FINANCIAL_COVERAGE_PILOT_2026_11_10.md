# V9 — original broad SEC financial-source availability pilot

**Registered 10 November 2026. Research-only original SEC acquisition, NO
broker, NO current legal security master, NO retrospective alpha claim.**

## Preexisting genuine evidence

The 14:03 UTC 10 November Nasdaq/SEC three-source acquisition (run
[42830230503](https://github.com/nicobouch97/fund100-research/actions/runs/42830230503))
identified **7,448** non-ETF/non-test listing candidates, **6,611** exact
contemporary SEC ticker-and-exchange associations and **5,027 distinct
current SEC issuer CIKs** behind **5,047 exact associations** whose original
Security Name contains explicit common/ordinary wording and no conflicting
instrument words. Source-name wording remains a TEXT cue, not proof of a
listed US common-share class; other original names can be missing, ambiguous
or misleading. An SEC CIK is an issuer, not a unique tradeable share class.

## Economic next step, not another fake stock backtest

A discovery pool without FINANCIAL source availability cannot deliver even
the quality/valuation pillars of the planned broad five-pillar engine.
To test this concrete data dependency using authentic original sources:

1. In one bounded research-only main workflow, retrieve same two original
   Nasdaq Trader directories and one official SEC current ticker/exchange
   association JSON, validate timestamps, source SHA, unknown market codes,
   null exchanges, exact ticker/market match, source-name uncertainty.
2. Before inspecting a SINGLE price, annual filing or financial ratio,
   deduplicate SEC issuer CIKs from the explicitly common/ordinary worded
   source-name tier, apply a preregistered SHA-256 ordering domain and retain
   the first **32 distinct CIKs**, never reselecting missing SEC/10-K data.
   Require at least **1,000** current eligible text-cue CIKs before probing.
   This is a deterministic non-return-based **source diagnostic sample**,
   not a statistical random representative sample of US ordinary shares.
3. Obtain, through the configured legally identifying SEC requester header,
   exactly one current official SEC companyfacts and submissions document per
   sampled issuer: maximum **64 document GETs**, average <=2.5/second,
   20-second endpoint timeout, 24 MB per source and 240 MB total. Preserve
   only original acquisition window, SEC source SHA aggregate and ordered
   sample SHA-256 commitment in the final REDACTED research report. Raw issuer
   CIKs, names, tickers, original SEC JSON and contacts are never stored in
   public artifacts or printed. A current SEC HTTP 404 is counted as absence;
   403/429/500+, wrong CIK, corrupt JSON, redirect and untrusted transport
   are **HOLD**, not fabricated missing data.
4. For both originally downloaded issuer documents with identical CIK,
   reuse the already implemented conservative P4A filing-linked annual
   quality source model. It requires two comparable own-accession 10-K
   fiscal years, filing availability lag and source-consistent revenue,
   operating income, CFO/capex. It may produce a descriptive 0-3 quality
   coverage score. Missing/unsupported bank, REIT, energy, financial and
   sector-specific accounting concepts must not be filled with zero, and
   no cross-sector rank or investment opportunity is inferred.
5. Report only total sampled issuers, missing-original-SEC-API-404 count,
   received-and-CIK-matched count, count with two-year filing-lagged generic
   quality available, unavailable, and structurally/sector-unsupported
   source counts. Make all source/count arithmetic reconcile. A later real
   run must be examined independently before claiming any coverage ratio.

## 10 November original SEC32 receipt and next root-cause research

The first deployed main-only 32-issuer original SEC availability probe
[run #42833812358](https://github.com/nicobouch97/fund100-research/actions/runs/42833812358)
succeeded with **32/32 issuer-matched original SEC submissions+companyfacts**,
**9/32** qualifying for the existing strict generic two-10-K P4A score,
**19/32** reporting `MISSING_ELIGIBLE_FULL_YEAR_FILINGS`,
**1/32** reporting stale annual filings, and **3/32** rejected by
the generic P4A original-source structure/fact contract. All 32 stayed
in the predeclared sample. Missing P4A scores are not poor investments.

The existing P4A contract requires its **four exact generic US-GAAP
dollar concept tags** within own original 10-K accessions, full-year
dates, two eligible consecutive FY reports, two-weekday filing delays
and nonstale current FY. It examines ONLY the SEC
`submissions.filings.recent` ledger already in the original API
response, not the extra `submissions.filings.files` older filing
archives. Missing coverage is therefore not proof that a company has
no valid original 10-K, or that its economic value is zero.

### No-extra-fetch diagnostic on the SAME 32 original GETs

Use the already downloaded SEC companyfacts and submissions **in memory**
and publish only counts for every unscored original issuer. The precedence
is declared in advance:

1. **P4A original strict validation rejected**: original facts conflict,
   malformed or issuer-specific model assumptions incompatible. Does not
   reclassify the issuer as low-score.
2. **Latest annual report too stale**: P4A reported its existing
   `LAST_ANNUAL_REPORT_TOO_STALE` state.
3. For P4A `MISSING_ELIGIBLE_FULL_YEAR_FILINGS`, count 0, 1 or
   2+ actual 10-K **forms in the authenticated current
   `filings.recent` ledger**. Zero/one means P4A lacks enough
   originally linked accessions in its **view**, not that the issuer
   never filed earlier forms.
4. For 2+ 10-K forms, independently count whether any of the
   four exact **generic** P4A US-GAAP tags lacks USD source rows;
   otherwise label them as **concepts present but no qualified
   pair**, where own-accession, filing period, FY comparison, lag or
   economics may still be unsupported. Do NOT impute missing facts.
5. For the cases in steps 2–4, separately count whether the current
   original submissions JSON advertises **older
   `filings.files` descriptors**. This metadata indicates additional
   files could be obtained under future explicit source contracts;
   it is NOT downloaded archive content and is not proof that any
   earlier 10-K is available or admissible.

All diagnostic category counts MUST reconcile to the existing strict
unscored total (including rejected original source cases); old-file
descriptor subset is separately bounded by the number of P4A
result-state unscored issuers. No CIK, ticker, issuer name,
document table, individual path, source raw bytes or financial value
is stored in the redacted public report.

This cannot distinguish every source/sector issue. It first establishes
whether the dominant gap is missing **recent** 10-K ledger coverage
versus exact generic tag coverage versus fully populated but
unqualified original annual packets. Any later access to SEC older
submissions must be a separate bounded, identity-verified prospective
source acquisition, NEVER asserted to be a vintage of the original
historical filing day. No cross-sector financial grade, value factor
or stock-picking signal is promoted by this diagnostic.

## 10 November — actual missing-data root causes and next original-tag test

The first [PR #615 original-root-cause main run #42844685650](https://github.com/nicobouch97/fund100-research/actions/runs/42844685650)
completed with the **same original sample roster SHA256** as the first
32-CIK capture (unchanged: 9 scored, 23 unscored), and 83,250,629
original SEC-document bytes observed. All reasons now reconcile:
- **11** unscored original issuers lack one or more of the four exact
  generic P4A US-GAAP USD accounting concepts in the current original
  companyfacts source. This is the dominant **observable** source gap;
  it does not mean the issuer has no economics or files no 10-K.
- **4** have 2+ 10-K forms and all four generic tags somewhere in the
  retrieved current companyfacts JSON, but no qualified, own-accession
  consecutive fiscal-year 10-K pair under P4A. Presence of the tag is
  not proof of an eligible original fiscal annual fact.
- **2** have one, and **2** have zero, 10-K forms in
  `filings.recent`; not proof there were never older 10-Ks.
- **3** strict original source/sector contract rejections and **1**
  explicitly stale annual report.
- **8** among the 20 with ordinary missing/stale P4A states include
  older `filings.files` metadata, NOT downloaded earlier SEC filings.

These results direct the next research question to **exact missing
generic accounting concepts** instead of blindly fetching older filing
indexes. Before substituting any field or changing the scoring
model, count separately for each original unscored missing-tag issuer:
which P4A concept (revenue, operating income, operating cash flow,
capital expenditure) lacks original `us-gaap.<tag>.units.USD`
rows. In the **same original downloaded companyfacts already in
memory**, count possible alternate *source-tag presence only* for:
- revenue: `Revenues` and `SalesRevenueNet`;
- capital expenditure: `PaymentsToAcquireProductiveAssets`.

These are historic US-GAAP concept names used in other SEC/issuer
contexts, NOT equivalent financial accounts, and may differ in
definition, fiscal year, USD unit, financial sector and period or
original 10-K accession. All aggregate counts use the same 32
denominator and compare against the previously admitted 11 missing
tag cases; missing-field tags can overlap, so sum of per-tag gaps may
exceed eleven. Every potential alternative is a separately labelled
REVIEW count, not a 10-K availability, validated revenue/capex fact,
quality score, value factor, backtest, market signal or authorization.

**No additional SEC GETs**, issuer roster or raw response publication
are introduced by this next diagnostic. Historic issuer source bytes
are STILL not permanently archived. Only independently matching
original accession/period, audited concept meaning and business-sector
appropriate economics should ever lead to a new scored model version;
do not silently change frozen P4A or older 24/100 SEC cohorts.

## 10 November — original missing-tag counts and 10-K pairing hypothesis

The verified original missing-tag capture
[run #42848022594](https://github.com/nicobouch97/fund100-research/actions/runs/42848022594)
succeeded on the SAME 32 issuer roster digest, with 9 generic
scores and the same 23 unscored. Within the 11 missing-generic-tag
issuers, original US-GAAP USD field absence overlaps:

- 10 lack exact P4A RevenueFromContractWithCustomerExcludingAssessedTax
- 5 lack OperatingIncomeLoss
- 3 lack PaymentsToAcquirePropertyPlantAndEquipment
- 0 lack NetCashProvidedByUsedInOperatingActivities

Candidate source-only alternates appear somewhere in original SEC
companyfacts: Revenues in 5, SalesRevenueNet in 1, and
PaymentsToAcquireProductiveAssets in 1. These groups can overlap.
Presence is NOT proof of semantic equivalence, same original filing,
current original period, US common-share identity or investable quality.

### Predeclared next original 10-K accession audit — NO new HTTP

On the same in-memory original 32-issuer SEC source, for each of these
potential alternate concepts (only where the required generic concept
is absent), validate whether its source USD facts actually match:

1. An original 10-K accession in that issuer's original SEC
   filings.recent ledger (not later comparative under newer filing)
2. Exactly matching filed date and original 10-K fiscal period end,
   full-year start/end separated 330–380 days, valid finite original
   numeric amount (not used as a financial score)
3. Two separate *unique* own-accession eligible 10-K fiscal years,
   330–400 days between ends, both publicly available under the
   already established two-weekday filing lag and current latest year
   no more than 550 days stale
4. No conflicting amounts or period starts for the same 10-K and
   no competing amended accession for the same fiscal year.
   Ambiguity remains a review state, never choose preferred values.

Publish ONLY aggregate alternate-source classification counts:
two original annual source years (REVIEW ONLY), fewer than two,
stale/nonconsecutive, and conflicting/multiple original 10-K vintages.
Reconcile categories against the existing 7 alternative tag-presence
observations; overlapping issuers are counted per relevant source tag.
A source-valid own 10-K pair still DOES NOT mean Revenues and
SalesRevenueNet are interchangeable, or that any revenue/capex amount
has the same economic interpretation across banks, REITs, foreign
issuers and industrial firms. No automatic substitutions into P4A,
no valuation, trading ranking, broker order or cross-sector grade.

The SEC issuer source panel remains current-prospective and is not
a survivorship-safe historical share-class/filing-vintage source.
Original source bytes and ticker/CIK roster are not permanently
archived for future historical replay.

## Explicit limitations and safety

Only a 32-issuer diagnostic sample; the 5,027-issuer source-wording
population has **not** been fully checked for original companyfacts.
The source identities and bytes are NOT preserved for replay in a private
secure permanent research registry; the per-run roster digest alone cannot
recreate them after exchange directories revise. Therefore:
- No genuine point-in-time historical security master or delisted stocks
- No verified US-common share class, CUSIP/ISIN or stable corporate actions
- No recorded price, liquidity, book cost, market cap or valuation
- No sector-neutral generic quality model (banks/REITs need alternatives)
- No analyst expectations, prospects, five-pillar scoring or alpha proof
- No actual LIVE broker orders, pilot-capital authority or readiness change

The next substantive phase needs **durably authenticated, rights-cleared
security identifiers/point-in-time constituents** (and allowed private
research artifact retention), plus sufficient issuer coverage by distinct
sector models, actual prices and original filing economics. Never promote
a successful SEC-source coverage pilot into a historical selection result.

The existing original $130.30 principal ceiling, $65 new-order limit,
HIGH risk selection, ACWI sale HOLD, operator STOP and ENGAGED broker kill
remain unchanged. This weekly nontrading source job uses only existing SEC
requester identity, no Alpaca keys and GitHub read-only contents permission.
