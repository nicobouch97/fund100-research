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
