# Fund-100 LIVE credential isolation — required release gate

**13 October 2026. Proposed security control only. No GitHub Settings
changes, Alpaca key moves, broker calls, or protected workflow edits
have been performed. The funded pilot kill switch stays ENGAGED.**

## Why the earlier `main` job guard is insufficient by itself

`workflow_dispatch` can run a workflow from a selectable repository
branch. **A different branch can contain an older or changed version
of the workflow with no `if: github.ref == 'refs/heads/main'` guard.**
If the Alpaca LIVE API keys exist as **repository- or organization-scope
secrets**, a sufficiently privileged branch workflow may still receive
them. Requiring a branch guard *inside the selected workflow file* is
useful defense in depth but is not a trust anchor for that file.

GitHub recommends storing production secrets as **environment secrets**.
Its environment deployment branch rule is evaluated against the
workflow run's `GITHUB_REF` before the referenced job accesses those
secrets. This control lives in repository Settings, not inside the
branch-controlled YAML. Source:
https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments

## Required protected environment

Before a LIVE release review can pass, the repository owner must create
and configure **`fund100-live-broker`** in GitHub Settings -> Environments:

1. **Selected branches and tags**: allow the exact branch **`main`**
   only, no wildcard or other branch/tag. Do not use the option
   **Protected branches only** unless branch protections themselves
   are independently verified: if none exist, GitHub documentation says
   all branches may be eligible.
2. Define environment-scoped secrets named exactly
   `ALPACA_LIVE_KEY` and `ALPACA_LIVE_SECRET`. The values themselves
   must never enter chat, a repository commit, workflow logs, or an
   untrusted agent. If there is reason to suspect previous exposure,
   perform a controlled credential rotation directly in Alpaca and
   GitHub Settings with all writers disabled.
3. Prove **no copies of those same LIVE secrets remain at repository
   or organization scope**. Merely duplicating them in the environment
   does NOT protect against earlier branch workflows that still use
   the repository/organization copies.
4. Where supported, add required reviewers and disallow admin bypass,
   and preserve the operator's explicit trading release policy. A
   reviewer approval or environment protection must NOT be treated
   as blanket permission to place orders.
5. Verify the environment actually exists and has the correct
   protections **before editing** any workflow to reference it.
   GitHub can auto-create a named environment without any secrets or
   protection rules when a workflow refers to a nonexistent one.
6. Verify the GitHub Actions secret metadata and environment policy
   using a permitted repo-admin view or a separately reviewed
   administration check. Our current GitHub connection **cannot
   inspect environment configuration or secret names**, so the
   external configuration remains unverified.

## Required 13 workflow-file changes — NOT APPLIED

All 13 LIVE-credential workflow files currently have **one credential
job each and zero job-level `environment:` assignments**. Each
credential job must receive the exact binding:

```yaml
jobs:
  existing-job-id:
    environment: fund100-live-broker
    # preserve existing runs-on/steps/capability gates
```

`fund100_live_workflow_mutex_audit_v1_0.py` now fails on the lack of
this exact binding. The original proposal also requires **bootstrap
and V5 production** to share root-level
`concurrency.group: fund100-alpaca-live-account-writer`,
`cancel-in-progress: false`, and the exact job-level
`if: github.ref == 'refs/heads/main'` guard. Thus the protected YAML
release needs 13 environment bindings plus 4 writer-specific
mutex/branch adjustments, with all original arms, manifests, dollar
caps and broker kill switch unchanged.

Credential-bearing workflow names are fixed in
`CREDENTIAL_SCRIPT_BY_WORKFLOW`, including the 11 currently
non-order-writing preparation/research/read-only consumers. Giving
those jobs the same environment does **not** authorize them to place
orders. The actual isolated LIVE keys should ideally be split later
into genuinely read-only versus write-capable provider credentials if
the brokerage supports suitable key-level permission constraints.

## Independent release evidence (still missing)

GitHub Actions YAML scanning proves only the **stated job binding**.
It **cannot verify** the environment Settings or identify every
repository/organization secret from public workflow text. The release
must stay blocked until an authorised repository admin verifies:

- `fund100-live-broker` configured with exact `main` branch policy;
- only environment-level copies of LIVE credential names remain;
- optional reviewer/bypass policy is decided explicitly;
- off-`main` jobs are actually denied access in a harmless,
  **no-secret-printing and no-order** controlled test;
- review of any other repository or external Alpaca account writers;
- the original layered LIVE static audit and strict step/mutex guard
  are both run, with all intended tests passing;
- proof of kill-switch, account/position/order reconciliation and
  pilot capital limits before separate operator order authorisation.

**Never put a real API key in a GitHub issue, PR, test fixture, chat
message, or screen capture. Never disengage the kill switch merely
to turn a CI check green.**

GitHub's documentation:
- https://docs.github.com/en/actions/concepts/workflows-and-actions/deployment-environments
- https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments
- https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments

Related drafts: [#5](https://github.com/nicobouch97/fund100-research/pull/5)
(writer/mutex scanner), [#6](https://github.com/nicobouch97/fund100-research/pull/6)
(legacy audit adapter), and open [security gate #3](https://github.com/nicobouch97/fund100-research/issues/3).
