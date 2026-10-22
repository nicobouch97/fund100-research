# V6-S1 — exclusive original ACWI owner fence protocol (22 October 2026)

## Precise problem

The current original HMAC-signed private order ledger produces byte-identical sequence-2 `POST_MAY_HAVE_BEEN_SENT` proposals when two runners read the same sequence-1 reservation. GitHub Contents conditional writes reject one runner, but if the response is lost, re-reading an identical blob cannot independently prove which runner wrote it. Before a funded first ACWI sale, a runner-specific durable ownership claim is needed to prevent both contenders from interpreting the same sequence-2 blob as their own successful write.

## Reviewed design candidate

The new pure module `fund100_v6_s1_acwi_unique_owner_fence_offline_v1_0.py` models a *separate* HMAC-signed first-order fence at `state/v6_s1_first_acwi_execution_owner_fence.json`. That file has **not been created in the actual private repository**. No LIVE order mechanism uses it.

An independently authenticated future owner would claim the initial fence with a single GitHub Contents SHA compare-and-swap and an original-workflow-specific identity: Actions run ID, run attempt, 256-bit unpredictable per-run nonce commitment, checked main revision, authentic original broker read run ID, original signed seq1 reservation SHA, computed seq2 SHA, and a commitment to the deterministic ACWI client-order ID. The claim is HMAC-signed with a separate domain and canonical exact bytes.

Two runners reading the same genesis fence produce different prospective claim hashes. In synthetic tests only one fake conditional Git update wins. A losing runner cannot authenticate the winning signed owner claim. A winning runner losing the write acknowledgement can identify its own claim on a subsequent read, but **this cannot itself grant permission to submit or resubmit an order**. Claims are never auto-expired or transferred. Unknown source, a wrong quantity, nonce, Git head, broker run or public witness all stop.

## Scope and necessary further work

- Entire feature is **offline only**. No production fence setup, Git writes, Alpaca GET/POST, secrets, automatic token creation, new order workflow, operator or risk permission, or mutation to the already SHA-pinned signed original ledger.
- Original private production ledger remains at signed sequence zero. The six reviewed writer locks and original stop remain engaged. This feature must not be used to justify activating them.
- A separate signer/reader for a real fence must be reviewed, guarded by verified private repo identity, exact source provenance, a protected single-writer GitHub workflow and current original account HIGH risk / $130.30 pilot cap.
- Git Contents SHA CAS is an atomic write check, **not an immutable external monotonic history**. A sufficiently privileged rollback could restore an earlier signed file. Independent rollback-resistant HEAD anchoring and source-age validation are mandatory before real execution.
- The existing actual ACWI SELL transport needs an explicit check of the independently authenticated owner-unique fence before one authorized broker POST; an isolated offline classifier does not bind a real transport.
- The full repository static LIVE audit and negative synthetic concurrency tests are required before merge.

This closes the *design and offline test* of ambiguous same-hash owner identification, not the complete real-world exclusivity guarantee.
