# V7 T1 — one preregistered cross-asset ETF momentum hypothesis

**Registered 27 October 2026 before first T1 actual vendor-source run.**
Do not tune the test or rerun the same vintage as independent alpha
after seeing outcomes. The idea is different from failed sector-only
equity R2, failed REIT/infrastructure R1 and failed CFTC C6:
a *single, balanced instrument universe from genuinely different
economic risk sources*, without derivatives or 24/7 trading.

## Fixed hypothesis and source, no fitting

Retrieve original publicly available adjusted ETF daily closes for
**SPY (US equity beta), TLT (long US Treasuries), GLD (gold) and
DBC (diversified commodity-futures ETP)**, starting 3 Jan 2012 through
the latest completed US cash-equity session before source acquisition.
Save original canonical CSV, SHA256 and evaluation JSON only to the
bounded GitHub Actions artifact. Verify every NYSE market day using an
independent exchange calendar, finite positive adjusted prices, and
no >45% unexplained one-day source discontinuity. Original Yahoo
adjusted ETF data are **vendor-revised in 2026**, not authentic
point-in-time close quotes, fillable prices or 2014 fund-membership proof.

At the **FIRST completed close of each calendar month**, compute
each asset's fixed **12−1 approximate momentum**: price at t−22
divided by price at t−253, less 1. The current execution-session
close t **must not enter its own ranking**. Rank positive momentum
assets from strongest to weakest (alphabetical ties); hold the
top two at **47.5% of post-fee NAV each**, or the lone qualifying
instrument at 47.5% and hold the rest in zero-interest cash, or
entirely cash if none qualify. The position cap is below original
HIGH 50%, and the strategy NEVER borrows or shorts. Targets update
monthly, with no new entries between decision dates.

Every first rebalance and subsequent turnover charges genuine
modelled **5, 15, 35 basis points for every dollar bought or
sold**, paid FROM synthetic NAV with the target CASH balance
5% or higher *after* fees. Explicit accounting solves the
post-fee position dollars and cost equation rather than treating
trading as free. On the last completed study session charge a
closing side liquidation cost to ALL alternatives; no actual
execution at that price is claimed.

## Benchmarks, predeclared eras and no re-optimization

The primary cost-matched passive comparator starts with **23.75%
each SPY/TLT/GLD/DBC and 5% cash, held without rebalancing**.
It has the same initial/terminal trading frictions, no artificial
monthly churn. The secondary benchmark **95% SPY / 5% cash**
is liquid but not beta/risk matched. Run three fixed
nonoverlapping periods with separate synthetic $100 NAV and
identical source:
2014-01-02–2016-12-30, 2017-01-03–2020-12-31, and
2021-01-04–2025-12-31. 2026 YTD is descriptive only, not
part of pass/fail.

Predeclared categorical ECONOMIC hurdle, not a proof of alpha:
at **15 bps per side**, costed T1 annualised returns must
strictly outperform the passive *same-four-asset* reference in
**all three** historical eras to earn even *further independent
research*. Record comparison with costed 95% SPY, actual modeled
fee dollars per $100 starting capital, turnover, realised
volatility, maximum drawdown, worst daily loss and sessions
breaching HIGH original 50% single / 95% gross / 5% cash,
−6% daily loss, −20% drawdown, 35% annual volatility.
If the original hypothetical rule loses, retain the failure.
Do **not** search lookbacks, exit periods or new holdings
against the already examined historical market price data.

## Limitations and LIVE boundary

DBC commodity index roll methodology changed in **2025**;
retrospective ETF adjustments, expense/roll assumptions and
contemporary fund choices create structural breaks and risks.
Long bonds, equities, commodities and gold each have material
macro/regime exposures; four ETFs are NOT diversified futures
trend following. Positive historical excess return could be
pure exposure/timing luck; *no original prepublication data
vintages or time-independent prospective outcome are present*.

No indication to sell existing ACWI, EEM, XLE or XLV,
extend original 14-ETF whitelist, change the $130.30 LIVE pilot
ceiling, change HIGH risk rules, unlock operator STOP or
environment kill, issue new paper orders or touch the broker
API. A real opportunity must be independently qualified, pass
the existing X6 cost/settlement/capacity chooser, and be
approved by a future standing mandate. This task is ONLY
source-backed comparative investment research.

## 29 October 2026 — post-hoc exposure-matched diagnostic (NOT a new hypothesis)

The original T1 test and its three-era 15 bp pass/fail hurdle above remain
**unchanged**. After the original results had been examined, we added a
*descriptive* fourth comparator to each existing window/cost scenario:
`EXPOSURE_MATCHED_FOUR_EQUAL`. On the exact same monthly decision close,
it uses the original trend rule's number of positive selected names (zero,
one or two) to set the same 0%, 47.5% or 95% equity budget, but divides
that budget equally across SPY/TLT/GLD/DBC. It charges the same per-side
transaction-cost schedule on its **own** entry, rotation and exit trades.
The comparator observes only the original signal's previous-session data;
it never learns the future market return. Matching gross exposure helps
identify whether the apparent trend advantage comes from timing gross risk
or selecting particular assets. Because the comparator inherits the
original signal's exposure and was added after viewing prior historical
results, it is **not** independent validation, an alpha claim, a revised
promotion gate or permission to trade. Original static four-ETF and SPY
benchmarks remain untouched.
