# C6 predeclared commodity positioning + ETF trend test — research only

**17 October 2026, prior to the first actual C6 economic run.**

### Objective and economic hypothesis

CFTC C5 unlocked real official 2026 disaggregated Futures Only managed-money positions for COMEX gold CFTC **088691** and NYMEX WTI-PHYSICAL **067651**, verified in [C5 run 39030028357](https://github.com/nicobouch97/fund100-research/actions/runs/39030028357), archive artifact ID **12100485342**. CFTC positioning may be a useful *trend participation filter* but is **NOT itself a futures-carry or predictive-return signal**. Test one deliberately simple long-only alternative against passive commodity ETPs.

**Fixed signal (no optimisation on the already-known 2026 prices):**

- Each CFTC weekly Tuesday report: managed-money **(long minus short) / total open interest** for gold or WTI, compare to **exactly 4 reports ago**, no interpolation, and require net-share change strictly positive.
- For each candidate ETF, separately require prior-completed **63 US-trading-session** adjusted closing-price return strictly positive. **GLD** represents the gold exposure; **USO** is a US oil-futures ETF proxy, **NOT the same expiry contract as CFTC physical WTI**, and its roll methodology differs from both NYMEX single-contract futures and DBC.
- Both pass: 50% GLD + 50% USO. Only gold passes: 70% GLD + 30% SHY. Only oil: 70% USO + 30% SHY. Neither: 100% SHY. No leverage/short; 70% is **RESEARCH ONLY**, exceeds original V5 LIVE satellite cap and requires explicit new risk approval before any LIVE order.
- **US market daily close trading** only, with a strictly conservative delay: map each Tuesday report to its **official *scheduled* CFTC publication date** (normally Friday **3:30 p.m. Eastern**, delayed for holidays); form the signal using prices **through the trading session before the FIRST ETF trading close strictly AFTER that scheduled publication date**, and assume trade AFTER that ETF close, earning returns only from the next session. No profit from the prior CFTC Tuesday-Friday gap.
- If a report is missing or its scheduled release date cannot be mapped exactly, never synthesize positions or use future data. **Important:** schedule is a *tentative publication schedule, NOT independent evidence of original release execution*. 2026 ZIP was downloaded October 17, so reconstructed earlier entries are a **retrospective approximation**; emergency publication delays and later revisions could invalidate historical knowledge.
- Rebalance on eligible first-next-session only if any absolute target-weight difference is >= **10 percentage points**; if triggered trade the entire target difference, both sides separately. 15/35/60bps per gross traded side. Already embedded GLD/USO/SHY adjusted-close fund expenses and USO futures roll must NOT be counted as fresh separately earned carry.
- Start research NAV at **May 1, 2026 close**, track trading sessions to last completed ETF session not later than October 16. Use earlier daily price and CFTC history only for warmup, never as independent 2026 forward results. Compare against static 50/50 GLD/USO, static 35/35/30 GLD/USO/SHY, and SHY passive from identical start.
- Report period *cumulative percent return*, largest peak-to-trough drawdown, gross traded notional turnover, decision counts, signals, and net performance vs both static comparisons. **DO NOT annualise a few months of historical results or claim a validated alpha coefficient.** Annualized CAGR in such a brief sample is misleading.
- A modest positive result is insufficient: require >= **12 distinct eligible decision dates**, +1.0 percentage points at 35bps vs static 35/35/30 and vs passive 50/50, positive at 60bps vs both, turnover <= **4x period NAV**, and max drawdown no worse than 50/50 benchmark. If any condition fails, do not promote. Even if all pass, still need authentic original point-in-time release vintages, executable spreads, independent forward confirmation, and separate account risk/asset enablement. No post-hoc threshold or window tuning to rescue a loss.

### Source contracts

- Original official 2026 CFTC ZIP plus immutable original SHA256 capture JSON downloaded **from existing original C5 artifact only**, never reconstructed from an external summary.
- **Original 2026 CFTC release schedule:** [CFTC official release schedule](https://www.cftc.gov/MarketReports/CommitmentsofTraders/ReleaseSchedule/index.htm) captured on 17 Oct 2026. Frozen April–October 2026 scheduled release dates listed below, including atypical **June 22 and July 6 Mondays** after US holidays. **This is a conservative historical simulation, not actual real-time provenance**. 2025 government-lapse release disruptions prohibit extending this simple rule back into 2025.
- Exact source-bound public Yahoo/yfinance GLD, USO, SHY adjusted-share closing prices are captured **once in an original Actions artifact**; vendor revisions are possible, and vendor history is not a contemporaneous quote archive. Refuse missing prices, malformed timestamps, duplicate/extra source columns or source discontinuities rather than filling missing.
- 2026 CFTC source and vendor prices are **historical 2026 observations acquired now, October 17**; they are NOT a new untouched holdout and cannot prove future real-world performance.

**Frozen 2026 *scheduled release* dates:**

April 03, 10, 17, 24; May 01, 08, 15, 22, 29; June 05, 12, **22**, 26; July **06**, 10, 17, 24, 31; August 07, 14, 21, 28; September 04, 11, 18, 25; October 02, 09, 16.

### LIVE account boundary

This C6 research never touches Alpaca, doesn't transmit orders or alter operator settings. Current four V5 LIVE ETFs have **not** been liquidated; operator STOPPED, kill switch ENGAGED, selected risk HIGH and total authorised starting-capital ceiling **$130.30**, ETF-only LIVE allowlist remains. GLD/USO/SHY are *not authorised by this research charter*. No individual asset class gains a separate capital budget.
