# V6-S1 original 95%-deployed cash-reserve economic audit (pre-result protocol)

**Frozen 19 October 2026, BEFORE first actual original-price study of the 95%-deployed S1 allocation.** No market outcome or threshold has yet been used to change S1.

## Why this study is necessary

The 18 October V6-L1 study showed that the ORIGINAL **100%-invested** sector basket (XLK 50%, XLE 30%, IWM 20%) had an exploratory, costed historical return of 17.89297%/year at 15bps per traded side over 2014–September 2026. The proposed S1 cash-account contract is **different**: XLK 47.5%, XLE 28.5%, IWM 19%, cash 5%. The first result **cannot** be passed off as S1's own historical result.

More importantly, the manifest describes a 5% **minimum** cash buffer while the first proposed holding rule maintains a 5% **target** only when the monthly 10-percentage-point drift band is triggered. If equities appreciate between rebalances, the amount of cash remains essentially fixed while total account equity rises: the cash percentage falls below 5%. Consequently the existing static/month-end architecture is not a true continuous hard 5% reserve rule. We will measure the discrepancy BEFORE considering any execution version.

## Precommitted analysis

1. Use ONLY SHA256-verified `research_lab/frozen_history_v2.csv` with locked original digest `acc2c8c08953b895ca5062b3cfba287efb97143b10e108e8ce4bd8b82ffb0d28`. This history has already been repeatedly studied and is **exploratory**, never fresh out-of-sample alpha evidence.
2. Reproduce the original month-end schedule and >=10 percentage-point drift trigger, lag-safe completed data, no volatility overlay and original flat-zero cash yield. Decision-day close fills are hypothetical and favourably assumed; daily price returns first accrue on following sessions.
3. Exact whole-account S1 target: XLK **47.5%**, XLE **28.5%**, IWM **19%**, cash **5%**. No optimization, tickers or target changes allowed in response to results.
4. Use fixed **5 / 15 / 35 basis points per BUY or SELL traded weight** exactly as in prior L1 frozen research, including initial entry. The current L1 simplified transaction-cost NAV convention (expense reduces NAV but is not separately removed from weight-level cash on the same date) is retained solely for apples-to-apples historical comparison. It is **optimistic** for precise cash-reserve enforcement, not a broker quote or settlement simulator.
5. Compare exact S1 to the previously implemented `fixed_mix` full-risk 50/30/20 study and ACWI over **2014 onward** and descriptive **2020 onward**, using original CAGR, maximum drawdown, realized daily volatility, worst day, gross turnover and rebalance count.
6. Count sessions with <5% cash after close, sessions when cash was already <5% BEFORE a month-end rebalancing decision, and sessions when any sector weight exceeded 50%; capture min modeled cash allocation and maximum exposure.
7. If any full history post-entry trading session breaches the 5% cash floor, state **"95% target cannot certify a continuous 5% cash minimum"**; an actual LIVE rule must separately reconcile daily cash/fill/fees and enforce minimum or explicitly rename reserve as a target with adequate extra buffer. Do NOT retroactively choose a convenient new 3%, 4%, 6%, daily trim cadence or altered cost assumption to rescue this backtest.
8. S1 source is unproven selected high-beta sector exposure and is **not** a genuine active equity stock-selection alpha bot. A historical gain over ACWI cannot support a future CAGR forecast. This diagnostic gives no broker orders or promotion permission.

## Launch implication

A completed positive historical S1 result **does not** remove the S1 PAPER $2 mechanical fill requirement, LIVE liquidation/settlement controls or original V5 STOP. This is a candidate-specific economics **and risk-contract consistency** gate, not a demand for weeks of paper profits. The user's original $130.30 capital ceiling, HIGH risk setting and delegated investment-choice discretion remain unchanged. Real original holdings stay ACWI/EEM/XLE/XLV.

Code: `fund100_v6_s1_exact95_costed_cash_floor_v1_0.py`.
Offline regressions: `test_fund100_v6_s1_exact95_costed_cash_floor_v1_0.py`.
Actual original-source diagnostic first to execute in review CI after this document is committed; archive complete JSON in short-retention GitHub artifact, preserve a permanent concise outcome report separately.
