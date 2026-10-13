# Fund-100 LIVE credential readers — transitive broker HTTP audit

**2026-10-13 — source review only; not a LIVE release certificate.**
Part of [draft security PR #7](https://github.com/nicobouch97/fund100-research/pull/7),
stacked on [PR #6](https://github.com/nicobouch97/fund100-research/pull/6)
and [PR #5](https://github.com/nicobouch97/fund100-research/pull/5).

## Why this extra review is necessary

The 13 workflows receiving real Alpaca LIVE credentials include **two**
confirmed order-writing entrypoints (bootstrap and V5 production) and
**11 other, intended non-order-writing entrypoints**. A script can be
read-only **in observed execution** but still import Python modules
containing a dormant live-order POST implementation. Therefore
classifying all 11 as proven incapable of writing merely because their
top-level scripts lack `Request(method="POST")` would be false.

Several of these scripts depend transitively on
`fund100_alpaca_live_writer_disconnected_v1_1.py`, which imports
`fund100_alpaca_live_writer_disconnected.py`. The latter contains a
real `urllib.request.Request(method="POST")` implementation, but its
`_post_live_market_order` and public
`submit_authorized_order_batch` functions currently call
`require_adapter_connected()` as their **first executable
statement**. That guard immediately raises `LiveWriterDisconnected`;
v1.1 delegates to the same hard stop. This is an intentional disabled
implementation, **not evidence that the POST code is absent**.

## Audited network transports

The currently reviewed entrypoint import closure includes these
explicit `urllib.request` implementations:

- `fund100_alpaca_live_readonly_smoke.py`: Alpaca trading API, literal GET.
- `fund100_live_pilot_prepare_v1_0.py`: Alpaca trading API, literal GET.
- `fund100_alpaca_live_scheduled_compiler.py`: Alpaca market-data API,
  literal GET (reached through the v1.1 compiler).
- `fund100_alpaca_live_writer_disconnected.py`: dormant GET and POST
  functions, both behind an unconditional disconnected-writer guard.

`fund100_live_broker_http_capability_audit_v1_0.py` recursively parses
local Python import dependencies as AST (no imports executed, no network
request). It pins all **five** reviewed transport/guard source blobs;
rejects newly referenced or missing internal files, unknown
`urlopen`/Request sinks, unexpected methods, dynamic imports and
subprocess-style transports; and validates the first-statement writer
hard stops in both disconnected modules. The negative test suite
mutates the sources in memory to show that removing an unconditional
raise, removing the first POST guard, adding an unknown POST or
removing an imported file is rejected.

The original `audit_fund100_live_boundary.py` now invokes this checker
as a **supplemental fail-closed gate** alongside the credential-scope
scanner from PR #5. Legacy independent restrictions remain intact.

## Explicit limitations

This is source-level evidence **only**. Static AST inspection does not
prove that every Python runtime can never import a different module,
monkeypatch a function, execute native extensions, gain credentials
through a different process, or issue broker orders through another
repository/local workstation. Nor does it verify GitHub Settings,
correct branch restrictions, environment-only secret placement, a
shared account-wide lock outside GitHub Actions, or a human LIVE trade
approval.

The pinned blob contract intentionally **fails when any reviewed
transport changes**, even innocuous comments, until a security
reviewer refreshes the expected source hashes with independent code
inspection. It cannot replace a live GET-only observation made under
a correctly scoped read-only test, and does not turn historically
disconnected code into a deployable trading adapter.

## Release state

The LIVE security release must stay **BLOCKED** until at minimum:

1. All 13 credentialed jobs use a verified main-restricted GitHub
   Environment with environment-only Alpaca secrets and no repo/org
   duplicates.
2. The two order writers share a noncancellable workflow-level mutex,
   preserve exact `main` job guards and authorisation inputs.
3. The new AST guard, strict step-scoped credential guard and original
   layered static audit all pass in the reviewed production commit.
4. Broker account binding, idempotence, cumulative notional cap,
   positions/open orders, absence of external writers, and operator
   order authorisation are separately verified.

No protected workflow files, GitHub Settings, keys, broker positions or
orders were modified in this review.

See [security release blocker #3](https://github.com/nicobouch97/fund100-research/issues/3).
