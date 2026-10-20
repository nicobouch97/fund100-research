# Fund-100 V6-S1 — actual GitHub Actions PRIVATE state READ token, source-frozen pre-registration

**2026-10-20, user confirms** `FUND100_PRIVATE_STATE_READ_TOKEN` was added as an environment secret to `fund100-live-broker` in the PUBLIC `nicobouch97/fund100-research` repo; actual value cannot be read by the GitHub connector. **First authenticated read from GitHub Actions is NOT YET PROVEN** before the workflow runs.

Prior evidence:
- New separately provisioned [`nicobouch97/fund100-state-private`](https://github.com/nicobouch97/fund100-state-private) exists and is PRIVATE, exact GitHub repo ID **1426833955**, main branch, and simple README accessible using the conversation's GitHub app.
- [PR #79](https://github.com/nicobouch97/fund100-research/pull/79) merged `fund100_v6_s1_private_state_actions_readonly_probe_v1_0.py` original immutable blob **e5553b27a6958f994732b41f533c0744cf2ef5ea**, two fixed GET only: repository metadata and `README.md?ref=main`; 19 source tests plus 18 private CAS planner tests. Original LIVE static safety audit postmerge [39433993856](https://github.com/nicobouch97/fund100-research/actions/runs/39433993856) passed.
- Existing LIVE trading account has operator **STOPPED**, broker kill `ENGAGED`, HIGH $130.30 pilot, still no V6 order release. The genuine LIVE broker order source [39317938514](https://github.com/nicobouch97/fund100-research/actions/runs/39317938514) returned original four holdings and three client-ID lookups not found; this is **not** proof no previous uncertain POST occurred.

## This PR scope

Introduce one source-reviewed, original-module-Git-blob-pinned, **main-only** protected Actions job to test that the new **read-only** GitHub fine-grained token indeed authenticates *from a GitHub runner* to exactly two nonfinancial GET endpoints on the separate PRIVATE repository. The job starts automatically on the first `main` push changing this new workflow and may be manually re-run for expiry/rotation; PR runs use synthetic contract tests only with **NO secrets**. The token is provided only to the single execution step in `fund100-live-broker`, is never logged, stored, printed or exposed to a command besides the exact vetted GET-only Python module. The regular `GITHUB_TOKEN` retains `contents: read` for this PUBLIC code repository and is NOT used for cross-repo private access.

**Static audit extension**: disallow any other workflow exposing `secrets.FUND100_PRIVATE_STATE_READ_TOKEN`; pin the exact reader Git blob SHA; insist on protected environment, first-party `main`, stop switch, only approved Python script executable, no branch PR credentials, no schedule, no trading enabling flags or script code changes. Negative mutation tests (workflow edits, credential redelegation or source changes) must STOP. Original production/global LIVE Alpaca permit pins remain unchanged.

## Deliberately excluded

- No GitHub private-repo PUT/POST, Git CAS state update, private production ledger initialization or account/quantity data reads.
- No change to genuine LIVE brokerage secrets, kill, remote operator, Alpaca API POST, position holdings, V6 S1 allocation, settled cash, $130.30 cap or risk limits.
- An Actions GET PASS will establish **cross-repo read connectivity only**. The remote CAS owner-write token, independent antireplay/genesis anchor and two-real-runner conflict proof remain to be engineered and approved separately.
- Any missing/expired/incorrect token, 401/403/404, wrong repo ID or unexpectedly public repo must fail closed without disclosing token or granting execution.

**Acceptance**: credentialless PR tests + global safety audit pass, merge, successful main Actions run with `private_repo_verified=True`, `github_get_requests=2`, `github_write_requests=0`, `broker_order_requests=0`, `live_trading_authorized=False`, then successful post-merge global audit. If access fails, report blocker honestly without weakening credential policy or requesting tokens in chat.
