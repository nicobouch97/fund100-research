# Fund-100 Phase 3 — C4 stress-aware commodity ETF challenger

**Frozen 15 October 2026 before first public-data historical run.**
**Research only, no PAPER or LIVE broker permission.**

## Why a fresh hypothesis now?

DBC's actual fund history includes underlying futures roll, fund
costs and tracking, while physically backed GLD has a very different
return driver. The capped monthly static GLD20%/DBC15%/SHY65% mix
**beat** the previously tested C1 trend and C2 macro regime models
on the already examined late historical sample. The DBIQ issuer
publishes a 28-commodity index but the relevant PDF downloads are
blocked behind its website terms gate. No exact historical roll and
dated per-expiry futures prices are available.

C4 is an explicitly distinct **portfolio-risk/hedging thesis**,
not a substitute or proxy for futures-curve/carry research:
commodities can lose some diversification value when they become
positively correlated to equities in volatile equity markets.
Test whether a narrowly-defined 63-session correlation/stress
overlay *reduces equity-crisis drawdown enough to justify added
turnover and lower commodity exposure*, versus the simple static
basket. Do not assume it will improve returns.

## Pre-declared, frozen strategy rules

Reference instruments only: **GLD**, **DBC**, **SHY**.
**SPY** is a signal/diagnostic reference and never bought by C4.
Initial hypothetical account: 100 notional in SHY.
On the *first session CLOSE of each month*:

1. Compute **63 complete daily close-to-close ETF returns through
   the PRIOR completed session**. Compute annualized realized
   SPY volatility = SPY daily sample standard deviation × sqrt(252).
2. Default to reference target GLD **20%**, DBC **15%**, SHY **65%**.
3. Only if SPY historical annualized volatility is **at least 25%**,
   and DBC's 63-session Pearson daily correlation to SPY is
   **at least +0.40**, reduce DBC from 15% to **5%**. Move 10%
   to SHY. No prospective market beta or future correlation used.
4. Independently if SPY volatility is at least **25%** AND GLD
   correlation to SPY is at least **+0.30**, reduce GLD from 20%
   to **10%**. Move 10% to SHY. No risk-on signal from gold.
5. If either series has zero variation and correlation is
   undefined, its condition does not trigger. No leverage,
   shorts, derivatives or more than GLD20%/DBC15%, and SHY
   reference target always at least 65%. Intra-month weights
   naturally drift between reference targets.
6. The close-to-close return earned before monthly rebalance
   belongs to the *old* portfolio. Charge **5/15/35 basis
   points per traded side** on absolute total weight turnover,
   including sale and funding legs, when new weights are applied
   after the close. No intra-month rerisking, smoothing or
   threshold tuning against history.

This model can lose money and can miss subsequent rebounds.
Equity volatility and backward-looking correlation do not predict
commodity returns, and high SPY volatility is not a reliable
state label. The research code is entirely isolated from
trading/broker routes.

## Comparison and evidence standard

The main comparator is the **simple capped static 20 GLD / 15 DBC /
65 SHY portfolio** under the *same trade-cost and rebalance
conventions*. Describe late-period cumulative **net return
difference in percentage points**, each model's peak-to-trough
drawdown, turnover, average strategy daily return on SPY <=−2%
sessions, and equity correlation. Compare SHY and SPY only as
diagnostics, not an investment-approved model.

Do not treat the 70/30 chronological late historic split as
independent unseen out-of-sample evidence: it was already explored
during C1, C2 and C3 commodity research. Report historical outcomes
as **EXPLORATORY** even if C4 wins. If C4 loses to static on
after-cost and risk-adjusted grounds, record non-promotion rather
than retuning the same 2020–2026 history.

New evidence requires a separate **forward-only** model scorecard
starting no earlier than code freeze and a completed new price
session; do not revise the previously begun C1/C2/static
prospective hash chain to add a model. To qualify for any future
commodity PAPER, require independent prospective data and
stable implementation, realistic ETF liquidity and spread models,
broker integration separate from LIVE whitelist, portfolio
risk budget and explicit user approval.

## Technical/data caution

Historical prices from public `yfinance` adjusted ETP closes
could later be revised. GLD holds physical gold; DBC tracks a
futures commodity index. The DBC fund's historical adjusted
share prices already embed its futures-roll and fund effects,
so a second ad hoc futures-roll drag would be double counting.
C4 is **not** a commodity futures contract, direct spot proxy,
current DBIQ-index sector weights, or inferred modified optimum
yield methodology.

Public DBIQ issuer page has a T&C modal. Direct link endpoints
were identified but PDF bytes have **not** been downloaded or
reviewed in Fund-100. The C3F/C3G evidence gates remain
unchanged, and can continue separately with authorized issuer
document access later.

**LIVE safety state unchanged:** only original V5 US ETF list is
whitelisted; LIVE operator STOP, engaged kill switch, HIGH risk
tier and $130.30 maximum pilot exposure remain frozen. C4
cannot issue an order or self-promote to PAPER/LIVE.
