# Fund-100 V7 M2 — original-source after-close forward entry observation, without same-day lookahead

**Preregistered 27 October 2026 before the fixed first M1 model entry session closes.** This change does NOT select different securities, forecasts, benchmark models, lookback windows, sector assignments, risk estimates, cost assumptions, or a different 21-session exit. Original source-run 40368883430 and its independently hashed Oct 26-selected 24-stock cohort remain immutable.

## What the source timing actually prevented

M1's first genuine source-vintage market entry is the **NYSE completed closing price on Tuesday 27 October 2026**. At 13:43 UTC on that date it has not happened. The original P4L historical public downloader requests end=today (EXCLUSIVE), so it cannot capture today's fully closed bar even at 23:45 UTC. Furthermore M1 previously rejected every data point whose price session matched the source capture calendar date. Thus a legitimate after-close data delivery was ineligible, delaying the actual first-observed price at least until next day.

A late original vendor-adjusted close is still **not** independently authenticated exchange final-auction data. No observed close is an actual buy execution or proof of availability at a market-on-close trading deadline. A 90-minute safeguard controls premature data but cannot replace an official consolidated exchange feed.

## Precisely bounded remedy

1. Add a **dedicated M1 follow-up-only Yahoo adjusted close fetch** with inclusive current-day coverage (by requesting tomorrow as the vendor's *exclusive* end). It does not change the original P4L research source downloader or its 26 Oct selection artifact. Retain exactly the same original 24 selected issuer IDs + SPY and SHY benchmark, same start, adjusted-price validation, and complete NYSE market-day history.
2. Demand that the acquisition be strictly after the official XNYS **session-specific UTC close plus 90 minutes**, using the actual calendar's DST shifts and shortened trading days; also refuse non-market days and prices more than five days stale. A present-day vendor bar observed while its market was open must **STOP** instead of claiming it is completed.
3. When the source legitimately reaches 27 Oct's completed close but the next session has not closed yet, report ENTRY_CLOSE_OBSERVED_AWAITING_FIRST_FUTURE_MARK, **zero** measured forward return intervals, no net-performance calculations, no sector hindsight rank and no prospective alpha promotion. Zero-day round-trip friction must not be presented as a realised strategy test.
4. For legitimate later completed sessions, retain the exact M1 frozen cash-matched 95% SPY, sector control, original preentry-only volatility match, original sector-conditional 24-issuer distribution, 5/15/35-bps side costs and one fixed 21-session exit. The already examined historical 24-stock roster is survivor-selected and the vendor adjusted bars are revisable.
5. Schedule the already existing M1 brokerless workflow at **23:45 UTC on weekdays** after the US regular cash session as well as the existing **12:35 UTC next-morning data vendor recovery**. Only a completed actual NYSE session can become a model observation. The original protected LIVE credential workflows are unchanged.

The change explicitly records official last session close, buffer and whether capture occurred on the same calendar date. Tests cover US daylight-saving session close changes, the actual 2026 early Black Friday close, weekend bogus bars, spoofed intraday session data, exact first Oct27 entry close and no zero-period performance, tomorrow-exclusive vendor end, after-close lag, and no trading path.

## What this doesn't do

- No forward return until the **second** completed NYSE close on/after 28 October; full prespecified 21-session comparison needs the remaining real daily observations.
- No guaranteed source feed, no original exchange-bid/ask or actual entry/exit fill, no total-return corporate-action verification, no statistical alpha or LIVE order authority.
- Does not change originally authorized **USD130.30** pilot ceiling, existing ETF holdings, engaged broker kill, original STOP, HIGH 6/20/35 risk controls or any execution writer.
