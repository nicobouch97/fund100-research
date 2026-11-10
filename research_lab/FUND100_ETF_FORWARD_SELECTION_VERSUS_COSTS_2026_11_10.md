# Fund-100 — ETF overlay selection versus cost attribution

10 November 2026 | **Not a live strategy, not performance promotion.**

## Observed evidence that motivates this check

The automated Forward Lab completed the 9 November NYSE session in
https://github.com/nicobouch97/fund100-research/actions/runs/42777067901.
The existing, hash-linked and continuously verified Forward Lab ledger
had 38 intervals (29 strict prospective, nine marked recovered after
outage). Its source-backed scorecard showed:
- ACWI benchmark -0.6521% since 16 Sep 2026
- V3 -2.1223%, net -1.4702 percentage points behind ACWI
- V4 -2.1519%, net -1.4998 percentage points behind ACWI
- RM25 -2.1221%, net -1.4700 percentage points behind ACWI

These are modeled, vendor-priced performance observations, not broker
fills, verified future alpha or a representative multi-year track record.

## Practical research question

How much of the lag was modeled 15bp one-way friction, versus genuinely
poor relative exposures? Are V3, V4 and RM25 actually three distinct
investment bets, or primarily the same factor exposure at different
sizing parameters? Looking for a fourth almost identical overlay
would be less useful if the selection signal itself needs attention.

## New read-only diagnostic

fund100_forward_active_attribution_v1_0.py first calls the original
source-hash and XNYS-calendar verifying scorecard, then checks each
original daily signed payload has exact algebraic coherence:

    net strategy daily return = benchmark daily return
                              + gross overlay selection return
                              + signed cost drag

The existing net NAV and benchmark day-to-day changes must also match
the signed daily source. It reconstructs a **same-realized-weights
gross-before-modeled-cost path** by compounding gross daily returns.
This is a descriptive same-exposure arithmetic counterfactual.
Trading with no costs would alter portfolio NAV/turnover/weights, so
the resulting gross NAV is NOT a fully recomputed investable strategy.

The script also separates STRICT FORWARD from RECOVERED rows when
adding log-relative-wealth market-selection and cost contributions;
it NEVER compounds discontinuous strict-only segments as a valid
investment record. It reports paired strict-forward correlations
between V3, V4 and RM25 to identify redundant exposure—not three
independent tests of alpha.

A research-only category flags whether all three gross-signal paths
still lag ACWI, and whether strict-forward exposures are highly
correlated. A poor result prioritises research into underlying
rankings, issuer breadth, quality, valuation and diversified
asset-selection signals over arbitrary re-optimization of the overlay
cap. This does **not** choose or backfit replacement investments.

The output regenerates each Forward Lab run as
forward_outputs/latest_forward_active_attribution.json and is
automatically included in the exact same bounded fast-forward-only
git publication/recalculation flow as the original scorecard.
No additional broker/public internet market-data call is needed.
The unchanged original ledger and model configuration are used.
No asset orders, LIVE capital changes or strategy promotion.

## Limitations and design discipline

Results are tiny-sample, not a confidence bound on alpha. Prices are
Yahoo adjusted equities in GBP-adjusted modeled benchmark accounting,
not Alpaca fills. One-way 15bp costs are assumptions, not exact fills.
The reported model correlation is a DESCRIPTIVE similarity on the
29 genuine prospective observations to date; three highly correlated
variants do not constitute three independent investment strategies.

Further research can use historical literature and walk-forward
purged/holdout simulations without requiring months of new
forward observations **before** the pilot can ever start. Any
replacement strategy must maintain audit lineage and release gates.
The operator STOP, $130.30 original live pilot limit, $65 ticket,
HIGH risk and independent broker funding provenance remain unchanged.
