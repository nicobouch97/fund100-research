# V6-R2 — concentrated quarterly 12-month absolute momentum (frozen)

**Preregistered 18 October 2026 BEFORE first R2 real historical evaluation.**
Research-only. Not a new operator mandate to trade.

## Hypothesis

The prior V6-R1 weekly 63/126-session *relative* 3-ETF rotation
failed dramatically: at 15bp per side the 2014-2026 annual
CAGR differential vs ACWI was −8.33 percentage points and
gross annual turnover 19.69× NAV. Simply tuning its coefficients
against that known history is not evidence.

**R2 is a distinct, published long-horizon timeseries trend family**
rather than tuning R1: quarterly rather than weekly decisions,
exactly 252/21 completed-session **12–1 absolute** return signal,
200-session moving-average risk gate, up to two concentrated winners,
residual cash instead of leverage; no SPY or ACWI allocated.
Reference research:
Moskowitz, Ooi and Pedersen, "Time Series Momentum",
Journal of Financial Economics, 2012,
https://doi.org/10.1016/j.jfineco.2011.11.003 .
Original research concerns futures across asset classes, not
a free alpha guarantee in ETF subsets; applying it to this selected
equity-heavy universe is an unverified hypothesis.

## Freeze — no retuning on these already-examined dates

- Instruments from the originally whitelisted **ETF-only**
  US stock risk universe: IWM, EFA, EEM, VNQ, XLK, XLF,
  XLI, XLV, XLP, XLY, XLE, XLU. Exclude ACWI (benchmark)
  and SPY (broad passive reference) from selection.
  This is not a proposal to buy any unapproved asset.
- Original immutable research price source
  `research_lab/frozen_history_v2.csv`,
  exact SHA256
  `acc2c8c08953b895ca5062b3cfba287efb97143b10e108e8ce4bd8b82ffb0d28`
  first through last source sessions as contained. This
  2014–September 2026 data has been repeatedly examined
  during previous Fund-100 engineering and must never be called
  a truly independent holdout.
- At the **last available US trading session each calendar quarter**
  (when following available trading date falls in the next quarter),
  compute a target from **previously completed sessions only**
  (prices through `t−1`, not decision-day `t`).
- Absolute long-horizon trend score:
  close at `t−22` divided by close `t−253` minus 1.
  This represents 12-to-1-month-ish historical returns,
  ignoring recent 21 full sessions. Require score strictly >0,
  and previous complete close `t−1` strictly above
  average of prior 200 completed closes.
  No future earnings, CPI or volume estimates and no
  hyperparameter search on this source.
- Rank all qualified ETFs by absolute 12–1 score descending,
  alphabetical tie-break. Hold top two: **60% rank 1 and
  40% rank 2**; if one qualifies only 60% that ETF and 40%
  cash; if none qualify **100% cash**. Cash earns ZERO
  interest and avoids assuming SHY can be traded LIVE.
  No shorts, leverage, margin, stock picking, derivatives,
  crypto or commodity futures. Single-name 60% exposure
  is **well above original HIGH V5 sector satellite constraints**;
  this is hypothetical and requires a new approved risk
  contract even if economics were promising.
- Only trade after quarter-end close. If any ETF weight
  differs from target by >=15 **percentage points**, trade
  all differences (sum absolute weight changes). Otherwise
  retain drifted portfolio weights.
  Entry and exit **each** incur one-way 5/15/35bp
  per gross traded unit; spread/market impact unverified.
  No overnight execution guarantee: close-to-close
  prices are a research idealisation.
- End-of-session execution cannot earn same session's
  return. P&L for next session must use final
  holdings after trade, and transaction friction
  must be deducted from NAV, not from benchmark.
- Benchmark passive `ACWI_BENCHMARK` from original source;
  source returns may omit time-specific dividend, point-in-time
  issuer adjustment and historical real execution spreads;
  no GBP currency conversion.
- Historical periods **2014-onward** and descriptive
  **2020-onward**, net 5/15/35bp side.
  Measure CAGR, maximum peak-to-trough drawdown,
  worst 1-day, equity exposure, rank-change dates,
  and **annual sum of absolute traded-weight changes**.
  Do NOT claim causal/tradable alpha or present high
  historical returns as future expected returns.
- **Predeclared minimal research gate, NOT permission
  to LIVE trade**: 15bp/side full CAGR at least
  **+2.00 percentage points above passive ACWI**;
  at 35bp/side full CAGR still strictly > ACWI;
  descriptive 2020-onward 15bp net CAGR > same-period ACWI;
  full-period annual gross turnover <=**3.0x NAV**,
  max drawdown no deeper than **−40%**. Even if
  passed: genuine independent upcoming prospective
  observations, account-specific micro-notional execution
  and new position/risk manifest needed. Failing one gate
  means REJECT R2, preserve negative result, and never tune
  same 252/21/200/60-40/15pp coefficients in response.

## Original LIVE financial status

Existing REAL V5 micro-pilot already owns ACWI/EEM/XLE/XLV
since Oct 5; we must not treat them as cash.
Original capital authorisation **USD130.30**,
risk HIGH, V5 operator `trading_enabled=false`,
broker kill switch ENGAGED at last verified audit.
No user instruction to liquidate, no order permits,
and the new concentrated R2 strategy exceeds original
HIGH sector exposure constraints. All R2 code is
broker-free research.
