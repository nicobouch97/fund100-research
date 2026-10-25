# V7-E5 — frozen prospective event signals versus independently later price-vintage marks

**Preregistered 22 October 2026. READ ONLY. No broker GET/POST, private ledger writes, allocations, liquidation, LIVE releases or alpha claims.**

## Evidence and purpose

- V7-E3's original 15 Oct SEC and 17 Oct price archives had ZERO genuine post-15 Oct Item 2.02 events and ZERO eligible source-bound signals. The later vendor revised the original P4G historical prefix, so E3 **correctly refused** to repair its immutable original chronology using later adjusted close history.
- V7-E4 added separately dated, archived SEC raw submissions and T+1 adjusted public-price snapshots, with original per-issuer SEC CIK/SHA and price JSON/CSV hashes; those are a *potential* future source of truly pre-entry observed signals. The first actual scheduled run's evidence is **not yet verified** in this protocol.
- The initial V7-E5 implementation compared **two successful main-branch E4 captures** and chose the newest eligible earlier capture solely by chronology. The 23 October coverage extension below instead evaluates every eligible earlier source within the latest 40-run archival discovery window; neither approach selects by subsequent P&L. The earlier original SEC and earlier original P4G source must each pass all existing source authenticity checks. Reconstruct the earlier event-screen statuses from those original bytes; never select event winners from a later source.
- The later P4G observation must independently validate its source JSON + canonical adjusted-close CSV + time. The entire earlier session calendar must still be present; any changed historical prefix is labelled as vendor revision. Later source must have been captured after the earlier source.

## Precommitted illustrative return measure

The only eligible names are E4 originally screened unamended SEC 8-K Item 2.02 events with an **original-snapshot, 2 percentage-point stock-minus-SPY reaction** after the second completed post-filing session, acquired before model entry. A missing/late source cannot be retrospectively recreated from another vendor vintage. Contemporary quality is the frozen Oct 15 cohort, with the E4 90-day research expiry and exact eight-issuer coverage.

The **first newly completed trading session** after the early frozen price as-of date is the illustrative entry close, and the **second newly completed session** is the illustrative exit close. Never choose the last/best exit of many. With fewer than two complete later sessions, report NO RETURN rather than 0% or a paper fill. Use only these two price rows from a single **later** independently captured vintage to compute same-vintage stock and gross SPY hypothetical returns. Deduct 5, 15, and 35 basis points **per stock-trade side**, with spread, broker fees and fill effects unverified; SPY remains an **uncosted benchmark** and must be labelled as such.

If no frozen source-eligible events exist, report NO_GENUINE_PRE_ENTRY_EARNINGS_SIGNALS. If no earlier source capture qualifies for a genuine two-session forward mark, the aggregate scheduled report explicitly records NO_SOURCE_QUALIFIED_FORWARD_EVENTS with null return statistics.

This is not a point-in-time provider-corrected proof of profits, no original-vintage P4I hash repair, no unbiased historical event sample, no Sharpe/CAGR or guaranteed executable close. GitHub Actions artifacts retain original bytes for only 90 days. A separate later research decision may consider improving durable storage or expanding the contemporary issuer roster; no strategy self-promotion.

## Operations

The read-only E5 GitHub Actions job starts at **11:15 UTC on weekdays**, after the planned E4 09:15 UTC snapshot, and on first main branch push after approval. No external identities or broker secrets: only read-only GitHub Actions API is accessed. A missing archive or conflicting source hash must fail closed. The NO DATA state is a valid research result. Existing V6 ACWI original LIVE signed-HMAC sequencing and trading STOP remain separate and unchanged. Original small funded ceiling **$130.30**.

## 23 October 2026 coverage extension — no new signal search

The initial implementation examined only the **newest** source-qualified E4
baseline and therefore discarded earlier independently recorded signals,
including any positive events in earlier runs. This is a sampling defect, not
evidence that those discarded events lost or won.

The updated existing E5 scheduled job examines **every eligible earlier
capture among the 40 most recent listed E4 runs**, each with two completed
sessions after its own original source, against the same latest authentic E4
price archive. Original SEC bytes, original price JSON/CSV, and the later
price JSON/CSV must all pass their existing validators. Missing, expired,
invalid, or mixed source artifacts fail closed rather than creating returns.

Each original accession/ticker/model-entry event contributes at most one
observation. Repeated captures with matching entry/exit costed returns are
deduplicated; conflicting duplicates cause an explicit failure. The cohort
reports descriptive mean, median, and positive fraction of the exact
stock-net-minus-gross-SPY one-session marks at 5/15/35 bp per side.
No p-value, Sharpe, prospective alpha claim, or LIVE strategy promotion
can be inferred from this tiny, non-survivorship-safe, overlapping
eight-issuer sample. If no eligible capture exists, the report records
zero observations with **null** descriptive returns, never zero profits.

This extension changes coverage only, not the frozen original event
threshold, trade timing, cost assumptions, risk limits or brokerage permissions.

## 25 October 2026 — prevent multi-filing pseudo-replication

Two distinct SEC Item 2.02 accessions for one ticker may lead to the **same**
hypothetical stock entry close. They are two filing observations, but not two
independent economic positions or return outcomes. Preserve the separate
filing/entry count for source audit, and collapse identical ticker/entry
positions before calculating the descriptive mean, median and hit fraction.
Disagreeing exit dates or costed returns for one ticker/entry must fail closed.
This does not expand the source universe, validate fills or establish alpha.
