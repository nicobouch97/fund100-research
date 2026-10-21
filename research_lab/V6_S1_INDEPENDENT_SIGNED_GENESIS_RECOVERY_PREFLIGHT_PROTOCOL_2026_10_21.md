# V6-S1 independent genesis readback/recovery verifier — 21 Oct 2026

**Pre-register before code/tests. OFFLINE mocks on PR. A MANUAL read-only recovery workflow may run only AFTER an independently reviewed one-time signed production genesis (#105) is actually completed and its public issue-8 witness comment ID + genuine Actions genesis run ID are known. No private write, no Alpaca GET/POST, no trading-authority changes.**

## Purpose and evidence
The bootstrap (PR #105) may create `state/v6_s1_original_legacy_sales.json` in private `nicobouch97/fund100-state-private` and publish a **SHA-256 commitment** to its initial Git blob in an independently stored, but editable, public issue #8 comment. We need proof from a *new* Actions process that the HMAC-signed private contents, exact Git blob SHA, original public nonce, original account-binding SHA, expected empty `sequence=0` and the precise independently retrieved public comment agree. This MUST NOT be treated as a permanent anti-rollback anchor: GitHub issue owners can delete/edit comments; SHA256 commitments are not independent signatures, and post-genesis state advances need their own external anchor policy.

- Original pinned V5 LIVE account binding and public nonce: `fund100_v6_s1_public_genesis_witness_v1_0.verify()`.
- Original private protocol: `fund100_v6_s1_private_git_cas_protocol_v1_0._read_source`, which enforces exact Git blob SHA and HMAC of a signed ledger.
- Current one-shot bootstrap `fund100_v6_s1_one_shot_private_empty_genesis_bootstrap_v1_0.public_head_commitment` and `public_comment` provide the precise original commitment.
- Original protected private READ PAT `FUND100_PRIVATE_STATE_READ_TOKEN` and original confidential HMAC key `FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX`. **Not** the production/SANDBOX WRITE PAT and no Alpaca credentials.

## Exact acceptance
A recovery verifier does only four allowlisted REST **GETs**: original private repo identity + README with original read-only token; private original production Contents GET on main; exact public issue-comment GET by numeric ID with the public GitHub Actions token. All response sizes bounded, fail-closed on 404, denied/timeout/redirect/unknown path, no state auto-create. Public comment must:
1. come from the real GitHub Actions bot account with exact public issue URL and unchanged text as rendered by bootstrap;
2. contain ONLY the exact original digest computed from a separately verified private original Git blob SHA and public nonce, a supplied legitimate `https://github.com/nicobouch97/fund100-research/actions/runs/<id>` link and sequence=0;
3. have the exact supplied numeric comment ID and be retrieved independently, not trusted from a prior run.

The private original document MUST have sequence=0, `entries={}`, `prior_document_sha=None`, exact original signed migration and real account binding. A later sequence>0 indicates future legitimate writes not covered by this genesis-only gate and MUST fail closed until there is a new independent external head anchor; do not incorrectly mark ongoing trading/recovery safe.

Report categorical status only: `GENESIS_CONTENT_AND_PUBLIC_HASH_WITNESS_RECONFIRMED_READONLY`, broker requests 0, private GET 3, public GET 1, private writes 0, Alpaca orders 0, LIVE release false. No HMAC/nonce/binding, raw private SHA, JSON, token, private account quantities or contents logged/artifacted.

The new PR workflow runs **only fake-source unit tests**, never authenticates secrets on PR. Manual main read-only workflow dispatch requires `comment_id` and `original_bootstrap_run_id` supplied *after* the one-time signed genesis has actually completed, fixed STOP/HIGH/kill, vetted exact module blob SHA. It has no schedule or push secret job, no broker keys and no Github write permissions. The same original launch safeguards remain intact.

## Failure tests
Fresh unit tests: valid exact source and public witnessed digest; HMAC wrong/missing; Git blob tamper; wrong account genesis; future sequence; private state missing; corrupt source; deleted/edited comment; wrong author/issue ID/body/link; direct URL injection; duplicate secret reuse; zero brokerage/write capability. Work may be merged BEFORE operator provisions production secrets; it MUST NOT create or infer the missing production file, and must never mark the LIVE pilot released.
