# V6-C12 — dated, evidence-qualified cross-asset risk preflight

**Pre-registered 21 October 2026, before implementation/tests. Entirely OFFLINE hypothetical research. This is NOT a trade allocator release, risk-factor model fit, or prediction.**

## Problem to address
The first central multi-asset research arbiter `fund100_multi_asset_portfolio_arbiter_v1_0.py` shares capital, constituent and risk-factor caps across strategies. But `risk_factors` in its proposals are freely declared strings, not independently measured exposures. A proposer can call DBC "CASH" or assume XLE energy-company equity exposure has the same beta as DBC's energy futures. The current simulator is deliberately **research-only**, but cannot be trusted as an evidence-qualified LIVE cross-asset allocation.

## This step — a separate preflight
Add an independent pure function which first calls the **unchanged** original registered-thesis audit and the same synthetic central allocator. It will:
1. Use only **actual scenario-allocated notional**, not requested/unfilled dollars; cross-asset exposure cannot double-count the same simulated capital.
2. Call existing C11's **SHA-pinned original SEC transcriptions** for the latest publicly available DBC 28-contract quarterly statement at a caller-chosen valid historical decision date. Before first public filing, record `NO_KNOWN_DBC_FILING`; never back-fill future filings.
3. Show exact stated provenance: SEC statement/available date, number of contracts, reported DBC gross-futures-notional **energy share**, days since the fund's statement date and source status. If DBC allocation exists and the reported statement is older than **45 calendar days**, mark it `STALE_HISTORICAL_SEC_LOOKTHROUGH`; this 45-day **data-freshness display threshold is a research convention, NOT a LIVE risk policy**. A quarterly filing is generally stale soon after publication; do not call this current NAV weights.
4. Report a purely **hypothetical pro-rata** DBC gross-futures-sector-notional illustration: scenario DBC dollars multiplied by reported share, explicitly **NOT beta, earned return, price delta, holdings of the user's account, a confirmed daily ETF constituent mix or a trade target**.
5. Identify simulated XLE energy-company equity notional separately from DBC energy-futures gross-notional mix. If both present, surface `CROSS_ASSET_ENERGY_CONNECTION_UNQUANTIFIED`. **Never add those unlike values and call the sum energy risk**.
6. Detect immediately false-looking self-declarations, such as DBC or XLE explicitly classified as `CASH` risk factor; report a fail-closed `REJECT_CONTRADICTORY_PROPOSAL_FACTOR`. Non-CASH factor names remain **UNVERIFIED_ASSERTIONS**, not authenticated sector beta.
7. Report unknown **current** look-through for EVERY proposed instrument in the simulation (including DBC). Existing original thesis candidates have `current_broker_live_approved=false`, so **none** is promoted; paper, LIVE and private-state write permissions remain false even if research coverage is good.
8. Include a fixed synthetic demonstration: V6-S1 $100 (original relative XLK/XLE/IWM 50/30/20) + V6-C10 $20 of DBC ETF proxy. These are not actual holdings, sourced economic signals or recommended trades. Illustratively XLE = $30 and DBC = $20; the latest publicly known June DBC energy futures gross-notional fraction ~47% gives ~$9.40 **NOT beta**. Do not claim these two notional numbers are perfectly correlated or additive risk.

## Falsification
Tests must prove dated SEC selection (before first available date, filing boundary, October), exact one-fund allocator dollar reconciliation, 45-day staleness and no fake current coverage, XLE/DBC semantic separation, a DBC-mislabeled-as-CASH rejection, identical output when proposals are permuted, refusal of unknown thesis, original C11 source tampering, and no network/broker/trading entry points.

## Out of scope
This **does not modify** `fund100_multi_asset_portfolio_arbiter_v1_0.py`, the current V6-S1 proposed **95%-invested/5%-cash** starting strategy, its original legacy holdings, user HIGH tier, $130.30 maximum capital, operator STOP or engaged broker kill switch. The input basket is fully synthetic. Actual allocation needs fresh portfolio/cash, look-through ETF holdings and beta/correlations, executable broker permissions, and independent expected-return evidence. A successful test does not satisfy those requirements.
