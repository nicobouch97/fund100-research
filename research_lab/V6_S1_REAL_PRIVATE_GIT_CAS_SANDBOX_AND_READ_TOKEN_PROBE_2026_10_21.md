# V6-S1: genuine private Contents CAS sandbox, and bounded Actions read-token verification

**21 October 2026; no Alpaca call, no financial records, no production state bootstrap, no trade release.**

## Authenticated private storage result (connector identity, not Actions identity)

The connected GitHub identity verified `nicobouch97/fund100-state-private` is private, on `main`, and initially contains only its README.

A separate **non-production** `sandbox/v6_s1_cas_smoke_2026_10_21.json` was created in that private repo with only invented flags and `broker_orders=0`. The first GitHub Contents create was accepted. A conditional Contents update using the current blob SHA advanced sequence 0 → 1; an attempted update with the **old** blob SHA was rejected by the real GitHub API with **409 Conflict**. A subsequent independent GET returned the new winning SHA, `ONE_WRITER_COMMITTED`, sequence 1, and no broker-trade authorization or other state changes.

Private evidence location: https://github.com/nicobouch97/fund100-state-private/blob/main/sandbox/v6_s1_cas_smoke_2026_10_21.json

This confirms the GitHub Contents expected-SHA mechanism and stale-write rejection under the connected GitHub identity. It does **not** establish identical behaviour or permissions for the separately installed GitHub Actions read token; a real two-writer race; robustness against admin force-push, branch deletion or rollback; independent genesis anchoring; a production order ledger; or any broker write capability. The production path `state/v6_s1_original_legacy_sales.json` is deliberately **not created** and must NEVER be auto-initialized from a missing file.

## Next bounded evidence: two REAL GitHub GETs using protected Actions read token

Add the manually dispatched `.github/workflows/fund100-v6-s1-protected-private-readonly-proof.yml` which:

1. Runs credentialless synthetic tests on PRs and manual dispatch; **only manual dispatch from main** may enter the credentialed job.
2. Uses pre-existing `fund100-live-broker` protected environment, checked `main`, `ENGAGED` broker kill switch, operator trading disabled, and exact pinned original read-probe Git blob. No third-party Python packages are needed by the credentialed job.
3. Supplies ONLY `secrets.FUND100_PRIVATE_STATE_READ_TOKEN` to the pinned `fund100_v6_s1_private_state_actions_readonly_probe_v1_0.py`. It executes exactly two allowlisted GETs: private repo metadata and README Contents. It cannot access the production ledger or any Alpaca endpoint. Logs are categorical only; never print the token or private response payload.
4. Does not request write permissions, invoke broker executors, reuse any Alpaca credential or create trade/state payloads. No automated schedule and no credentials for pull-request runs.

**Acceptance:** protected run must pass (repo ID/visibility/main, README readability, original STOP), and be inspected as an actual main-run result before marking cross-repository Actions **read** access proven. A failed/blocked run is simply NOT PROVEN. Private Actions **write** access and production CAS still require a separate expressly reviewed test. No claim about T+1 cash settlement, BUY eligibility, or performance.

## Execution constraints still unchanged

Original genuine Alpaca BUY order↔FILL six GET passed on 21 October 2026; original V5 ACWI/EEM/XLE/XLV remain held, HIGH pilot ≤USD130.30, and V6 objective is staged ACWI/EEM/XLV exit while keeping XLE. V6 target 47.5% XLK, 28.5% XLE, 19% IWM, 5% cash remains **proposed only**. Operator STOP and broker kill switch remain engaged. The Trading API has not supplied independently verified settled cash after any sale; there have been **no actual V6 SELLs or BUYs**.

No further PAPER profitability waiting is required to prove this storage property, but this result alone releases **no** trade.
