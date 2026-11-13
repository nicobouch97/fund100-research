# Fund-100 private STOP controller — locked source, not deployed

The project uses an existing protected GitHub emergency workflow to commit both persistent STOP latches and cancel only Fund-100 orders. Its receipt requires the **original GitHub dispatch run ID**, all three terminal successful jobs, both current-main controls, and fresh broker account + OPEN-order GET evidence. Workflow dispatch ACK is **not STOP completion**.

## Proposed private topology
- A separately isolated, **non-public**, continuously running Railway STOP-only worker; not the existing public diagnostic service. One replica, non-cron, restart always, no sleeping.
- A private persistent volume mounted at \`/data\` for SQLite full-synchronous one-attempt journal; no ephemeral fallback, no automatic redispatch after network uncertainty.
- Two distinct GitHub credentials: contents read-only for current-main STOP controls, and a narrowly managed Actions:write dispatch token. GitHub Actions:write is NOT intrinsically workflow-scoped, so the worker has a fixed exact STOP endpoint, no arbitrary URLs, ref, or inputs. Protect the Actions credential with repository/app policy, environment isolation and tight expiry.
- **No Alpaca key** (including a software “read-only” alias of a full-scope trading key), **no Ed25519 signer key**, **no trading intent writer** in this worker. No inbound HTTP listener or public domain. All returned statuses deny new trading authority.
- Existing broker-protected STOP workflow runs cancellations. A separately protected exact-run verifier must fetch the original workflow result + fresh account and broker open orders. This worker does not and cannot claim those confirmations.

## Current limits (deliberate safety locks)
\`SOURCE_RELEASED=False\` and \`STOP_DISPATCH_RELEASED=False\`; no private token, no database in production, no genuine STOP dispatch. Even if someone sets a Railway environment variable, it cannot override these source constants. Actual protected GitHub Actions job end-to-end STOP/cancel and credential isolation are **not proven**.

When a latch shows GO or its GitHub evidence cannot be verified, the code would (if separately reviewed and unlocked) persist one durable alarm and request the existing emergency STOP. While no signed risk receipt producer is integrated, it cannot approve a running system. Its same alarm stays permanently fenced after an ACK or unknown outcome; independently authenticated evidence and an atomic clear/re-arm recovery protocol must be developed before real unattended repeating operation. This first phase is intentionally safe but **not production-ready**.

A clean observed pair of STOP controls does not prove there are no broker open orders or fills, and never means risk PASS.

## Railway staged configuration (13 Nov 2026)
Project: \`fund100-risk-monitor-research\` / development. Staged service: \`fund100-private-stop-controller-staged\`, single replica in SFO, always-on restart policy, no cron, private network DNS, no public domain. Staged 128 MB durable /data volume; nothing has been committed/deployed. A reviewed service-to-GitHub source connection and correct Dockerfile path are still prerequisites. No secrets have been provisioned.

## Release requirements
1. Exact-head scoped offline adversarial tests + terminal full LIVE Static Safety Audit; protected-main merge and postmerge audit.
2. Reliable controller uptime, independent watchdog/failover and explicit outage escalation, not mere cron declarations.
3. Protected secret provisioning and actual Actions dispatch **only after** policy/cost review, no per-trade approvals.
4. An append-only authenticated journal that binds detection alarm, exact run ID and protected actual STOP + broker cancellation evidence. The current SQLite-first fence is only a safe un-retryable source contract.
5. Signed genuine independent broker-risk freshness and a failsafe veto at every real trade; no GO path in the STOP controller.
6. Original $130.30 pilot cap, HIGH risk limits and V5/V6 STOP + broker kill remain unchanged until a separately audited limited release.

Offline test: \`python -m pytest -q test_fund100_private_stop_controller_locked_v1_0.py\`.
