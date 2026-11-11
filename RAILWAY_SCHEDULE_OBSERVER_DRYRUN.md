# Fund-100 independent Railway observer — dry run only

**Purpose:** establish a no-secrets, non-trading, external process that reports whether GitHub has actually recorded a recent scheduled run of the legacy Fund-100 risk-watch workflow. This probes a real operational dependency missing on 11 November 2026. It is NOT a financial risk monitor and it NEVER emits an order authorization, broker account value or verified risk PASS.

## Boundaries

- Exactly one unauthenticated public GitHub REST GET every 600 seconds, with a 12-second timeout, a bounded response and redirects denied.
- Reports `SCHEDULE_RUN_RECORDED_NOT_RISK_PASS`, `SCHEDULE_ACTIVITY_STALE`, `NO_RECORDED_SCHEDULE_RUN`, or `SOURCE_UNAVAILABLE`, and prints an UTC timestamp in a small JSON line.
- No Alpaca credentials, broker network calls, GitHub writes, repository private state, secrets, order submission, order cancellation, or GO/STOP mutation.
- Docker image copies **only** the observer file and runs as an unprivileged user; nothing else from this repository is present in the image.
- Railway project: `fund100-risk-monitor-research`, environment `development`. Service is staged-only and intentionally unconnected to a source until the prototype is separately tested. No deployments, no volume, no hostname, no database, no paid plan change.
- Public GitHub API anonymous rate limits and possible GitHub API outages are expected; errors are diagnostic and cannot promote evidence. Railway process uptime and logs alone are not an independently attestable durable heartbeat.
- A recorded cron event is NOT evidence that broker GETs occurred. An absent event is NOT a market exposure measurement. No financial safety permission should ever depend on this prototype directly.

## Offline test

`python -m pytest -q test_fund100_railway_schedule_observer_dryrun_v1_0.py`

## Future review prerequisites before broker-aware external risk monitoring

- Separate read-only Alpaca OAuth app approved and tested in a restricted environment; NEVER copy existing full-trading keys.
- Authenticated, tamper-evident, durable receipt visible to the order executor and independent observer; stale/missing/failing evidence must veto all new orders.
- Existing open orders must have a separate, narrowly scoped automatic cancellation mechanism and a verifiable durable V6 STOP.
- Exact original four-holding V6-S1 checks are only valid before the first sale; portfolio-aware ongoing monitors are separate work.
- End-to-end market-session outages, V5 historical STOP, V6 GO/STOP, failover, ambiguous cancellation, latency, economics and signed-ledger safety tests.
- Explicit deployment-cost inspection before enabling any paid running service, and verification of the complete live safety audit before any change to order permissions.

This is a credential-free **prototype**; it cannot substitute for independent live broker account risk surveillance.
