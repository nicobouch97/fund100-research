# Fund-100 Phase 3 — C2 commodity regime protocol, frozen before first test

**Status:** Research hypothesis C2. No new trading permissions. Prior historical C1
study already examined the 2020–2026 late segment, so evaluating C2 there
**cannot constitute a fresh independent out-of-sample test**. Retrospective
comparison is exploratory; no promotion from historical backtests.

## Why continue commodities after the first strategy failed

C1 tested six-month GLD/DBC momentum and beat SHY in the historical late
segment but LOST to a simpler capped static 20% GLD / 15% DBC / 65% SHY
portfolio at all costs. That is evidence against **C1**, not against
all commodity diversification or every conceivable systematic strategy.

C2 explicitly separates:
- **Physically backed GLD:** permanent 10% reference allocation in the
  commodity sleeve; raise to 20% during *falling 10-year real yields*
  or *widening corporate credit spreads*. This is a testable safe-haven
  and real-yield hypothesis, not a guarantee gold hedges equity shocks.
- **Futures-linked DBC:** add up to 15% if 10-year market inflation
  breakevens rise >= 0.10 percentage points over 21 trading sessions,
  DBC's prior-close 63-session price return exceeds SHY and zero, and
  credit spreads did not widen >= 0.30 pp. Breakevens are NOT realised
  inflation surprise, futures roll yield or validated futures carry.
- **Residual SHY:** short-Treasury ETF (not cash), minimum 65% at monthly
  rebalance targets. Intra-month weights drift.

## Fixed rules (chosen as hypotheses, not fitted results)

1. Use prices completed through the *previous* US trading session, and
   macro data assumed available by that previous close.
2. For each monthly first-session close compare the latest available
   **DFII10** real yield, **T10YIE** 10-year breakeven and **BAA10Y**
   Baa credit spread to their as-of values 21 ETF sessions earlier.
3. Physical gold GLD target 20% if real yield fell >= **15 basis
   points** OR corporate Baa spread widened >= **25 bp**; otherwise 10%.
4. DBC target 15% only with breakeven rise >= **10 bp**, DBC positive
   and outperforming SHY on 63-session lagged absolute/relative return,
   and credit spread widening strictly < **30 bp**. Otherwise DBC 0%.
5. Remainder SHY. No leverage, shorting, futures contracts or orders.
   When macro observations are missing/stale (>10 calendar days), C2
   uses its neutral **GLD 10% / SHY 90%** target. Missing data do not
   trigger a risk-on DBC position.
6. Charge 5, 15 and 35 basis points **per side** on the sum of
   absolute target/current dollar-weight changes at every monthly
   rebalance. These costs represent ETP trading friction; DBC's
   historical fund shares already incorporate roll/tracking/fees,
   so DO NOT add a fictitious duplicate futures-roll deduction.

## Sources and historical limitations

- US Treasury 10Y real yields: FRED `DFII10`, inflation breakeven:
  FRED `T10YIE`, corporate Baa-minus-10Y Treasury spread:
  FRED `BAA10Y`, retrieved from public `fredgraph.csv` history.
- Snapshot histories are downloaded **today**, hence can incorporate
  revised observations from the past. A research-only 2-weekday lag
  is applied to every observation; that is NOT verified source
  release timestamps, official US holidays, or true historical
  ALFRED real-time vintages. No claim of point-in-time reliability
  or actual alpha is defensible without those records.
- GLD, DBC, SHY, SPY adjusted ETP close history downloaded separately
  via `yfinance`; CSV and the two SHA256 digests stored with the report.
  These histories can be revised and do not supply tradable quotes.
  GLD physically backed; DBC futures-linked (term-structure and
  fund-specific roll exposure must be separately studied).
- SPY and SHY are controls/reference symbols only, not LIVE additions.

## Benchmarks, selection, promotion

Evaluate C2 against (1) SHY hold, (2) fixed static 20% GLD / 15% DBC /
65% SHY, and (3) prior C1 six-month price-only trend model on the
**same later 30% historic segment** at identical trading frictions.
This segment was already inspected by our C1 study; its numbers are
**EXPLORATORY**. Do not optimise these preset thresholds against it
and call that an untouched holdout.

Record net return differences, maximum drawdown, trading-cost sensitivity,
turnover, SPY daily correlation and performance on SPY -2% daily shocks.
If C2 historically beats C1/static, do not grant trading permission:
freeze version and source before a genuine prospective period with
verified point-in-time macro release data and dated forward decisions.
If C2 does not outperform simpler comparators on risk-adjusted grounds,
keep it research-only; investigate gold/DBC separately and design a
different thesis only on newly reserved data. Maintain cumulative one
portfolio-level LOW/MEDIUM/HIGH risk budget and the operator STOP.

**Important:** Commodity workstream continues alongside Phase 1 genuine
V5 US-equity ETF PAPER event proof. GLD/DBC are NOT LIVE-whitelisted,
do not have Alpaca broker authorizations and cannot place PAPER/LIVE orders.
