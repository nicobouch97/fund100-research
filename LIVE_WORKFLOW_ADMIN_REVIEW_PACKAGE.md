# Fund-100: administrator's protected-workflow security review package

**13 October 2026 — REVIEW ONLY. Not a release authorisation.** This
document accompanies [draft PR #7](https://github.com/nicobouch97/fund100-research/pull/7),
stacked on [#6](https://github.com/nicobouch97/fund100-research/pull/6)
and [#5](https://github.com/nicobouch97/fund100-research/pull/5).
All three remain unmerged. Neither GitHub protection settings nor
protected LIVE workflow files were edited by this package.

## Read-only release blueprint

File: `fund100_live_workflow_release_blueprint_v1_0.py`

The generator pins every one of the 13 known credential-bearing YAML
files to its *Git blob SHA-1* as observed on the original production
`main` commit:

`3dc2ccf77bd8e08089fbaddbf6977af2abbea511`

It refuses to generate anything if those files have changed and reruns
the strict supplementary scanner in memory before emitting a unified
diff. It requires exactly **13 job-level environment bindings**, **two
writer concurrency replacements**, and **two writer job-level main
guards**. It does not write to files.

To inspect the proposed text in an isolated checkout of PR #7:

```bash
python fund100_live_workflow_release_blueprint_v1_0.py
```

The output has a header declaring **NOT APPLIED**, the pinned baseline
commit, a SHA256 of the exact diff text and ordinary unified-diff hunks.
It contains workflow names and metadata only, not API keys. A reviewer
can redirect the output to their own temporary workspace for a proper
Git diff review; the generation command does not call GitHub APIs.

The independent regression
`test_fund100_live_workflow_release_blueprint_v1_0.py` checks the 13
pinned source blobs, deterministic output, exact 17 edits, strict
scanner acceptance of the *in-memory* proposal, rejection of source
drift and absence of any workflow-write or broker-client code.

## Required Settings change — external, not in the patch

The operator or approved repository administrator must first inspect
Settings -> Environments in GitHub. The connected assistant cannot
confirm or set these policies:

1. Create **`fund100-live-broker`** before referencing it in a
   workflow. Set **Selected branches and tags**, adding exactly a
   **Branch** rule `main` and **no other branch/tag rule**.
2. Verify both `ALPACA_LIVE_KEY` and `ALPACA_LIVE_SECRET` are stored
   as **environment-only secrets**. Do not expose or copy the values
   into chat, code, test fixtures, PRs, comments, job output, or logs.
   In particular, there must be **no remaining repo-level or
   organisation-level LIVE copies** accessible to untrusted workflows.
3. Decide any required reviewers/admin bypass policy with the
   operator; a reviewer and protected environment do not imply
   authorisation to submit LIVE orders.
4. Record independently verifiable, non-secret metadata for the
   deployment branch rule, environment existence, and absence of
   repo/org duplicate secret names. Do not assume the result can be
   inferred by the existence of `environment:` YAML alone.
5. Coordinate an intentional transition. Moving keys to the
   environment before adding all 13 job bindings will temporarily
   break those LIVE-credential workflows. This is acceptable only
   when deliberate and the kill switch remains **ENGAGED**.

GitHub documents that an unknown environment referenced from workflow
YAML can be auto-created **without branch restrictions or secrets**.
Therefore the administrator must first verify the intended environment
and its protections outside code. See:
https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments

## Exact proposed YAML delta — not applied

- All **13** credential-bearing workflow jobs: add exactly
  `environment: fund100-live-broker` beneath the job's runner
  setting, keeping the original name, trigger, arm and commands.
- `.github/workflows/fund100-live-bootstrap.yml` and
  `.github/workflows/fund100-v5-live-production.yml`: replace each
  workflow-level concurrency group with
  `fund100-alpaca-live-account-writer` and preserve
  `cancel-in-progress: false`.
- The same **two** writer jobs: add exact
  `if: github.ref == 'refs/heads/main'`. This guard is defense in
  depth **only**, because branch-controlled workflow YAML can itself
  change off main. The Settings-enforced branch rule plus
  environment-only credentials is the stronger access boundary.

No other file or trading setting is part of this patch. Do not apply
against a changed or rebased main without regenerating and re-reviewing
the source. In particular, never change the operator kill switch to
make a failed CI job green.

## Newly identified write-sink stop (independent from 17 YAML issues)

Source review found that the shared `fund100_live_bootstrap_v1_0.live_request`
accepts arbitrary POST paths and does not directly enforce the process
kill switch at the last HTTP request boundary. Normal bootstrap and V5
controller code have higher-level release/capability gates, but the raw
transport has no independent final STOP. See
`LIVE_TERMINAL_POST_WRITE_GATE.md` and the new
`fund100_live_terminal_write_guard_audit_v1_0.py`, which has been
integrated into the existing layered LIVE audit.

**The proposed 17-edit YAML patch is NOT sufficient for LIVE approval.**
A separately stacked **draft-only** writer-code change now proposes
the final process kill-switch / exact `/v2/orders` POST restriction.
Its source hash has been pinned in the draft terminal audit for code
review; production `main` is **not modified**, and no launch permission
has been granted. Any per-request check of local `os.environ` remains
distinct from real-time revocation across a running GitHub Actions
process. Neither that operational gap nor independent GitHub
environment/secret policy may be waived because tests pass.

## Independent acceptance evidence

The release candidate must satisfy all of the following **separately**:

- Reviewed source-code changes match the pinned proposal with no
  extra credentialed scripts or external actions.
- Repository/organisation secret-name metadata is checked by an
  approved GitHub administrator; no LIVE key aliases or copies remain
  outside the protected environment.
- A harmless off-main dispatch (without printing keys or touching
  Alpaca) is blocked by the environment branch rule. Admin confirms
  this from GitHub UI rather than relying only on a unit-test mock.
- No new workflow can gain LIVE API secrets without the protected
  environment; any standalone external Alpaca order writer is
  separately controlled or permanently disabled.
- Full `pytest -q`, the layered existing LIVE static audit and
  the supplemental strict mutex/step-scope audit all pass under safe
  test state. The currently red LIVE static audit is a **release stop**.
- V5 production's stale-manifest fix in draft PR #1 and pilot policy,
  notional cap, no-leverage/no-shorting, restarts and broker-state
  reconciliation receive independent confirmation before any
  separate operator decision to permit real orders.

**Release status: BLOCKED.** Passing an in-memory patch simulation
does not prove GitHub Settings, broker exclusivity or LIVE safety.
