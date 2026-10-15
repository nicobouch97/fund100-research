# Fund-100 Phase 4B — first genuine SEC fundamental source capture

**Source observed 15 October 2026 at 13:52:50 UTC. Research only.**

## Operational fix and source provenance

The operator provided a legitimate SEC requester identification via
the existing repository secret `FUND100_SEC_USER_AGENT` and requested
a two-company SEC capture. The initial manually started GitHub run
[38744413858](https://github.com/nicobouch97/fund100-research/actions/runs/38744413858)
failed because real SEC filings/submissions can encode the company
CIK as a **padded string** (e.g. `0000320193`), while SEC
CompanyFacts often uses a **numeric CIK** (e.g. `320193`).
The initial collector erroneously required integers in both.
The fix in [PR #32](https://github.com/nicobouch97/fund100-research/pull/32)
accepts only matching 1–10 digit integer/text CIKs, rejecting
mismatches and nonnumeric/float/bool identifiers.

After the corrected 865-test premerge suite and 36 LIVE boundary
checks passed, the existing requester secret was used for a
**single read-only capture retry**. The corrected
[GitHub Actions run 38746277418](https://github.com/nicobouch97/fund100-research/actions/runs/38746277418)
**SUCCEEDED**.

- Captured at: **2026-10-15T13:52:50Z**.
- Source requests completed: **four** official
  `data.sec.gov` JSON documents, two each for **AAPL**
  and **MSFT**.
- Retained 90 days in GitHub artifact
  `fund100-phase4b-real-sec-snapshot-38746277418`
  (artifact ID `11980335484`).
- Original `manifest-and-quality.json` source SHA256
  `887bb4df1d6371aa52bafdbd7f0dde3dc0480cb432341f1b843c20fa6e7dc1cb`.
- Exact official `companyfacts` and `submissions` raw
  source file SHA256 digests, source accessions and scores
  are preserved as a small independent review manifest at
  `research_lab/stocks/prospective/p4b_actual_sec_2026_10_15.json`.
  The full raw SEC documents are in the artifact, not Git.

The SEC contact secret was **never recorded in the report** or
passed to the repository test suite. The one-time automatic retry
branch condition has been **removed** after success; future actual
SEC downloads require an explicit `workflow_dispatch`
`capture_prospective_sec`, as before.

## Actual published annual company financial features

**This is the first real SEC-derived Fund-100 stock research
observation, not simulated or extrapolated prices.**

| Stock | Latest eligible fiscal period | Annual revenue growth | Operating margin | Free cash flow / revenue | P4A quality score |
|---|---|---:|---:|---:|---:|
| AAPL | FY ended 2025-09-27 | **+6.43%** | **31.97%** | **23.73%** | **3 / 3** |
| MSFT | FY ended 2026-06-30 | **+17.79%** | **46.78%** | **20.19%** | **3 / 3** |

AAPL's latest annual accession is
`0000320193-25-000079`; conservative
research availability is **2025-11-04**.
MSFT's latest annual accession is
`0001193125-26-323660`; conservative
availability is **2026-07-31**.
Metrics were computed from source-matched annual revenue,
operating income, annual cash flow and capital spending,
using the frozen Phase 4A tag definitions. They are not
simultaneous fiscal periods or normalized sector-relative
valuations. A three-of-three score is only a historical
fundamental-descriptor result, **not a stock buy signal**.

## What this does and does NOT demonstrate

The source captures genuinely prove that the SEC official
files were accessible with the user's registered
identification, the requested company CIK matched both
source documents, raw hashes were archived, and source
annual-report data passed the fixed quality pipeline.

**None** of the following has yet been established:
- independent point-in-time source vintages for each former
  historical trading date; this is a **2026 capture**, not
  a source database captured in 2010–2025;
- historical point-in-time US stock universe including
  failed/delisted companies (AAPL/MSFT are selected
  from today's survivors);
- daily individual stock prices, split/spinoff adjustments,
  execution costs, earnings announcement market gaps;
- date-stamped analyst EPS consensus estimate **revisions**;
- out-of-sample expected returns, excess alpha against
  SPY/RSP or sector-neutral alternatives; or
- any individual-stock PAPER or LIVE order permission.

**Research decision:** Retain AAPL/MSFT as the first
forward-only SEC quality-source observations. Expand
prospective issuer coverage through explicit authorized
captures, independently build a survivorship-aware security
master and estimates-revision source, and avoid all
premature stock trading.

Original V5 US ETF PAPER pilot unchanged. Operator
LIVE STOP, engaged kill switch, selected HIGH tier,
$130.30 pilot ceiling and 14 US ETF-only LIVE whitelist
unchanged. Zero stock/broker orders.
