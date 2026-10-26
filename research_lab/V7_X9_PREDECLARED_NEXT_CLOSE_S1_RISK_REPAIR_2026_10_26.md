# Fund-100 V7 X9 — Fixed delayed S1 risk-maintenance experiment

**Registered 26 October 2026 before viewing any X9 historical results.**
This is ONE standalone risk-operability sensitivity, NOT another search
for an alpha-producing sector timing rule. No source, risk contract,
mandate, intended live trade, paper fill or protected operator modified.

## Fixed original HIGH risks and risk-repair assumptions

Use exactly the same source-verified, repeatedly inspected 2014–2026 ETF
adjusted-close data, initial 47.5% XLK / 28.5% XLE / 19% IWM / 5% cash
and equal 95% ACWI benchmark from X8, fixed windows beginning
2014/2020/2023, and costs of 5/15/35 bps **per traded side**. Include
initial BUY costs *inside* the 95% invested budget and model every
subsequent SELL and final terminal sale fee. No new securities,
margin, shorts, interest, invented funding or same-run buy with sale proceeds.

The original proposed HIGH ceilings are not optimized: single instrument
50%, gross 95%, cash >=5%, daily account loss 6%, peak-to-trough
drawdown 20%, annual realized portfolio volatility 35%.

At each **completed close**, observe current share holdings, fund NAV,
cash, account daily return, drawdown and trailing 63 completed daily
fund returns (only when all 63 exist). Stop triggers are a daily loss
at or below -6%, a running drawdown at or below -20%, or
trailing annualized realized volatility strictly above 35%.
A stop is permanent in this diagnostic: on the **following completed
session's close**, attempt to sell all existing holdings, charge
per-side costs, and remain in cash. Re-attempt any tiny original
inventory that could not pass the assumed $1 minimum. A stop
does NOT magically fill at the moment a risk limit is crossed.

In the absence of a stop, if the 50% single-name, 95% gross or 5%
cash limit is exceeded, compute one conservative **SELL-only** repair
to a 48% per-name and 90% gross cushion, taking the larger sale
quantity required by either exposure limit. Signal uses only the
known prior close, then sends the *same precomputed share quantities*
to the following close. No filling at the earlier or more favorable
close. Ignore modeled order sides below **$1**; retain those
unexecuted holdings and count any unrepaired cap breaches.
At a gap, precomputed quantities need not restore full compliance.

Always measure breached sessions **after** hypothetical delayed
execution, costs, partial/unfilled hypothetical order limits.
At the fixed study endpoint, apply the original X8 terminal
liquidation-cost convention for a fair *return comparison*, but
never claim that endpoint trade was submitted or funded.

## What to learn, not optimise

Report the costed risk-managed return versus (a) **exact unmanaged X8
S1** and (b) an identically costed 95% ACWI reference, for each
pre-fixed cost/era; drawdown, stop timing, volatility, transaction
fees, modeled volume, maintenance frequency, and unresolved
cash/gross/single-name risk breaches. Do **not** retroactively tune
trigger windows, repairs, cushions or minimum sizes to rescue a
bad return. The 2018 L1 volatility overlay was previously rejected
on this broad price history; X9 is a **risk operability** investigation
and may well substantially reduce return without preventing fast
crashes or satisfying a hard drawdown ceiling.

No claim of point-in-time independent evidence, realized account
performance, actual bid/ask spreads, executable next-close orders,
accurate fill amounts, tax or broker-verified $1 minimum. $130.30
original pilot principal ceiling, original four V5 holdings,
engaged STOP and environment kill switch are unchanged. No
credential read, capital authorization or execution.
