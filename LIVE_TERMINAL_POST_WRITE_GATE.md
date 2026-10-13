# Fund-100 — terminal Alpaca LIVE POST write-sink release gate

**13 October 2026 — review-only finding. No LIVE trades or deployment.**
Draft security [PR #7](https://github.com/nicobouch97/fund100-research/pull/7)
remains stacked on drafts #6 and #5. Production `main` has not changed.

## Confirmed gap

The normal order-writing code paths in bootstrap and V5 production
check policy, cap and the *process-local* `FUND100_BROKER_KILL_SWITCH`.
But **both ultimately call the same
`fund100_live_bootstrap_v1_0.live_request`**.

The shared `live_request(method, path, body)` function currently:
- accepts `POST` as a generic HTTP method;
- accepts a URL path starting with `/`, without restricting a POST
  to exactly `/v2/orders`;
- constructs `urllib.request.Request` and calls `urlopen`
  without a **terminal kill-switch check**.

This is a **missing defense-in-depth at the final broker-writing
transport**, not proof a normal approved controller bypasses its
higher-level authorisation, nor evidence an actual trade occurred.

In an **offline synthetic test**, `urlopen` is replaced by a fake,
never a network client. The fake observes a POST even with
`FUND100_BROKER_KILL_SWITCH=ENGAGED` when the transport is invoked
directly. A second synthetic test shows the transport would accept
a different POST endpoint. Neither test makes an Alpaca request or
uses a real secret.

## Review-only repair requirement

The last transport before real `urlopen` must independently enforce:

```python
# Suggested safety contract only; NOT applied to executable writer.
if method == "POST":
    if path != "/v2/orders":
        raise LiveBootstrapStop("Unsupported LIVE POST path")
    if (
        os.environ.get("FUND100_BROKER_KILL_SWITCH", "")
        .strip().upper() != "DISENGAGED"
    ):
        raise LiveBootstrapStop("LIVE kill switch engaged")
```

This must run **before creating/sending the HTTP request** and in
addition to—not in place of—higher-level release-lock, operator
arm, event, cash, shorting, cumulative-cap, idempotency, account
identity and workflow environment restrictions.

`fund100_live_terminal_write_guard_audit_v1_0.py` examines
the actual two writer source trees as AST. It requires this direct
pre-request POST path/kill guard, exactly the documented `/v2/orders`
order POST callers, and unchanged reviewed Git blob hashes. The
current baseline is **expected to FAIL**, proving the proposed
security control is not present. Synthetic tests verify that an
**in-memory only** insertion of the two checks would satisfy the
logical guard (with hash repinning disabled for the simulation only).
A later separately approved writer-code security patch must refresh
the pinned source hash after independent review.

**This does not solve the separate in-flight emergency-stop problem.**
Even a new direct `os.environ` check sees the running process value,
not a later change in GitHub Settings. A separately tested remote
revocation/account freeze capability and broker-order reconciliation
are required before any autonomous funded-account release.

## Release state

Maintain all 17 existing protected-workflow blockers (13 environment
jobs, two mismatched mutexes, two absent branch guards), plus this
**terminal write-sink hardening** and in-flight revocation requirement.
The source-only gate does not attest GitHub Settings, external writers,
Alpaca account state or actual execution safety.

No writer source code, protected workflow YAML, GitHub settings,
credentials, broker positions or orders was changed by this proposal.
Keep `FUND100_BROKER_KILL_SWITCH=ENGAGED`.
