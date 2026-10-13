# Fund-100 — last-mile Alpaca LIVE POST guard: draft-only repair

**13 October 2026 — proposed code change, not deployed. No LIVE orders.**
This file now accompanies the **separate draft repair PR**, stacked on
[security PR #7](https://github.com/nicobouch97/fund100-research/pull/7),
which is in turn stacked on #6 and #5. Production `main` remains
unchanged, with `FUND100_BROKER_KILL_SWITCH` expected ENGAGED.

## Observed baseline weakness

Both bootstrap and V5 production eventually use the shared
`fund100_live_bootstrap_v1_0.live_request` Alpaca HTTP transport.
On original `main`, the transport accepted POST to any leading-slash
path and did not independently inspect the process-local kill switch
before reaching `urllib.request.urlopen`. Normal callers contain
earlier operator, cap and kill-switch checks; the defect is a missing
independent final boundary, not proof of unauthorized trading.

## Proposed fix — isolated in this draft

Within `live_request`, before construction of the HTTP request and
before `urlopen`:

- Only the exact `POST /v2/orders` broker endpoint is permitted.
- POST refuses to proceed unless the **local process** environment
  `FUND100_BROKER_KILL_SWITCH` is exactly `DISENGAGED`.
- GET/read-only transport behavior and higher-level pilot policy,
  manifests, authorization, cumulative cap and risk constraints are
  otherwise unchanged.
- `fund100_live_terminal_write_guard_audit_v1_0.py` checks the
  precise AST structure and pins the changed writer's Git blob.
  A source modification without independent review fails the pin.

The tests replace `urlopen` with an in-memory fake. They assert
ENGAGED blocks before any fake network call, unknown POST endpoints
block even with an in-process test-only DISENGAGED setting, and an
approved POST can reach only the fake sink under test conditions.
**No Alpaca request or real account credentials are involved.**

## What this does NOT solve

The direct local switch check does not poll a remotely revocable
permit or automatically observe changes to GitHub Settings after a
job starts. It does not cancel already accepted Alpaca orders,
reconcile partial fills, eliminate outside order writers, isolate
LIVE secrets in protected GitHub Settings, or prove strategy alpha.
Those independent release controls and an operational emergency
stop still require formal review and tests.

## Separate release prerequisites

This draft must undergo independent review and be merged in an
approved sequence only when GitHub security environment controls
have been independently attested. On current production `main`,
the layered LIVE audit still reports the prior **18** release gaps.
If this draft guard is approved, the code-level terminal defect can
be removed from that list, but the **17 workflow** gaps and
settings/runtime operational gates still block launch.

Keep V5 repair PR #1 separate. Keep [master launch plan #8](https://github.com/nicobouch97/fund100-research/issues/8)
as the GO/NO-GO tracker. Do not unlock LIVE solely to validate this
fix or treat a green unit-test suite as trading permission.
