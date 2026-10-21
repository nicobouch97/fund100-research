# V6-S1: separate protected Actions SANDBOX write/CAS proof (21 October 2026)

**Pre-registered before code/test integration. NO live account, broker, order, or production state mutation.**

## Prerequisite satisfied
[Original protected Actions private repository READ run #39600082142](https://github.com/nicobouch97/fund100-research/actions/runs/39600082142) passed on `main` on 21 October 2026 at 12:30 UTC. Both the offline source-contract job and actual `protected-main-private-get-only` job succeeded; all fixed private identity/README and STOP checks passed. This certifies read access only.

## NEW narrow experiment
A synthetic-only sandbox file `sandbox/v6_s1_actions_cas_smoke_2026_10_21.json` has been seeded by the connected GitHub identity (NOT by Actions) on the already-private `nicobouch97/fund100-state-private`, `main`. It contains no trading quantity, account reference, order ID, financial data or HMAC. The exact original Git blob SHA is `fdd46a87febedd8bab1e625cef2299d959d8d280`, content original sequence 0, broker_orders 0, trade_authorized false.

New source and workflow may perform the following ONLY AFTER a manually dispatched `main` protected GitHub Actions job passes source hash, repository, STOP, kill-switch checks **AND** has a separately granted secret `FUND100_PRIVATE_STATE_SANDBOX_WRITE_TOKEN`:
1. GET exactly one known sandbox file from the private repo via GitHub REST (fixed URL, no redirects to other hosts, bounded response); verify original Git SHA/content schema and read actual `main`.
2. PUT **only that same sandbox path on main** with original SHA as precondition. New synthetic-only document is strictly deterministic sequence 1 with prior SHA and still no trader permissions.
3. GET the same path; verify that the new file's Git blob SHA matches *exactly* the intended content and prior-SHA link.
4. Attempt one stale PUT using the old SHA and require GitHub **409 Conflict**. Any accepted duplicate, no change, exception, wrong status, or unexpected file/branch fails closed.
5. On re-run after a successful write, return `ALREADY_COMPLETE_NO_NEW_WRITE` without triggering any write. Do not confuse that with proof of a new successful Actions write.

The source has no URLs to production ledger, private README or Alpaca; no broker or market endpoints, no POST /v2/orders. It does NOT initialize `state/v6_s1_original_legacy_sales.json` and never requests or prints account/cash/quantity.

## Credential and permission constraints
DO NOT modify the existing `FUND100_PRIVATE_STATE_READ_TOKEN`. It must remain read-only. The optional new WRITE token would be a **distinct fine-grained PAT restricted to this one PRIVATE repository**, with Contents read/write, zero unrelated repositories/permissions, and short expiry; add only as a secret in the existing `fund100-live-broker` environment via GitHub Settings. GitHub fine-grained Contents permissions are **repository-wide, not path-limited**: this test's path allowlist mitigates only code-level misuse. Before using the token for actual production-state writes, a separate release must independently review branch protection, workflow change-control, token abuse risk, genesis/HMAC/rollback anchoring, and position/order reconciliation. This synthetic experiment is **not** that production approval.

The protected test is **manual dispatch only on main**, no automatic schedule or PR secrets. PRs run only credentialless mock regressions. The test must fail closed if a token is missing; do not use the read-only token as fallback.

## Remaining LIVE release boundaries
Original pilot cap $130.30, HIGH risk, 95% original V6-S1 entry proposal, STOP and ENGAGED kill switch unchanged. NO LIVE order submission, broker credentials, new strategies, paper/live promotions or new permission to liquidate existing positions. A passed CAS sandbox test would establish one private repository write with stale conflict under the Actions principal, **not** an adequately anchored real order ledger, exact settled proceeds, permanent writer authority or profitable trading.
