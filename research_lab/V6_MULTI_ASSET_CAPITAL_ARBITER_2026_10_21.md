# Fund-100 V6: shared multi-asset research allocation

Pre-registered on 21 October 2026. This change is OFFLINE and uses synthetic scenarios only.

## Objective

The final Fund-100 architecture combines ETFs, individual stocks, commodities, bonds, crypto and FX under one central capital and risk budget. The active ETF experiment is a first execution sleeve, not the full fund.

## Implementation contract

A self-contained deterministic research allocator must validate research candidates against the existing registered strategy IDs and asset families. Research priorities come from the frozen thesis register; they do not indicate proven future returns.

For a fully synthetic portfolio, requests express notional dollars, constituent instrument exposures and coarse shared risk-factor exposures. Unknown strategy, invalid weights, duplicate requests, short exposure, excess money precision, or unexplained exposure fail closed. The arbiter processes rank-ordered valid requests subject to a combined USD 130.30 example budget, 95% gross example investment ceiling, 5% simulated cash floor, 50% per instrument, and 60% coarse shared factor bucket cap. By-family research caps are illustrative only: ETFs 95%, individual equities 50%, commodities 25%, bonds 50%, crypto 10%, FX 10%. Unfilled demand is left in simulation cash, not reassigned by hidden optimization. Check conservation to the cent and input permutation invariance.

The factors are illustrative coarse tags, not independently verified ETF constituent look-through. The cash is invented, not an actual brokerage balance. The preference order is hypothesis research order, not cost-adjusted performance ranking.

The code must have no network, credential, broker, GitHub private ledger or order operations. All outputs must declare no PAPER or LIVE authority. Future upgrades require genuine independent performance evidence, actual position and cash snapshots, broker routing checks, approved combined cross-asset policy, and separately reviewed trading release. This research step does not change the existing V6-S1 STOP or original holdings.

## Falsification tests

Prove shared caps across multiple strategies requesting the same instrument or factor, prevent per-bot capital duplication, challenge malformed/negative/fractional-precision proposals, reject missing thesis and LIVE-permit claims, hold back unknown asset classes, prove zero requests cannot create capital, and verify cash floor for seven registered thesis candidates.
