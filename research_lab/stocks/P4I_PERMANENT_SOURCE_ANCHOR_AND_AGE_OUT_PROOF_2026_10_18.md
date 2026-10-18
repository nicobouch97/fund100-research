# P4I — permanent SHA anchor for genuinely prospective stock returns

**Created 18 October 2026. Original selection recorded 17 October 2026 before the first Monday session. RESEARCH ONLY.**

## Original evidence recovered (real, not fabricated)

On [original P4G run 39015519726](https://github.com/nicobouch97/fund100-research/actions/runs/39015519726), the stock-quality model's original 17 October 2026 snapshot from the Friday **16 October close** selected
**MSFT, KO, PG**, in that order. This is less inherently aggressive
than the operator's desired V6 replacement; treat it as an independently
frozen comparison rather than a strategy selected for launch.

The exact original P4G artifact **12094995126** contains the complete
original research JSON and vendor adjusted-close price CSV.
GitHub Actions output printed the original price SHA256
`9c01c045f6fe9d54f455513249c23433a806ffb350575bef9bfdbde5372d921d`,
and separate P4H original-artifact verification on
[run 39145252280](https://github.com/nicobouch97/fund100-research/actions/runs/39145252280)
calculated the original JSON SHA256
`403a6e23ad53ace626cb9663e3889ab9c0b4e58d7c582ad3aab85aa024bdffb7`.

The frozen prospective comparison is MSFT/KO/PG equal-weight vs
passive SPY and AAPL/AMZN/GOOGL/KO/MSFT/PG equal-weight
P4E six-issuer accounting-quality reference. The latter is NOT an
investible or independently validated quality factor; the
2026 GAAP scores were unknown before 15 October 2026.
No analyst-level EPS revisions were authenticated. No
IPO/delisting-safe historical 2015 universe or original
adjusted-close vendor vintages were established.

## Why the anchor was needed

Standard GitHub Actions artifacts expire at most 90 days
in this repository. Without a durable original research
provenance record, the previously implemented P4H
forward-return evaluator would stop when the original
17 Oct artifact expired, regardless of how many NEW
completed market sessions subsequently appeared.

P4I commits only immutable identifiers and source hashes
to `research_lab/stocks/P4I_PERMANENT_2026_10_17_SOURCE_ANCHOR.json`.
It does **not** copy vendor-owned 2025-26 historical
price CSV or private brokerage account information
into a publicly accessible Git repository.

P4I's source code
`fund100_stock_forward_permanent_anchor_p4i_v1_0.py`
verifies each later canonical adjusted-price CSV through:

1. Exact frozen 16 Oct 2026 cutoff, fixed original
   watchlist **MSFT, KO, PG** and six-name reference.
2. Recalculate SHA256 of **ALL original price rows up
   to and including 16 Oct** in the new source file,
   using P4G's own canonical CSV format. Require
   equality to original 17 Oct archive price SHA256.
   If vendor restates past adjusted closes, fail
   with `FAIL_CLOSED_SOURCE_REVISION`.
3. The original baseline JSON hash and GitHub source
   artifact ID stay fixed in every result; later price
   captures each have their own original SHA256.
4. Candidate's first hypothetical entry is **NEXT
   completed US close** after 16 Oct (earliest Monday
   19 Oct); first earned return can only occur at the
   second new session close (earliest Tuesday 20 Oct).
   Same-session captures add **zero** observations.
5. Compute buy-and-hold forward-only return for the
   exact old frozen stock selection versus the two
   fixed references, with **5/15/35 bp per side**
   for BOTH hypothetical entry and exit, and no
   daily rebalance. If there are fewer than two new
   sessions, no return is calculated.
6. No CAGR, alpha significance, hypothetical
   broker fill, GBP-converted return, payment, asset
   whitelist expansion or real order is asserted.

The PR workflow immediately checks its anchor against
the original 17 Oct artifact while that artifact
still exists. Afterwards, the recurring P4H/P4I
workflow uses **only P4I's SHA-pinned provenance
manifest and later dated P4G capture**. A vendor
restatement will intentionally prevent comparison;
the right response is a new independent-source
investigation and explicit method version, not
forging a price series or hiding revisions.

## CME stream, in parallel

[CME's official Continuous Price Series](https://www.cmegroup.com/market-data/cme-group-continuous-price-series.html)
actually publishes settlement, underlying contract IDs
and next roll date in a **Standard** delivery.
This is a stronger route to test WTI futures roll economics
than falsely inferred term structure from USO's
historical ETP price. However CME's
[DataMine API](https://www.cmegroup.com/datamine/datamine-api.html)
requires entitlement and paid licensing may apply.
The exchange's [energy continuous price catalog]
(https://datamine.new.cmegroup.com/catalog/dataset/33c2b6a2a39649a0b69c76163f49f4c1)
lists CLCPA and CLCP1 daily sources.
No original delivered standard futures contract prices,
settlement history or roll P&L have been obtained.
No subscription or redistribution is authorised on
the $130.30 micro-pilot budget.

## Financial boundary

Real Alpaca LIVE holdings ACWI/EEM/XLE/XLV have been
verified through 18 Oct fresh GET-only requests; none
was liquidated. The user's delegated investment
decision remains **HOLD until viable V6 candidate**.
HIGH risk, USD130.30 original ceiling, operator STOPPED
and most recently confirmed kill switch ENGAGED.
No broker access, PAPER stock orders, LIVE individual
stocks, futures, crypto, margin or leverage in P4I.
