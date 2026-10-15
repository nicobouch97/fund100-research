# Fund-100 Phase 4A — individual US company quality, SEC filing source gate

**Frozen 15 October 2026. Status: source contract and synthetic offline tests,
NOT validated historic alpha, NOT an earnings-revision bot, NOT PAPER/LIVE.**

## Different investment philosophy from Phase 1 ETFs

Phase 1 uses an ETF core and medium-term relative momentum satellites.
Individual-stock research should independently identify **financial quality
and improving fundamentals**, eventually combined with *properly dated*
earnings-estimate revisions, medium-term price momentum, diversification,
liquidity, stock-specific risk and event/corporate action checks.
Stock earnings gaps, delistings, split-adjustment errors and survivor
selection make stock research fundamentally different from an ETF model.

The US SEC provides official
[companyfacts and submissions JSON APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces),
without an API key. CompanyFacts contains standardized **US-GAAP facts
associated with individual 10-K/10-Q filings**, and submissions tracks
accession numbers, filing dates and acceptance information.
A *current download* can contain later restatements or comparatives
and does not itself prove the archived values that a real trader saw
years ago. Historical ticker/CIK mappings and company failures must
be reconstructed independently before any survivorship-safe backtest.

## Implemented P4A source gate

The offline `fund100_stock_sec_quality_p4a_v1_0.py` accepts
both source JSON documents for the SAME 10-digit CIK and
the target research decision date. For **annual 10-K only**, it:

1. Requires SEC recent submissions accession/form/filing date/report
   date/acceptance time arrays, with a full source identity check.
   SEC 10-Q, unmatched and later comparative 10-K observations cannot
   be substituted as if they were an older original 10-K report.
2. Allows only the four fixed annual US-GAAP USD facts:
   `RevenueFromContractWithCustomerExcludingAssessedTax`,
   `OperatingIncomeLoss`,
   `NetCashProvidedByUsedInOperatingActivities`,
   `PaymentsToAcquirePropertyPlantAndEquipment`.
   Exact same accession, annual report period end and annual flow
   interval (330–380 days), no cross-report metric combinations.
   Missing tags/data ⇒ missing quality state, **not zero**.
3. Conservatively delays knowledge to TWO subsequent ordinary
   weekdays after official SEC filing date, without asserting this
   equals a fully verified US exchange holiday/timezone calendar.
   Its calendar proxy still requires additional real as-of review
   before any trade decision.
4. Uses the most recent **two distinct consecutive full-year
   reports** both available by the decision date. Stale latest
   annual accounts older than 550 calendar days ⇒ unavailable.
   Conflicting duplicate same-year or accession facts fail closed.
5. Provides **exactly 3 predeclared binary quality tests**:
   annual reported revenue growth non-negative (+1), annual
   operating income/revenue at least 10% (+1), annual free cash
   flow/revenue at least 5% (+1), where FCF = operating cash
   flow less reported property/equipment acquisition spending.
   These are *descriptive source-linked fundamentals*; a score
   is NOT a recommendation, target position or predicted return.

The 10-K cash-flow statement convention is annual and can
combine non-comparable businesses. Tag availability varies by
industry, fiscal calendar, acquisition accounting, bank reporting
and SEC XBRL taxonomy; do not silently substitute alternative
revenue tags, annualize 9-month cash flows or equate missing
tag with a failed quality company. Annual period comparisons
can still reflect revised statements in a current SEC API dump,
which is a limitation until independently archived source vintages
and original accession documents are confirmed. The model never
labels this as verified historical point-in-time data.

**Important separate future signal:** analyst expected EPS
revisions are not the same as changes in SEC-reported revenue
or operating margins. No analyst consensus data, revision clock
or earnings announcement surprise feed exists in P4A.
`analyst_earnings_revision_signal: null` is mandatory.

## Frozen initial *contemporary* research cohort

`research_lab/stocks/p4a_contemporary_universe_2026_10_15.csv`
contains eight public US stock identifiers/CIKs across major
business sectors, frozen as an illustrative **15 October 2026
prospective cohort**: AAPL, MSFT, GOOGL, AMZN, XOM, JNJ, PG, KO.

This is **NOT a historic US stock universe**. Those companies
are selected from today's visible firms and therefore carry
severe historical survivorship/selection bias if backtested
back to 2010. Do not claim broad-market generality or use the
cohort to benchmark historical small-cap/failed-stock alpha.
Each company's source identity, active exchange listing, float,
ADV, institutional liquidity, spin-offs, ticker history, share
class and corporate actions need independent review before
a trade-eligible stock universe.

The frozen cohort is NOT the Phase 1 14-ETF LIVE whitelist.
All `approved_for_backtest`, `approved_for_paper` and
`approved_for_live` flags remain **false**.

## Source-data workflow

For locally, legally obtained official SEC files:
- `https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json`
- `https://data.sec.gov/submissions/CIK0000320193.json`

SEC automated-access rules require an identifying User-Agent
and reasonable request rate. No SEC download credentials,
contact email or implicit data-harvest authorization are
invented by this source-validation PR. The CI suite is
completely **offline**; all numeric test values are synthetic.

After obtaining both actual source files with permitted SEC
access, run locally (all output stays untraded, outside GitHub):

```bash
python fund100_stock_sec_quality_p4a_v1_0.py \
  --companyfacts-json /private/sec/CIK0000320193_companyfacts.json \
  --submissions-json /private/sec/CIK0000320193_submissions.json \
  --expected-cik 0000320193 \
  --asof-date 2026-10-15 \
  --output-json /private/reports/P4A_AAPL_2026-10-15.json
```

The output embeds both exact raw source SHA256 values and refuses
to attest that source vintages were independently archived at
past trade times. Do not upload personal/private data; SEC public
source itself generally does not contain broker information.

## Later acceptance gates for a real stock strategy

1. Legally download original SEC company filings/snapshots with
   clearly identifiable publication timestamps and historical
   restatement handling; assess 10-K alternative tags, 10-Q
   annualization and corporate accounting comparability.
2. Acquire genuinely point-in-time analyst EPS consensus
   estimates, *revision publish dates* and missing-coverage
   policy or freeze a revised fundamental-only hypothesis
   without calling it analyst revision alpha.
3. Build survivorship-safe US security master including
   de-listed historical names, ticker/CUSIP mapping,
   mergers, dividends, split/spinoff events, market caps
   and historic liquidity.
4. Freeze a diversified quality × revisions × momentum
   hypothesis before an **untouched independent time period**.
   Rank strictly against a broad benchmark and simpler
   sector-neutral alternatives with execution costs, gaps,
   delisting losses, slippage, taxes, event gaps and
   single-company caps. Do not overfit tech survivors.
5. Only then start separate prospective stock research/PAPER
   integration after operator review. An offline score cannot
   auto-promote stock orders into Alpaca.

**All trading controls unchanged:** the existing V5 US ETF
pilot remains the only LIVE-eligible asset group, with
selected HIGH risk, $130.30 maximum exposure, operator STOP
and engaged kill switch. No individual-stock PAPER/LIVE
permission, accounts, deposits or orders.
