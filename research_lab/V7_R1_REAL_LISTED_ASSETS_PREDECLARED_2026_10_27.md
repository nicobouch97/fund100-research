# V7 R1 — first causal listed real-assets satellite investigation

**Predeclared 27 October 2026, before new original vendor-source acquisition. Research only.**

This is a differentiated listed-real-assets question, not a claim that REITs
or infrastructure equities are independent of equity-market beta. Use actual
US-listed ETF vehicle adjusted closes for VNQ (US REITs), IGF (listed global
infrastructure), SPY (US equity) and ACWI (global equity), from **2012-01-03**
through the last already completed NYSE close **2026-10-23**. Freeze the
retrieval-vintage CSV SHA256, acquisition time, complete NYSE calendar and
full report as a GitHub Actions artifact. Yahoo adjusted closes reflect a
vendor's revisable distribution/corporate-action assumptions, not broker
fills or a point-in-time independently licensed total-return feed.

## Fixed hypothesis and test (no retuning after seeing results)

At the **first NYSE session close of each month from 2013-03-01**, use
ONLY two historical closes: t-253 and t-22 completed NYSE sessions.
Choose the stronger 12-minus-1 month momentum between VNQ and IGF.
At that month's close, rebalance the whole model to **47.5% SPY,
47.5% chosen real-asset ETF, 5% zero-interest cash**. Apply 5, 15,
35 bps per dollar traded on every side, including the initial entry.
There is no same-close signal lookahead, shorting, leverage, or
optimisation of the signal window.

The *primary matched-exposure passive comparator* buys 47.5% SPY,
23.75% VNQ, 23.75% IGF and holds with 5% cash. This keeps the same
SPY core and aggregate listed real-asset exposure; it does NOT match
duration, country, style, beta, volatility or factor exposures.
Secondary controls buy 95% SPY or ACWI and hold with 5% cash. The
static controls are charged the same one-way entry cost, but are not
artificially charged monthly turnover. Rotation marks and
intramonth single-asset drift above 50% are reported, not hidden.

Compare **net** annualized returns, maximum drawdown and volatility in
three fixed nonoverlapping periods: 2013-2016, 2017-2020, 2021-2025.
2026 YTD is diagnostic only and excluded from the categorical screen.
Use 15 bps/side as the primary scenario, with 5 and 35 bps stress.
The fixed screen asks whether monthly real-asset selection exceeds
the matched passive real-asset mix in all three historical periods.
A favourable answer would only justify further independent evaluation,
not LIVE deployment. An unfavourable answer should be retained without
changing the selected periods or lookback.

## Critical caveats and release boundary

The 2026 retrieval is not an untouched prospective holdout and the
historical tickers/periods were known when designed. VNQ and IGF are
equity-like, with property/interest-rate, country, sector and financing
risks. Daily adjusted closes assume instant hypothetical closing-price
fills; spreads, market impact, taxes, fund expenses beyond NAV price,
broker permissions, and fractional eligibility remain unverified.
An investment hypothesis with a poor net-cost result should not be
promoted by searching more parameter combinations on this same sample.

No source acquisition is an order request. All LIVE controls, existing
14-symbol V5 whitelist, operator STOP, engaged kill switch, HARD LOCKED
writer, and original **$130.30** principal ceiling remain untouched.
Zero broker HTTP, zero orders, zero private-state mutations.
