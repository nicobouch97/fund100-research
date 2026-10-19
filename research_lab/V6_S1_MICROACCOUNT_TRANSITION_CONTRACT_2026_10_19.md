# V6-S1 — aggressive HIGH-risk microaccount transition: proposed, not activated

**19 October 2026. Engineering stage: original-contract design and genuine paper ASSET GET only.**

Fund-100 will now evaluate **small LIVE experimental strategies** using historical economic reasoning, a short mechanical PAPER rehearsal and subsequent LIVE observation. Months of paper profitability are NOT a launch requirement. However, historical exploratory performance is not a demonstrated alpha signal, and the specific account must be technically tradeable.

## Why this proposal is deliberately narrower than V6-L1

The original fixed 50% XLK / 30% XLE / 20% IWM high-risk factor basket had **17.89297% historical annual return at 15bps/traded side** during the frequently examined 2014–September 2026 ETF period. The candidate L1 SPY volatility-managed version had **16.23951%**, and its volatility rule cost **1.65346 percentage points/year**, with essentially identical worst drawdown. These are backtests with overlapping research and favourable technology exposure, NOT credible expected future returns or proof of an autonomous trading alpha engine.

S1 is the **fixed concentrated sector equity risk-premium experiment** only; no L1 volatility scaling and no adaptive prediction claim. It remains a periodically maintained factor allocation, NOT a high-frequency bot. If the operator wants evidence of more active stock-selection skill, continue the separate prospective SEC stock and licensed analyst research in parallel. The experiment may have large losses or badly lag ACWI.

**The original S1 95% invested / 5% reserve was NOT included in the initial 100% fixed-sector historical comparison. Do not cite 17.89% as its own validated return.** The 5% reserve is execution risk budgeting, not post-hoc tuning to improve historical returns.

## Proposed contract, for a later separately authorised release

| Feature | Specific proposed S1 rule |
| --- | --- |
| Account | Existing Alpaca LIVE only, original **$130.30** max authorised pilot ceiling; no extra deposits |
| Risk | HIGH, concentrated, long-only, **no borrowing, shorts, options, futures or crypto** |
| Research weights | XLK **50%**, XLE **30%**, IWM **20%** of invested slice |
| Maximum deployed | **95%** of current permitted NAV; **5% minimum cash buffer** |
| Whole-account target weights | XLK **47.5%**, XLE **28.5%**, IWM **19%**, cash **5%** |
| Single ETF max | 50% (a **NEW** risk contract; current V5 HIGH sector limit remains 25% and is NOT relaxed by this file) |
| Account daily loss stop | ≥6% account equity decline — blocks new execution, not guaranteed loss limit |
| Rolling peak-to-trough drawdown stop | ≥20% account drawdown — blocks new execution, cannot prevent market gaps |
| Account annualised realised volatility stop | Greater than 35% — halt new execution pending risk review |
| Orders if released separately | Regular session `DAY` market fractional buys by **notional**, long fractional sells by **quantity** only |
| Minimum notional | Broker's **$1** entry minimum, check each asset `fractionable` |
| Max new single buy order | **$65**, under absolute capital cap |
| Sell → buy transition | Reconcile entire legacy four-ETF portfolio, avoid concurrent V5, wait for cash and actual settlement/buying-power permission; no implicit margin |
| Controls now | `PROPOSED_NOT_LIVE`, V5 operator STOPPED, LIVE kill switch ENGAGED, ZERO order permission |

Illustrative **ONLY IF $130.30 of allowed capital is all available as SETTLED CASH with NO existing positions and all stops pass**, and before true quotes/fees:

- XLK **$61.89**; XLE **$37.13**; IWM **$24.75**.
- Total indicative ETF notional **$123.77**; uncommitted cash **$6.53** (5.01% of authorised pilot).
- Current actual LIVE account **does not meet the all-cash prerequisite**: four V5 ETFs are invested; the Oct18 LIVE account GET proved those positions were still held.
- These figures are NOT submitted order requests, current spendable balance, guaranteed fills or a basis for selling now.

## Actual documented broker constraints

The official [Alpaca fractional trading documentation](https://docs.alpaca.markets/us/v1.1/docs/fractional-trading) and [April 2026 $1 notional minimum response](https://alpaca.markets/support/can-we-submit-orders-smaller-than-1-usd-in-notional-value) describe fractional trading, DAY order and asset eligibility. Live and paper account environments have separate API keys. Fractional permission is per asset, not proven by a paper account in general.

This PR adds a **main-branch-only authenticated GET check of the actual Alpaca PAPER `/v2/assets/XLK`, `/v2/assets/XLE`, `/v2/assets/IWM` records** using the original existing PAPER secrets and the already-tested GET-only helper. It confirms the paper-reported asset status is `active`, `tradable=true`, `fractionable=true`. It does **not** place paper orders, verify live account-specific order permissions, quote spreads, slippage, settlement, account buying power or current prices. It emits only public ticker and boolean eligibility; credentials and private balances are never logged.

Previously on **14 October 2026**, a V5 ETF $2 PAPER buy/sell fill probe successfully demonstrated day order mechanics in the separate prior paper strategy. That result does not independently prove all three new S1 ETFs support fill/reconciliation. A SHORT S1-specific $1–$2 PAPER round trip and order-ID/retry/idempotency verification remains a practical next step once GET eligibility passes; **no months-long PAPER P&L test**.

## Risk math + activation boundary

New files:
`fund100_v6_s1_concentrated_risk_and_paper_asset_v1_0.py`,
`test_fund100_v6_s1_concentrated_risk_and_paper_asset_v1_0.py`,
`research_lab/v6_s1_high_risk_micro_pilot_proposed_manifest.json`,
`.github/workflows/fund100-v6-s1-paper-asset-readiness.yml`.

The immutable proposed manifest cannot be edited to increase cap, alter loss thresholds, add symbols or flip the LIVE switch while retaining its schema. The synthetic-only `theoretical_preview` checks original V5 STOP/policy, live previous-position clearance, fully settled cash, original $130.30 ceiling, per-order minimum, gross reserve, current market hours and risk stops; returns **NO broker order intents** even if all pass.

This is **not an actual reviewed LIVE release**. To switch the user's existing four real ETFs, create a distinct V6 executor and V6 execution authorisation, verify customer/account minimums and fresh GET-only holdings/cash, reconcile staged sales, and safely release the new single strategy without enabling V5. The user's delegated investment-choice discretion is acknowledged; existing GitHub/broker kill-switch and platform approvals cannot be bypassed.

**Current portfolio decision: HOLD ACWI/EEM/XLE/XLV while we verify a true execution route.** Nothing sold. No leverage. No new funding. Original maximum authorised capital $130.30.
