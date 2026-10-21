# V6-S1 production-state continuity gate: real READ-only first look (21 October 2026)

**Pre-registered, before implementation. NO production ledger creation/write, no Alpaca credentials/requests, no market activity, no order release.**

## Actual prerequisite now passed
Original GitHub Actions manual run [#39600082142](https://github.com/nicobouch97/fund100-research/actions/runs/39600082142) proved the protected environment's private state **READ** PAT can authenticate private repo `nicobouch97/fund100-state-private`, exact immutable ID `1426833955`, and README via the original pinned 2-GET probe. [Run #39618444064](https://github.com/nicobouch97/fund100-research/actions/runs/39618444064) independently proved a **separate temporary sandbox WRITE** PAT can do one CAS update and reject stale writes. That test's permanent private synthetic sandbox file has sequence 1. None of these proves a funded-account-bound PRODUCTION order-state ledger.

On 21 October at 14:40 UTC, connected GitHub GET for `state/v6_s1_original_legacy_sales.json` on `main` returned 404: production ledger not yet created. This is intentional. No bootstrap from a missing file.

## Concrete first production persistence interface
Create a **read-only** narrow original `main` Actions access probe that:

1. Checks the original public repo identity, operator `trading_enabled=false`, `FUND100_BROKER_KILL_SWITCH=ENGAGED`, and exact source Git hash before receiving any secret.
2. Reuses the existing original immutable private repository identity/README two-GET read-only authentication with the existing `FUND100_PRIVATE_STATE_READ_TOKEN` secret. Then makes ONE additional exact allowlisted GitHub Contents GET to `https://api.github.com/repos/nicobouch97/fund100-state-private/contents/state/v6_s1_original_legacy_sales.json?ref=main`; nothing else. No read of financial account details, order receipts or quantity from Alpaca.
3. If the third response is 404, report `MISSING_OR_UNAVAILABLE_PRODUCTION_LEDGER_STOP`, always fail closed with zero writes and **no implied permission to bootstrap**. A 404 may be permission failure rather than absence; do not assert state nonexistent solely on API status.
4. If the file exists, it is **UNTRUSTED until externally pinned head Git blob SHA, sequence, independently generated genesis, original account binding, and an HMAC private key** are available. Never accept mere presence, arbitrary HMAC from repository itself or an auto-derived on-host key as sufficient.
5. Supply separate pure verifier which delegates to the original unchanged `fund100_v6_s1_private_git_cas_protocol_v1_0._read_source`; original Git bytes vs blob SHA and HMAC signature verification are mandatory. Require `expected_head_blob_sha`, `expected_sequence`, `private_genesis`, `account_binding_sha256`, HMAC `bytes >= 32` independently. A tampered head, rollback in sequence, changed account, missing genesis/key, malformed source or altered signature must fail closed. This is an **offline proof with synthetic anchors**, not a working actual LIVE anchor provision yet.
6. For present-but-unanchored data, report `PRESENT_UNANCHORED_PRODUCTION_LEDGER_STOP`, no public output of file/body/commit SHA, counts, account identifiers, private bytes or tokens. Do not treat successful private GET as state continuity.
7. PR unit tests only use fake HTTP transports and synthetic HMAC-signed ledger fixtures; LIVE/principal Actions secret job is main-only and uses **existing READ PAT**, no production/sandbox WRITE token. Merge will initiate one protected read-only inspection. The credentialed read-only main job records only categorical status. Any original job failure/401/403 remains a hard failure (not false success).

**When the production ledger is actually authorized to be initialized later**, a separately reviewed genesis/expected SHA must be anchored outside the mutable private state file, tied to **fresh genuine Alpaca LIVE binding and settlement/account risk state**, with a reviewed minimum-permission production writer and explicit release decision. GitHub Contents CAS resists stale concurrent writers but does not protect against privileged rollback or prove broker fill. Missing ledger -> no LIVE sells/buys. Avoid spending time on broad extra market research while this path is open.

Original V6-S1 95% entry proposal, $130.30 maximum cap, HIGH risk, operator STOP, kill ENGAGED, old holdings and all LIVE writer permissions remain untouched. No user credential contents printed.
