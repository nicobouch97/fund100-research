# Fund-100 Phase 3 — Commodity candidate C2 review (15 October 2026)

**Decision: C2 RESEARCH ONLY; NO PAPER or LIVE promotion.**

The user requested ongoing commodity strategy development, rather than
abandoning commodities after the first challenger failed its benchmark.
C2 was separately preregistered under
`research_lab/commodities/C2_REAL_YIELD_INFLATION_PROTOCOL_2026_10_15.md`,
using physically backed GLD's real-yield/credit stress response and a
breakeven-inflation/price trend gate for futures-linked DBC.

## Research execution

- Code: `fund100_commodity_macro_c2_v1_0.py`.
- First fixed-code merge SHA `37a05f4ba8dbf3bc2eca0decfbfe0bab9dd27d78`
  ([PR #19](https://github.com/nicobouch97/fund100-research/pull/19)).
- Real public-data research [Actions run 38711280282](https://github.com/nicobouch97/fund100-research/actions/runs/38711280282).
- Price source SHA256:
  `1bf5970d977b3655d5551fcd38ed3f8df037dc5eb9dd69bd24fb12a7dc19a62f`.
- Macro source SHA256:
  `d7bc0f91846e48d93409a32e1d6a027d9133f3c91299d4970d70ddb2ed2d575b`.
- Public macro dataset: 5,943 aligned complete observation dates, latest
  retained observed 9 October 2026. Availability is **ASSUMED** observation
  date plus two business weekdays, NOT actual ALFRED vintage history nor
  verified publication times. Present-day downloaded history can be revised.
- Test run [38711280290](https://github.com/nicobouch97/fund100-research/actions/runs/38711280290):
  **727 tests** passed, LIVE static boundary PASS. Thirteen specific
  C2 tests passed with one nonfatal dependency deprecation warning.
- No live broker API, credentials, order endpoints, broker permissions or
  whitelist changes. Full priced and macro CSV artifacts linked from
  research run; persist decision separately after the artifact expires.

## Historical comparison

Historical late-segment sample was already examined by the C1 commodity
study, and is **NOT** an untouched out-of-sample period for C2.
Figures below are *cumulative differences in percentage points against
SHY over the later sample*, not annualised alpha, investment forecasts,
or live/PAPER returns.

| Cost per traded side | C2 real-yield/inflation | Earlier C1 trend | Monthly static 20% GLD / 15% DBC / 65% SHY |
|---|---:|---:|---:|
| 5 bps | +12.53476 pp | +29.19026 pp | +39.68468 pp |
| 15 bps | +11.28596 pp | +27.91679 pp | +39.50014 pp |
| 35 bps | +8.82557 pp | +25.40366 pp | +39.13174 pp |

C2 trails both C1 and a simple capped static commodity mix at all costs.
Underperformance of specific active models does NOT logically imply
commodities lack portfolio diversification potential. It does show that
these tested active rules have not earned additional complexity or capital.

## Research next steps (new evidence required)

- Treat capped static GLD/DBC/SHY mix as an honest *benchmark champion*,
  **not** a proven LIVE-ready commodity strategy.
- Develop a truly **independent futures-curve and carry** hypothesis for
  DBC from historical, time-stamped contract-level term structure /
  roll schedule, NOT from pseudo-carry inferred from its ETF price.
- Research gold separately as a portfolio hedging sleeve using real-time
  real-yield vintages and equity stress data; do not adjust historic C2
  rules to improve this already observed result.
- Establish a **prospective, append-only research-only comparison**
  of static baseline, C1 and C2, with dated observations, realistic costs,
  source digests, no brokerage account access and no possible self-promotion.
- Require stronger net, risk-adjusted *prospective* performance over
  appropriate baselines before even proposing standalone commodity PAPER.
- Preserve existing Fund-100 V5 US ETF LIVE whitelist, HIGH tier, operator
  STOPPED, $130.30 capital ceiling and engaged LIVE kill switch.

**Status: `COMMODITY_C2_HISTORICAL_EXPLORATORY_NOT_PROMOTED`.**
