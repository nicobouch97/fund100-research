# QuantConnect Free Cloud V2 coverage experiment

**Status: prepared, not executed in a real Cloud account.** This is an
**external, read-only research-only** experiment that would require an
operator-owned QuantConnect Free account. No vendor data exports, no
subscriptions or API-key sharing, and **no connection to Alpaca**.

Free tier: one Research node, one Backtest node and **zero LIVE nodes**.
Official documentation:
- https://www.quantconnect.com/docs/v2/cloud-platform/organizations/tier-features
- https://www.quantconnect.com/docs/v2/research-environment/universes
- https://www.quantconnect.com/docs/v2/research-environment/key-concepts/research-engine
- https://www.quantconnect.com/docs/v2/cloud-platform/projects/files
- https://www.quantconnect.com/data/quantconnect-us-etf-constituents
- https://www.quantconnect.com/docs/v2/cloud-platform/datasets/licensing

## What it proves — and what it doesn't

The **equity** probe calls the supported `QuantBook.add_universe` and
`QuantBook.universe_history` APIs on three brief past periods (2018, 2020,
2024) and counts Fundamental records that pass a $5/$5m turnover research
filter. It is NOT a proof that today's adjustments or issuer identifiers
match what was available to traders on those historical dates.

The independent **SPY ETF constituents** probe calls
`qb.universe.etf("SPY", universe_filter_func=...)`, then adds the
universe and queries one bounded November/December 2020 period.
It counts the **equities SPY held**, *not* historical tradable SPY ETF
share prices or the full US ETF universe. ETF reported holdings can be
delayed, and neither holdings dates nor source `last_update` fields
prove the actual historical publication instant.

Both probes select at most a few symbols for transient data access.
No fund weights, trade orders, authenticated source vintages, spread
quotes, delisting payouts, or return estimates are produced. The reports
contain aggregate counts and SHA256 digests, never raw licensed data.

## Operator handoff — only when a user-owned Free account is available

1. Open https://www.quantconnect.com and select a **Free** organization.
   Do **not** select paid subscriptions, a LIVE trading node, or connect
   the Fund-100 funded Alpaca account.
2. Create a **Python** Cloud research project. Use its existing
   `research.ipynb` Research notebook. QuantConnect Cloud supports
   importing Python code files stored in the same project.
3. In the project file explorer, create directory `fund100_v2` and
   copy these exact files from draft PR #2 under that directory:
   `__init__.py`, `qc_cloud_feasibility.py`,
   `qc_etf_cloud_feasibility.py`. The copy must remain research-only;
   no other Fund-100 files, brokerage credentials, or secrets are
   necessary. The project stays private under the operator's terms.
4. Run this *read-only notebook cell*:

```python
from QuantConnect.Research import QuantBook
from fund100_v2.qc_cloud_feasibility import (
    run_cloud_coverage_probe,
    aggregate_report_json,
)
from fund100_v2.qc_etf_cloud_feasibility import (
    check_etf_constituent_coverage,
)

qb = QuantBook()

equities = run_cloud_coverage_probe(qb)
print("EQUITY_AGGREGATES_ONLY", aggregate_report_json(equities))

etf_constituents = check_etf_constituent_coverage(qb)
print(
    "ETF_CONSTITUENTS_AGGREGATES_ONLY",
    {
        "etf": etf_constituents.etf,
        "reported_snapshots": len(etf_constituents.dated_snapshots),
        "evidence": etf_constituents.evidence,
        "audit_sha256": etf_constituents.audit_sha256,
        "real_cloud_execution_proof": "NEEDS_INDEPENDENT_CONFIRMATION",
    },
)
```

This exact code has **not been run inside QuantConnect Cloud**.
If one of the documented interfaces has changed, STOP, record only the
sanitized error message and request engineering review. Do not bypass
date limits or broaden the selections merely to get a successful result.
The published `UniverseHistory` return is a pandas Series whose values
are Fundamental/ETFConstituentUniverse collections; GitHub CI mocks are
not a substitute for this actual Cloud result.

No need to paste raw vendor rows or keys into ChatGPT. Aggregate counts,
date range, reported coverage flags and sanitized errors are adequate
to assess the next data-quality gate.

## Acceptance/rejection

- **Evidence found:** The actual Cloud environment returns nonempty,
  bounded dated universe snapshots with coherent sources, and the audit
  digests are reproducible across a rerun. Classify this as
  `CLOUD_COVERAGE_ONLY_NOT_PIT_ALPHA_EVIDENCE` and
  `ETF_CONSTITUENTS_ONLY_NOT_ETF_PRICES_OR_PIT_ALPHA`.
- **Missing evidence:** Any empty/invalid series, selector not called,
  timestamp inconsistency, duplicate symbol identity ambiguity, project
  import failures or costs beyond the free tier remain unresolved.
- **Always missing even on success:** Certified vintage archives,
  corporate-action restatement chronology, independently validated
  delisted-name coverage, terminal delisting payouts, real bid/ask
  data/auction executable fills, and untouched OOS alpha evidence.

**Do not merge V2, enable paper or LIVE orders, or unlock the Alpaca kill
switch on the basis of this feasibility test.** Existing LIVE execution
audit blocker [Issue #3](https://github.com/nicobouch97/fund100-research/issues/3)
and V2 data gate [Issue #4](https://github.com/nicobouch97/fund100-research/issues/4)
remain OPEN.
