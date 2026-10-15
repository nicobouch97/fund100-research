# Phase 2 bond macro-regime exploratory decision — 15 October 2026

**Decision: RESEARCH ONLY / DO NOT PROMOTE.** No broker execution, PAPER
promotion, trading capital, live-universe permission or exposure-budget change.

## Protocol and evidence

- Implementation: `fund100_bond_macro_regime_v1_0.py`; predeclared rules in
  `research_lab/bonds/PHASE2_MACRO_REGIME_PROTOCOL_V1.md`.
- Code revision: `9608cbf864e151dfe6936c45ccbe4144db05d807`.
- Completed public-data research:
  [GitHub Actions 38702666336](https://github.com/nicobouch97/fund100-research/actions/runs/38702666336).
- Source: vendor-revised Yahoo adjusted bond-ETF daily close histories and
  *currently downloadable* FRED histories for DGS2, DGS10, T10YIE, BAA10Y.
- Common historical bond-ETF dates: 4,726 sessions through **2026-10-14**.
  Downloaded macro dataset: 5,943 complete macro observation days after
  applying a two-business-day **ASSUMED, NOT VERIFIED** availability delay.
  Exact historical release calendars and ALFRED point-in-time vintages were
  **not** independently verified.
- Reproducible CSV inputs and report stored in run artifact
  `fund100-phase2-macro-bond-exploratory-38702666336`, artifact
  `11957470658` (retained 90 days). The JSON contains dataset hashes and
  the fixed rules; no broker account data or live positions.
- Post-merge suite: [GitHub Actions 38702666394](https://github.com/nicobouch97/fund100-research/actions/runs/38702666394),
  **702 tests** passed, existing LIVE static boundary **PASS**.

## Exploratory historical comparison (NOT an independent holdout)

Earlier Phase 2 bond price-only research already inspected this later
historical segment, so these figures cannot be called untouched
out-of-sample validation of the new macro hypothesis. They are cumulative
net-return differences against SHY over the later 30% historical period,
in **percentage points**, not annualized rates or future return estimates:

| One-way trading cost | Macro bond regime vs SHY | Prior 126-session price-only bond challenger vs SHY |
|---|---:|---:|
| 5 bp | -8.0748 pp | -7.8706 pp |
| 15 bp | -10.3948 pp | -9.9808 pp |
| 35 bp | -14.8805 pp | -14.0742 pp |

The macro regime challenger was modestly worse than the prior price-only
challenger in each scenario. Neither demonstrates a credible positive
historical SHY-relative edge in this comparison. The difference may reflect
parameter design, how regimes align with history, trading costs, or vendor
revisions. Do not retroactively optimize these fixed rules using the
already-reviewed data, or present subsequent iterations on that segment as
independent validation.

## Required next step

Keep bond Phase 2 gated as research-only. The next bond hypothesis requires
true vintage/release-timestamp data (ALFRED and published release clocks)
and genuinely prospective evaluation. Unless that can be established,
prioritize Phase 3 commodity ETP **research-only** or the existing Phase 1
genuine ETF PAPER launch milestone. No asset class is eligible to promote
itself from a backtest.

**Fund-100 Phase 1:** existing approved US-equity ETF pilot remains the
only LIVE-whitelisted universe; HIGH portfolio risk, $130.30 maximum pilot
exposure, operator STOPPED and LIVE kill switch ENGAGED remain unchanged.
