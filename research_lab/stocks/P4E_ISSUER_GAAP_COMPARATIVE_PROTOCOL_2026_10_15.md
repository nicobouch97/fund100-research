# Fund-100 Phase 4E — issuer-specific annual SEC accounting contract

**15 October 2026 — research-only rules frozen before the first P4E real-data study.**

## Why a separate model

Original Phase 4A scored 2/8 companies from the genuine Phase 4C eight-company SEC source capture, because its fixed four US-GAAP annual concepts were missing in other issuers' original annual filings. P4E researches **data definition compatibility**, not stock alpha, analyst earnings revisions, or a broker strategy. The previous P4A/P4B/P4C source observations, their original SHA256 hashes, and quality values are not rewritten.

The frozen source map is in research_lab/stocks/p4e_frozen_issuer_gaap_concept_contract_2026_10_15.csv. It is strictly pinned by ticker, CIK and accepted source concepts:

- AAPL/MSFT/AMZN/JNJ retain the original RevenueFromContractWithCustomerExcludingAssessedTax annual reported revenue concept.
- GOOGL/PG/KO/XOM use standardized US-GAAP Revenues, which represents each issuer's own annual revenue but is not asserted equivalent across every industry or tax/revenue reporting arrangement.
- AMZN only uses PaymentsToAcquireProductiveAssets instead of PaymentsToAcquirePropertyPlantAndEquipment, as the issuer's annual cash-flow **productive-asset purchases proxy**. It is not automatically equivalent to PP&E capex across companies. This is a versioned research-specific definition, not proof of cross-sector comparable free cash flow.
- The remaining firms retain PaymentsToAcquirePropertyPlantAndEquipment.
- Every company continues to require NetCashProvidedByUsedInOperatingActivities and, critically, OperatingIncomeLoss. XOM and JNJ have no matching newest original annual operating-income source under that concept, and therefore **remain missing**. We explicitly forbid substituting pre-tax/net earnings for operating profit.

**The original P4A threshold logic remains fixed:** +1 for nonnegative annual revenue growth, +1 for operating margin >=10%, and +1 for operating cash flow minus issuer-mapped capital spending at least 5% of revenue. These are descriptive research measures, not comparable cross-sector rankings or expected stock returns.

## A stricter latest-original-filing, no-lookahead calculation

The latest eligible SEC original 10-K must have been publicly filed at least two ordinary weekdays earlier (a conservative calendar proxy, not exchange-holiday or distribution-time authentication). Source CIK, accession, filing date and fiscal period end must match SEC submissions.

Both the current annual year and preceding **consecutive** fiscal-year period must be represented as full-year (330–380 **calendar day** reporting intervals) USD facts **inside the SAME latest original 10-K filing accession**. This permits like-for-like issuer presentation of prior-year comparatives after the most recent 10-K publication, without pretending those comparative figures were known a year earlier. The prior financial-year end is cross-checked against its own published original 10-K submissions record. Missing facts, wrong tags, conflicting duplicates, quarter/YTD values, later filings, source errors or outdated reports produce **UNKNOWN**, not zero and never fallback to an older complete accession.

In particular, GOOGL's most recent original 10-K has its latest and preceding fiscal-year Revenues values under the same accession; the old original 2024 filing used another presentation. This model must never claim that a 2025 filing's re-presented comparative was available to a 2024 trader.

## First study evidence and risk boundaries

The GitHub Phase4E workflow runs synthetic invariant tests before merge. On merged main, it reopens the immutable SEC source artifact captured in [Actions 38756477914](https://github.com/nicobouch97/fund100-research/actions/runs/38756477914), independently checks every original source byte SHA256 and previous P4A score through the P4C audit, and generates a second-version, 90-day P4E descriptive quality report.

There are **no new SEC HTTP requests**, no use of the identifying SEC contact in this evaluation, no analyst consensus estimates, no equities prices, no survivor/delisted securities history, no trading signals, no broker environments or credentials, and NO stock PAPER or LIVE trading permissions. Eight historical 2026 survivors do not constitute a backtest.

Next, audit the issuer-specific cash-spending definitions against complete cash-flow statements, and seek independent true-vintage analyst EPS revision, dated stock price/corporate action and delisting-safe security-master data. Missing JNJ/XOM operating profits remain source gaps rather than a reason to force a proxy.

Fund-100 equity ETF V5 PAPER remains separate; the original 14-symbol LIVE whitelist, operator STOPPED, engaged kill switch, HIGH risk profile and $130.30 exposure ceiling are unchanged.
