# V6-S1 — completed one-time $2 PAPER roundtrip; automatic replay retired

**Decision: 19 October 2026 after genuine result and an unwanted scheduled retry.**

- First genuine Alpaca **PAPER** $2 buy and exact acquired-quantity sell **PASSED** on the real PAPER account, source [GitHub Actions 39269640353](https://github.com/nicobouch97/fund100-research/actions/runs/39269640353). Two PAPER orders filled; original PAPER holdings returned to baseline; ZERO LIVE orders. It was a transaction-mechanics proof, not an estimate of strategy forward investment performance.
- A separate later [Actions 39311296047](https://github.com/nicobouch97/fund100-research/actions/runs/39311296047) was triggered by the workflow's old **annual cron**. It FAILED on **`PAPER day session not open for protected tiny test`** before placing orders. This is evidence the legacy automatic trigger was still active, and no reason to retry the already completed one-time test.
- The one-time workflow file `.github/workflows/fund100-v6-s1-paper-fill-once.yml` has therefore been converted into **PR-only, offline-regression testing**: NO `schedule`, NO `workflow_dispatch`, NO PAPER key or secret injection and NO command to invoke the actual broker `paper_probe()` executable. The underlying source and source-frozen policy remain unchanged for audit and test provenance.
- There is no change to original LIVE account operator STOPPED, broker kill ENGAGED, HIGH pilot, $130.30 capital cap, original positions ACWI/EEM/XLE/XLV, or planned V6 S1 strategy draft weights. ZERO REAL MONEY or new PAPER trades are authorized.
- Actual authenticated LIVE pre-migration inquiry [39317938514](https://github.com/nicobouch97/fund100-research/actions/runs/39317938514) independently found original held four ETF quantities and **no existing matching three V6 client IDs** (three HTTP 404 responses, which are NOT never-POSTed proof). This is **not** an order-release.
- Further work should be directly on **durable private cross-run actual order-attempt coordination**, time-of-order original broker GET/reconciliation, versioned V6-specific HIGH policy, settlement proof and a safely reviewed LIVE order transport, rather than repeated forward PAPER tests.

Full static LIVE audit must still pass on this retirement; no access to actual PAPER or LIVE keys in the new PR-only workflow.
