# V6-E2 — historical feasibility review for the frozen V6-E1 SEC earnings reaction

**Fixed before computing outcome, 17 October 2026. Research-only retrospective
diagnostic; NOT an independent out-of-sample or a real-market earnings
surprise dataset. The October 2026 surviving eight-company source cohort
is selected in hindsight for all earlier 2025–2026 reports.**

Original data MUST match exact existing archived 15 Oct 2026 SEC eight-company
source bytes and the 17 Oct 2026 price snapshot (same as V6-E1).

Deterministic study:
1. Include ALL nonamended original SEC 8-K filings containing exact Item
   2.02 dated **1 November 2025 through 31 August 2026**, if filing
   date falls strictly AFTER an available preceding complete stock
   price session and if 13 future completed price sessions exist.
2. Filing timestamp does not establish when the news reached the
   market. Use 2 full US market sessions strictly after the filing
   date to evaluate **(stock prior-to-second-close return) minus
   (SPY same-window return)**. Ignore same-session last-trade timing.
3. A studied positive-reaction event qualifies if the above **≥+2.00
   percentage points**. Negative/no-reaction events are documented
   too, never silently discarded to inflate hit rate.
4. To avoid buying at the second close after observing it, simulate
   an unrealistic but explicit **third completed session CLOSE as entry
   proxy**, then the CLOSE exactly **10 further completed sessions**
   later as exit proxy. Compute close-to-close adjusted stock excess
   return versus SPY over that same holding window. This is not
   executable intraday/next-open price evidence, and ignores overnight
   execution gaps. No dividend/quote vintages authenticated.
5. Net-of-trading friction stress of **5, 15, and 35 basis points on
   EACH side** applied to stock return (not SPY buy-and-hold). Market
   spread, actual fractional Alpaca order price and tax/FX remain
   unsupported. Do not assume fills at actual closing prices.
6. Count all dated full-horizon event observations; tally missing
   pre-close/future-window in separate excluded source counters.
   Keep each independently filed accession once. A new 8-K/A
   must not create an extra event. Multiple overlapping observations
   are events, NOT independent portfolio NAV returns.
7. Report source dates, N, issuers, signal N, mean, median, hit rate
   versus SPY, min/worst outcome, all three cost curves. No strategy
   CAGR, Sharpe, annual alpha or real-money profit because overlapping
   event windows and source cohort bias prevent that.
8. **Minimal evidence threshold for further independent validation,
   NOT permission to trade:** at least 24 qualifying unique events
   from 6 issuers; median 35bps net excess >0; more than half
   35bps events positive; chronological earlier/later halves both
   positive mean 35bps net excess. Even if every condition holds,
   evidence is contaminated by the 2026 issuer selection, late
   reconstruction and unreproducible fills; independent future
   validation is still mandatory.

This is not a rescue optimisation of the rejected V6-R1 ETF momentum
coefficient set. No parameter tuning after the results on these dates.
Do not promote any individual stocks to the LIVE-only 14-ETF current
allowlist and do not sell original four positions. Existing operator
STOPPED, kill switch ENGAGED, HIGH risk, $130.30 maximum remain intact.
