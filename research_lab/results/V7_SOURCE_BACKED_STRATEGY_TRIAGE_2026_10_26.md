# Fund-100 V7 — original-source strategy triage and next capital decision

**26 October 2026. Source-backed investment research decision, not a live trading release.** This update records results observed in the actual successful GitHub Actions main-branch original-source runs. It is not a new parameter fit, a prospective return forecast, or a backtest alpha assertion.

## 1. SEC stock quality: ABSTAIN/DO NOT PROMOTE

Original [P4N/P4R/P4AB post-merge 40345993054](https://github.com/nicobouch97/fund100-research/actions/runs/40345993054) captured official SEC issuer history and original source-hashed vendor price observations on the protected `main` workflow; every source stage ran and passed. Archived `quality-calendar-regime-fragility.json` SHA256: `a88047af1a8a2ce56283dce953a96ebdd082be5c906e41c6104699c7c1417d08`; `quality-126-session-event-study.json`: `058c0d023cfd618d63af501748d7903ce66591153aba6c8b3c44c906771ba042`.

- **63** historical 126-session stock-minus-matched-SPY events, **12** distinct issuers; each of the stock and matched SPY sides charged the 15bp-side model. Original cohorts were selected using **2026 surviving issuers**; vendor history is revisable and SEC CompanyFacts was retrieved in 2026, not vintage archived in prior calendar years.
- Across all events, average stock excess was +0.901727 percentage points, but **median was −2.5065pp; only 44.44%** of events beat same-period SPY. Do not promote on the positive mean.
- High original SEC quality (2/3) had **54 events / 10 issuers / +0.734168pp mean**, versus score 0/1 with **9 events / 2 issuers / +1.907076pp mean**. This overall cross-issuer contrast cannot establish quality ranking skill.
- The fixed same-entry-year issuer-equal high-minus-low comparison had both quality groups in 8 calendar years, but only **one** year had at least 2 disjoint issuers per group (2025), yielding a **−0.455711pp** high-minus-low quality spread. It therefore FAILED the predeclared descriptive breadth screen of 4 comparable years over at least 2 regimes: `ABSTAIN_INSUFFICIENT_COMPARABLE_YEARS_OR_REGIMES`.
- The attractive *separate* historical six-slot, SPY-funded portfolio result (**17.100049% net historical CAGR against 14.966582% SPY, difference +2.133467pp**) uses 25 retrospectively selected admission events and is **not investable alpha**. Its survivor bias, future-selected roster, overlapping exposures, missing delistings and unverifiable contemporary trading remain unresolved. This 2017–2026 historical average MUST NOT be treated as a forward return forecast.

**Decision:** no LIVE stock-selection quality signal, and no attempt to optimize score thresholds/lookback/costs on these same 63 events to rescue the hypothesis. We can revisit only after a genuinely independent historical common-share universe, full delisting and corporate-action return treatment, original SEC as-of reporting, and untouched evaluation material are available.

## 2. SEC diluted EPS earnings yield: ABSTAIN/DO NOT PROMOTE

Same original research run, archived `gaap-eps-yield-event-diagnostic.json` SHA256 `f398b79b1b08c6e564bd45856f48a9d1884a5a4dc6927a2b1b97690883e76520`.

- Original accession-linked diluted EPS was found in **58/63** events; the original, previously fixed 5% earnings-yield cutoff is not a model-calibrated alpha threshold.
- With **positive pre-filing SPY-relative momentum**, just **4 high-yield events from 3 issuers**, compared with **27 lower-yield events from 9 issuers**. The high-yield event mean (+1.476709pp) is actually lower than the low-yield (+4.183543pp), despite a positive issuer-paired difference in the tiny matched sample.
- Restricting to **same issuer AND same prior-momentum sign**, high-minus-low net 15bps matched-SPY event differences average **+10.300939pp among only 3 paired issuers** under positive momentum; for nonpositive momentum the apparent **+19.170746pp** comes from **only 1** paired issuer. Both are explicitly flagged insufficient (<5 independent issuer pairs) by the source model. These are **not** expected future gains.
- Split-adjusted as-traded price reconstruction, dilution/share-class comparability, survivor bias, and vendor revisions remain material.

**Decision:** neither momentum-conditioned EPS yield subgroup is qualified to predict Fund-100 switching. Do not infer a winning return merely from three favorable issuers or a single high-yield company.

## 3. Gold versus cash trend: research comparison, not an equity-alpha replacement

Original source-backed C13 [run 40298967469](https://github.com/nicobouch97/fund100-research/actions/runs/40298967469), `fund100-c13-gold-cash-trend.json` SHA256 `57f8050adf29776b7b961ce784b2ad4f0aca7d43cd71b96adeee057a074334c9`. Fixed 75%-equity XLK/XLE/IWM common sleeve; compares cash vs an additional **10% GLD**; 15bp per ETF side and IRX-gross lagged illustrative cash accrual.

- 2014–2026: net CAGR **13.0273% dynamic gold/cash**, **13.2087% static 10% gold**, **12.3320% all 25% cash**. Dynamic advantage +0.6953 percentage points/year versus cash, **−0.1814pp/year versus simply holding static 10% gold**.
- Dynamic max drawdown **−31.7417%**, versus cash control **−31.4539%**. The dynamic strategy made 22 gold/cash switches and 6.774534x initial-NAV notional turnover.
- Relative log wealth over cash benefited heavily from **2025 (+4.660036pp out of total +7.901382pp)**. The 126-day rule was developed after seeing static gold historical behavior; these same dates were already examined, and removing 2025 arithmetically is not a forward holdout.

**Decision:** the current dynamic GLD timing signal lacks incremental advantage over the simpler static-gold comparator. Do not promote it to a funded active return seeker. Gold diversification can remain a separate future total-fund allocation consideration, subject to capital limits and independently better evidence.

## 4. What changes next — progress toward an actual active fund

**Priority A: source-independent direct-equity/factor or event thesis.** Start from the historical issuer/security population, not a 2026 survivor roster. The existing P4T official 2017 full 10-K census of 7,074 filers is *not* a listed-common-stock universe. Next valuable research must obtain authentic historic listed-share identifiers, delisting/total-return treatment, as-of availability and a predeclared event/factor rule versus simple ETFs. No more fitting the failed SEC score or the previously rejected original eight-issuer post-earnings price-reaction model. If an independent analyst-revision source is unavailable, report that blocker explicitly and redirect, rather than invent it.

**Priority B: genuinely distinct commodity carry and crypto risk/return mechanisms only with credible accessible instruments and data.** Current C6 CFTC positioning+ETF trend and C1 BTC/ETH active strategy failed their original economic gates (see their 17 October result files). A different, dated futures roll/carry thesis or lower-turnover crypto hypothesis would require new source and genuine broker suitability evidence; do not retune rejected versions in-sample. At the original $130.30 account size, large-margin direct futures/options/FX are not assumed tradable.

**Portfolio implementation readiness:** PRs #275 and #276 implemented research-only cost-aware multi-candidate HOLD-versus-SWITCH selection, including settled cash for purchase friction. That is a useful allocator, **not** a source-certified return prediction. The existing live account may appreciate but the original pilot cap is **$130.30**, HIGH 50% single-name, 95% gross, 5% reserve, $65/order. The owner wants automatic decisions and ongoing trades **without per-trade confirmation once the standing mandate is activated**, but the existing operator STOP and engaged broker kill switch remain in place. No sell/buy order or live release is authorised by this research note. Do not liquidate ACWI purely to complete an engineering milestone.

## Accountability

This decision was formed *after* reviewing the actual October 26 source outputs; it is deliberately an observed-result triage, **not** a pre-registered alpha validation, and none of these historical figures is a future-return estimate. The next strategy investment should be measured against a simple genuinely investable passive comparator, net of feasible costs, from issuer/security population and source timestamps that would actually have been available at the decision dates.
