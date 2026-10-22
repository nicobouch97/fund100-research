# V7-E5 — frozen prospective event signals versus independently later price-vintage marks

**Preregistered 22 October 2026. READ ONLY. No broker GET/POST, private ledger writes, allocations, liquidation, LIVE releases or alpha claims.**

## Evidence and purpose

- V7-E3's original 15 Oct SEC and 17 Oct price archives had ZERO genuine post-15 Oct Item 2.02 events and ZERO eligible source-bound signals. The later vendor revised the original P4G historical prefix, so E3 **correctly refused** to repair its immutable original chronology using later adjusted close history.
- V7-E4 added separately dated, archived SEC raw submissions and T+1 adjusted public-price snapshots, with original per-issuer SEC CIK/SHA and price JSON/CSV hashes; those are a *potential* future source of truly pre-entry observed signals. The first actual scheduled run's evidence is **not yet verified** in this protocol.
- V7-E5 compares **two successful main-branch E4 captures** from different workflow runs. Choose the newest eligible earlier capture **solely by completed market-session chronology**, requiring at least two later completed price sessions in the latest genuine capture; never choose based on subsequent P&L or whether a particular name won. The earlier original SEC and earlier original P4G source must each pass all existing source authenticity checks. Reconstruct the earlier event-screen statuses from those original bytes; never select event winners from a later source.
- The later P4G observation must independently validate its source JSON + canonical adjusted-close CSV + time. The entire earlier session calendar must still be present; any changed historical prefix is labelled as vendor revision. Later source must have been captured after the earlier source.

## Precommitted illustrative return measure

The only eligible names are E4 originally screened unamended SEC 8-K Item 2.02 events with an **original-snapshot, 2 percentage-point stock-minus-SPY reaction** after the second completed post-filing session, acquired before model entry. A missing/late source cannot be retrospectively recreated from another vendor vintage. Contemporary quality is the frozen Oct 15 cohort, with the E4 90-day research expiry and exact eight-issuer coverage.

The **first newly completed trading session** after the early frozen price as-of date is the illustrative entry close, and the **second newly completed session** is the illustrative exit close. Never choose the last/best exit of many. With fewer than two complete later sessions, report NO RETURN rather than 0% or a paper fill. Use only these two price rows from a single **later** independently captured vintage to compute same-vintage stock and gross SPY hypothetical returns. Deduct 5, 15, and 35 basis points **per stock-trade side**, with spread, broker fees and fill effects unverified; SPY remains an **uncosted benchmark** and must be labelled as such.

If no frozen source-eligible events exist, report NO_GENUINE_PRE_ENTRY_EARNINGS_SIGNALS. If fewer than two suitable completed successful E4 archival captures with two genuinely later completed price sessions exist, the scheduled report instead states explicitly FEWER_THAN_TWO_SUCCESSFUL_GENUINE_E4_SOURCE_CAPTURES (an intentionally broad no-suitable-pair status).

This is not a point-in-time provider-corrected proof of profits, no original-vintage P4I hash repair, no unbiased historical event sample, no Sharpe/CAGR or guaranteed executable close. GitHub Actions artifacts retain original bytes for only 90 days. A separate later research decision may consider improving durable storage or expanding the contemporary issuer roster; no strategy self-promotion.

## Operations

The read-only E5 GitHub Actions job starts at **11:15 UTC on weekdays**, after the planned E4 09:15 UTC snapshot, and on first main branch push after approval. No external identities or broker secrets: only read-only GitHub Actions API is accessed. A missing archive or conflicting source hash must fail closed. The NO DATA state is a valid research result. Existing V6 ACWI original LIVE signed-HMAC sequencing and trading STOP remain separate and unchanged. Original small funded ceiling **$130.30**.
