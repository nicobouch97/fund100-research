# Fund-100 LIVE emergency-stop and order-risk contract review

**13 October 2026 — SECURITY REVIEW ONLY, NO LIVE ACTIVATION.**

The broker kill switch last verified in an Alpaca read-only workflow was
`FUND100_BROKER_KILL_SWITCH=ENGAGED`. This file **does not** independently
re-query the current GitHub setting or actual Alpaca account positions.
Production `main` has not changed. LIVE release remains BLOCKED.

## Code-level controls inspected

Two confirmed real Alpaca order writers:
`fund100_live_bootstrap_v1_0.py` and
`fund100_live_production_controller_v1_0.py`.

- Bootstrap `require_environment()` refuses to start unless the
  `FUND100_BROKER_KILL_SWITCH` process environment is `DISENGAGED`,
  explicit bootstrap arm is `YES`, and further policy and artifacts
  validate. Its order submission reconstructs client-ID history,
  counts submitted notionals against the standing pilot policy
  ceiling, and rejects unknown/terminal-failed order statuses.
  This review does NOT authorise a repeat bootstrap.
- V5 production additionally checks that local environment switch is
  `DISENGAGED` before each *new* POST in `submit_order_batch()`.
  It reconstructs orders by deterministic client IDs, validates
  event-gross notional against the pilot cap, and rejects a BUY phase
  exceeding **fresh account cash**, not available margin buying power.
  Current policy also disallows shorts and leverage.
- Both are dependent on **the same Alpaca LIVE account** and therefore
  require a single shared account-writer lock, protected credentials,
  actual broker reconciliation and explicit future release review.
  Source-level guards cannot prevent unknown external writers.

## Critical limitation: not a real-time revocation

The existing workflow YAML evaluates
`FUND100_BROKER_KILL_SWITCH: ${{ vars.FUND100_BROKER_KILL_SWITCH }}`
as a job environment value. Both writer scripts read **local**
`os.environ`. Once that process has started, changing the GitHub
repository variable is **not a real-time revocation** mechanism and
does not push a new value into the running Python process.

Thus a later operator change to **ENGAGED** must not be assumed to
interrupt an already-running writer. In particular:

- The bootstrap initial guard is not re-read before each POST.
- The V5 production per-order recheck reads **local process state**,
  not a fresh remote GitHub API value. It does not prove that a
  subsequent GitHub Settings change was observed.
- Engaging the kill switch **does not cancel open broker orders** and
  **does not liquidate existing positions**. Cancelling a GitHub
  Actions run can terminate its software process, but cannot undo
  a POST already accepted by Alpaca.

These are release/operating limitations, **not evidence of an order
currently executing**. The last verified account read-only check
(13 October 2026) found four positions and zero broker-held open
orders at that earlier instant. That is not a current snapshot.

Official GitHub documentation:
- https://docs.github.com/en/actions/concepts/workflows-and-actions/variables
- https://docs.github.com/en/actions/reference/workflows-and-actions/contexts
- https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-cancellation

## Contingency procedure for the authorised human operator

**Only when an actual emergency is occurring**, and without
disengaging any safety control or supplying secrets to chat:

1. Immediately set the GitHub repository variable
   `FUND100_BROKER_KILL_SWITCH` to **ENGAGED**. This prevents
   correctly gated *future* work, not guaranteed in-flight work.
2. In GitHub Actions, identify any **running or queued** production,
   bootstrap or other credential-bearing job. Cancel jobs with
   write capability as appropriate and confirm their final status.
   Cancellation may interrupt code during broker reconciliation;
   do not then assume the account is flat or consistent.
3. Inspect Alpaca **LIVE** (not Paper) directly for broker-held open orders,
   recent submissions, fills, cancellations,
   buying power, positions, and account equity. Handle unwanted
   open orders via authorised Alpaca controls, and verify actual
   cancellation acknowledgements/fills. Do not automatically
   liquidate positions or attempt an order in this document.
4. If active credential compromise is suspected, handle API-key
   revocation/rotation with the broker and GitHub security admin
   directly, maintaining the trading hold. Coordinate with any
   independent processes also using this account.
5. Reconcile all resulting partial fills, positions and broker
   order IDs before a reviewed incident closure. Do not restart
   a writer just because a GitHub run was cancelled.

These are **operator contingency steps**; they have not been executed.

## Mandatory prospective release work

1. Keep all 17 currently identified workflow protections blocked:
   13 protected GitHub Environment bindings, two shared writer
   mutexes and two exact `main` job guards.
2. Separately confirm the Environment's exact `main`-only deployment
   restriction, environment-scoped secrets only, absence of
   repository/organisation duplicates and other external writers.
3. Agree a **tested live-writer emergency-stop design**, with
   bounded in-flight order risk and explicit broker-level
   verification. A short-lived permit or independently
   revocable execution authority may be appropriate, but neither
   can be assumed to exist today and must not be implemented
   as an unauthorised production change.
4. Independently test the bootstrap/production long-only, cash-only,
   order-recovery and pilot-ceiling controls under no-network
   synthetic scenarios before any order permission is granted.
5. Keep the funded pilot's explicit capital policy unchanged
   (historical `$130.30` cap, not a request to increase it).

**No credential, order, workflow, production file or broker state was
changed by this review. This is not permission to trade.**
