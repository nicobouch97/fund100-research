# Fund-100 — LIVE credential workflow / account-order mutex release gate

**2026-10-13, supplemental safety proposal only. NOT implemented on `main`.
Do not enable LIVE orders or disengage `FUND100_BROKER_KILL_SWITCH`.**

## Verified repository inventory

The default-branch GitHub Actions repository has **40** workflow YAML
files. **13** workflows expose the two Alpaca LIVE credentials in isolated
steps. They are not all order writers.

| LIVE credential workflow | Invoked script | Order-entry classification |
| --- | --- | --- |
| `fund100-live-bootstrap.yml` | `fund100_live_bootstrap_v1_0.py` | **REAL ORDER WRITER** |
| `fund100-v5-live-production.yml` | `fund100_live_production_controller_v1_0.py` | **REAL ORDER WRITER** |
| `fund100-live-micro-pilot-prepare.yml` | `fund100_live_pilot_prepare_v1_0.py` | Preparation; asserted GET-only, needs source proof |
| `fund100-alpaca-live-readonly.yml` | `fund100_alpaca_live_readonly_smoke.py` | GET-only, successfully checked on 2026-10-13 |
| `fund100-alpaca-live-boundary-test.yml` | `fund100_alpaca_live_execution_boundary.py` | Boundary verification; not a confirmed writer |
| `fund100-alpaca-live-intent-validator.yml` | `fund100_alpaca_live_intent_validator_v1_1.py` | Intent validation; not a confirmed writer |
| `fund100-alpaca-live-manifest.yml` | `fund100_alpaca_live_manifest_v1_1.py` | Manifest compiler; not a confirmed writer |
| `fund100-alpaca-live-permit-v2-issuer.yml` | `fund100_alpaca_live_permit_v2_issuer_v1_1.py` | Permit issuance, **not** automatically broker-safe |
| `fund100-alpaca-live-permit-v2-simulation.yml` | `fund100_alpaca_live_permit_v2_simulator.py` | Permit simulation |
| `fund100-alpaca-live-position-reconcile.yml` | `fund100_alpaca_live_position_reconcile.py` | Position reconciliation |
| `fund100-alpaca-live-preconnect-runtime-check.yml` | `fund100_alpaca_live_preconnect_runtime_check.py` | Preconnect GET-only check |
| `fund100-alpaca-live-preflight.yml` | `fund100_alpaca_live_preflight.py` | Preflight check |
| `fund100-alpaca-live-scheduled-compiler.yml` | `fund100_alpaca_live_scheduled_compiler_v1_1.py` | Event compilation |

No statement here proves an arbitrary script is incapable of writing.
Read-only and permit-issuance paths require independent verification; the
scanner verifies **which script** receives secrets, not the entire transitive
call graph or GET-only transport behavior.

## Two incompatible existing writer mutexes

- Bootstrap: `group: fund100-live-micro-pilot-bootstrap`
- V5 production: `group: fund100-v5-002-live-production`

Both use `cancel-in-progress: false`, but different groups provide no
shared GitHub Actions queue. The checks in
`fund100_live_workflow_mutex_audit_v1_0.py` therefore intentionally
**FAIL on the current protected default branch**.

## Exact proposed protected-workflow edit — **not applied**

After a reviewed release authorises updating protected YAML, change only
the root `concurrency.group` values in the two account-order writer
workflows to the exact same constant:

```yaml
concurrency:
  group: fund100-alpaca-live-account-writer
  cancel-in-progress: false
```

Do **not** use `cancel-in-progress: true`: cancelling a LIVE writer
mid-reconciliation is dangerous. Do **not** rely on a separate job-level
group or a ${{ github.workflow }} prefix, because those can fragment the
mutex across workflows. Independent external writers or other repositories
would still require a stronger, verified account-owned coordination
mechanism.

This exact workflow modification was previously blocked by the
authorised GitHub connector; **do not work around branch protections or
tool access restrictions**. No edits to protected workflows have been
performed in this PR.

## Supplemental fail-closed guard

`fund100_live_workflow_mutex_audit_v1_0.py` uses PyYAML and operates
on local repository text only, with **zero HTTP calls or Alpaca credentials**.
It requires:

1. Every one of the thirteen known credential-receiving entrypoints has
   a single exact script command within one step-local secret scope;
   an unknown credentialed workflow or compound shell command fails.
2. No credential exposure at workflow/job scope or directly in run shell;
   the two credentials must be exact GitHub Secrets references.
3. Both account-order writer workflows have a common top-level
   `fund100-alpaca-live-account-writer` concurrency group with cancellation
   disabled and the existing repository kill-switch variable intact.
4. Removing or renaming a previously audited LIVE workflow cannot
   silently make the inventory pass.

`test_fund100_live_workflow_mutex_audit_v1_0.py` covers synthetically
healthy/mismatched groups, secret scope, unseen writer scripts, compound
commands and regression enumeration. **The new guard supplements — it
does not replace or weaken — the older static audit v1.17/v1.18.**

Its command, for a future reviewed *offline* CI gate, is:

```bash
python fund100_live_workflow_mutex_audit_v1_0.py
```

**The production repository should return non-zero until the protected
workflow groups are actually repaired.** The standalone audit is not
wired into an existing protected workflow by this draft PR.

## Other required release checks

- Reconcile the legacy static audit's credential allowlist with the
  deliberately added bootstrap/production/prepare scripts. The existing
  auditor scans *all* commands in a workflow when any credential is
  referenced anywhere in it; this produces the known three-entrypoint
  failure. **Do not add broad allowlist exceptions or disable it to green
  the CI.** Audit step scopes, business invariants and imports instead.
- Prove bootstrap and production cannot concurrently mutate the same
  account *even across repositories or out-of-band processes*, or
  explicitly operationally disallow those extra writers.
- Independently test both broker-write code paths for fail-closed kill
  switch, account binding, immutable release proof, idempotent recovery,
  cumulative $130.30 deployment ceiling, and no leverage/shorts.
- Only after an approved *separate* safety PR passes end-to-end offline
  tests and the original audit is consistent may release be considered.
  No operator has authorised additional LIVE trades.
- Never claim `ENGAGED` cancels existing orders or liquidates positions;
  it prevents only correctly gated future writers.

Related: [LIVE release blocker #3](https://github.com/nicobouch97/fund100-research/issues/3),
[V5 no-event repair PR #1](https://github.com/nicobouch97/fund100-research/pull/1),
[V2 research draft PR #2](https://github.com/nicobouch97/fund100-research/pull/2).
