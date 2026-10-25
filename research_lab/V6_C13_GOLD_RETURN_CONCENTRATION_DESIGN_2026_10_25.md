# V6-C13: Historical gold/SHY return concentration diagnostic (25 October 2026)

**Status: diagnostic specification, written before this branch's original-source run.**
This is a post-result robustness investigation, **not** an independent holdout or
new allocation rule. Previous C13 V4 gold-vs-interest-bearing-cash results were
already inspected and may bias interpretation. No weights, cost assumptions,
historical source, trading permissions or execution paths change.

## Question

Did the historical advantage of replacing 10% interest-bearing cash with gold
arise consistently, or was it concentrated in one or two calendar years?

## Frozen method

Use the existing V4 monthly-rebalanced **net NAV** histories at **15 bp per
actual ETF traded side** and **IRX_GROSS** lagged Treasury-bill cash proxy.
Compare the fixed 75%-equity **GOLD_ONLY**, **SHY_ONLY** and **GOLD_SHY**
baskets with the identical-equity 75% **CASH_CONTROL**. No additional
strategies, weights or optimised break dates.

For each sleeve, calculate the **log of its net terminal wealth divided by
cash-control terminal wealth**, including the difference in inception
transaction costs. Attribute that log relative wealth by calendar year using
daily log NAV differences, assigning inception-cost difference to the first
year. The annual log contributions must reconcile exactly (before rounding)
with terminal log relative wealth. Report negative and positive year counts,
the largest positive contributing calendar year and the remaining total log
relative wealth after arithmetically excluding that single year.

**Interpretation:** these are calendar-year contributions to log relative
wealth, **not** calendar-year CAGR differences, actual strategy returns, an
executable leave-one-year-out strategy, confidence intervals, or investment
alpha. First and last years are partial. The largest year is chosen *after*
observing the data, so its omission is sensitivity analysis only.

## Required verification

Deterministic fixture tests for initial ETF transaction-cost inclusion,
telescoping/reconciliation, annual aggregation, no future-price leakage,
negative-contribution cases and fail-closed NAV/index validation. Existing
V4 price/rate acquisition and results must remain unchanged. Run focused
original-source CI and the complete LIVE static audit on the exact PR head
before merging; no merge on failing or incomplete checks.

No broker connectivity, funded orders, private-state writes or changes to
the $130.30 ceiling, operator STOP, ENGAGED kill switch, or LIVE release locks.
