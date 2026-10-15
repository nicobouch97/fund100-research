# Fund-100 Phase 4C — original SEC source coverage and forward-only ledger

**Protocol frozen 15 October 2026. Research only, no market orders.**

## What changed

P4A built the fixed annual financial-quality rule; P4B successfully
collected the first true public SEC CompanyFacts and submissions
JSON files for **Apple and Microsoft** (first source capture
[38746277418](https://github.com/nicobouch97/fund100-research/actions/runs/38746277418),
UTC 2026-10-15T13:52:50Z). The authentic files are stored in the
90-day GitHub artifact `fund100-phase4b-real-sec-snapshot-38746277418`.
The original 2-company compact evidence anchor is committed at
`research_lab/stocks/prospective/p4b_actual_sec_2026_10_15.json`.

Phase 4C supplies `fund100_stock_sec_forward_audit_p4c_v1_0.py`,
a **second independent validation pass** for a downloaded/extracted
P4B archive. It rejects file-name traversal/duplicates, missing/extra
source files, forged URLs/CIKs, wrong SHA256 byte digests, absent SEC
reporting fields, unsupported trade permissions, nonmatching or
unpublished annual filings, inconsistent stored quality scores,
unknown stock research cohorts and scores derived from sources other
than the acquired original SEC data.

It then reports:
- actual eligible quality coverage among the issuer files collected;
- 2026 contemporary eight-company cohort coverage;
- individual issuer quality score 0/1/2/3 or genuinely unavailable;
- the precise SEC original 10-K accession, fiscal period and
  conservative filing-available day;
- hashes of both original source JSON files and original capture
  manifest; and
- a candidate **hash-chained, append-only prospective capture record**
  which rejects any duplicate/backdated timestamp, altered
  predecessor record, changed source manifest or attempted
  PAPER/LIVE promotion.

**Very important:** A record is a source observation, not a
portfolio allocation or historical trading signal. The five
named future prerequisites remain (1) delisting-safe historical
security master, (2) genuine analyst consensus/revisions with
original publication times, (3) price/corporate-action data,
(4) unbiased independent evaluation period and (5) approved
broker risk/execution permissions. Source-hash verification does
not make a *current SEC API dataset* an authenticated historical
API vintage.

The P4C tool intentionally never contacts SEC itself. Actual
live downloads remain a **manual-only** Phase 4B GitHub Actions
workflow, with the operator's existing real SEC requester
User-Agent injected only during that explicit capture.
No requester contact is recorded in reports.

## Using an authentic P4B artifact

After manually running the existing
[Phase 4B SEC Source Snapshot workflow](https://github.com/nicobouch97/fund100-research/actions/workflows/fund100-p4b-sec-source-snapshot.yml)
in `capture_prospective_sec` mode with `limit=8`,
its capture job will:

1. Fetch the eight frozen 2026 issuer identities from public SEC
   endpoints (at most 16 GETs with the SEC contact/rate limits).
2. Save and SHA256 the *original* SEC CompanyFacts and submissions
   JSON bytes; compute P4A quality or an honest unavailable state.
3. Invoke the new independent P4C byte-level source audit and
   recompute all company quality values.
4. Upload **two separate** 90-day GitHub artifacts: the raw P4B
   files and the independently checked P4C coverage/ledger
   **candidate**. This preserves the format of original P4B
   archives so they can be verified later unchanged.

Or on a downloaded P4B ZIP:

```bash
python fund100_stock_sec_forward_audit_p4c_v1_0.py \
  --source-artifact /private/fund100-phase4b-real-sec-snapshot.zip \
  --report-json /tmp/fund100-p4c-quality-coverage.json \
  --record-json /tmp/fund100-p4c-next-capture-record.json
```

To add an observation to an append-only research ledger, check
the candidate capture's time/source against the previous
hash-validated records before committing it. Existing source
captures must never be rewritten or assigned earlier dates.
No workflow writes to `main` automatically.

## Known model boundaries

The original P4A thresholds (revenue growth >=0,
operating margin >=10%, FCF margin >=5%) remain
**UNCHANGED**, even if other companies score poorly or
have missing tags. In particular a financial-sector or energy
company might not report all the same XBRL concepts. Missing
information is NOT a negative score; true point-in-time GAAP
tag replacements would require a separately preregistered
source equivalence map with independent prospective testing.

An 8/8 complete-source download does NOT guarantee eight
eligible scores, still less validated alpha. Historical
2020–2026 backtesting against today's hand-picked surviving
names would be biased and is prohibited.

The old GLD/DBC/SHY C1/C2/static forward commodity ledger
and V5 ETF Alpaca PAPER execution remain independent.
Fund-100 LIVE STOPPED, kill switch ENGAGED, HIGH risk
and $130.30 pilot ceiling remain unchanged. No individual
US stock is added to the LIVE whitelist.
