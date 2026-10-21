# V6-B4: original issuer-dated 19 Oct bond duration snapshot (research-only)

**Pre-registered 21 October 2026 before applying exposure calculations.**

## Evidence and economic mechanism

Unlike ETF ticker/category labels, effective duration measures approximate percentage bond-price sensitivity to small yield changes. Verify original iShares US issuer product pages, separately date the reported portfolio characteristics and actual **first research web retrieval**.

All five following effective durations were **displayed with "as of Oct 19, 2026"** when inspected on 21 Oct 2026; manual public-page transcription, NOT raw-HTML bytes or a timestamp-authenticated daily history:

| ETF | ETF driver | Effective duration, years | Original issuer page |
| --- | --- | ---: | --- |
| TLT | Nominal US Treasury rate | 14.79 | https://www.ishares.com/us/products/239454/ishares-20-year-treasury-bond-etf |
| IEF | Nominal US Treasury rate | 6.83 | https://www.ishares.com/us/products/239456/ishares-7-10-year-treasury-bond-etf |
| SHY | Nominal US Treasury rate | 1.80 | https://www.ishares.com/us/products/239452/ishares-1-3-year-treasury-bond-etf |
| TIP | Inflation-linked US Treasury *real* yield | 6.16 | https://www.ishares.com/us/products/239467/ishares-tips-bond-etf |
| LQD | Corporate bond rates AND option-adjusted credit spread | 7.54 | https://www.ishares.com/us/products/239566/ishares-iboxx-investment-grade-corporate-bond-etf |

All pages explicitly state data are subject to change; exact HTML bytes and first publication UTC were NOT collected. The observation cannot be used as if available on 19 Oct and must NOT enter a historical backtest before research capture date **21 Oct**. The separately checked-in normalized JSON has a pinned Git blob SHA. This is a **single dated cross-section, not a validated time series or live account risk measurement.**

## Registered synthetic cross-asset experiment

- Fund-100 one-fund **$130.30 synthetic capital cap**, original 95%-at-entry scenario unchanged, no leverage. S1 equity $50 across **XLK 50%, XLE 30%, IWM 20%**; commodity research C10 $20 through DBC; bond research B3 $40 evenly across **TLT/IEF/SHY/TIP/LQD**; $20.30 nominal cash. This is invented capital for risk diagnostics only, NOT selected strategy performance or a recommended holding.
- Reuse central arbiter, existing C12 check (with June SEC DBC filing dated 30 June, published by 10 Aug, ~47% energy gross-futures-notional), and the same original thesis IDs. Recognize unknown equity index look-through and DBC actual daily weights.
- Compute **first-order duration-dollar sensitivity** for each hypothetical bond ETF as `notional_usd × effective_duration_years`; a modeled **+100bp shift in each instrument's relevant yield driver** has `-duration_dollars / 100` approximate dollar P&L. This mixes real yields, nominal Treasury yields and corporate total yields as a *joint deliberately artificial shock*, not a single economic factor or realized portfolio drawdown.
- Keep Treasury nominal rate, TIP real-rate and LQD blended corporate rates/spreads as **three separate buckets**. Do NOT sum them into one homogeneous measured Treasury-duration exposure, infer yield-curve key-rate duration, assume unchanged spread or infer independent portfolio performance. Bond duration shock ignores convexity, carry, coupons, embedded optionality, realized ETF price tracking and transaction costs.
- Even with complete five issuer rows, capture remains a **manually normalized web observation**: fresh for illustrative **21-Oct research ONLY**, not continuous verified portfolio holdings and not authorised LIVE factor weights. Other symbols do not become cash or zero-beta.
- Fail closed on unrecognized/unknown bond ticker if assigned positive capital; source tampering; missing rows/duplicates; untrusted/early/backdated date; risk label 'CASH' for material bond ETF; unauthorized order flags, financing or fund capital cap.

The original V6-S1 proposed 95% entry / 5% cash, current real account four ETFs, HIGH setting, STOP, ENGAGED kill switch, no derivatives and $130.30 pilot cap remain unchanged. No API credentials, browser automation in CI, broker calls, signals, orders or live permissions.
