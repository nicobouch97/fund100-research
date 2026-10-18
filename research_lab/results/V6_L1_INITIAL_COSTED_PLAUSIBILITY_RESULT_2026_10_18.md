# V6-L1 initial precommitted costed historical result — plausibility passed, alpha unproven

**First actual original research run 18 October 2026:
[GitHub Actions run 39164109643](https://github.com/nicobouch97/fund100-research/actions/runs/39164109643).**

The strategy selection/exposure/20-session SPY-vol/30%-boundary/month-end/10-percentage-point rebalance/costs were FROZEN in
`research_lab/V6_L1_FROZEN_AGGRESSIVE_VOL_REGIME_FAST_LAUNCH_2026_10_18.md`
**before this original-source historical test. No tuning has occurred.**

Only original locked
`research_lab/frozen_history_v2.csv`, SHA256
`acc2c8c08953b895ca5062b3cfba287efb97143b10e108e8ce4bd8b82ffb0d28`,
was accepted. 13 source/no-lookahead/no-orders synthetic regression tests
and this first real backtest completed successfully. This
2014–2026 history was already used in several Fund-100
hypothesis tests, so results remain **exploratory and NOT an
independent forward validation or alpha forecast**.

### 2014–September 2026 actual source, modelled costs per side

| Side cost | L1 CAGR | ACWI CAGR | L1 minus ACWI | L1 max drawdown | Annual gross weight turnover |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 5 bps | 16.31800% | 12.29808% | +4.01992 pp/yr | −34.27826% | 0.67470× NAV |
| 15 bps | 16.23951% | 12.29808% | +3.94143 pp/yr | −34.29313% | 0.67470× NAV |
| 35 bps | 16.08258% | 12.29808% | +3.78450 pp/yr | −34.32287% | 0.67470× NAV |

The original volatility gate occurred at **10 month-end
decision points**. This does not prove it increased returns.
An equal-weighted or fixed-allocation
**unmanaged comparison using the exact same XLK/XLE/IWM
underlyings** remains to be done as a separate diagnostic;
without it, apparently attractive L1 outcomes could simply
reflect large historic sector exposure, especially XLK.
No underperformance rescue tuning is permitted.

### Descriptive 2020–September 2026 (NOT independent)

| Side cost | L1 CAGR | ACWI CAGR | L1 minus ACWI |
| ---: | ---: | ---: | ---: |
| 5 bps | 17.52440% | 12.18279% | +5.34161 pp/yr |
| 15 bps | 17.40909% | 12.18279% | +5.22630 pp/yr |
| 35 bps | 17.17863% | 12.18279% | +4.99584 pp/yr |

This favorable recent period cannot create statistically
credible prospective return expectations.

### Original preregistered experimental PLAUSIBILITY gate: PASS

- Annual gross trading turnover <=4×: **PASS**, 0.67470×.
- 15bps maximum modelled historical drawdown not below −60%:
  **PASS**, −34.29313%.
- Annual net return at 35bps above −5%:
  **PASS**, +16.08258%.
- At least one volatility-management decision occurred:
  **PASS**, 10.

**Meaning: eligible for a costed launch-engineering feasibility
discussion only. NOT yet executable or demonstrated skill.**

The user's selected HIGH tier has V5's original non-ACWI
sector maximum of **25%**. L1's **50% XLK** breaches that
permission. L1 needs a separately versioned concentrated
risk model with loss limits, stale-mark handling, and
a tested minimal-paper-fills LIVE execution controller.
No direct trade, new cash, stop release or early gains
guaranteed by the PASS outcome.

Actual 18 October LIVE Alpaca account verification still
shows original four ACWI/EEM/XLE/XLV ETF quantities
unchanged and zero open orders. Those investments remain
HELD; operator STOPPED, last audited kill switch ENGAGED,
authorised original capital **$130.30**.
