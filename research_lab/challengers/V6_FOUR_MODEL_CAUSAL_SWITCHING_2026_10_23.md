# V6 four-model quarterly switching — causal historical comparison (23 October 2026)

**Research only. No independent holdout, no portfolio replication, no broker
connectivity, no strategy promotion.** Uses the existing immutable
market-price source and four already-implemented costed NAV paths.
No original model signal or production risk policy is changed.

## Single predeclared allocation rule

At the **close of the first trading session of each quarter**, use the
preceding 252 completed model daily returns, ending at the **previous**
session close. Among S1, R1, L1 and R2, select the largest positive
252-session log excess growth over ACWI whose same-window maximum drawdown
is no worse than -20% and annualised daily volatility no greater than 35%.
If none qualifies, select CASH (zero yield). Ties resolve by model name.
The selected model first earns the following close-to-close return.

Use existing 5/15/35bp original one-way cost scenarios. Model NAV paths
already contain original model trading costs. Charge an *additional* same
one-way cost on entry/exit of a synthetic model sleeve (one side when
moving from/to cash; two sides when switching models). No leverage, short,
margin, new securities, or LIVE authority. Extra costs are an approximation,
not a replicated ETF trade ledger; overlapping sleeve positions are not netted.

## Evaluation and limitations

Report historical 2014+, 2020+, 2023+ CAGR versus ACWI, downside,
volatility, worst day, switches and cash sessions. These are the same
already-examined ETF price histories, so a causally lagged selector is NOT
independent out-of-sample evidence. The original model families, costs and
periods were studied repeatedly, and this new rule is now tested on those
same prices. Dividends/corporate actions, FX, spreads, market impact,
underlying strategy replication, live cashflows and fills are not
independently verified. Favorable historical returns must not cause promotion.

This is an integrated selection evaluation, not a separate trading engine.
Untouched forward data, executable sleeve reconciliation and total-portfolio
risk assessment are needed before any promotion discussion.

The original USD 130.30 ceiling, operator STOP, ENGAGED kill switch,
LIVE release locks and holdings are untouched. No PAPER or LIVE orders.

## Fixed four-sleeve economic comparator (24 October 2026)

To distinguish any benefit of the quarterly *selector* from simply owning
the four existing strategies, report a **predeclared 25%-per-model,
buy-and-hold synthetic sleeve blend** alongside ACWI. The comparator
starts at the same first eligible quarterly close after 252 completed
training returns. It holds cash before that date, pays one 5/15/35bp
synthetic entry side on the whole capital at inception, then retains
fixed sleeve units (weights drift; no quarterly rebalancing). Each
original model NAV already embeds its own transaction costs. Both
selector and comparator earn no new-sleeve return until after entry.

Report the blend's CAGR and maximum drawdown and selector-minus-blend
CAGR in all existing 2014/2020/2023 windows and cost scenarios.
No additional model parameters, optimized blend weights, hindsight
rebalancing, order code or strategy promotion. This comparator is a
**synthetic model-of-models accounting reference**, not executable
holdings replication; overlapping ETF transactions, spreads and
market impact remain unverified. All histories were already inspected.
A favorable selector-versus-blend result would still NOT prove alpha.


## Predeclared unlevered volatility-managed blend sensitivity (24 October 2026)

The fixed 25%-per-model sleeve blend produced attractive retrospective returns
but an approximately 29% historical peak-to-trough drawdown, exceeding the
descriptive HIGH 20% screen. Test **one** causal downside-control challenger
on the **same original four costed model NAVs**, not a fifth alpha model:
target 10% annualised realised volatility, estimated from the preceding
63 completed close-to-close blend returns. Set risky exposure at each close
to `min(100%, 10% / trailing annualised volatility)`; use 100% when
volatility is effectively zero. Hold the remainder in zero-yield cash.
No borrowing, shorts, or exposure above 100%.

Enter at the identical first eligible quarterly close as the fixed blend;
the newly selected exposure earns its first return only over the **next**
close-to-close session. Thereafter, earn each session's return using the
**previous close's** exposure, then recompute exposure and charge an
additional 5/15/35bp one-way cost proportional to synthetic notional
changed. The original four sleeves' costs remain embedded in their NAVs.
Report CAGR, maximum drawdown, realised volatility, mean exposure,
synthetic turnover and a descriptive 20% drawdown breach for the same
2014/2020/2023 windows. Compare directly with unchanged fixed blend and
ACWI. No optimization across lookbacks or targets.

**Critical limitations:** Volatility targeting does not guarantee a
20% drawdown limit and can suffer sudden gaps or prolonged trends.
The equal-sleeve synthetic blend is not a verified holdings-level
execution strategy; underlying model overlap, correlated positions,
tax, dividends, corporate actions, market impact and trade-time prices
remain incompletely modelled. All data were previously inspected,
so any improvement is in-sample and not independent evidence of alpha.
No automatic promotion or funded execution is authorized. Original
$130.30 ceiling, operator STOP, ENGAGED kill switch and all LIVE locks
remain unchanged.


## Original four-model return-dependence diagnostic (24 October 2026)

A 25% allocation to four strategy *names* is not automatically four
independent sources of risk. The same four original costed model NAVs now
produce a descriptive, common-session return-correlation diagnostic for
each 2014/2020/2023 comparison window, beginning no earlier than the
shared first eligible quarterly close. It reports maximum and mean
pairwise daily return correlation and the correlation-matrix participation
ratio, `trace(C)^2 / trace(C @ C)`, ranging from one (effectively one
correlated return dimension) to four (four uncorrelated return dimensions).
Near-constant model paths explicitly return **unidentifiable**, never a
fabricated diversification statistic. Synthetic regressions test perfect
duplication, distinct return paths, future isolation and constant sleeves.

This diagnoses potential *return* redundancy, not security-level
look-through, gross combined holdings, liquidity, forward correlations,
transaction netting, independent holdout alpha or permission to trade.
Correlations and effective dimensions are in-sample and may change
abruptly under stress. No strategy parameters, costs, capital limits,
risk policies or LIVE release locks change.


## ACWI equity-beta and bad-market-day attribution (24 October 2026)

Four correlated strategy sleeves can merely repackage a shared equity
benchmark exposure. Diagnose the existing fixed 25%-per-model, naturally
drifting, already-costed synthetic blend against the **same original ACWI
NAV** using identical close-to-close sessions after the first eligible
quarterly entry date. For 2014+, 2020+, 2023+ and 5/15/35bp original
cost scenarios, report daily OLS beta, the fraction of blend daily variance
explained by ACWI (R-squared), a descriptive annualised *arithmetic*
regression intercept with **zero assumed cash yield**, active tracking
error, and average blend/ACWI returns on the worst 5% of ACWI sessions.
The latter is a conditional historical stress diagnostic, not a downside
guarantee. The original model costs and synthetic entry cost are retained;
no new fitting or trading signals are introduced.

A high R-squared or large loss on ACWI's worst days would challenge the
interpretation of the blend as a truly diversified alpha portfolio.
A positive OLS intercept is **not** proof of executable alpha: it depends
on the zero-rate assumption, is not a CAGR, has no statistical-significance
claim, and is calculated on repeatedly examined history. Benchmark or
blend return series with effectively zero variance explicitly yield
unidentifiable beta rather than spurious precision. This remains
research-only, not independently replicated ETF holdings or fills.
No capital ceiling, operator STOP, kill switch, LIVE release lock, or
protected private-state record is changed.

## 26 October 2026 — correct volatility-blend drifted-weight trading costs

The original volatility-managed blend earned the preceding close's risky
allocation return, then charged costs only for changes between two *target*
risky weights. That omitted the rebalance needed to restore an unchanged
target after a nonzero market return: the risky fraction naturally drifts.

For each session, calculate the pre-rebalance risky fraction as
`old_target * (1 + risky_return) / (1 + old_target * risky_return)`.
Charge the existing 5/15/35bp one-way cost on the absolute difference
between the new target and this **drifted** fraction, after earning the
preceding target's gross return. Entry and exit still incur their original
one-way costs; no leverage or new parameter is introduced.

This fixes understated synthetic turnover and potentially overstated net
historical returns for the existing 10% vol-target sensitivity. The
historical comparison is still in-sample, a synthetic model-of-models,
and not a broker-executable portfolio or evidence of new alpha.


## Simple ETF economic controls (26 October 2026)

The previous factor regression showed that same-session broad equity and sector
proxies explained most of the fixed four-model blend's daily return variance.
Regression fit does not answer the economic question: **did running four
overlapping models beat simply holding the corresponding exchange-traded
funds?** The existing four-model evaluation therefore now reports two
transparent, non-optimised, buy-and-hold controls alongside the *unchanged*
fixed model-sleeve blend:

1. 100% ACWI benchmark ETF adjusted-price proxy.
2. 25% each ACWI, XLK, XLE and IWM adjusted-price proxies.

Both controls enter at the **same first eligible quarter close** as the
existing fixed model blend, pay the same 5/15/35bp **one-time entry-side**
cost, and then **never rebalance**; their ETF weights naturally drift.
The fixed model blend continues to embed each original model's trading costs
and the existing synthetic one-time model-sleeve entry cost. All comparisons
use identical completed sessions and the same SHA-pinned frozen adjusted
prices. The report provides CAGR, realised volatility, drawdown, worst daily
return and blend-minus-control CAGR for 2014+, 2020+ and 2023+ windows.

**Interpretation:** A buy-and-hold ETF control has substantially lower
trading requirements than a strategy with recurring model-level turnover.
Equal 25% ETF weights are deliberately simple, not optimised or risk matched;
the control is not a factor-mimicking portfolio or an ETF constituent-stock
look-through. The entry fee is present in full simulated wealth but cancels
from the CAGR of windows that start at/after entry, so differing cost scenarios
affect the four models much more than the passive controls. Vendor-adjusted
closes are not verified execution prices and cannot guarantee historical
investability, spreads, dividend treatment, tax or capacity. These histories
have already been examined repeatedly: **any observed return difference is
descriptive, not independent alpha or a promotion decision**.

No trading strategy, protected LIVE risk policy, holdings, pilot capital
ceiling, STOP switch, environment kill switch or release lock changes.


## Matched equity-market downside comparison (26 October 2026)

The simple ACWI and ACWI/XLK/XLE/IWM buy-and-hold economic controls now
also report **paired stress exposure**, using precisely the same completed
sessions as the existing costed four-model fixed blend. The analysis selects
the worst 5% of ACWI daily sessions and the worst 21-session ACWI return
interval *ex post*, then measures all three portfolios over those **same**
days. This avoids the invalid comparison of each portfolio's different
worst dates and helps establish whether active complexity bought meaningful
protection during historical market selloffs. The 21-session horizon and 5%
tail are descriptive fixed reporting conventions, not fitted trading rules.

The selected market dates depend on the complete historical sample: this is
**not** a point-in-time market-stress forecast, trade trigger, causal hedge,
risk-matched performance test, independent holdout or evidence of new alpha.
The original costed strategy NAVs, simple ETF holdings, frozen prices, LIVE
capital ceiling, operator STOP, kill switch and release locks remain unchanged.
