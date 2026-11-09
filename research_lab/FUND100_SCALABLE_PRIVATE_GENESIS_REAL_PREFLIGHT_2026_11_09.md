# Fund-100 — protected real private funding genesis readiness (GET only)

9 November 2026 | Zero capital expansion, zero broker orders, zero private writes.

## Why this check is needed

The 9 November protected Alpaca funding-history run #42683146607
verified an account-creation-derived query boundary, three account
activities, and gross deposits ABOVE the original $130.30 pilot cap.
Neither those historical activities nor the original ETF holdings
authorise a new purchase, first sale, or use of excess deposits.

PR #597 added a synthetic signed HMAC/CAS private principal protocol.
PR #598's independent HEAD fixtures are still under review. Neither
created the private production funding ledger.

The existing private repository is repo ID 1426833955 with three older
trade-state files. The new namespace state/scalable_contributed_principal.json
was absent from its listed state directory on 9 November.
The separate public recurring-trade release asset #688837795 is actually
provider-immutable but explicitly protects only the older recurring
trading-state journal. It CANNOT authorize a capital ledger.

## Main-only actual-source preflight

A protected Actions job first runs no-credential tests, pins the exact
script Git-blob hash and enforces HIGH risk tier, V5 and V6 STOP, and
broker kill ENGAGED before any secret-bearing step.

It then uses two existing distinct private GitHub principals:
FUND100_PRIVATE_STATE_READ_TOKEN and
FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN, strictly as GET credentials.
Each checks exact private repository identity, ID, visibility, main branch,
and the capital state file's Contents metadata. Both principals must
agree on a missing file or the identical current Git blob SHA; any
401/403/uncertainty or disagreement hard-stops. No writes are enabled
despite the second credential's separate private repo permission.

The job independently GETs the existing other-namespace public immutable
release metadata without any credentials, verifies the specific release
ID, asset ID, digest, immutable/draft flags. This is ONLY evidence that
the pre-existing GitHub immutable release facility can be used. It is
NOT a signed capital ledger genesis nor a fresh provider head for funds.

No Alpaca requests, no private contents, account details, cash values,
financial records or credentials are published or persisted. The only
possible outcomes, both non-tradable, are a missing private capital file
or a present BUT UNANCHORED private capital file.

## Remaining actual production work

1. Independently sign and provider-immutably anchor an original
   capital-ledger genesis using real separate production signing custody.
   A missing file must not trigger automatic unreviewed initialization.
2. Prove full actual broker account funding/transfer/corporate-action
   history, exact USD settlement and portfolio cashflow attribution.
3. Bind production private Git CAS to a verified current immutable
   capital head on EVERY revision, including uncertain commit recovery.
4. Obtain an explicitly bounded owner-approved standing capital mandate
   before expanding beyond the original $130.30 cumulative limit.
   Qualifying within-mandate future deposits then need no repeated
   approvals. Owner controls remain simple risk tier and emergency STOP.

Original $130.30 pilot, $65 ticket cap, ENGAGED broker kill, both STOPs,
blocked ACWI first sale and all LIVE order writers are unchanged.
