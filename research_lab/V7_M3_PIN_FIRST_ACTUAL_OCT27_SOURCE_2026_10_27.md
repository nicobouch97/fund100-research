# V7 M3 — before 27 October NYSE entry close: pin the FIRST forward source vintage

**Predeclared 27 October 2026 ahead of the first M1 entry close.** Do not reselect any historical stock or change the original M1 pick algorithm, Oct26 selected-issuer source SHA, 27 October first-entry model date, 21-session model horizon, same 5/15/35bp per-side costs, cash reserve or passive SPY/sector comparison.

## Core research data problem

Yahoo adjusts its historical public price files and can revise even previous "final" daily adjusted-close values (split/dividend backfills, source corrections). M1 correctly pins its *pre-entry selection source* from original E7 run 40368883430. But each later M1 observation downloads ALL historic prices again. **Without another source pin, the 27 October model-entry stock and SPY prices might silently change after that first actual observation**. Comparing next-month prices to a hindsight-restated starting quote would not be the same prospective experiment.

P4H's source-integrity audit already discovered actual upstream historical price revisions. This is a specific reproducibility repair, not new portfolio/strategy optimization.

## First-entry anchor chosen automatically, without discretionary selection

The existing brokerless M1 workflow observes actual **27 October 2026 NYSE closing prices** only after genuine exchange close + 90 minutes. When it first reports exactly ENTRY_CLOSE_OBSERVED_AWAITING_FIRST_FUTURE_MARK, with **zero holding intervals**, upload the original 26-column public price-vintage CSV and M1 full no-performance JSON to a uniquely named original GitHub Actions artifact, fund100-v7-m3-first-entry-20261027. Multiple catch-up observations of exactly that sole entry day can create separately immutable artifacts with the same name; **earliest creation timestamp / GitHub artifact ID wins**, not the easiest or best-returning vintage. Original workflow stays main only with explicit actions:read, no order API and no new GitHub write token.

A later M1 source with at least **one full completed future NYSE interval** must find the first nonexpired original M1 artifact uploaded from a completed, successful, main workflow run **after the originally planned 27 October entry close**. Fail CLOSED if it is missing. Verify the exact same original 26 equities/benchmark source columns (24 issuers + SPY + SHY), entry date, M1 original Oct26 source SHA, frozen selection, completed-close metadata, no brokerage path, and compare each of those first-entry share prices at the source's fixed 10-decimal canonical precision.

If any originally accepted 27 Oct source price changes in the later vendor history, **HOLD_SOURCE_REVISION**, never silently use the adjusted 2026 future price to improve the prospective score. It may require a separately and explicitly specified corporate action entitlement correction; don't invent such fixes on original historical data. Only when all entry quotes match can later source-captured M1 model-vintage return comparisons be archived with an audit record.

Artifact retention is 90 days, sufficient for this fixed 21-NYSE-session study; expiry or unavailable historical source must cause HOLD rather than a new, discretionarily reset anchor. Source-vintage continuity does NOT prove actual investor total return, exchange print availability, executable fills, prediction skill, a delisting-free historical universe or any trade permission.

## Explicitly no LIVE work

No new Alpaca client, no LIVE read/write, no private account balances, no fund contribution or operator-stop modifications. V5 holdings, HIGH loss/volatility limits, **USD130.30** existing pilot authorization, engaged original operator STOP and broker kill remain unchanged. No real orders.
