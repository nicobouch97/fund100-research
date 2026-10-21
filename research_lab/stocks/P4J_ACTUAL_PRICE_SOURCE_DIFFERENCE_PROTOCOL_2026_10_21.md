# P4J genuine source-vintage mismatch diagnosis — pre-registered 21 October 2026

**Research/source diagnosis only. NO broker calls, performance claims, order authorisation, or retrospective signal reselection.**

## Observed failure to resolve

2026-10-21 scheduled P4H/P4I run [39578449225](https://github.com/nicobouch97/fund100-research/actions/runs/39578449225) rejected P4G follow-up run 39571738927 with `FAIL_CLOSED_SOURCE_REVISION`. The existing P4I anchor pins the original 17 October P4G run 39015519726 and artifact 12094995126. Both original P4G artifacts remain unexpired as of 21 October and are available through GitHub Actions. The failure demonstrates a historical-prefix SHA disagreement, *not yet* a proven causal diagnosis of why bytes differ.

## Controlled authentic investigation

1. Use the exact original P4G artifact from run **39015519726** and the exact post-freeze P4G artifact from run **39571738927**; never choose a cherry-picked later date.
2. GH Actions token can only read repository actions artifacts and contents. No Alpaca keys, LIVE environment, private-state tokens, write APIs or market orders.
3. Verify original original P4G JSON hash `403a6e23ad53ace626cb9663e3889ab9c0b4e58d7c582ad3aab85aa024bdffb7`, price CSV SHA `9c01c045f6fe9d54f455513249c23433a806ffb350575bef9bfdbde5372d921d`, pre-selected MSFT/KO/PG and the unchanged existing P4I anchor. Verify followup snapshot self-authenticating canonical hashes, acquired after the original.
4. Compare identical original-session and original-symbol intersections using *the bytes originally archived*, not current downloaded prices. Report hashes, earliest differing date, changed-cell counts by ticker, maximum absolute price **percentage** difference by ticker, and presence/absence of missing original sessions or symbol columns. Do **not** print original prices, raw CSV, account data or market P&L.
5. Report categories `EXACT_PREFIX_PRESERVED`, `DIFFERING_ORIGINAL_PRICE_CELLS`, or `MISSING_OR_REORDERED_BASELINE_SESSIONS`. Do not auto-waive P4I source checks even if the differences are tiny. A result must remain **NO_FORWARD_RETURN_CALCULATED**.
6. Offline artificial-source unit tests challenge actual source-hash consistency, changed symbols and sessions, tampering and no-trade statements before the authentic Actions step runs automatically on merged `main`.

## How it helps our multi-asset mandate

We need authentic forward stock returns to compare individual-stock quality/momentum to equities, commodity carry, bonds and crypto. A hidden data restatement can falsify alpha. This diagnosis is an efficient prerequisite to a dedicated, transparently versioned forward-only first-seen source ledger rather than adding months of paper-P&L delay. Do **not** change the frozen original signal, any actual brokerage strategy, portfolio cash policy or risk tier in this PR.
