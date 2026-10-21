# Fund-100 V6 launch evidence — private Actions read proof gate (21 October 2026)

**Pre-registered before implementation. Read-only, no broker credentials, no trading permissions and no instrument approvals.**

## Why this is now the critical path

S1 has already proven a real $2 **PAPER** fractional BUY/SELL round trip, with holdings restored, in authenticated GitHub [run 39269640353](https://github.com/nicobouch97/fund100-research/actions/runs/39269640353). The private state repository's *GitHub connector* has also demonstrated non-production conditional SHA updates and a rejected stale-write conflict; see original `research_lab/V6_S1_REAL_PRIVATE_GIT_CAS_SANDBOX_AND_READ_TOKEN_PROBE_2026_10_21.md`.

What remains **not established by those facts** is whether `secrets.FUND100_PRIVATE_STATE_READ_TOKEN` within GitHub Actions' protected `fund100-live-broker` environment can make even an authenticated private repository read. The original proof workflow is `.github/workflows/fund100-v6-s1-protected-private-readonly-proof.yml`, which has a credentialed job **only on manual workflow_dispatch from main**. A successful pull-request *offline* test does NOT prove protected-environment access.

The original LIVE broker still holds four ETFs (ACWI, EEM, XLE, XLV at the last verified state), requires original capital limit **$130.30**, user HIGH risk, staged legacy sell before buy, actually verified cash/settlement and durable order journaling. This report does NOT update those holdings or prove settled cash.

## Deterministic proof acceptance

A new **unprivileged research-only** GitHub Actions status workflow may use solely the GitHub Actions `GITHUB_TOKEN` with read-only `actions:read` permission to list runs for the **one exact** protected workflow and read the exact latest manual run's jobs. No protected environment, no Alpaca credentials, no FUND100 private state token; no private-repo GET.

Proof is `VERIFIED_PROTECTED_ACTIONS_PRIVATE_READ` ONLY if:
- Repo identity `nicobouch97/fund100-research` and GitHub workflow filename are fixed and unchanged;
- GitHub Actions API shows the **most recent eligible** `workflow_dispatch` run on `main`, originating no earlier than the 21 October proof deployment, `completed / success`;
- The **protected** job named `protected-main-private-get-only` itself completed successfully, with BOTH original locked-source/STOP validation AND `Authenticate private repo identity and README only (redacted two GET)` AND post-check STOP steps all **success**;
- The credentialless offline source-contract test job also completed successfully, and the verified manual run is not merely a PR, scheduled event, wrong ref, other job, or a run that skipped the protected step.
- A missing, denied, malformed, failed, cancelled, or still-running API result explicitly returns `NOT_PROVEN` or `EVIDENCE_UNAVAILABLE` instead of manufacturing success.
- If a newer eligible manual run fails, report NOT PROVEN even when an older run succeeded; never cherry-pick a passing result. The most recent Actions run is sorted using its returned created timestamp and run ID (not by arbitrary iteration order).

The reporter always distinguishes:
**protected read access proven** from **write access proven** (NO), **remote production CAS proven** (NO), **broker settlement proven** (NO), and **LIVE orders released** (NO). Even a successful read proves nothing about trading authority.

## Operator workflow still manual

One-time protected credentialed probe is intentionally **not** re-triggered or automated by this read-only reporter. Run:

1. https://github.com/nicobouch97/fund100-research/actions/workflows/fund100-v6-s1-protected-private-readonly-proof.yml
2. Select **Run workflow** and branch **main**.
3. No user inputs and no LIVE orders.

The new report is separately runnable on `main` and is run once on merge. Use the GitHub Actions job artifact for a sanitized, permanent-after-merge snapshot of the proof state. After running the protected probe, the user can re-run the unprivileged status job on `main`. Do not persist a private token, balances, order identifiers, private repository data or unredacted API responses into reports.

The original private Actions token can only be meaningfully verified by its own protected job. This reporter does not create or dispatch that job.

## Tests and non-goals

Artificial fixtures must reject a PR run, a success with protected job missing/skipped, a failed auth step, wrong main/ref, wrong repo, later failed attempt overriding previous success, missing/invalid API, malformed data and stale dates. Original V6-S1 manifest, operator STOP and kill switch stay unchanged; no writes to protected/private state or Alpaca. Avoid broad changes to V5/ETF cash policy, trading engine, commodity/bond research code or asset authorisations.
