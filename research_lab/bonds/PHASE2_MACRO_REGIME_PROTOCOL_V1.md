# Fund-100 Phase 2 — Macro bond regime challenger v1 (predeclared)

**Status:** PREDECLARED RESEARCH ONLY. No promotion rights; no orders; no Alpaca or LIVE/PAPER keys.

This is a *new hypothesis*, not optimisation of the previously disappointing bond price-trend model. Compare on the SAME later historic segment for exploratory context only. That later segment was already examined by our first study and therefore **cannot** be presented as an untouched independent test of the new macro hypothesis. Any causal/edge claim needs archived real-time data vintages and prospectively time-stamped forward results.

## Research inputs and known shortcomings

| Public series | Meaning | Units | Issue |
|---|---|---|---|
| FRED `DGS2` | 2-year Treasury constant maturity yield | percent | H.15 publication timing/vintage not independently archived |
| FRED `DGS10` | 10-year Treasury constant maturity yield | percent | Ditto |
| FRED `T10YIE` | 10-year Treasury breakeven inflation rate | percent | Market inflation compensation is not inflation *surprise* |
| FRED `BAA10Y` | Moody's Baa corporate yield minus 10-year Treasury yield | percentage points | Corporate credit risk proxy, not a tradable spread or total-return series |

Sources are FRED publicly downloadable historical CSV, not FRED API keys. The combined data require a date for each observation and a separately labelled **ASSUMED** earliest availability date: observation date + 2 US *weekdays*. Actual release calendar timing, public holidays and revised vintages are *not* independently validated by this assumption. No model may claim point-in-time accuracy from this data; later ALFRED vintages and archived release calendars are required.

No publication-day information is used: monthly rebalance decisions occur at the first monthly trading session close, using macro values whose assumed availability was no later than the *previous* trading session. Data older than 10 calendar days produce SHY fallback. No interpolation of missing macro observations. Uses public adjusted-close ETF data and an explicit SHA256 of every input CSV. Data are not suitable for live execution pricing.

## Fixed, non-optimised allocation rules

Reference portfolio always includes SHY as a defensive *ETF*, not cash. Once a month, choose a single state based on 21-trading-session changes to the most recently knowable macro readings:

1. If 10Y yield has fallen at least **15 basis points** and Baa spread has not widened more than 30 bp: **15% TLT / 20% IEF / 65% SHY**.
2. Otherwise if Baa spread has tightened at least **20 bp** and its level is at most **3.50 percentage points**: **20% LQD / 15% IEF / 65% SHY**.
3. Otherwise if inflation breakeven rose at least **10 bp** while 10Y yield rose at least **10 bp**: **20% TIP / 15% IEF / 65% SHY**.
4. Otherwise **100% SHY**.

Every rule is only an illustrative, mechanically fixed research hypothesis. We have no evidence yet that these thresholds are optimal or profitable. All are unlevered reference allocations; total non-SHY risk target is <=35%. Current Fund-100 live LOW/MEDIUM/HIGH aggregate risk budgeting is separate.

Assume trades at each monthly decision session close (after that session's adjusted-close return) and pay a cost on both ETF legs at one-way **5/15/35 bp**. Positions drift between monthly closes. Compare vs SHY buy-and-hold and previously trained 126-session price-trend bond reference at identical costs. No portfolio rebalance may be submitted to a broker by this code.

## Research promotion gate

- FRED snapshots from the present are revised historical observations, not archived point-in-time data.
- Reusable, chronologically available macro observations must be validated against historical real-time ALFRED vintages and release timestamps, particularly around recessions and crisis periods.
- Avoid reoptimising fixed thresholds on the already-viewed later history. Reserve a genuinely new prospective forward period, with source/hypothesis/code fixed before observing performance.
- Evaluate against SHY and an appropriate benchmark mix on costs, turnover, drawdown, correlations to US equities, duration concentration, liquidity and stress/regime results.
- Even favourable retrospective performance is **not** promotion. PAPER research requires a separate proposed gate and broker evidence. LIVE universe/controls remain unchanged.

### Running

The GitHub `Fund-100 Phase 2 Macro Bond Regime Research (NO BROKER)` workflow executes offline tests on PR. On its first merge to `main`, it fetches public vendor historical series once, runs the retrospective exploratory comparison, and stores CSVs/JSON as temporary GitHub artifacts. It uses `contents: read` and has no secrets, no Alpaca endpoints, no writes to repository and no ability to create orders.
