# V6-S1 5%-cash rule resolution — order-time reserve and pause, NOT forced daily churn

**19 October 2026. Source-pinned exploratory engineering only. Not a live risk policy or trade permit.**

## Problem actually established

[Original S1 exact 95%-invested historical check](https://github.com/nicobouch97/fund100-research/actions/runs/39249437572) found **2,792 post-entry sessions** with CASH / NAV **below 5%** in the unchanged 2014–September 2026 month-end/banded-drift strategy. The historical minimum was approximately **2.3371%** cash. Its 2014-onwards original source exploratory return **17.08743%/year at 15bp per traded side** is NOT an independently valid expected return or an active alpha result.

An unqualified "**hard 5% minimum cash each session**" is mathematically incompatible with passively letting a **95% invested** portfolio rise in value while a fixed number of idle dollars sit in cash. Even a daily rebalance can breach before its next decision bar; a 24/7 unconditional percentage guarantee cannot be supported by monthly trades. Automatic tiny forced trims may violate Alpaca $1 fractional minimum and create tax, spread and execution costs disproportionate to the entire $130.30 trial.

## Two honest alternatives — pre-execution research design

**A. Strict continuous 5% of current NAV cash floor**: would require monitoring and trading at much higher frequency, a market-gap plan, strict sell sizes/permissions, conservative future price buffer and budget for spread/slippage. Cannot honestly guarantee this across closed markets with an exposed ETF portfolio. Our original S1 historical implementation **does not meet A**.

**B. 5% whole-account cash TARGET at funded entry, with mandatory at-order >=5% NAV cash check and automatic HOLD/PAUSE of new purchases when passive appreciation or transaction costs move it below 5%. No forced sell solely because portfolio NAV rises.** This is coherent for a tiny account and aligned with low turnover. It is NOT a permanent intraday cash minimum. It permits the observed 5% fractional drift during HOLD, but no new funded buy may use the reserve and no broker-side 95% exposure expansion may be silently permitted.

### Engineering recommendation: B, pending separate versioned live policy

Use original S1 targets **XLK 47.5%, XLE 28.5%, IWM 19% and 5% uncommitted cash AT ENTRY**, remain long-only, original original-capital authorization **$130.30**. Explicitly rename the proposed risk control from '5% minimum cash at all times' to **'5% minimum of fresh NAV immediately after each newly authorized BUY, net of conservative expected ALL-IN costs; idle cash percentage may drift when there are no orders'**. A separate reviewed LIVE release would also require adequate cash + trade-fee headroom, broker-source settled funds, locked operator execution, current positions/cost basis, real risk stops and order reconciliation.

The original file `research_lab/v6_s1_high_risk_micro_pilot_proposed_manifest.json` is intentionally **NOT edited**: it remains the old contradictory `PROPOSED_NOT_LIVE` contract. Changing this policy requires a NEW, separately versioned signed launch policy and live adapter. Our present module merely demonstrates B as a pure mathematical risk preflight, never assuming LIVE data source authenticity or account-specific fees.

## Tested outcomes (pure synthetic, no real account access)

`fund100_v6_s1_cash_at_order_no_churn_v1_0.py` accepts a caller's **UNVERIFIED GET-ONLY CLAIM**, fresh 5-minute timestamp, reconciled cash/equity/position market values, the STOP controls and optional purely hypothetical notional and conservative ALL-IN cost estimate.

- **Original illustrative three S1 trades at zero trading fees**: entry purchases $61.89, $37.13 and $24.75 leave exactly **$6.53** cash from a fully settled original $130.30 balance (5.0115%). This is just pre-trade arithmetic and certainly not proof of Alpaca executable spreads/fills.
- If the final $24.75 order requires even **$0.02** in actual transaction costs while the account has $31.28 cash, its remaining **$6.51** is less than **5% × $130.30 = $6.515**. **Block**, rather than fudge the cash rule or round a broker balance in our favor.
- With original ETF investments appreciated 20%, an unchanged ~$6.53 cash reserve becomes less than 5% of elevated NAV. Return `NO_NEW_BUYS_HOLD_AND_RECONCILE` rather than make a micro SELL just to enforce an impossible continuous floor.
- Open orders, legacy positions or restricted source are blocked/paused; missing/forged numbers, clocks, nonfinite values and contradictory account equities fail shut. There is **no broker client, POST, GET or order payload**.
- The illustrative buy status `HYPOTHETICAL_BUY_SCREEN_CLEARED_NOT_AUTHORIZED` specifically is **NOT a trading authorization**. An actual LIVE executor will need additional independently authenticated risk/cap/settlement checks. The script intentionally does not use an API, broker keys, actual filled positions, customer account ID or price feed.
- This does NOT evaluate the original 6% daily account-loss, 20% drawdown or 35% realized-volatility rules; their proofs are still mandatory in an eventual separate LIVE release.

## Research decision and immediate next step

Promote **B only as the next candidate release design**, not as live permission, and preserve the earlier historical 95%-target economics as descriptive evidence; they already allowed daily cash-ratio drift. Do not optimize monthly or daily rebalance triggers against this same history after observing the failure.

Continue original **19 October 2026 at 13:43 UTC** Alpaca PAPER $2 fractional buy/sell rehearsal; its actual run and both FILLS must be seen, not assumed. A successful PAPER mechanics test is necessary to verify execution plumbing and is unrelated to historical outperformance. No months-long PAPER-return waiting period is created.

Separately, independently verify the real account's original four holdings, available settled cash, operator STOP, kill switch and share-side constraints before even preparing a new versioned real-world transition. Existing actual real holdings ACWI/EEM/XLE/XLV are not sold. Capital ceiling HIGH/$130.30 and original ETF-only LIVE universe remain unchanged.
