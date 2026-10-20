# V6-S1 — dedicated PRIVATE GitHub state repository verified (20 October 2026)

## Authenticated facts and scope

- [Private `nicobouch97/fund100-state-private`](https://github.com/nicobouch97/fund100-state-private) **EXISTS** (GitHub repo ID 1426833955), visibility **private**, default branch `main`, not archived.
- Existing connected GitHub account can read the new private repo's `README.md`. Separate existing `nicobouch97/fund100-research` remains **public** by user choice.
- The GitHub app metadata reports repository push eligibility, but an attempted real create of a harmless private canary and README update from the chat **were blocked by the platform's safety controls**; **NO private remote write or CAS conflict test occurred**. This limitation must not be disguised as GitHub API 409 proof.
- Original 19 October [LIVE static audit 39319145214](https://github.com/nicobouch97/fund100-research/actions/runs/39319145214) succeeded. Later [V5 LIVE production 39338220340](https://github.com/nicobouch97/fund100-research/actions/runs/39338220340) returned `TRADING_STOPPED_BY_OPERATOR` and zero orders; genuine original V6 [client-ID lookup 39317938514](https://github.com/nicobouch97/fund100-research/actions/runs/39317938514) found no orders for three planned exit client IDs. This is NOT future authorization or never-POSTed proof.

## Next first-party GitHub Actions read-only access boundary

A new pure offline / GET-only helper `fund100_v6_s1_private_state_actions_readonly_probe_v1_0.py` accepts a short-lived in-memory repo-read token, allows *exactly two GET URLs*:
1. Repository metadata for `nicobouch97/fund100-state-private`;
2. `README.md` on its `main`.

It checks exact owner/name/id, private visibility and README metadata. It never requests financial state, Alpaca endpoints, HMAC, balances or trading data, never sends PUT/POST and prints privacy-safe booleans only. It has synthetic negative tests for wrong host, wrong repo, private->public, wrong ID, timeout, bad token and unauthorized path.

This PR intentionally does **NOT** install a credentialed Actions workflow: that attempted credentialed write was denied by the connected tool safety boundary. Independent GitHub Actions cross-repository authorization has NOT been tested. Do not treat private repo read access through this chat as Actions workflow credential access.

## Required for genuine remote persistence

A future separately reviewed job will need user-established *least-privilege authorization* to this new private repository, not to all personal repos, private storage state genesis, independent rollback anchor and original security audit scope. In GitHub Free, prefer keeping the existing PUBLIC strategy repo and protected `fund100-live-broker` environment unchanged. **Do not share any PAT, Alpaca key, account ID, HMAC key or positions in the chat.** Never deploy LIVE orders until remote compare-and-swap conflict and crash recovery genuinely pass from two independent runners, original live V6 HIGH risk release and T+1 sale-cash gate are approved.

$130.30 pilot capital, original HIGH profile, broker kill ENGAGED and main operator STOPPED remain unchanged. **Zero LIVE orders requested or submitted in this phase.**
