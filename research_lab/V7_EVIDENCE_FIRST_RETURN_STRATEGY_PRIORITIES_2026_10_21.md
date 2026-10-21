# Fund-100 V7 — evidence-first returns-oriented strategy priority plan

**Registered 21 October 2026. Research sequencing and operational launch plan only. No LIVE order release or claimed proven alpha.**

## User-selected priorities — preserve ordering by urgency, not promises of return

| Research group | Priority | Next testable step | Fund-wide overlap / execution caveat |
|---|---|---|---|
| Individual US stocks: quality × medium-term momentum | **1 — very high** | Expand real-source price/corporate-action provenance beyond P4G/P4K; SEC quality issuer coverage; strict post-selection net-of-cost stock-vs-SPY/ETF marks | Long stock and XLK/sector ETFs share equity-beta, tech and single-issuer risk |
| Earnings and other event-driven equities | **1 — very high** | Dated SEC 8-K Item 2.02 event time, pre-entry two-session observation, post-entry actual returns; track true analyst surprises only if authentic estimate vintages arrive | An event-driven position is a *stock trade*, not a second capital pool |
| Equity factors: momentum/value/quality/profitability | **1 — very high** | Time-stamped constituent screens with survivorship/delisting/corporate-action and transaction-cost controls; compare to broad and sector/factor ETFs | Factor strategy allocations overlap direct stocks and equity ETFs |
| Crypto BTC/ETH trend/risk regimes | **2 — high** | Independent venue/broker availability and position/custody/access, 24/7 signal and wide-cost scenarios; reject fabricated prospective profit | Extreme gap/operational risk; does not inherit the equity broker's release |
| Commodity trend/carry and exposure look-through | **2 — high** | Extend true futures term structure and CFTC/CME source vintage plus DBC look-through; test investable ETF costs/roll independently | DBC futures energy notional is NOT identical to XLE energy-equity beta |
| Options and volatility structures | **2 — conditional research** | Payoff and expiry/margin/assignment stress first; evaluate only defined-risk permissions and capital eligibility | High risk of 100% premium loss; no LIVE eligibility presumed |
| REITs and listed real assets / infrastructure | **3 — medium** | Listed US-accessible REIT/infrastructure selection, liquidity and financing sensitivity; evaluate relative to sector ETFs | These are often listed equities and count toward equity/real-rate concentration |
| Bonds, credit and rates | **3 — selective** | Complete vintage-correct rate, credit, inflation model; revisit failed SHY late-holdout bond strategy | ETF route realistic at $130.30; direct fixed income may require higher minimums |
| FX liquid major pairs | **4 — longer term** | Dedicated execution broker/permissions, true carry/financing/spread and market calendars, risk-managed no-leverage test | No direct FX trading path in current LIVE Alpaca pilot |
| Direct commodity futures and other derivatives | **4 — longer term** | Margin + exchange contract size, historical original settlement data, basis/roll, no-liquidation stress | Pilot size is incompatible with normal margin or contract-size exposure |

The **P0 operational launch track** is separate: original actual account-bound private sequence-0 HMAC ledger and signed recovery are proven; only the initial guarded ACWI intent-only storage workflow has been merged and is **NOT run**. Complete order ledger reservation/recovery, genuine broker fill/history, independent order-time risk, and separate LIVE transport/release before any real SELL. Do not defer the small pilot until all research streams mature, but do not pretend research plans release a trade.

## Capital and promotion policy

- Treat the initial XLK 47.5% / XLE 28.5% / IWM 19% / cash 5% as **PROPOSED 100% of the entire fund**, not a permanently protected ETF sleeve. Nothing is now allocated to standalone stock, crypto, credit, event or factor sleeves. Every later promoted strategy MUST compete for the same total capital/risk budget.
- The active account's **$130.30 original pilot capital ceiling** is immutable here. Illustrative research limits from the existing `fund100_multi_asset_portfolio_arbiter_v1_0.py` are NOT live risk caps, actual holdings, or broker buying power. Do not add e.g. 10% crypto *on top of* a 95%-invested equity portfolio.
- Distinguish three classifications: (a) **instruments** such as stock, ETF, option, future, bond, (b) **underlying exposures** such as equity, rates, commodity, crypto, and (c) **alpha mechanisms** such as earnings PEAD, quality/momentum/factor, trend, event or carry. A factor overlay is NOT automatically a unique diversified asset.
- Candidate preregistration must contain a dated source, honest coverage and point-in-time/corporate-action review, benchmark, replicable signal, 5/15/35bps *per side* research stress plus spread/fee/funding/micro-notional rounding where appropriate, and independent later source vintage or honest historical nested walk-forward. The short pilot does not need to wait months in PAPER to begin *its already-approved* LIVE strategy, but no new candidate self-promotes on one attractive backtest.
- Assessment prioritizes expected **net** return under genuine capacity and total risk, not strongest hypothetical CAGR alone. Risk includes maximum loss, bankruptcy, drawdown, correlated losses, liquidity, and the inability to exit in a discontinuity. One day's stock P4K result did not beat SPY (15bps/side: −0.034129% vs +0.034520%). Original late-period bond regimes failed against SHY. Commodity forward study so far mostly remained SHY; nothing demonstrates excess returns. Options, FX, REITs and factors are new research, not currently proven.
- Promotion gates: `RESEARCH_HYPOTHESIS` → `SOURCE_QUALIFIED` → `EVALUATED_NET_COST` → `BROKER_PRACTICAL` → `REVIEWED_EXECUTION_CANDIDATE` → **independent explicitly versioned LIVE release**. Advancement is evidence-specific; stage tags NEVER constitute brokerage authority. Source failure or high worst-case loss may reject an idea before paper/live tests.
- No auto-training on noisy small-funded returns. Algorithms may propose challenging new hypotheses with versioned manifests and immutable evidence; the allocator cannot change current risk caps, trade instruments or LIVE STOP by itself.

## Source-frozen baselines and explicit dependencies

The existing frozen `research_lab/V6_INVESTMENT_PHILOSOPHY_THESIS_REGISTER_2026_10_19.json` and `fund100_v6_investment_thesis_gate_v1_0.py` remain the authoritative original seven-thesis history. This new V7 **overlay queue** groups equities into direct stock / event / factor experiments and adds listed real assets and derivatives *as separate research only*; it does not modify the original register or its currently tested capital arbiter.

Already created evidence references:
- Stock P4K actual one-interval negative relative result: `research_lab/stocks/P4K_FIRST_REAL_AUTHENTIC_FORWARD_MARK_RESULT_2026_10_21.md`.
- SEC earnings event registered source: `research_lab/stocks/V6E1_REAL_SEC_EARNINGS_CATALYST_PROTOCOL_2026_10_17.md`.
- Investor-inspired actual original seven-family thesis register: `research_lab/V6_INVESTMENT_PHILOSOPHY_THESIS_REGISTER_2026_10_19.json`.
- Genuine quarter-dated DBC source: `research_lab/commodities/V6_C11_SEC_FILING_DBC_LOOKTHROUGH_PROTOCOL_2026_10_21.md`.
- Failed early bond screening: `research_lab/bonds/INITIAL_HOLDOUT_REVIEW_2026_10_14.md`.
- Original crypto 24/7 proposal: `research_lab/crypto/V6C1_CRYPTO_24_7_TREND_PROTOCOL_2026_10_17.md`.
- Existing shared capital conservative scenario: `fund100_multi_asset_portfolio_arbiter_v1_0.py`.

**This PR contains no quotes, brokerage credentials, secret, private JSON body, position size, brokerage POST, change to original HIGH STOP, trade-state CAS or LIVE orders.**
