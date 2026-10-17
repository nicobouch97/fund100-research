# Fund-100 V6-C1 — active crypto trend + crash-regime hypothesis

**Preregistered 17 October 2026, BEFORE first V6-C1 real historical evaluation.**
Research only. Existing LIVE account ETF positions, trading STOP, broker kill
switch, HIGH profile and USD 130.30 capital authorisation are unchanged.

## Why this idea is distinct

Previous V6-R1 rapidly rotating equity-sector ETFs and V6-E2 post-earnings
reaction screens **failed** to show compelling cost-adjusted advantage.
V6-C1 is an economically distinct liquid 24/7 risk-premium/trend
hypothesis: own BTC and/or ETH only while each has positive intermediate
absolute momentum and sits above a long-term price average; scale down
when basket volatility is elevated. A trader can lose in sideways/choppy
periods and can underperform dramatically during strong bull markets.

This is NOT the separate pre-existing **BTC/GBP synthetic-paper bot**,
which cannot be silently counted as independent research data, and
BTC-USD/ETH-USD history cannot prove GBP-denominated returns.

## Source and period gates

- Public vendor-adjusted USD daily **BTC-USD and ETH-USD**, downloaded
  once into an immutable source artifact with SHA256 plus captured
  UTC timestamp. No exchange/broker account credentials or API calls.
  Yfinance Yahoo is revisable, not an authenticated executable
  historical quote source; reject empty, incomplete, duplicate or
  implausibly gapped time series. Require completed UTC daily sessions,
  ending *before* acquisition UTC calendar date.
- Source start: 1 January 2018 or the earliest daily observation
  returned after that date, with no missing interior UTC calendar
  days. Prior lookback observations exist solely for signal features.
- Signal-driven historical comparison: 1 January 2020–latest completed
  source date. Report both **2020–2022** and **2023 onward** as named
  descriptive subperiods, not independent prospective holdout.
  All those crypto years are well known in financial research.
- Snapshot must include source hash, exact date bounds and initial
  acquisition UTC timestamp. All results are exploratory, not
  evidence that a historically selected signal will repeat.

## Fixed V6-C1 trading policy

1. **Sunday 00:00 UTC daily close decision** using **prices only through
   Saturday 00:00 UTC close** (one full daily bar of latency). A close
   is a vendor daily bar time, not a guaranteed exchange execution
   price. New weights earn only subsequent day returns. No intraday
   fills or funding yield assumed.
2. BTC eligible if Saturday adjusted close > average previous 180
   completed closes **and** previous 63 daily closes return >0.
   ETH obeys identical rule. Other tokens and leverage prohibited.
3. If both eligible: BTC **65%**, ETH **35%**. If BTC alone
   BTC **65%**/cash 35%; ETH alone ETH **45%**/cash 55%.
   If neither qualifies, **100% USD cash** (zero interest).
   Daily close feature data MUST be at least 181 bars.
4. Calculate 30 prior daily return observations on prior-completed
   prices for currently proposed basket, estimate covariance matrix
   with sample ddof=1 and annualize by sqrt(365). If portfolio basket
   annualized volatility exceeds **50%**, uniformly scale down all
   crypto weights to 50%/estimated-volatility (no scaling UP).
5. Apply weekly targets to **Sunday close only**. If any single target
   position differs from its already market-drifted weight by
   >= **5 percentage points**, trade all legs, otherwise retain
   drift. Rebalance costs are **gross traded turnover** times
   per-side fully loaded friction assumptions: **25bps, 35bps,
   60bps** per side. 25bps reflects Alpaca's documented Tier 1
   crypto taker fee *alone*, NOT a realistic guaranteed all-in
   rate. 35/60bps provide additional hypothetical spread/slippage.
   These still might underestimate real stress execution. Fees are
   modelled on both opening and closing.
6. Compare to BTC-only buy-and-hold and **constant 65/35 BTC/ETH
   buy-and-hold** from the same reporting period; controls have
   no active signal costs (not a promise of cost-free real entry).
   Report annualized net return, maximum drawdown, realized
   volatility, turnover, worst one-day loss, cash fraction, count
   of orders/rebalance days, and positive-return-month fraction.
   No statistical p-value/alpha proof from overlapping or previously
   examined markets.
7. Numerical/precision fail-closed: all OHLC source rows complete,
   all prices finite positive, no equal-date duplicates, daily change
   absolute <=65% (except data must be separately reviewed), no
   100% losses or >1x leveraged gross, no negative cash. No shorts,
   borrow, derivative products or overnight leverage.
8. **Promotion gate** (research comparison only): select a viable
   further candidate if the 35bp scenario outperforms the BTC
   buy/hold benchmark on a **drawdown-adjusted** basis, no >5x NAV
   turnover per year, does not rely on a single bull-market year,
   and survives the 60bp stress scenario without an unexplained
   >5 percentage point CAGR erosion. Independent future data and
   executable broker account validation required regardless.
   No parameter tuning of this same source to rescue a poor result.

## Broker and jurisdiction verification required BEFORE LIVE

Official Alpaca docs consulted 17 Oct 2026:
- https://docs.alpaca.markets/us/docs/crypto-trading
- https://docs.alpaca.markets/us/v1.1/docs/crypto-fees
- https://docs.alpaca.markets/us/v1.1/reference/cryptobars-1
- https://docs.alpaca.markets/us/docs/crypto-orders

These describe generally supported crypto markets and fractionable
orders. Alpaca's lowest-volume maker/taker crypto fees listed as
0.15%/0.25% respectively **as of the documentation viewed**; the
fee actually applicable to this customer/account can differ.
Account-specific eligibility, residence/jurisdiction,
crypto permissions, KYC, reliable live quotes, min order sizes,
fractional execution, USD/GBP FX and custody/account protection
are NOT established by public docs. Use a distinct **read-only
GET** asset/permissions check before any paper or live crypto order;
not the existing US-equity ETF production controller and definitely
not 24/7 keys exposed to a weekday risk watch.

**No crypto LIVE or PAPER authorisation.** Current 14 ETF
LIVE allowlist remains. No exchange withdrawals, existing
holdings sales, margin, leverage, keys, broker POST or
automatic asset-class promotion.
