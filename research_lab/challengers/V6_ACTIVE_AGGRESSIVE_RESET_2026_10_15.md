# Fund-100 V6 — ACTIVE / AGGRESSIVE RESET (research charter)

**Declared 15 October 2026 after the operator rejected V5 as the intended final experiment.**
This is a replacement STRATEGY DESIGN, not an authorisation to sell existing holdings, activate a new bot, widen the brokerage whitelist, or change risk limits.

## Operator intent / project success

- The four actually filled V5 LIVE ETF positions from 5 October 2026 are a **temporary bootstrap portfolio**, not acceptance of an essentially passive 75%-ACWI core as the Fund-100 experiment.
- Goal: a **small-capital active, aggressive, rules-driven multi-strategy trading experiment**, with an honest chance of outperforming passive investing and a correspondingly material possibility of losses. Select HIGH total-portfolio risk, not merely bigger ticket sizes.
- Do **not** demand weeks/months of imaginary-money profitability before starting a versioned, limited-capital LIVE experiment. Use historical evidence + a short broker order-mechanics check + explicit operator release + live risk monitoring and genuine realised performance. No performance guarantees.
- V5 should not be silently recommissioned just because the workflow exists. Original operator control remains `trading_enabled=false`; broker kill switch ENGAGED. No cash deposit, liquidation or opening order without separate explicit user approval.
- When the operator authorises a replacement, first obtain an account/holdings and liquidity snapshot; consider spread/fees/taxes/FX consequences of selling the four positions, ensure the OLD event writer cannot re-enter, then independently deploy a signed new strategy with TOTAL new buying notional within the original $130.30 pilot ceiling. Never assume sale proceeds can be reused before confirmed fills/settlement. Abort on partial liquidation/reconciliation disagreement.
- If the operator instead elects to liquidate early, that is a **separate sell-only authorised action**, after verifying the exact holdings and impact. Do not sell merely because this note exists.

## First fast, empirically testable strategy challenger V6-R1 (NOT final automatically)

**Thesis:** intermediate momentum and cross-sectional leadership can identify stronger equity segments; avoid a static 75% global benchmark core. Academic time-series momentum is established in some liquid markets, but it is NOT proof of this particular weekly sector-rotation implementation. Momentum can suffer abrupt reversals/crashes. Sources:
- Moskowitz, Ooi & Pedersen (2012), Journal of Financial Economics: https://doi.org/10.1016/j.jfineco.2011.11.003
- Daniel & Moskowitz (2016), Journal of Financial Economics: https://doi.org/10.1016/j.jfineco.2015.12.002

**Initial research instruments:** the frozen historical US equity/sector ETF set SPY, IWM, EFA, EEM, VNQ, XLK, XLF, XLI, XLV, XLP, XLY, XLE and XLU; ACWI_BENCHMARK as comparison ONLY. GLD/DBC, individual stocks, bonds, crypto and direct FX need their separate source, broker, and thesis gates; they are NOT already V6 live trade-authorised. No leveraged products, options, short sales or margin.

**Precommitted V6-R1 calculation**, using only prior completed daily closes at each Friday close rebalance decision:
1. Eligibility: full 200-session SPY/asset lookback; previous-close price must exceed its trailing 150-session simple moving average; asset 126-session total price return > 0; and asset 63-session return above SPY's 63-session return. All price returns based on frozen existing data; source has vendor-adjustment/revision limitations.
2. Deterministic score: `0.6 * (asset_63d_return - SPY_63d_return) + 0.4 * (asset_126d_return - SPY_126d_return)`. Exclude nonpositive scores, rank by score, ticker alphabetical for ties.
3. Choose the top 3 eligible candidates, no blanket global-equity benchmark core. When SPY's prior-close price is above its 200-session simple moving average, use **35% / 35% / 30%** target for three names; with two or one, use **35% each** and leave residual in cash. This is more concentrated than the current HIGH live guard allows, so **a separate versioned risk/release review is mandatory**.
4. In an SPY below-200-day regime: reduce each selected noncash exposure to **35%** of the otherwise proposed weights (max 35% gross), leaving remaining capital as cash. This is a transparent regime heuristic, not a guaranteed crash hedge.
5. Reassess **weekly**, never same-day intraday day-trading. Use Friday close target with **last available close Thursday or earlier**; positions for Friday close-to-close return are the OLD holdings; apply new portfolio only AFTER Friday close. If no Friday bar (holiday), no automatic backdating to Thursday. No lookahead. To limit $130 transaction frictions, only rebalance if a slot allocation differs by at least five percentage points, otherwise retain all drifting positions (unless current exposure exceeds a hard risk limit, addressed separately).
6. Historical run charges **5/15/35 bps per traded side** times full gross turnover (both sells and buys), plus no positive interest on idle cash. It must report yearly turnover, largest weekly losses, annualized return/volatility, drawdown and equity beta/correlation against ACWI_BENCHMARK and a simple equal-weight instrument control where appropriate.
7. Frozen **v2 CSV**, 2008-03-28 through 2026-09-16; verify the *file bytes SHA256* `acc2c8c08953b895ca5062b3cfba287efb97143b10e108e8ce4bd8b82ffb0d28`. Public Yahoo/vintage limitations and prior work on this same date range make **all historical numbers exploratory**, not an independent out-of-sample proof. Dates or weights should never be tuned to rescue losses on this set.
8. The experiment remains **broker-free** and cannot issue an Alpaca permit, create a live order or change V5. The earliest possible new V6 live event requires distinct versioned source, fail-closed order executor, end-to-end fill/restart reconciliation, and explicit user-approved transition.

## Wider active multi-strategy roadmap, without pretending all markets are ready

- **V6-R1 active sector/country ETF relative momentum**, the immediate testable strategy, execution candidate only if evidence is viable.
- **V6-R2 individual-stock earnings quality + analyst revision + momentum**: existing P4E accounting quality is real for six firms but P4F broker estimates and delisting-safe historical prices remain missing. This is *not* an independent proven stock trading edge yet.
- **V6-R3 physical gold vs broad commodity futures ETP regimes/carry**: commodity C1, C2 and C4 failed to beat a static reference in explored history; do not use them as an unearned high-return proposition. Obtain dated roll/carry evidence.
- **V6-R4 crypto momentum**: isolate 24/7 market infrastructure, spreads/exchange custody and crash-risk before any LIVE permit.
- Every strategy competes under ONE shared account ceiling, risk tier and STOP; no strategy gets an independent full $130.30 budget.

## Before any real-money transition

A: show explicit historical results and costs, not marketing projections; B: compare to ACWI, the frozen V5 strategy and simple controls, including stress periods; C: confirm exact existing live holdings + sale estimates, outstanding orders and cash, execute only after explicit sell/new-buy permission; D: separate old and new event namespace to prevent V5 re-entry; E: migrate or replace HIGH per-name/sector constraints deliberately if justified, not secretly; F: cap gross combined account exposure and continue automatic STOP / monitor; G: record live post-trade results versus original starting equity and simple benchmark.

**Operator authorisation to sell V5 holdings: NOT GIVEN. New V6 LIVE entry: NOT GIVEN.**
