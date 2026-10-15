# Fund-100 P4F — original analyst EPS estimate revision source contract

**Frozen 15 October 2026 — research only, broker permissions unchanged.**
This is a source qualification and calculation protocol, NOT original
analyst data, alpha or a validated stock-selection strategy.

## Exact problem to solve

P4E measured six annual SEC issuer accounting scores from eight
contemporary large-cap stock observations. SEC *reported facts* cannot
establish changes in professional analysts' **forward EPS estimates**.
A 2026 statement revision is also not a 2024 analyst forecast revision.

To test whether analyst expectations strengthen a quality strategy,
we need the original individual contributor's EPS estimate before and
after each revision, published timestamps, acquisition timestamp,
future fiscal-year identity, equity identifier, share class, measure
and currency. We must be able to prove both data points were
knowable at the research decision time.

Potential legitimate commercial sources:

- [LSEG I/B/E/S Broker Estimates](https://www.lseg.com/en/data-catalogue/company-data/ibes-estimates/broker-estimates):
  original analyst-level forecast detail, measure/period metadata
  and contributor identity. A suitable licensed export must
  actually include both previous/current forecast versions,
  original published timestamps and broker IDs.
- [FactSet Estimates datafeed](https://insight.factset.com/resources/factset-consensus-estimates-datafeed):
  details and historic snapshots may provide individual
  contributor-level data, subject to contract permissions.
  The **FactSet Point-in-Time Consensus** product is a
  separate daily consensus snapshot dataset, not equivalent
  to individual analyst revision events. It requires its
  OWN future adapter; do not put consensus changes into this
  broker-level source contract.
- Neither vendor is connected or licensed in this Fund-100
  repository. Price, availability, redistribution and APIs
  have NOT been negotiated or assumed. The engine **does
  not place vendor network requests**.

The SEC's periodically refreshed ticker/CIK listings
(https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)
are *not* historical exchange listings or delisting-return
coverage. Our frozen 15 Oct 2026 eight-company roster is
a prospective research cohort, NOT a historical stock universe.

## Fixed P4F prospective revision hypothesis

At a preselected research decision timestamp in strict UTC:

1. Take only the immutable, SHA256-matching original source
   bytes, declared provider, dated acquisition and rights
   manifest. External vendor exports remain
   **unverified until independent licence/data review**;
   synthetic fixtures always remain synthetic. There is
   no fallback from an absent feed to guessed analyst
   revisions or SEC revenue growth.
2. Require same ticker/issuer 10-digit CIK, stable vendor
   security/share-class ID, original broker/contributor
   ID and unique vendor revision ID. Only eight companies
   from the **2026 contemporary prospective cohort** are
   eligible; NEVER replay that list in 2015.
3. Require normalized diluted forward EPS in **USD per share**
   (not basic EPS, IFRS vs GAAP surprise, revenue estimates,
   split-adjusted hindsight or currency-mixed measures),
   one **future** fiscal-year end, no more than 540 days ahead.
4. For each paired revision, the old estimate publication
   must precede the new publication; new publication ≤
   vendor-received timestamp ≤ original file capture.
   All dates UTC. Make the decision no earlier than
   **24 hours after original vendor receipt**; revisions
   in the preceding **30 calendar days** qualify.
   Previous estimate must be at most **180 days old**
   when the revision occurred.
5. Count only each distinct analyst's **latest** qualified
   revision in the window. Treat EPS changes as material
   when absolute change ≥ max(**$0.02 per share**, **1% of
   max(abs(old EPS), $0.50)**). Count upward, downward,
   and neutral revisions. Require at least **three distinct
   analysts with material direction** before producing
   a descriptive revision pressure:
   (number upward − number downward) / (upward + downward).
6. Missing source, <3 directional contributors, ineligible
   dated records, conflicting issuer identity, source hash,
   measure mismatch or rights uncertainties result in
   UNKNOWN or hard failure, **not a buy/sell decision**.

These thresholds were specified before seeing ANY authentic
broker data. They are an exploratory hypothesis, not
evidence of predictive performance. A change to vendor
normalisation, timestamp semantics, fiscal years or
thresholds needs a new preregistered version and separate
prospective tests, not retrospective tweaks.

## Exactly what has been implemented

- `fund100_stock_analyst_revisions_p4f_v1_0.py`:
  source-manifest/raw-byte audit, event-time leak checks,
  issuer/share-class continuity, contributor de-duplication,
  fixed 30/180-day windows and no-PAPER/no-LIVE results.
- Dedicated synthetic fixtures:
  `test_fund100_stock_analyst_revisions_p4f_v1_0.py`.
  All mock EPS numbers and IDs are synthetic ONLY; no
  actual analyst recommendation or consensus feed.
- Read-only offline GitHub CI:
  `.github/workflows/fund100-p4f-original-analyst-revisions.yml`.
  It generates a **truthful readiness artifact**:
  real analyst events retrieved **0**, vendor connected **false**,
  validated signal count **0**, broker orders **0**.
  No vendor credentials, website scraping, SEC contact secret,
  Alpaca environment, or added live security list.

## Genuinely necessary next steps

First, secure permission for a provider export with **true historical
individual analyst version timestamps**, revision predecessor,
actual fiscal-period identifier, stable security IDs and
research retention rights (LSEG I/B/E/S and/or FactSet Detail
are candidates). Pricing and entitlements may be substantial:
do not purchase or contact a vendor without the operator's
decision. Integrate exact export into an isolated offline
adapter; do not claim independently authenticated vendor
records merely because a file has its own hash.

Second, construct a delisting-inclusive historical stock
security master: historical membership and selection dates,
permanent issue/class IDs, ticker changes, exchanges,
listing/delisting and delisting proceeds, dividends/splits,
past liquidity and total-return quote vintages. CRSP-like
datasets are candidates if licensed, but live current SEC
ticker links cannot substitute for this coverage.

Only after both data families exist can Fund-100 preregister
a quality × revisions × momentum stock strategy; require
a prospective, genuinely new validation interval, price
slippage/delisting/sector exposure controls and explicit
operator approval before PAPER. There is **no stock trade
signal today**.

**LIVE boundary frozen:** the existing US ETF V5 PAPER
workflow and frozen 14-ETF LIVE whitelist are unchanged;
LIVE operator STOPPED, kill switch ENGAGED, HIGH tier and
$130.30 exposure ceiling remain enforced.
