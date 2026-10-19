# Fund-100 | Sequenced multi-asset build plan

Status: engineering plan, 14 October 2026. This document is **not**
authority to trade or expand LIVE permissions.

## Mission

One operator-selected LOW / MEDIUM / HIGH risk level governs the
*combined* portfolio; one STOP control blocks all strategy engines.
Strategies compete for capital on forward-tested, cost-adjusted evidence,
not number of markets, backtest return, or how often a bot trades.

## Phase order and acceptance gates

| Sequence | Scope | Distinct investment thesis | Progress and promotion rule |
|---|---|---|---|
| **1: ETF pilot** | US-listed global/sector equity ETFs (V5-002) | ACWI benchmark core plus relative momentum satellite, threshold-based rebalance, constrained exposure | **CURRENT:** genuine V5 PAPER strategy runner operational and micro-fill broker test completed; awaiting naturally scheduled strategy rebalance and reconciliation. LIVE GET-only readiness verified, operator STOPPED; any LIVE release requires separate explicit approval |
| **2: Bond ETFs** | TLT, IEF, SHY, TIP, LQD (research universe, not LIVE-whitelisted) | Duration / yield-curve regimes, inflation surprise and credit-spread compensation; protect capital when equities struggle | Price-only and predeclared macro-regime bond research completed; both underperformed SHY in reviewed historical late periods across 5/15/35 bp costs. NO PROMOTION. Real vintage/release-time proof and prospective paper evaluation remain necessary |
| **3: Commodity ETPs** | GLD, DBC (research universe, not LIVE-whitelisted) | Trend / inflation regimes / curve carry where applicable; ETF tracking, roll costs and concentration matter | C1 trend and C2 gold real-yield/inflation challengers both lag the capped static GLD/DBC mix in known history. Prospective daily public-data shadow scorecard now operational, research only; independent futures curve data and later forward performance required before any trading promotion |
| **4: Individual US stocks** | Liquid unlevered shares | Quality and earnings revision trends plus medium-term momentum; fundamental and corporate-action filters | Point-in-time fundamentals, delisting/survivorship-safe history, realistic turnover, diversification, corporate actions |
| **5: Crypto** | Existing **separate** BTC/GBP synthetic paper bot | Slow momentum and long-run trend in a 24/7 market with high gap/liquidity/custody risk | Continue prospective forward paper; demonstrate improvement versus simple buy-and-hold net of costs, integrate 24/7 monitoring and exchange-specific API before any LIVE enablement |
| **6: Direct FX** | Major liquid pairs, contingent on brokerage access | Rate differential/carry conditioned on economic regime and trend; account for overnight financing | Dedicated broker/API, realistic spreads/slippage, timezone/event calendar and leverage/margin prohibition or explicit risk model |
| **7: Options/futures** | Only if later justified by independent tests | Structural hedges, carry or volatility opportunities, not naked directional bets | Derivatives account permissions, Greeks, margin, expiry/assignment/roll, stress and capital controls; separate human release decision |

This sequence is subject to empirical evidence and broker permissions.
An asset class may remain paper-only indefinitely if no durable edge appears.

## Non-negotiable shared contracts

1. Risk-level budgets are TOTAL portfolio budgets, not a complete
   budget for each bot. Aggregate asset, sector, factor, currency and
   broker exposures, including overlapping ETF look-through where known.
2. Existing Fund-100 pilot ceiling **USD 130.30** remains a separate
   hard LIVE boundary. No additional deposits enlarge it automatically.
3. No shorting, leverage or options in the current pilot.
4. No bot may self-promote a new strategy/asset universe to LIVE from
   a backtest; it may automatically test and rank research candidates.
5. A single operator STOP must halt new execution across all engines.
   Existing fills/positions require an explicit separate response policy.
6. Each new market must pass: clean point-in-time research, walk-forward
   testing, multiple cost scenarios, independent prospective paper
   operation, end-to-end failure testing and capital/broker reconciliation.
7. Risk monitor must account for each market's actual trading session:
   equities/bonds trading hours; crypto 24/7; FX across time zones.
8. Keep model-selection data separate from evaluation data and preserve
   immutable experiment records. Backtest outperformance alone is not
   proof of an exploitable edge.

## Current milestone evidence

- V5-002 LIVE policy permits only 14 US-listed broad/sector equity ETFs;
  direct crypto, options, FX, bond and commodity orders are not approved.
- The standalone BTC/GBP bot is an independent **imaginary-money**
  experiment with no live-order keys.
- `fund100_etf_paper_rehearsal_v1_0.py` exercises the production
  strategy parser, sizing, risk guards, SELL/BUY orchestrator, cap
  proof, synthetic fills, restart idempotence and STOP response.
  It **does not** connect to Alpaca's paper trading account.
- On **14 October 2026**, `fund100-connected-paper-launch-gate.yml`
  successfully combined the V5 synthetic ETF acceptance suite with
  a real **Alpaca PAPER** endpoint test via the existing connected
  orchestrator (GitHub Actions run **38560023371**): one $1 PAPER
  order submitted, recovery after restart, zero duplicate POSTs,
  broker-side cancellation with zero fill and no outstanding test
  orders. No LIVE request was made. The static LIVE audit passed
  on the same commit (run **38560023377**, 507 tests).
- This validates connected broker mechanics **separately** from the
  V5 current risk-sized ETF rehearsal; an actual V5 strategy-driven
  rebalance through Alpaca PAPER remains the next acceptance gate.
- The **one-time** market-hours PAPER fill probe scheduled for
  **14 October 2026 at 13:35 UTC (14:35 London BST)** is an additional bridge test.
  `fund100_v5_connected_paper_fill_probe_v1_0.py` selects an eligible
  symbol from the frozen V5 ETF weights, rejects conflicting paper
  holdings/open orders, purchases only **$2 imaginary PAPER notional**,
  then attempts to sell exactly the newly acquired shares and verifies
  the test position is flat. It requires operator STOPPED, kill switch
  ENGAGED and risk HIGH, with no LIVE credentials. It is **not** a
  genuine compiler-triggered V5 event. GitHub workflow:
  `.github/workflows/fund100-v5-paper-fill-probe-once.yml`.
- A genuine dynamic V5 event processed end-to-end through Alpaca PAPER
  during market hours remains the last pre-launch execution-parity test.
- Until explicit launch authorization, operator control stays STOPPED
  and broker kill switch remains ENGAGED.

- On **14 October 2026**, corrected the V5-002 compiler v1.1 →
  production-controller contract: genuine-event eligibility now comes
  from the explicit compiler `genuine_scheduled_event` boolean, and
  final full-portfolio weights are reconstructed from
  `executed_satellite_weights` plus the ACWI core. Synthetic PAPER
  rehearsal fixtures now use the real compiler field names. A new
  offline regression invokes the actual v1.1 position-aware intent
  generator (without broker credentials). Tests and full static audit
  passed: GitHub Actions **38564627571** (106 regression tests) and
  **38564627586** (529 suite tests, static boundary PASS).
- No naturally occurring V5 scheduled execution event has yet been
  submitted through Alpaca PAPER as a full strategy-driven rebalance.

- On **14 October 2026**, added `fund100_v5_genuine_paper_parity_v1_0.py`:
  a **read-only, non-executable** genuine-event → PAPER plan gate. It
  consumes a v1.1 compiler event, rejects NO_EVENT, re-computes PAPER
  directions against separately supplied PAPER holdings, applies the
  selected risk profile and uses production order materialization to
  verify a two-phase plan entirely in memory. It never replays LIVE
  client IDs to PAPER. Broker POST/DELETE and certificate generation
  are deliberately absent. The caller must later prove compiler event
  freshness and origin before any real PAPER execution is permitted.
  CI **38567506077**: 32 parity + compiler + rehearsal tests passed;
  full suite **38567506040**: 542 passed, static audit PASS.

- On **14 October 2026**, added a read-only V5 event provenance
  module `fund100_v5_compiler_attestation_v1_0.py`. The
  `plan_attested_paper_event` entrypoint rejects stale compiler
  packages, modified content digests, manifest/state divergence,
  inconsistent market-snapshot evidence, missing genuine-event flags
  and executable compiler claims. For a real GitHub invocation,
  `attest_current_files` requires the exact compiler output to
  have been produced after the current compiler invocation began.
  This internally verifies file consistency and recentness; it does
  NOT authenticate a hostile external producer. It makes no broker
  calls and cannot place orders.
  Test evidence: genuine V5 PAPER parity run **38569026258**
  (52 passed), full safety audit **38569026228** (562 passed,
  static boundary PASS).
- Remaining work: a real strategy event produced by the
  compiler and submitted/fill-reconciled via the PAPER-only
  broker path, with release evidence bound to the exact compiler
  invocation. Do NOT re-use the LIVE compiler's account-relative
  directions for the PAPER portfolio. Separate user approval
  remains required before LIVE activation.

- On **14 October 2026**, added the real strategy-to-broker
  **PAPER execution bridge**, `fund100_v5_paper_execution_bridge_v1_0.py`,
  plus `fund100_v5_paper_broker_adapter_v1_0.py`. They are not linked
  to a scheduled account-writing workflow yet. Offline acceptance
  exercises an attested V5 compiler event through SELL-before-BUY,
  fresh cash/broker risk rechecks, deterministic PAPER-only client
  IDs, historical cumulative ceiling, no duplicate replays, stop-on-
  failure and post-fill position reconciliation. The restricted broker
  adapter requires a separate explicit PAPER arm, Alpaca PAPER
  credentials only, repository identity, engaged LIVE kill switch and
  the remotely confirmed operator STOP. The 14 frozen ETF symbols are
  hard-whitelisted. No LIVE orders or credentials are used.
  GitHub Actions **38571747533**: 56 targeted tests PASSED;
  previous full suite **38571548684**: 584 passed, audit PASS.
- Remaining: integrate a genuine **freshly produced** strategy
  compiler package with the dedicated PAPER broker runtime, conduct a
  real strategy-driven multi-order PAPER fill during market hours, and
  verify its reconciliation before considering LIVE activation. The
  independent $2 micro-fill check remains separately scheduled.

- On **14 October 2026 at 13:44 UTC**, confirmed **actual Alpaca
  PAPER filled BUY and SELL** via GitHub Actions **38574171335**.
  The entry used **USD 2 imaginary PAPER notional**, selecting an
  approved ETF. A first attempt (**38573526176**) safely stopped
  without any order because all four frozen V5 ETFs were already
  present in the PAPER account. The corrected probe snapshots
  existing shares, buys USD 2 PAPER, sells only newly acquired
  shares, and verifies the ORIGINAL share quantity is restored.
  Workflow logs confirm 16 offline acceptance tests passed, both
  PAPER legs filled, and no LIVE orders. Full static audit
  **38574171329**: 586 suite tests and audit PASS.
  Sanitized release evidence is in
  `live_activation_outputs/v5_002/paper_etf_fill_evidence_v1_0.json`.
  The automatic test trigger was retired after success.
- Remaining: prove a **naturally occurring fresh scheduled V5-002
  event** can enter the PAPER broker execution bridge and reconcile
  under the HIGH profile. The BUY/SELL fill probe verifies broker
  mechanics, **not** a full strategy-driven PAPER rebalance.

- On **14 October 2026**, implemented a scheduled, **GET-only**
  V5 PAPER account-and-signal readiness watcher:
  `fund100_v5_paper_readiness_v1_0.py` and
  `.github/workflows/fund100-v5-paper-readiness.yml`.
  The workflow validates the current shadow pending-signal state
  separately from broker account micro-pilot compatibility and cannot
  submit any order. Real Alpaca PAPER check **38576238357** passed:
  four existing approved ETF holdings, zero open PAPER orders,
  HIGH risk exposure and recent account history within current gates,
  overall PAPER account preflight compatible. The latest saved
  shadow state has NO pending genuine rebalance. Full safety audit
  **38576238362**: 596 tests passed and static audit PASS.
  Sanitized evidence:
  `live_activation_outputs/v5_002/paper_readiness_evidence_v1_0.json`.
  This is a readiness assessment, NOT evidence of a strategy-driven fill.

- On **14 October 2026**, implemented the separate `fund100_v5_paper_launch_decision_v1_0.py`
  contract. Historical real PAPER fill success and account readiness
  are treated as prerequisites, never order authority. With no fresh
  same-invocation compiler package, result is explicitly
  `WAITING_FOR_GENUINE_V5_EVENT`, with PAPER and LIVE order
  authorisations both false. Attested genuine events advance only to
  fresh PAPER broker preflight; they cannot directly authorize POST.
  Offline GitHub Actions **38597658271**: 7 tests PASS, no credentials
  or broker requests. Most recently inspected V5 shadow state
  (2026-10-13) contains no pending scheduled target.

- **14 October 2026:** completed the scheduled native V5-002
  **genuine-strategy → Alpaca PAPER execution runner**
  `fund100_v5_paper_native_runner_v1_0.py`, paired with
  `.github/workflows/fund100-v5-paper-native-execution.yml`.
  Once each US trading weekday at **15:22 America/New_York**, the
  workflow loads the *actual* checked-out main shadow state. With no
  scheduled pending event it exits before broker credentials or market
  data are used; if one is due it checks a fresh PAPER market clock,
  the immediately following trading session, frozen IEX market-data
  observations, compiler provenance, risk profile and pilot ceiling,
  then delegates SELL-before-BUY orders to the PAPER-only adapter and
  broker reconciliation bridge. No LIVE credentials or LIVE environment.
  **First real workflow run 38600412587:** 40 offline acceptance
  tests passed, `NO GENUINE EVENT`, **zero PAPER and LIVE orders**.
  Follow-up no-delta genuine-event handling also passed; full
  regression **38600713058:** 622 tests, static boundary PASS.
  This is operational forward PAPER automation, but NOT evidence that
  a genuine scheduled multi-order event has filled at Alpaca yet.
  The separate USD 2 PAPER buy/sell probe did fill earlier today.

- **14 October 2026:** Hardened genuine V5 PAPER event replay control.
  Before loading market data or recomputing any pending signal,
  the runner now GETs Alpaca PAPER's accepted/closed/open order history
  from the signal date, using `status=all`, `after` and a maximum
  500-entry response. It refuses further submissions if any
  `f100paper-` strategy order exists (even canceled or filled),
  or history is invalid/truncated. This prevents a failed SELL/BUY
  run from rebuilding new client IDs from changed market prices and
  unknowingly repeating an event. It deliberately requires human
  review before resuming an interrupted PAPER event, rather than
  liquidating any positions automatically. Standalone $2 PAPER
  fill-probe IDs use a different namespace.
  Offline [GitHub Actions 38601914449]: 47 targeted tests passed.
  [Full static boundary 38601914406]: 628 tests passed, audit PASS.
  Broker API query constraints checked against Alpaca's Get All Orders
  reference (maximum 500, status `all`, supported `after` filter).
  First genuine strategy-driven PAPER fill remains pending a natural
  scheduled model signal; no LIVE trading was enabled.

- **14 October 2026:** Ran a new **GET-only LIVE account preflight**
  via `.github/workflows/fund100-live-account-readiness-getonly.yml`
  in the existing protected `fund100-live-broker` environment.
  Account ACTIVE, binding matched frozen policy, holdings entirely in
  approved ETF universe, no open orders, HIGH exposure and history
  checks passed. Real LIVE account equity is **below** the maximum
  USD 130.30 pilot ceiling and currently available cash is **below
  USD 1**. No account numbers, cash amounts or positions were stored.
  A future SELL-before-BUY event may free cash, but there is not
  enough idle cash to fund a new USD 1 BUY alone.
  GitHub Actions **38603864104**: 4 approved LIVE GET requests and
  0 POST, operator STOPPED. Full static audit **38603864590**:
  628 passed, static boundary PASS. Sanitized release evidence:
  `live_activation_outputs/v5_002/live_getonly_account_readiness_evidence_v1_0.json`.
  Do not confuse a capital ceiling with an actual funding balance.


## Phase 2 first evidence — 14 October 2026

The isolated bond-ETF study, `fund100_bond_etf_research_v1_0.py`, now
covers TLT/IEF/SHY/TIP/LQD without adding any to LIVE broker permissions.
One-time [research run 38623102500](https://github.com/nicobouch97/fund100-research/actions/runs/38623102500)
processed 4,725 trading sessions of vendor-adjusted closes through
13 October 2026. Training selected 126-session lagged momentum and a 25%
per-satellite target cap (TLT 15%). In the untouched chronological holdout,
net cumulative excess versus the SHY ETF control was **negative** at all
three one-way cost assumptions: -7.86688 percentage points (5 bp),
-9.977167 percentage points (15 bp), and -14.070787 percentage points
(35 bp). This is not annualised excess return or proof of future performance.

**Decision: candidate rejected for promotion.** No bond PAPER or LIVE
orders are authorised. The next *new* bond experiment requires externally
timestamped yield-curve, breakeven inflation and credit-spread inputs, plus
fresh prospective evidence instead of reoptimising to this holdout.
Experiment provenance and the decision are in
`research_lab/bonds/INITIAL_HOLDOUT_REVIEW_2026_10_14.md`.
The full main-branch audit at run 38623102573 passed 691 tests.

Phase 1 remains the active execution priority: the genuine V5 PAPER
runner passed its latest no-signal run and must complete a natural scheduled
rebalance before a separate decision to enable any small LIVE event.
The operator remains STOPPED, LIVE kill switch ENGAGED, HIGH risk selected,
and USD 130.30 is a hard pilot ceiling, not necessarily available cash.

## Phase 2 macro challenger update — 15 October 2026

A second bond-only macro regime challenger was implemented and passed its
full research and LIVE safety checks in PR #17. Four FRED public historical
rates/breakeven/credit series (DGS2, DGS10, T10YIE, BAA10Y) are explicitly
lagged by an *assumed* two business days; this is NOT archived release-time
or vintage authentication. The first real research run used 4,726 bond ETF
sessions through 14 October 2026 and 5,943 complete available macro dates.

In the most recent previously inspected historic segment, cumulative net
SHY-relative excess (not annualised) was **-8.0748, -10.3948 and -14.8805
percentage points** at 5, 15 and 35 bp per traded side. At all costs it
was slightly worse than the prior price-only bond challenger on the same
segment. THIS IS EXPLORATORY, NOT A CLEAN NEW HOLDOUT.

**Decision: macro bond regime research-only, NOT PROMOTED.** No more
holdout-driven threshold tuning. Full detail in
`research_lab/bonds/MACRO_EXPLORATORY_REVIEW_2026_10_15.md`;
[real-data study run 38702666336](https://github.com/nicobouch97/fund100-research/actions/runs/38702666336).
Full main-branch audit: 702 tests, LIVE boundary PASS
([run 38702666394](https://github.com/nicobouch97/fund100-research/actions/runs/38702666394)).
Phase 1 remains the only LIVE-whitelisted asset group, with no verified
genuine strategy-driven PAPER fill yet. Phase 3 commodities may progress
as isolated research next while Phase 2 awaits point-in-time vintages and
prospective data.

## Phase 3 commodities baseline — 15 October 2026

The isolated GLD / DBC commodity research engine has completed its first
public-data historical study at
[GitHub Actions 38708680599](https://github.com/nicobouch97/fund100-research/actions/runs/38708680599).
Physically backed GLD and futures-based diversified DBC were modelled
separately. SHY was a short-duration ETF reference, SPY an equity stress
diagnostic only. The preregistered strategy checked prior-session
six-month absolute and SHY-relative trends, set fixed GLD/DBC target caps
of 20%/15%, volatility-reduced candidate positions, and charged turnover
5, 15 and 35 basis points per traded side. DBC's fund price already
includes historic embedded roll/tracking and fund expenses, so no
unsupported second roll-cost deduction was applied.

Historical series: **4,977 sessions** through 2026-10-14; later evaluation
started 2020-11-02. The trend strategy's cumulative excess return over
SHY was +29.19, +27.92 and +25.40 **percentage points** across the three
cost cases, but a capped, monthly-rebalanced static 20% GLD / 15% DBC /
65% SHY comparator performed better, exceeding SHY by +39.68, +39.50
and +39.13 percentage points respectively. **These are historical-period
return differences, NOT annualised returns or proved predictive edge.**
The trend strategy's daily equity-return correlation to SPY was about
0.15 over that period; this is not a verified crash hedge.

**Decision: do not promote the commodity candidate to PAPER or LIVE.**
Require a new preregistered futures-carry/roll/physical-gold regime
hypothesis using point-in-time and liquidity evidence, followed by
prospective PAPER research before any separate human authorization
to expand the trading universe. Detailed negative decision recorded in
`research_lab/commodities/INITIAL_HOLDOUT_REVIEW_2026_10_15.md`.
The full static boundary audit
[run 38708680785](https://github.com/nicobouch97/fund100-research/actions/runs/38708680785)
passed **714 tests**. LIVE remains limited to the original 14 equity ETFs,
operator STOPPED, HIGH risk tier, $130.30 hard pilot ceiling, no new LIVE
orders approved.

## Commodity research continuation — 15 October 2026

Commodity research stays ACTIVE rather than advancing past the asset
class after one poorly performing bot. Physical-gold/real-yield and
futures-linked DBC inflation hypotheses must remain distinct. The
second preregistered active C2 model was evaluated in GitHub
[run 38711280282](https://github.com/nicobouch97/fund100-research/actions/runs/38711280282).
Over the *already inspected* late historical interval, its **net cumulative
percentage-point excess vs SHY** at 5/15/35 bp costs was +12.53476,
+11.28596 and +8.82557 respectively, worse than the C1 commodity trend
(+29.19026/+27.91679/+25.40366) and the static capped GLD/DBC/SHY
mix (+39.68468/+39.50014/+39.13174). This is NOT annualized
outperformance, independent validation, or evidence of forward edge.
C2 is NOT promoted to PAPER or LIVE.
The C2 research decision is frozen in
`research_lab/commodities/C2_HISTORICAL_REVIEW_2026_10_15.md`.

To avoid overfitting this previously examined period, PR #20 implemented
a daily, **broker-free, append-only prospective commodity comparison**
between the static capped GLD/DBC reference, unchanged C1 and unchanged
C2, plus SHY and SPY passive observations. The [first completed workflow
run 38712443715](https://github.com/nicobouch97/fund100-research/actions/runs/38712443715)
committed the initial **14 October 2026** market snapshot to
`research_lab/commodities/prospective/observations.jsonl`.
All models begin at research-only NAV 100 on that date. **No future
performance has yet been measured**; the next completed sessions must be
observed subsequently. The ledger is hash-chained and refuses to
backfill an intervening missed session or revise previous hypothetical
wealth. Source ETF adjusted histories are vendor-revisable and FRED
two-weekday availability is still only an assumption, not verified
real-time-vintage evidence. The new forward workflow is scheduled
weekday mornings UTC, has no Alpaca or broker secrets and cannot trade.
Full main-branch suite and LIVE static boundary
[run 38712443906](https://github.com/nicobouch97/fund100-research/actions/runs/38712443906)
passed 738 tests.

**Next commodity research goals:** obtain verifiable point-in-time
futures contract term structures, roll schedules, collateral yield
and trading-friction information to test carry and roll yield
directly; separately assess physical gold's equity stress
diversification using dated macro releases, without retuning C1/C2
against their historical evaluation period. Preserve a combined
portfolio risk budget and require new prospective evidence before
even PAPER promotion. Existing V5 US-equity ETF pilot remains the
only LIVE-whitelisted universe and is STILL awaiting a genuine
strategy-driven PAPER rebalance. Operator STOPPED, LIVE kill switch
ENGAGED, HIGH selected and $130.30 LIVE ceiling unchanged.

## Commodity Phase 3 C3 — observed futures curve data milestone (15 October 2026)

**Commodity research is ongoing, and C1/C2/static daily prospective
comparison remains active, research only.** The next hypothesis requires
real expiry-identified futures term structure and fund roll selection
data, not more tuning to the already examined historical price period.

PR #21 implemented the first market-source data contract for EIA's
discontinued `RCLC1/RCLC2` NYMEX WTI nearby futures price series.
Features explicitly distinguish observed positive-price contango /
backwardation and per-barrel price differences from *earned roll P&L*.
Negative WTI settlement observations cannot silently become positive
percentage-carry calculations. The public EIA historical source
**ends on 5 April 2024**, so it supplies NO current 2026 curve.
DBC's underlying optimum-yield index changed methodology on
**10 November 2025**, so even historical WTI rank spreads alone
cannot identify actual DBC constituent contract selection or carry.

Initial EIA source run
[38714742378](https://github.com/nicobouch97/fund100-research/actions/runs/38714742378)
passed dedicated offline C3 research tests, but direct public EIA API
returned **HTTP 403 Forbidden**; no historical curve dataset,
performance figures or DBC roll returns were generated or reported.
PR #22 gated the source-dependent download behind explicit
manual retry, keeping normal static audit and curve-feature tests
deterministic. Details and source requirements are documented in
`research_lab/commodities/C3_WTI_FUTURES_CURVE_DATA_PROTOCOL_2026_10_15.md`
and `research_lab/commodities/C3_WTI_PUBLIC_EIA_SOURCE_STATUS_2026_10_15.md`.

**Next engineering gate:** obtain a legally available, authenticated
contract-level futures history (expiry, settlement/availability
timestamp, quotes, liquidity and exchange), and dated DBC basket
constituents, optimum-yield roll schedule and collateral treatment
reflecting the 2025 method change. Only after successful provenance
checks can C3 become a separately predeclared futures-curve/carry
strategy candidate, then face out-of-sample and forward research
versus the static baseline. No commodity PAPER/LIVE trading or
whitelist expansion is authorised. HIGH risk tier, $130.30 maximum
LIVE pilot ceiling, operator STOP and kill switch stay unchanged.

## Commodity Phase 3 C3B — expiry-identified data importer (15 October 2026)

The blocked EIA futures API is NOT the only possible historical input.
CME's official DataMine offers contract-level settlements and
continuous-series settlement/expiry information, but historical
commercial data/licensing was **not acquired**. The CME delayed
settlement REST API requires OAuth, entitlement and a Public Website
(Delayed) Redistribution licence; anonymous access cannot be
assumed. CME's public website makes settlement quotes viewable
after midnight CT, but this is not a verified, reusable historical
data API. With Fund-100's current small LIVE pilot, no paid data
commitment has been made.

PR #23
([C3B implementation](https://github.com/nicobouch97/fund100-research/pull/23))
merged a **broker-free provider-neutral identified futures contract
CSV+source manifest importer**. It requires exact exchange/commodity,
contract ID, delivery month/expiry, observed daily settlement,
UTC publication and capture times, quote units, volume/open interest,
source licence and SHA256 provenance. It rejects duplicate/revised,
expired, unverifiable timestamp, mismatched unit, cross-contract and
unowned-source input. Near/far calculations explicitly measure
contemporaneous expiry-normalised quoted curve slope, NOT earned
rolling P&L or an investment signal. Source dates are self-reported
by a provider and do not establish independently verified historical
release vintages.

Offline tests use SYNTHETIC fixtures only, including actual identified
expiry/tenor consistency, negative settlement handling, source hash
and no-promotion invariants. **No real futures contract dataset
has been acquired, no C3B historical result exists, and no paper/live
trade permission is implied.** The official data/licensing discovery
and exact offline import procedure are in
`research_lab/commodities/C3B_IDENTIFIED_CONTRACT_DATA_ACQUISITION_2026_10_15.md`.

Next commodity tasks are (i) obtain legitimate contract-level source
with release/expiry and true historical settlement evidence, (ii)
obtain contemporaneous DBC constituents and methodology-specific roll
weights across the 2025-11-10 change, (iii) freeze and prospectively
evaluate an actual basket carry/curve candidate versus existing static
GLD/DBC, C1/C2 and SHY before any PAPER proposal.

The existing daily C1/C2/static forward scorecard remains active
without any change to the V5 US ETF pilot, operator STOP, engaged
LIVE kill switch, HIGH risk or $130.30 LIVE ceiling.

## Commodity C3C — actual SEC-reported DBC positions (15 October 2026)

We have crossed a substantive data milestone without buying exchange
contracts or inventing market data: PR #24
([merged filing-dated holdings study](https://github.com/nicobouch97/fund100-research/pull/24))
transcribed **all 28 open futures positions** from each of DBC's
March 31 and June 30, 2026 official SEC Form 10-Q schedules,
including delivery months, contracts, USD notional, accession number
and source URL. The transcribed file is auditable at
`research_lab/commodities/dbc_sec_futures_holdings_2026_q1_q2.csv`.

The March statement was publicly filed on **7 May 2026** and the
June statement on **7 August 2026**. Historical strategy information
becomes eligible conservatively the NEXT business day (8 May and
10 August respectively): a June 30 decision must NOT know the
June quarter-end holdings until after the filing.
The historical notional-weight sector mixes (not official DBIQ index
weights) were:

| Futures sector | March 31 | June 30 |
|---|---:|---:|
| Energy | 48.8% | 47.0% |
| Agriculture | 17.3% | 18.5% |
| Precious metals | 14.4% | 13.2% |
| Industrial metals | 11.4% | 12.8% |
| Livestock | 8.1% | 8.5% |

The fund disclosed different delivery months for **10 of the 28**
futures descriptions between March and June. These are TWO disclosed
holdings snapshots and DO NOT establish the actual dates, prices
or gains of rolls between those reports. March and June aggregate
futures reported notionals were $1,689,474,972 and $1,576,215,941,
approximately reconciled to the SEC statements of shareholders'
equity; NOT trading P&L. Full research protocol and limitations:
`research_lab/commodities/C3C_SEC_DBC_ACTUAL_HOLDINGS_PROTOCOL_2026_10_15.md`.

The official September 2025 filing describes the former
**14-commodity index** before the **10 November 2025**
rules expansion. The March/June 2026 schedules contain 28 reported
position descriptions, confirming much broader market exposure, but
we still cannot reconstruct a daily DBIQ optimum-yield weight/roll
schedule or a valid C3 carry-return backtest.

**Next:** supplement the 2025 Q3 validated pre-change snapshot
with the genuinely *earlier-filed* 2025 Q1/Q2 holdings, and the
post-change 2025 Q4 filing when publicly released, then acquire
actual dated futures contract settlements and issuer roll schedules
before attempting any futures-carry strategy.
Our append-only C1/C2/static ETF-based shadow scoreboard remains
operational. No DBC trades are authorized; the only LIVE-eligible
universe is unchanged US ETF V5 with operator STOP, engaged kill
switch, HIGH risk setting and $130.30 ceiling.

## Commodity C3D — verified pre/post index break (15 October 2026)

PR #25
([merged actual DBC SEC pre/post comparison](https://github.com/nicobouch97/fund100-research/pull/25))
adds all **14** actual September 30, 2025 pre-change open futures
descriptions to the **28** actual March and June 2026 post-change
positions. The 2025 SEC schedule's open futures notionals total
**$1,288,934,852**, consistent with separately reported
**$1,289,445,913** shareholders' equity.

**Critical date issue:** The Sep 30, 2025 SEC 10-Q was formally filed
**7 November 2025**; its holdings are treated as knowable only
**10 November 2025**, the very day the new index methodology became
effective. This Q3 filing is NOT valid as a prospective pre-change
trading signal, even though it reliably records actual pre-change
positions at quarter-end. The post-change March/June 2026 SEC
snapshots are similarly delayed to May 8/August 10, respectively.

Verified reported futures notional sector exposure (% rounded):

| Futures sector | Sept 2025 old index | Mar 2026 new index | Jun 2026 new index |
|---|---:|---:|---:|
| Energy | 55.0 | 48.8 | 47.0 |
| Agriculture | 19.0 | 17.3 | 18.5 |
| Precious metals | 13.5 | 14.4 | 13.2 |
| Industrial metals | 12.5 | 11.4 | 12.8 |
| Livestock | 0.0 | 8.1 | 8.5 |

Fourteen previously absent commodity exposures were added under the
issuer's Nov 10 2025 8-K/A, including coffee, cocoa, cotton,
several livestock products, Kansas wheat, soybean products, nickel
and lead. These are **sparse quarterly disclosed fund positions**
and reported futures notionals, *not* official daily DBIQ index
weights, actual futures rolls/earnings or portfolio performance.
All checks use public filing dates rather than quarter-end
data hindsight. The precise original sources and restrictions are
in `research_lab/commodities/C3D_PRE_POST_2025_INDEX_DISCLOSURE_PROTOCOL.md`.

**Decision remains unchanged:** C3D proves a material real-world
commodity index structure change and advances the research dataset,
not a viable profitable commodity bot. The daily C1/C2/static
forward shadow scorecard continues separately; no commodity
PAPER/LIVE activity or symbols have been authorized. Fund-100
V5 ETF LIVE operator remains STOPPED, kill switch ENGAGED, HIGH
risk selected, and the $130.30 pilot maximum unchanged.

## Commodity C3E — five SEC-disclosed DBC futures snapshots (15 October 2026)

PR #26
([merged DBC five-period chronology](https://github.com/nicobouch97/fund100-research/pull/26))
incorporated two additional genuine SEC open-futures schedules:
**30 June 2025** pre-reform **14** futures descriptions and
**31 December 2025** post-reform **28** descriptions. Together with
30 September 2025, 31 March 2026 and 30 June 2026, this creates
**five dated public holdings snapshots covering 112 actual reported
open futures positions** across the November 10, 2025 DBIQ
optimum-yield commodity index methodology break.

**Critical SEC disclosure timing:** June 2025 positions were
reported August 7, 2025 and become conservatively research-usable
August 8, 2025. The *December 31, 2025* holdings were accepted
after-hours February 27, 2026, given an official **SEC filing date
of March 2, 2026**, and conservatively become research-usable
**March 3, 2026**. No trading analysis can use that December
2025 28-market basket in December or January. The prior
September 2025 SEC schedule was released November 7, and only
becomes eligible November 10—the reform day itself.

New public-SEC reported open futures gross notionals were
**$1,230,805,407** for June 2025 and **$1,223,550,999**
for December 2025, reconciled to reported equity
of **$1,230,605,532** and **$1,223,200,118** respectively.
Source files/filing IDs, normalized line descriptions and strict
known-as-of rules:
`research_lab/commodities/C3E_DBC_FIVE_SEC_FILING_CHRONOLOGY_2026_10_15.md`.
Data checked against original
[June 2025 SEC 10-Q](https://www.sec.gov/Archives/edgar/data/1328237/000095017025105193/dbc-20250630.htm)
and
[December 2025 SEC 10-K](https://www.sec.gov/Archives/edgar/data/1328237/000119312526083563/dbc-20251231.htm).

A real reported sector notional structure change is visible:
energy was **55.76%** in June 2025 versus **37.40%**
in December 2025, as livestock grew from zero to **9.69%**
and more non-energy markets entered the fund. These are
**sparse position-notional exposures**, not official index
weights, forward curve carry, P&L or forecasts.

C3E premerge research checks passed **33** relevant tests;
the full LIVE audit passed **796** tests with 36 static
boundary checks, and no commodity order or account
credential exposure was added.

**Next:** acquire real date-stamped exchange futures settlement
curves and DBIQ actual constituent contract-selection/roll
records. Historical filings have now substantially improved
our commodity coverage; they still cannot verify a futures
carry strategy, and a price-only proxy must not be presented
as such. Keep C1/C2/static prospective ETF research live
*as research only*, the separate V5 US ETF PAPER pilot
unchanged, original 14 equities-only LIVE whitelist,
HIGH risk, $130.30 ceiling, operator STOPPED and kill switch ENGAGED.

## Commodity C3F — official monthly DBIQ index contract-selection catalogue (15 October 2026)

PR #27 ([merged issuer publication registry](https://github.com/nicobouch97/fund100-research/pull/27))
identified an important official data source beyond sparse quarter-end
DBC fund holdings: Deutsche Bank's
[DBIQ Diversified Commodity Index](https://index.db.com/dbiq-web/indices/95400)
(index Bloomberg identifier **DBLCDBCE**) lists its 2025 index
methodology guide and annual November 2025 commodity index weights
documents. The official
[DBIQ issuer publications catalogue](https://dbindex.db.com/dbiq-web/publications)
lists **12 monthly 'DBIQ Optimum Yield indices Selection Report'
publications from November 2025 through October 2026**, with real
issuer-posting dates and site clock text. The source site's displayed
clock timezone remains unverified. The index provider's April 2025
notice describes the November 2025 switch to Modified Optimum Yield
contract selection, liquidity screening, production/liquidity-based
weights, sector/commodity concentration caps and intra-year controls.

A fully source-linked, 12-line issuer report registry is committed at
`research_lab/commodities/dbiq_official_selection_report_registry_2025_2026.csv`.
The code in `fund100_dbiq_publication_registry_c3f_v1_0.py`
strictly validates source titles, chronology, conservative calendar
as-of timing and SHA256/source/rights intake requirements for *any
future actually obtained original PDF*. It is
**metadata/evidence-gate code only**: the official PDF bytes or
actual contract selections, exact contract expiry details, genuine
monthly DBC diversified basket weights and rolling P&L have NOT
been acquired/extracted/verified. The 2-weekday visibility delay is
not an independently verified historical release timestamp or
holiday-aware exchange trading calendar.

CI tested **14** issuer-source constraints; full baseline was
**810 passing tests and 36 passing LIVE static safety checks**.
Research protocol:
`research_lab/commodities/C3F_DBIQ_ISSUER_MONTHLY_CONTRACT_REPORT_REGISTRY_2026_10_15.md`.

**Next concrete dependency:** obtain and authenticate the
actual 2025 index guide / official November weights and monthly
selection PDF files, respecting copyright and source usage
permissions, verify exact report publication times, differentiate
single-commodity subindex contract selection from DBC's actual
index basket, then integrate only date-available futures settlement
data. Do not backtest carry without true contract-level quotes
and roll rules. The existing C1/C2/static public-data forward
comparison and Phase 1 genuine ETF PAPER execution continue
unchanged. LIVE operator STOPPED, kill switch ENGAGED, HIGH tier
and $130.30 pilot ceiling unchanged; no commodity trading authorised.

## Commodity C3G — issuer indexed basket contracts and real document links (15 Oct 2026)

PR #28
([merged DBIQ issuer index basket evidence](https://github.com/nicobouch97/fund100-research/pull/28))
captured a materially more specific source than quarterly SEC
futures notionals: the official
[DBIQ diversified commodity index page](https://index.db.com/dbiq-web/indices/95400)
(`DBLCDBCE`) is web-indexed with an **28-entry index constituent
table** showing individual contract codes, displayed contract-month
calendar dates and issuer index weights totaling **99.99%**
due to display rounding. A reviewed, source-linked **manual
transcription** of all 28 is now in
`research_lab/commodities/dbiq_diversified_index_web_indexed_28_constituents_2026_10_15.csv`.

The web-indexed issuer table includes Brent `LCOZ6` at 17.85%,
WTI `CLX26` at 15.07%, gold `GCZ26` at 8.95% and
separate COMEX/LME copper markets. Index sector weights derived
from these 28 issuer records are: **53.27% energy, 17.14%
agriculture, 11.29% industrial metals, 11.76% precious metals,
6.53% livestock**. These are **issuer index displayed
weights**, NOT historical actual DBC fund holdings or notional
weights; do not compare them as simultaneous with the June 2026
SEC schedule.

**Vital source limitations:** the publicly indexed webpage does
NOT carry an independently verified issuer effective/capture
timestamp; only the **15 Oct 2026 retrieval date** is known.
The issuer's `Contract Month` displayed calendar dates are NOT
verified exchange last-trading/expiry dates; no C3B contract
settlement or historical trading simulation can safely use these
as-is. No historical constituent sequence or carry P&L is
present. C3G thus is an index SOURCE snapshot and mapping,
not a new profitable investment strategy or confirmed 2026
realtime trading signal.

A read-only headless browser separately rendered the real issuer
page and confirmed **exact official PDF document download routes**:
- Index guide `/dbiq-web/rest/docsnoticesdata/file?id=3182&documentType=SPECIFIC_INDEX_DESCRIPTION`
- November 2025 weights `/dbiq-web/rest/docsnoticesdata/file?id=3205&documentType=SPECIFIC_REBAL_DOC`

Those links are relative to `https://index.db.com` and stored in
`research_lab/commodities/dbiq_official_methodology_document_dom_links_2026_10_15.csv`.
The site presented a **terms-and-conditions modal**, so the runner
did not click through or accept terms; the public document
previewer did not support the `application/octet-stream`
response. **Original PDF bytes/contents are not yet acquired or
visually inspected**, and no index methodology-specific contract
selection/P&L has been inferred from just their file names.
Study `research_lab/commodities/C3G_DBIQ_28_CONTRACT_INDEX_WEB_EVIDENCE_2026_10_15.md`
contains the source-time, licensing, roll and date controls.

Research-only CI passed **13** C3G checks and the full
**823-test** LIVE static safety suite with **36** boundary checks.
No broker orders, fund risk settings, secrets or LIVE symbol
permissions changed. The user-selected HIGH risk tier and $130.30
pilot ceiling, original 14-ETF LIVE whitelist, operator STOP and
engaged kill switch remain unchanged. The existing C1/C2/static
commodity forward scoreboard and Phase 1 V5 genuine PAPER
executor remain separate and operational.

**Next:** obtain issuer documents only through a legitimately
authorised path after reviewing any required access terms;
independently verify original PDF bytes, page contents and
publication timestamps. Combine authenticated contract-selection
records with trade-date-specific exchange settlements, then
preregister an actual carry hypothesis to test prospectively
against static GLD/DBC and C1/C2.

## Commodity C4 — separate lagged ETF equity-stress hypothesis, first result (15 Oct 2026)

Because the official DBIQ PDF endpoints are discovered but not yet
permitted/verified as document content, a **new independently fixed
C4 ETF-level portfolio-diversification challenger** was built in
[PR #29](https://github.com/nicobouch97/fund100-research/pull/29).
This is NOT a futures roll/carry strategy and does not infer index
constituents from unsupported document downloads.

**C4 fixed monthly rules:** maintain GLD20%/DBC15%/SHY65%
as capped default reference; using the prior **63 completed**
market sessions, reduce DBC to 5% if SPY annualized realized
volatility >=25% AND DBC/SPY daily correlation >=+0.40;
independently reduce GLD to 10% if SPY vol >=25% and
GLD/SPY correlation >=+0.30. Transfer reductions to SHY.
No SPY trade, leverage, intramonth trading or broker path.
Compare at 5/15/35bp per traded side against the simple
capped static basket under identical reference accounting.
Frozen research protocol:
`research_lab/commodities/C4_STRESS_OVERLAY_PROTOCOL_2026_10_15.md`.

**First real retrospective study**:
[Actions 38736979158](https://github.com/nicobouch97/fund100-research/actions/runs/38736979158);
public price source SHA256
`fe47ef3a637e5fa74b1d735ceac57a2003746ce9d28b1f4b8cadf86506dbdc17`.
C4's **net cumulative return minus capped static** over the
ALREADY INSPECTED late historical segment was **−1.40360pp**
at 5bp, **−1.56678pp** at 15bp and **−1.89152pp** at 35bp
per side. This is not an independent holdout or forecast,
and no risk-adjusted superiority has yet been verified.
**DECISION: C4 NOT PROMOTED**; do not opportunistically tune
the frozen rules using the same history.
Full data, no-promotion decision and limitations:
`research_lab/commodities/C4_EXPLORATORY_REVIEW_2026_10_15.md`.

The [postmerge LIVE safety audit 38736979039](https://github.com/nicobouch97/fund100-research/actions/runs/38736979039)
passed **834** tests and **36** boundary checks. The separate
C1/C2/static append-only commodity forward shadow ledger still
has its **one starting observation (14 Oct 2026)** with zero
measured forward trading days as of this check; the next session
must genuinely be recorded before claiming prospective evidence.
Do not rewrite that hash chain to add C4.

**Next research priority:** access and independently inspect
issuer original DBIQ index methodology / weights / monthly
contract-selection PDFs with proper permission; acquire
exchange-dated actual per-contract settlement and roll records
before any claim of futures carry alpha. Parallel Fund-100 V5
US-ETF genuine PAPER event workflow remains separate and on
its existing schedule. User HIGH, LIVE $130.30 ceiling,
operator STOPPED, engaged kill switch and frozen 14 US
ETF LIVE universe remain unchanged.

## Phase 4A — US individual-stock SEC filing quality source (15 Oct 2026)

Phase 3 commodity C1/C2/C4 historical challengers failed to
establish a robust advantage over capped static GLD/DBC/SHY;
the separate C1/C2/static daily forward hash-chain continues
with only its initial 14 Oct 2026 observation as of the latest
review. DBIQ individual futures source PDFs / historical
exchange settlements remain unauthenticated and blocked
behind source-data access terms. We are continuing commodities
prospectively while moving to the *next independent asset
group*, rather than repeatedly tuning the same explored ETF
history.

[PR #30](https://github.com/nicobouch97/fund100-research/pull/30)
merged `fund100_stock_sec_quality_p4a_v1_0.py`, an OFFLINE-only
SEC annual filing-identity / conservative-as-of quality
engine. It combines official [SEC companyfacts and submissions
JSON](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
for the same 10-digit CIK and requires matching original 10-K
accession, filed day, annual fiscal start/end and standardized
US-GAAP USD tags. Date-gates each 10-K by **two ordinary
weekdays after filing** (conservative proxy, not true
exchange-holiday/release-time proof). Uses consecutive
complete 10-K reporting periods, rejects same-year
restatement conflicts, too-stale reports, annual-vs-YTD
mixing and missing cash-flow tag imputation.

The **research-only** stock-quality score has three fixed
binary flags: reported annual revenue YoY growth >=0,
annual operating-income margin >=10%, and annual
FCF/revenue >=5% (FCF = annual operating cash flow less
property/equipment acquisitions). This is not an
estimated-EPS analyst revision model and not a trade signal.
Analyst revisions remain `null` until a legitimate
timestamped point-in-time estimates provider is available;
current SEC API histories are NOT independent archived
past vintages.

A frozen example **2026 contemporaneous research cohort**
(AAPL, MSFT, GOOGL, AMZN, XOM, JNJ, PG, KO) is stored in
`research_lab/stocks/p4a_contemporary_universe_2026_10_15.csv`.
Its CIKs are explicit but it is NOT survivorship-safe to
backtest historically and NONE of its stock symbols are
PAPER/LIVE allowed. Missing historic defunct stock records,
corporate events, earnings release timestamps, analyst
estimate revisions, execution prices, earnings gap risk,
and diversification/correlation proofs still block stock
strategy promotion. Source and next data gates:
`research_lab/stocks/P4A_SEC_FILING_QUALITY_PROTOCOL_2026_10_15.md`.

Offline synthetic SEC fixtures passed **14** dedicated tests.
Full static LIVE safety audit passed **848** repository tests
and **36** LIVE boundary checks. No actual SEC value
download, verified fundamentals dataset, stock historical
return or alpha measurement is claimed yet.

**Next engineering milestone:** acquire permission-compliant
actual SEC annual filings and source hashes for the frozen
current cohort, then build a forward-only, point-in-time
quality research scorecard and separately establish an
analyst revision source / survivorship-safe security master
before evaluating historical strategy performance. Do not
auto-trade the roster; original 14 US-ETF pilot LIVE
whitelist, operator STOP, engaged kill switch, HIGH risk
and $130.30 LIVE pilot ceiling remain unchanged.

## Phase 4B — controlled REAL official SEC stock source ingestion (15 Oct 2026)

[PR #31](https://github.com/nicobouch97/fund100-research/pull/31)
merged a deliberately source-compliant, no-broker SEC
CompanyFacts + submissions **prospective raw-data capture**
capability. The production script
`fund100_stock_sec_source_p4b_v1_0.py` is bounded to
**two official `data.sec.gov` read-only GET endpoints per company**
for the frozen 8-stock contemporary cohort. It requires a
real user-supplied SEC requester identity and email and
rate-limits requests; no contact address is fabricated.
Any source access denial or missing identity FAILS CLOSED.
Every successful future capture will record UTC acquisition
time, original SEC JSON raw bytes, SHA256 hashes and a
frozen P4A accession-linked reported quality score (or
`MISSING`), with missing original price/delisting/analyst
revisions explicitly labelled.

The GitHub Actions workflow
`.github/workflows/fund100-p4b-sec-source-snapshot.yml`
runs offline source tests on PR/main commits, and only
fetches actual SEC data on an explicit **manual
`capture_prospective_sec` dispatch**, with a genuine
requester contact supplied as repository secret
`FUND100_SEC_USER_AGENT`. Read-only scope, no Alpaca
keys, no LIVE/PAPER environments, and no automatic broker
activation. Normal workflow never receives that contact.

**Operational state at this checkpoint:** P4B code and
CI are MERGED but **no real SEC JSON captures have
yet been executed**. The actual user's contact
information must be supplied by the operator for
SEC-compliant automated access. Do not mistake the
27 passing synthetic source/fundamental fixture tests for
real financial observation, point-in-time original
archived history, independent alpha, analyst EPS
revisions, or a survivorship-safe market database.
Full suite after change passed **861 tests** and all
**36 LIVE boundary checks**. Source and operator
instructions:
`research_lab/stocks/P4B_SEC_REAL_SOURCE_CAPTURE_PROTOCOL_2026_10_15.md`.

**Next operator action:** Configure a genuine
`FUND100_SEC_USER_AGENT` Actions repository secret
containing the SEC-required requester identity and
contact email, then explicitly run
`Fund-100 Phase 4B SEC Prospective Stock Snapshot`
in `capture_prospective_sec` mode for two companies.
Inspect actual issuer data coverage and SHA artifact;
then build append-only prospective quality observations
with timestamps, and separately establish price/actions,
failed/delisted security history and dated analyst
revision inputs. Don't promote current survivors
to historical alpha or trades.

The prior commodity C1/C2/static forward scorecard,
V5 ETF PAPER workflow, STOPPED LIVE operator,
engaged kill switch, HIGH risk tier and $130.30
pilot maximum remain intact. No direct US stock
PAPER or LIVE order authority has been created.

## Phase 4B — first real SEC annual-quality observations (15 Oct 2026)

After the user supplied a legitimate SEC identifying
contact secret and ran manual EDGAR ingestion, the
initial [run 38744413858](https://github.com/nicobouch97/fund100-research/actions/runs/38744413858)
failed a strict CIK type check (numeric SEC CompanyFacts
versus text/zero-padded SEC submissions identifier).
[PR #32](https://github.com/nicobouch97/fund100-research/pull/32)
corrected exact-matching integer/digit-string issuer
identity while still rejecting wrong companies and
invalid types. The 865-test premerge LIVE safety audit
passed all 36 boundary checks.

A **single user-authorized retry**
[Actions 38746277418](https://github.com/nicobouch97/fund100-research/actions/runs/38746277418)
successfully fetched the **four genuine official SEC
JSON source files** for **Apple (AAPL)** and
**Microsoft (MSFT)** at **2026-10-15T13:52:50Z**.
Raw bytes and source SHA256s are in the 90-day artifact
`fund100-phase4b-real-sec-snapshot-38746277418`.
The first frozen-source prospective reporting record:
`research_lab/stocks/prospective/p4b_actual_sec_2026_10_15.json`.
Full report:
`research_lab/stocks/P4B_FIRST_REAL_SEC_REVIEW_2026_10_15.md`.

The **real** SEC reported annual financial quality (P4A
frozen score) observations:

| Stock | Latest original eligible FY end | Revenue growth YoY | Operating margin | FCF margin | P4A quality |
|---|---|---:|---:|---:|---:|
| Apple | 2025-09-27 | +6.43% | 31.97% | 23.73% | 3/3 |
| Microsoft | 2026-06-30 | +17.79% | 46.78% | 20.19% | 3/3 |

The one-off retry trigger was subsequently **removed**;
actual future SEC captures remain **manual only**, with
the previously configured user SEC contact source secret.
The live stock data now exist, but they do NOT constitute
a delisting-safe historical universe, genuine historically
archived SEC market vintages, analyst EPS revisions,
priced stock returns, stock alpha or any stock trade
approval. The AAPL and MSFT observation dates/fiscal
periods differ, and both firms are selected 2026 survivors.

**Next:** extend the explicitly dated, forward-only
source coverage to the remainder of the frozen eight-stock
cohort via authorized manual SEC capture; add a validated
issuer-tag coverage review and independently timestamped
estimates-revision and historical security-master research
before attempting any performance-based stock ranker.

Commodity C1/C2/static append-only forward scoreboard and
V5 genuine US ETF PAPER execution are unchanged.
Original 14 US ETF-only LIVE whitelist, operator STOPPED,
engaged kill switch, HIGH risk and $130.30 pilot ceiling
remain frozen. No equity individual-stock orders.

## Phase 4C–4D — eight real SEC issuer sources, 2/8 fixed-tag coverage (15 Oct 2026)

At the user's request to continue after real AAPL/MSFT research,
Phase 4C added an original-source-audited, **append-only prospective
SEC capture ledger** in
[PR #34](https://github.com/nicobouch97/fund100-research/pull/34).
Its source validator independently opens P4B ZIP/raw directories,
verifies original SEC CompanyFacts and submissions bytes against
the manifest SHA256 and actual SEC CIK/URL, recomputes all stored
annual quality values, rejects malicious/partial source archives,
and emits an optional hash-linked chronological next-capture
record. It does not rewrite the first two-company research
observation or place any stock orders.

One tightly bounded, operator-requested **eight-company SEC
capture** succeeded in
[GitHub run 38756477914](https://github.com/nicobouch97/fund100-research/actions/runs/38756477914)
at **2026-10-15T15:01:45Z**. It acquired **16 genuine SEC
CompanyFacts/submissions JSON documents** for the frozen
AAPL/MSFT/GOOGL/AMZN/XOM/JNJ/PG/KO research cohort.
Source SHA256 review manifest:
`bafc7a084a6d4deaf7c7b7a5e982d52a8b5ecd6fe1b70a0ebaf3e64a610b1e18`.
Original SEC artifact:
`fund100-phase4b-real-sec-snapshot-38756477914`,
ID `11983422763`. Independent verified coverage artifact:
`fund100-phase4c-sec-coverage-validated-38756477914`,
ID `11983907325` (both retained 90 days).

**Observed quality coverage:**
- **8/8 genuine issuer source captures verified**, but
  **only 2/8 complete** under P4A's fixed original four US-GAAP
  annual concepts. AAPL and MSFT independently reproduce
  original **3/3** scores. Missing fields never become zeros
  or negative company judgements.
- GOOGL latest 2025 original 10-K missing the exact
  revenue concept annual row. AMZN lacks the exact capex
  concept annual row. XOM lacks the fixed latest revenue
  fact and `OperatingIncomeLoss` tag. JNJ has no matching
  current original full-year `OperatingIncomeLoss` fact.
  PG and KO lack the exact fixed revenue concept; other
  non-equivalent revenue tags are visible but not used.
- The original P4A sometimes categorised a newer incomplete
  10-K as an older stale complete year. To address this
  WITHOUT mutating first-capture history, the separately
  versioned **P4D current-filing completeness overlay**
  in [PR #35](https://github.com/nicobouch97/fund100-research/pull/35)
  checks the latest SEC-filed original 10-K first, labels
  missing concept availability, and suppresses stale
  carry-forward of prior complete scores in future prospective
  research. It does NOT change the original P4A score
  thresholds, automatically substitute GAAP concepts or
  approve stock orders. New P4D tests are synthetic; its
  exact current cohort source findings are manually documented.
- P4C–P4D complete SEC results/limitations and original
  hashes: `research_lab/stocks/P4C_P4D_FIRST_EIGHT_REAL_SEC_QUALITY_REVIEW_2026_10_15.md`.

**Security/operations:** the temporary one-shot SEC capture
trigger has been **removed** from the official P4B workflow
(restore commit `a8ba0c35ad6b7a0e69d2e97e9d94cbd8505d642b`).
Future SEC contacts are MANUAL `workflow_dispatch` only
with the prior user-supplied requester identity and no
broker credentials. Final premerge repository audit passed
**895 tests and 36 LIVE boundary checks** after P4D.

**Next meaningful development:** preregister audited
company/sector-specific GAAP fact alternatives only where
they are economically comparable; keep other companies
UNKNOWN rather than score-filling. Separately seek
publication-timestamped analyst earnings *consensus revisions*
and a survivorship/delisting-safe historical security master
before any alpha claim, and a new forward-only priced
scorecard before stock PAPER. Still NO stock PAPER/LIVE
authorization, no changes to the original V5 ETF
whitelist, operator STOPPED, engaged kill switch, HIGH
risk tier or $130.30 LIVE exposure limit. Existing
commodity C1/C2/static forward research remains separate.

## Phase 4E — frozen issuer-accounting source improves quality coverage to 6/8 (15 Oct 2026)

[PR #36](https://github.com/nicobouch97/fund100-research/pull/36)
merged a separate, frozen issuer-specific P4E annual
SEC accounting source contract. It preserves original
P4A quality thresholds (nonnegative revenue growth,
>=10% operating margin, >=5% annual cash-based FCF
margin) while pinning exact permitted latest-original
10-K US-GAAP revenue/capital-asset purchase tags per
issuer/CIK. Changes never rewrite first P4A/P4C
actual-source scores. All periods and concepts come
from **one latest publicly eligible original 10-K**
for the current and prior-year annual comparative.
The earlier comparative is available to the 2026
researcher after this filing, **not** a historical
vintage a trader knew in the prior year.

Source study against the exact earlier 8-company
real SEC archive, NO new SEC downloads:
[Actions run 38760165063](https://github.com/nicobouch97/fund100-research/actions/runs/38760165063)
**PASS**, source raw-manifest SHA256
`bafc7a084a6d4deaf7c7b7a5e982d52a8b5ecd6fe1b70a0ebaf3e64a610b1e18`.
P4E real-source quality coverage **6/8** versus
P4A's original **2/8**. Scores: AAPL=3/3,
MSFT=3/3, GOOGL=3/3, AMZN=2/3,
PG=3/3, KO=3/3. Exxon Mobil (XOM) and
Johnson & Johnson (JNJ) remain **UNKNOWN**
because their latest original 10-K lacks
the required full-year `OperatingIncomeLoss`
for both periods. Their financial health is
not thereby negative.

AMZN's annual `PaymentsToAcquireProductiveAssets`
is a **company-specific** cash productive-asset
spending proxy and not proven cross-industry
equivalent to other companies' PP&E purchases.
GOOGL/PG/KO issuer-specific `Revenues` tags
are consistently presented over both annual
periods in their latest 10-K accession, but
the scores are not standardized stock ranks
or expected returns.

Original-source 90-day GitHub P4E review
artifact: `fund100-p4e-frozen-eight-company-sec-issuer-quality-38760165063`
ID `11984384799`. Detailed actual outcome,
report financial percentages and no-promotion
decision:
`research_lab/stocks/P4E_FIRST_REAL_ISSUER_GAAP_SCORE_REVIEW_2026_10_15.md`.
Frozen policy:
`research_lab/stocks/P4E_ISSUER_GAAP_COMPARATIVE_PROTOCOL_2026_10_15.md`.
The original-P4E merged main full static LIVE safety
audit [38760164965](https://github.com/nicobouch97/fund100-research/actions/runs/38760164965)
passed **907 tests and 36 LIVE boundary checks**.

**Decision:** research only. Source completeness is NOT
alpha, independent prospective stock performance,
point-in-time analyst EPS revisions, a delisting-safe
universe, sector-neutral factor validation or trade
approval. The next genuine Phase 4 bottleneck is
historical company master & price/corporate action
coverage and separately dated earnings-consensus
revision data, plus full cash-flow tag semantics.
Commodity forward C1/C2/static and the existing
genuine V5 ETF PAPER workflow remain independent.
Live operator STOPPED, engaged kill switch, HIGH
risk selected, $130.30 pilot cap and the unchanged
14 US ETF-only LIVE whitelist remain mandatory.

## Phase 4F — independent dated analyst earnings-revision source contract (15 Oct 2026)

[PR #37](https://github.com/nicobouch97/fund100-research/pull/37)
merged Fund-100's first completely separate **analyst EPS
estimate-revision research source**. It specifically avoids
conflating SEC-reported accounting quality with *sell-side
forecast revision alpha*. Its analyst estimate source is
NOT yet obtained/licensed/connected, and the engine's
honest GitHub readiness report has **0 genuine estimate
observations, 0 real revision scores and 0 broker orders**.

The frozen research hypothesis in
`fund100_stock_analyst_revisions_p4f_v1_0.py`
requires the original vendor detail/estimate-change JSON
bytes and matching SHA256, declared rights, source
acquisition/publication timestamps, ten-digit company
CIK/ticker and stable share-class identity, individual
broker IDs and unique forecast revision identifiers,
exact same normalized diluted EPS USD per share and
future fiscal year. Only revisions published in the
trailing 30 days and known after a conservative
24-hour vendor receipt lag qualify. Previous estimates
must be <=180 days old, with revisions >= the greater
of 2¢ EPS or 1% of max(abs(old EPS), $0.50).
It uses each broker's last qualifying observation and
requires >=3 material directional revisions before
showing a **descriptive** (ups - downs)/(ups + downs)
pressure reading. No signal is trade-authorized.

Official source candidates:
[LSEG I/B/E/S broker detail](https://www.lseg.com/en/data-catalogue/company-data/ibes-estimates/broker-estimates)
and
[FactSet historical analyst detail](https://insight.factset.com/resources/factset-consensus-estimates-datafeed).
FactSet's [separate PIT consensus snapshot
product](https://insight.factset.com/resources/at-a-glance-factset-estimates-point-in-time-consensus)
is NOT the same as genuine individual broker changes,
and would require a different feed adapter. Neither
commercial vendor service is currently connected or
priced for Fund-100. Do not impersonate a licensed
client, fabricate original estimates or charge
the operator without asking.

The independent
`research_lab/stocks/P4F_ORIGINAL_ESTIMATE_REVISION_PROTOCOL_2026_10_15.md`
freezes source requirements and the non-trading threshold
before real data. Dedicated **18 synthetic fixture tests**
passed, plus premerge full **925**-test repository audit
and **36** LIVE safety boundary checks. CI generates
a documented source-unavailable state, not simulated
alpha or trade forecasts.

**Next research tasks:** obtain a legitimately licensed
PIT individual broker estimate export if cost and
available rights make sense; independently verify
publication/collection timestamps and security IDs.
In parallel build a **delisting-inclusive historical
security master and corporate-action/total-return
price source**. SEC's current ticker/CIK lookup is
NOT a survivorship-safe historic listing. The current
eight-company 2026 cohort is still prospective and
stock PAPER/LIVE permissions remain ABSENT.
No automatic signal promotion from fixtures or
source-completeness to real capital. The US ETF V5
PAPER pilot and commodity C1/C2/static forward ledger
continue without modification. Operator STOPPED,
engaged kill switch, HIGH selected risk, $130.30
pilot ceiling and frozen 14 US-ETF LIVE allowlist remain.


## Phase 4G — forward-only US stock quality x momentum observation (15 Oct 2026)

[PR #38](https://github.com/nicobouch97/fund100-research/pull/38)
introduces a completely broker-free, source-fingerprinted prospective
stock momentum research observer. It keeps the six authentic original
P4E 15 Oct 2026 issuer-accounting scores fixed: AAPL=3, MSFT=3,
GOOGL=3, AMZN=2, PG=3, KO=3. XOM and JNJ remain UNKNOWN, not zero.
The descriptive shortlist predeclares the 126-session adjusted-close
absolute return >0, the 63-session adjusted-close return greater than
SPY's own 63-session return, and P4E issuer quality >=2. Up to three
names with the highest 63-session SPY-relative momentum are returned
as a research watchlist, NOT a stock purchase recommendation.

The isolated P4G GitHub workflow tests source and chronology fixtures
on commits and PRs; at 03:30 UTC Tuesday-Saturday or explicit manual
dispatch it separately fetches public vendor-adjusted share closes
for all eight issuers and SPY/SHY, retains a canonical dated input
CSV and its SHA256, and emits one research-only descriptive snapshot.
The earliest source-eligible completed market session is 15 October
2026, with capture no sooner than the next UTC date. Public Yahoo
adjustments can be retrospectively revised. No future price outcomes
exist yet for P4G, and no automatic historical stock return study
has been inferred from the eight current 2026 surviving companies.
The first real P4G public stock price acquisition is **PENDING**.

Next: observe genuinely new market sessions and develop an append-only
cost-aware forward comparison of top-three research shortlist versus
equal-weight six covered issuers and SPY/SHY. The separate licensed
P4F original broker EPS revision feed, historical security master,
delisting and original corporate-action total return are STILL missing.
The Phase 3 C1/C2/static commodity forward ledger and V5 genuine ETF
PAPER workflow remain independent. No individual-stock PAPER/LIVE
permissions. LIVE operator STOPPED, kill switch ENGAGED, HIGH risk,
USD 130.30 pilot ceiling and fixed 14 equity-ETF whitelist unchanged.


## Operator-directed V6 active/aggressive strategic reset (15 October 2026)

The operator clarified that their desired Fund-100 start is **not** a
largely passive 75%-ACWI ETF core. Although four V5 LIVE bootstrap ETF
buys were genuinely filled on 5 October 2026, these constitute
**transitional investments, not approval of V5 as the active strategy
experiment**. The 14-ETF LIVE list was a permission list, not 14 held
positions. The user's intent is concentrated, actively managed,
well-specified strategies with high upside *and material downside*,
launched with the existing small funded capital after a lean but real
risk/execution release check, not months of imaginary-money performance
waiting.

New priority: V6 replacement design and candid frozen-history
comparison, as documented in [PR #39](https://github.com/nicobouch97/fund100-research/pull/39)
and the immutable-research V6 charter:
\`research_lab/challengers/V6_ACTIVE_AGGRESSIVE_RESET_2026_10_15.md\`.
First V6-R1 candidate is weekly, 3-position concentrated sector/country
ETF momentum (63/126-session relative to SPY; up to 35/35/30 allocation)
with an explicit prior-session 200-day SPY risk-regime de-risking rule,
5/15/35bp one-way trading friction and comparison against passive ACWI.
It is an **experimental hypothesis, not yet demonstrated excess profit**.
The previously inspected historical set cannot be sold as new independent
validation. Its 35% concentrated positions would violate the existing
HIGH per-satellite 25% limit; these parameters **must not** be inserted
into V5 LIVE executor without an independently versioned risk model and
operator approval.

In parallel: pursue the distinct stock-earnings/quality/momentum,
commodity futures/carry and crypto research lines; they remain broker-
unapproved until genuine data/execution work exists. No automatic
strategy self-promotion or doubled per-bot capital budget.

**Real-money transition remains wholly unapproved:** operator
\`trading_enabled=false\`, BROKER kill switch ENGAGED, HIGH risk profile,
original $130.30 ceiling; the operator suggested they may later wish
to sell four old ETF positions but has NOT instructed their liquidation.
Do not sell anything, permit new buys, unlock existing LIVE scheduling,
change guardrails or assume available cash now. When the operator
explicitly chooses to migrate, read fresh LIVE broker positions and
order history, prepare an exact staged transition, review sale proceeds
and costs, prevent old V5 loop from repurchasing positions, verify risk
limits and ask for specific buy/sell authorisation before any order.


### V6-R1 empirical result (15 Oct 2026) — rejected, no live migration

The first separately frozen aggressive contender was run on genuine
immutable Fund-100 historical price observations (NOT imaginary expected
returns) in
[Actions 38772847954](https://github.com/nicobouch97/fund100-research/actions/runs/38772847954).
Its 16 dedicated risk/source/no-lookahead tests passed.
Weekly concentrated rotation of up to three sector/country ETFs
suffered severe trading friction and underperformed passive ACWI
in the exploratory 2014–2026 comparison: **−6.2656 percentage points
annualised** at 5bp per traded side, **−8.3343 pp** at 15bp and
**−12.3557 pp** at 35bp. Gross annual portfolio-weight turnover was
**19.68715 x NAV**. These historical observations were already known;
no claim of independent historical alpha can be made from them.
Preserved rejection:
\`research_lab/results/V6_R1_AGGRESSIVE_ROTATION_FIRST_REAL_RESEARCH_REJECTION_2026_10_15.md\`.

**REJECT V6-R1.** Do not alter it until its reused sample fits a desired
result. Do not trade it LIVE or replace old V5 holdings with this losing
prototype. The operator's priority remains a better active high-risk
strategy—not more trading for its own sake. Seek genuinely distinct
sources and evidence (individual stock analyst revisions/catalysts,
authentic futures carry, and other appropriately cost-aware methods)
before a separately approved small-capital LIVE strategy reset.


## 17 October 2026 — V6-E1 first original SEC earnings-catalyst research

As the operator rejected the passive V5 75%-ACWI core and the
experimental V6-R1 weekly concentrated ETF rotation lost heavily
to ACWI net of historical costs, the next economically separate
active-system challenger is **SEC Item 2.02 earnings-event price
confirmation**. It is an individual-stock catalyst *hypothesis*,
not actual verified predictive alpha or an approved stock trade.

Preregistered source protocol:
\`research_lab/stocks/V6E1_REAL_SEC_EARNINGS_CATALYST_PROTOCOL_2026_10_17.md\`.
Implementation:
\`fund100_v6_sec_earnings_catalyst_e1_v1_0.py\`.
Read-only external evidence workflow:
\`.github/workflows/fund100-v6-e1-real-catalyst-source-audit.yml\`.
The workflow independently cross-binds original SEC eight-firm
issuer submission JSON captured 15 Oct (original actual SEC
artifact run 38756477914) with the first actual new completed
stock-price public adjusted-close observation captured 17 Oct
(original artifact run 39015519726). It accepts only real issuer
8-K Item 2.02 records and waits two subsequent completed sessions
before describing a benchmark-relative public-market reaction.
The data source may yield **zero** eligible post-freeze events;
a positive earnings surprise or future holding return must not
be fabricated. Original SEC 8-K is NOT analyst consensus.
Real stock quote vintage, bid/ask, point-in-time broad security
master, independently genuine post-entry returns and actual
broker stock authorisation remain missing.

Potential future high-risk concentration would be capped at four
positions of max 25% each, no leverage, an explicit shared
$130.30 total pilot ceiling and independent cost/market-liquidity
checks. Those are **research parameters only**, not LIVE authority.
Current V5 portfolio unsold, V5 operator STOPPED, kill switch
ENGAGED and current 14-ETF LIVE allowlist intact. The operator
has not instructed liquidation or new stock purchases.


### V6-E1/E2 first REAL cross-source result — fail to establish an edge (17 Oct 2026)

The source audit on [workflow run 39024722787](https://github.com/nicobouch97/fund100-research/actions/runs/39024722787)
verified two original independent archives and passed 15 dedicated
negative/chronology tests. **Zero** new Item 2.02 SEC earnings
catalysts occurred in the first genuine post-freeze source slice:
there is no current V6-E1 research watchlist, let alone an order.

The predeclared E2 feasibility diagnostic used the ORIGINAL archived
SEC accessions and the ORIGINAL price dataset, but the 8-company
cohort was selected in 2026, and the old filing/data vintages are
not independent contemporaneous archives. **23** historical events
were observable; **11** passed the frozen +2pp SPY-relative
initial price confirmation. Ten-session hypothetical third-close
entry→exit event results (compared to passive SPY) were **negative**:
at 5bp/side −1.44015pp *median* / −1.38165pp *mean*; at
15bp/side −1.63633pp median / −1.58207pp mean; at
35bp/side −2.02810pp median / −1.98231pp mean. Only 27.273%
had positive excess at 35bp/side. These are small-sample
survivorship-biased EVENT statistics, **not** an achievable portfolio
CAGR or independent source-proven alpha. Source evidence and
precommitted fail in
\`research_lab/results/V6_E1_E2_REAL_EARNINGS_EVENT_FIRST_REVIEW_2026_10_17.md\`.

**REJECT V6-E2 for live migration.** Avoid fitting fresh filters to
the same failed data; pivot to independent predeclared ideas and
better market-source coverage. The user's intention is an
aggressive LIVE small-capital experiment backed by credible
evidence, NOT blind promotion after a negative test.
No old holdings sold; operator STOPPED and kill switch ENGAGED.


## 17 October 2026 — V6-C1 distinct 24/7 crypto regime research

After rejecting V6-R1 overtrading sector ETF rotation and V6-E2
post-earnings chase, prioritize an economically different BTC/ETH
trend following strategy with long-trend gates and volatility-limited
exposure, without guaranteeing profitable alpha. The fixed **before**
first real V6-C1 backtest spec lives in
\`research_lab/crypto/V6C1_CRYPTO_24_7_TREND_PROTOCOL_2026_10_17.md\`.
Companion broker-free code:
\`fund100_v6_crypto_trend_c1_v1_0.py\` and
\`.github/workflows/fund100-v6-c1-real-crypto-trend.yml\`.

This new source experiment requests public historical BTC-USD/ETH-USD
24/7 vendor closes (not original authenticated exchange historical
fills), preserves acquisition UTC and original SHA256, tests weekly
Sunday decisions using *prior* completed Saturday data, 180-day SMA
plus 63-day absolute trend, 30-day realized basket volatility
target 50% annualized, BTC/ETH long-only 65/35 maximum
with cash fallback, and 25/35/60bps fee/spread stress.
Compare to BTC passive buy-and-hold and a constant 65/35 BTC/ETH
passive portfolio. Vendor histories and already observed past market
regimes make any returns exploratory, not independent proof.
Crypto 24/7 event monitoring and precise live fees/eligible
assets/jurisdiction require further account-specific checking.
Coin/fiat rights are separate from the original V5 ETF capital
permission. No Alpaca secrets or brokerage calls in this research
workflow, no broker crypto order permits. The existing V5
operator remains STOPPED and kill switch ENGAGED, with pilot capital
ceiling USD130.30 and four ETF holdings unchanged.


### V6-C1 source-true result: reduced past drawdown, did NOT beat holding crypto

[Actual real public historical BTC/ETH run 39027912139](https://github.com/nicobouch97/fund100-research/actions/runs/39027912139)
completed the predeclared strategy research, archiving a canonical
original data CSV (SHA256
\`ae796a3141a4fe52453af8aa83e879b95841dc28b11b4294b1e0f43077e9f22f\`)
and study result. 15 dedicated tests passed.

For retrospective **2020 onward** at 35bps per traded side,
V6-C1 yielded **30.0175% annualised compound** vs
**42.9567%** BTC buy-and-hold and **47.2411%** passive
65BTC/35ETH; corresponding maximum drawdowns V6 **−48.4349%**,
BTC **−76.6346%**, BTC/ETH **−76.9412%**.
At 25bps V6 was 30.8591%, at 60bps 27.9349%.
Annual gross turnover **6.43953 × portfolio value**, ABOVE
predeclared 5 × NAV limit. For descriptive 2023 onward,
35bps V6 +29.6544% annual versus BTC +52.1256%;
V6 max drawdown −33.2414% versus BTC −53.06%.
These extremely high historical crypto returns and drawdowns are
**not future expected rates**. Venue spreads, taxable activity,
FX conversion and crypto account eligibility remain unverified.

**Do NOT promote V6-C1 to LIVE.** It did reduce historical
drawdowns but underperformed both long-hold crypto benchmarks,
failed turnover criterion and lacked executable quote/permission
evidence. Preserve rejected result:
\`research_lab/crypto/V6C1_FIRST_REAL_RETROSPECTIVE_CRYPTO_RESULT_2026_10_17.md\`.
Do not optimize the reviewed historical segment to manufacture
a successful high-frequency strategy. Continue independent dated
commodity-carry source efforts and distinct active portfolio
hypotheses. Four original V5 LIVE ETFs remain held and the operator
is STOPPED.


## 17 October 2026 — official CFTC positioning data and DBIQ gasoil event (C5)

The public EIA daily WTI RCLC1/RCLC2 source was discontinued in
April 2024 and the GitHub runner returned HTTP 403 in the previously
recorded attempt. **It does not supply 2026 forward curves.**
To make concrete independent commodity progress, Fund-100 added a
read-only official 2026 CFTC *Disaggregated Futures Only* original ZIP
source check for COMEX GOLD (contract code `088691`) and NYMEX WTI
(code `067651`). Managed-money longs and shorts / open interest are
observable trader positioning, **not actual futures settlement
prices, a carry signal, or a profitable investment strategy**.
Publication timing must account for the 2025 CFTC government shutdown
and delayed releases; latest annual files are current compilations
rather than weekly independently archived original vintages.

Separately, Deutsche Bank's official indexed DBIQ publications page
lists a **9 October 2026** gasoil extraordinary-weight amendment for
its diversified commodity index: trigger observation 1 October,
rebalancing effective 8 October. That amendment is AFTER the rebalance
and **cannot be used to claim a tradable early-warning signal**. The
original October 1 PDF and original real contract maturities/weights
are still missing; official issuer website access terms remain an
explicit acquisition gate. Frozen source review:
`research_lab/commodities/C5_CFTC_ORIGINAL_POSITIONING_AND_DBIQ_GASOIL_NOTICE_2026_10_17.md`.
Offline CFTC source ingestion and source-only workflow:
`fund100_cftc_official_positioning_c5_v1_0.py`,
`.github/workflows/fund100-c5-official-cftc-positioning.yml`.
If original CFTC ZIP cannot be obtained, report BLOCKED, do not
manufacture source observations. CFTC positioning remains research-only.
No change to trading STOP, four current ETF holdings, HIGH risk,
USD 130.30 cap or 14-ETF LIVE whitelist.


### C5 first genuine current official commodity trader positions — 17 October 2026

CFTC's actual 2026 Disaggregated Futures Only annual ZIP source
**SUCCESSFULLY downloaded** in
[run 39030028357](https://github.com/nicobouch97/fund100-research/actions/runs/39030028357).
2026 report code/name format was validated against the authentic
public source; original ZIP and SHA256-linked JSON were archived
as artifact **12100485342**. 10 source contract / anti-forgery
synthetic tests passed.

Real reported Tuesday **13 October 2026** positions:
- **COMEX gold / 088691:** managed-money net **+107,089 futures
  contracts** (27.02% of aggregate open interest), down **3,898**
  contracts from preceding weekly report.
- **NYMEX WTI-PHYSICAL / 067651:** managed-money net **+40,574
  contracts** (2.14% of open interest), down **13,024**.

The original annual file was acquired after Friday 16 October
(the CFTC calendar's ordinary intended release), but this is a
current compiled/archive copy, **not independently archived release-
timestamp original data**. Historical release anomalies in 2025 are
material. No futures expiry settlements or authentic roll carry
have been acquired, so **no commodity strategy alpha and no trading
signal was proven**. Research finding preserved:
`research_lab/commodities/C5_FIRST_AUTHENTIC_2026_CFTC_GOLD_WTI_REVIEW_2026_10_17.md`.

This source unblocks a future properly release-lagged commodity
positioning hypothesis, not the separate contract-price/expiry
requirements for a real futures-carry trading edge. Continue
commodity strategy development without promoting an unverified
source to LIVE. Four original ETFs remain unsold and STOPPED.


## 17 October 2026 — C6 authentic CFTC positioning plus GLD/USO trend candidate

The original successful C5 gold and WTI official CFTC 2026 archive
(artifact 12100485342) now supports a distinct **C6 historical
economic test**: managed-money net/open-interest share *rising over
exactly four official weekly reports* alongside positive 63-session
public ETF adjusted-price momentum, with GLD as gold, USO as an
imperfect oil futures ETP (NOT a matched CFTC futures contract),
SHY as fallback exposure. Trade only at next ETF close
STRICTLY AFTER official **SCHEDULED** release date, so the model
cannot collect Tuesday-to-Friday price movements before the
3:30 p.m. ET publication. 2026 CFTC schedule includes delayed
**22 June and 6 July Monday** release dates.
The annual CFTC ZIP acquired on 17 October is not an independently
archived historical weekly **actual release vintage**, so
2026 backtests remain RETROSPECTIVE / source-clock approximate;
CFTC publication anomalies may undermine assumed dates.

Preregistered C6 rule and explicit economic thresholds:
`research_lab/commodities/C6_PREREGISTERED_CFTC_GOLD_WTI_POSITIONING_TREND_2026_10_17.md`.
Research-only source implementation, original-archive
integrity test, reproducible public-price workflow:
`fund100_commodity_cftc_positioning_trend_c6_v1_0.py`,
`test_fund100_commodity_cftc_positioning_trend_c6_v1_0.py`,
`.github/workflows/fund100-c6-cftc-positioning-trend.yml`.
Economic review from May 1 to October 16 2026 is a short **cumulative**
return comparison against static 50/50 GLD/USO,
static 35/35/30 GLD/USO/SHY and SHY alone at
15/35/60bps one-way gross buy/sell turnover.
Any positive historical number is NOT independent alpha or
a real execution profit. Even a promising signal cannot grant
new LIVE permission or sell existing V5 positions.
Trading remains STOPPED, kill switch ENGAGED,
HIGH user-selected risk, unchanged USD 130.30 ceiling.


### C6 empirical result: failed historical commodity positioning/ETF filter (17 October 2026)

C6's genuine original C5 official futures-only CFTC source was cross-bound
to a new archived GLD/USO/SHY public vendor adjusted-close source in
[real action run 39030915263](https://github.com/nicobouch97/fund100-research/actions/runs/39030915263).
**16** dedicated no-lookahead/source-cost guard tests passed.
After frozen CFTC publication-schedule lag and 15/35/60bp one-way
turnover deductions, the short **1 May–16 October 2026**
cumulative returns were:

- Static 50/50 GLD/USO: **+1.77429%**.
- Static 35/35/30 GLD/USO/SHY: **+1.36231%**.
- C6 at 15bp per traded side: **−20.26548%**.
- C6 at 35bp per traded side: **−22.01665%**.
- C6 at 60bp per traded side: **−24.15823%**.
- 24 CFTC scheduled-release signal decisions; **11.06523 x NAV
  gross accumulated target-weight turnover** (exceeds precommitted
  total-period 4× threshold). At 35bp C6 drawdown **−22.28503%**.

**C6 economic gate FAILED: DO NOT PROMOTE OR RESCUE-TUNE ON THE
ALREADY STUDIED DATA.** This result is source-limited retrospective,
not real historical release-vintage or actual ETF close fills.
Original futures carry/roll settlement P&L remains unavailable.
Results archived at
`research_lab/commodities/C6_FIRST_REAL_CFTC_POSITIONING_ETF_RESULT_2026_10_17.md`.
Research priorities should now be genuine independent contract-level
forward-curve original prices, licensed analyst earnings-revision
source, or a separately justified **cost-controlled and lower
turnover** hypothesis. Aggression is not a substitute for
positive net economic evidence. Do not liquidate the four V5
ETF live holdings or extend their 14 ETF-only LIVE allowlist.
Operator STOPPED, broker kill switch ENGAGED, risk HIGH and
USD 130.30 total capital ceiling unchanged.


## 17 October 2026 — C7 ORIGINAL CME futures-contract settlement source discovery

After C6 original-data commodity positioning × GLD/USO ETF
trend lost 20–24% in the short exploratory May–October
period, avoid another high-turnover parameter search.
A genuinely different commodity-specific information
source is CME Group's original daily energy bulletin,
**Section 61**:
https://www.cmegroup.com/daily_bulletin/current/Section61_Energy_Futures_Products.pdf
It contains NYMEX CL **named delivery-month settlements and OI**,
the fundamental original inputs for a *futures term-structure*
hypothesis rather than an ETF momentum proxy. CME public
webpage index https://www.cmegroup.com/market-data/daily-bulletin.html
links this first-party PDF, subject to CME's data rights.

The PDF uses a ROTATING URL and must never be treated
as an immutable dated file. 17 Oct web observations were
discrepant: **October 16 PRELIMINARY text** versus
**October 8 FINAL screenshot** at the exact same URL.
Only bytes actually fetched and independently hash-stored
with direct first-page extraction, date, FINAL status,
physical NYMEX CL identity, unique delivery contracts,
and complete per-contract OI sum matching the bulletin
can be admitted. A newer PRELIMINARY is rejected even
if older FINAL is all that is currently accessible.

C7 original source intake/negative test/one-off workflow:
`fund100_cme_section61_original_c7_v1_0.py`,
`test_fund100_cme_section61_original_c7_v1_0.py`,
`.github/workflows/fund100-c7-official-cme-final-curve.yml`,
`research_lab/commodities/C7_ORIGINAL_CME_SECTION61_FUTURES_CURVE_SOURCE_PROTOCOL_2026_10_17.md`.
One verified date is a **cross-sectional curve only**,
NOT earned carry/rolling futures P&L. Need multiple validated
dated finals, authenticated chronology, roll/expiry and
fees. CME's licensed historical DataMine/APIs must not
be purchased automatically against USD130.30 pilot.

Four original V5 LIVE ETF investments remain held;
operator STOPPED, kill switch ENGAGED, HIGH tier and
USD130.30 ceiling unchanged. No new futures/commodities
LIVE or PAPER permit.


### C7 original official CME source probe: PRELIMINARY rejected (17 Oct 2026)

A direct original GitHub Actions GET of CME Daily Bulletin
Section 61 **succeeded** at the network/extraction level in
[run 39039186006](https://github.com/nicobouch97/fund100-research/actions/runs/39039186006).
Original PDF first-page heading was **BULLETIN #200, Friday
16 October 2026, PRELIMINARY**. C7 correctly rejected this
document; the reference status for the first live probe is
**NO ADMISSIBLE FINAL SETTLEMENT DATA / NO CARRY**.
Nine synthetic format/source/anti-forgery tests passed.
CME's rotating URL served another date/status in an earlier
web renderer, demonstrating why exact raw PDF SHA256,
FINAL document status and completed acquisition timestamp
must be reconciled to each source. When a dated FINAL
appears, source admission requires real contract-by-contract
open-interest reconciliation and delivery-month identity.
CME futures expiry rules, historic FINAL vintages and
roll P&L are still **not** established by this attempt.

Truthful source result:
`research_lab/commodities/C7_FIRST_OFFICIAL_CME_BULLETIN_SOURCE_STATUS_2026_10_17.md`.
No CME subscription, ETF liquidation, new futures trading
or LIVE operator permission. Continue independent research
with verified source admission; do not fabricate alpha.


## 18 Oct 2026 — C8 source provenance and transparent FINAL-admission state

CME officially explains that next-business-day **FINAL**
Section 61 bulletin is generally published at **10:00 a.m.
Chicago time**. Friday 16 October 2026 bulletin was observed
as **PRELIMINARY** on Saturday 17 Oct; Monday 19 Oct is the
next business-day FINAL target, subject to actual publication
and caching. The official rotating /current/ URL alone is
not an immutable historical reference.

C8 introduces a one-off (not background cron) original-PDF
status workflow that records a **SHA256 source fingerprint,
acquisition UTC and printed date/status/bulletin number**
even for rejected PRELIMINARY documents WITHOUT copying
rejected PDF bytes or its commodity quotations into
research. FINAL is accepted only after complete C7 date,
CL product, maturity, settlement and open-interest
reconciliation. Each source outcome can be distinguished:
REJECT_PRELIMINARY / REJECT_INVALID / REJECT_UNAVAILABLE /
REJECT_FINAL_INVALID / ACCEPT_FINAL_SOURCE_ONLY.
No futures carry profit or trading right can be inferred
from a single final source.

Official CME notice indicates certain daily settlement
files remain **free of charge after midnight through
DataMine** following retirement of the prior FTP endpoints,
but this does NOT verify anonymous access, all historical
files, API/redistribution rights or account registration;
no paid subscriptions or credentials should be opened
without separate operator consent. CME physical NYMEX CL
margin/expiry/delivery mechanics would not suit the
$130.30-long-only micro-pilot directly. Future approved
commodity exposure, if justified, would need an accurately
tracked small-size instrument.

Research doc:
`research_lab/commodities/C8_CME_ORIGINAL_SOURCE_AND_FREE_DATAMINE_ENTITLEMENT_2026_10_18.md`.
Code/tests/workflow:
`fund100_cme_source_state_c8_v1_0.py`,
`test_fund100_cme_source_state_c8_v1_0.py`,
`.github/workflows/fund100-c8-cme-source-status.yml`.

Trading remains STOPPED; the existing four V5 ETFs remain
invested, no sell permission, HIGH risk, USD130.30 ceiling
and current ETF-only LIVE whitelist unchanged.


## 18 Oct 2026 — C9 hard feasibility of a real $130.30 long-only commodity strategy

Research is not economically useful if its intended instrument
cannot be held at the original LIVE microcapital size.
CME's official WTI contract-comparison page reports
**7 July 2026** indicative initial margins of
**$6,826 CL** (physically deliverable 1,000bbl),
**$3,423 QM** (500bbl), and **$685 MCL**
(financially settled 100bbl). MCL alone requires ~5.26×
the **entire USD130.30 cap** *before* reserves or losses.
The proposed smaller 10-barrel WTI contract is marked
pending regulatory review and not established LIVE.
Broker customer margin, leverage/futures permissions
and actual available cash are not verified and are not
implied by CME's 2026 estimates.

A new **C9 source-bound instrument feasibility audit** reads
only the original checked-in LIVE micro-pilot policy and
STOP control, hashes both and fails if the cap, 14-ETF
whitelist, crypto/leverage/order permissions or STOP changed.
It rejects CL/QM/MCL as capital-infeasible and prohibited.
GLD, USO and SHY remain research-only because **not
in the existing LIVE ETF universe**; XLE is allowlisted
equity-energy companies, **not crude-oil futures carry**.
Any actual ETF buys require source-true current cash/asset
support, explicit user decision and separately versioned
strategy/risk authority. None of these constraints change
with the HIGH risk selection. No CME payment, financial
transfer, sales or trading workflow activation is performed.

Implementation and dated official evidence:
`fund100_microaccount_instrument_feasibility_c9_v1_0.py`
`research_lab/commodities/C9_MICROACCOUNT_CME_MARGIN_AND_TRADABLE_INSTRUMENT_ROUTE_2026_10_18.md`.
C9 focuses future strategy research on **low-turnover,
evidence-led and feasible low-dollar trading instruments**.
There is still no validated V6 replacement; no fake
paper-performance delay is required to *propose* a credible
real-money pilot once it exists. Existing four V5 ETFs
remain invested and STOPPED, $130.30 authorisation intact.


## 18 October 2026 — V6-R2 lower-turnover, genuinely active micro-pilot candidate

Because direct CL/MCL futures fail the **$130.30 capital**
test (C9), original CME FINAL multi-date futures carry prices
are not yet available (C7/C8), and the earlier V6-R1 weekly
momentum candidate lost heavily to ACWI with ~19.7x/year
turnover, test a distinct **slow concentrated time-series
momentum** hypothesis based on empirical academic research.

V6-R2 holds up to **TWO** selected, currently LIVE-whitelisted
but still STOPPED equity/sector ETFs, excluding passive
SPY and ACWI, with **quarterly** decisions, **252-day
lookback excluding latest 21 sessions**, positive absolute
trend and prior-completed 200-day moving average gate.
Concentration is **60% first / 40% second** (residual
cash if fewer qualifying; no interest/leverage). Only
rebalance when a weight drifts ≥15 percentage points;
compare **5/15/35bp each traded side** to passive ACWI.
This is NOT a tweak to V6-R1's 63/126d weekly relative
momentum, and must NEVER be tuned to rescue failure on
the previously studied frozen sample.

Frozen preregistration:
`research_lab/stocks/V6R2_PREREGISTERED_QUARTERLY_CONCENTRATED_MOMENTUM_2026_10_18.md`.
Script/tests/actual original data run:
`fund100_v6_quarterly_concentrated_trend_r2_v1_0.py`,
`test_fund100_v6_quarterly_concentrated_trend_r2_v1_0.py`,
`.github/workflows/fund100-v6-r2-quarterly-trend.yml`.
Source is original immutable exact
`research_lab/frozen_history_v2.csv`
with SHA256
`acc2c8c08953b895ca5062b3cfba287efb97143b10e108e8ce4bd8b82ffb0d28`.
2014 onward and 2020 onward were previously analysed,
so these are **exploratory return differences and NOT
independent validation or projected LIVE alpha**.
Predeclared **further-research-only** conditions: 15bp
full +≥2pp annual return vs ACWI; 35bp full positive
vs ACWI; 15bp 2020 onward positive vs ACWI; ≤3x
annual turnover; no >40% historical drawdown.
Even passing would not make this a LIVE order plan:
60% single-ETF weight exceeds the original V5 HIGH
portfolio risk contracts and must be explicitly
redesigned/authorised. There is no liquidation
permission, no broker POST and no new account activation.
Keep C7 futures data as a separate research stream.


### V6-R2 real historical study outcome (18 October 2026)

Original SHA256-exact 2014–September 2026 research
[Actions run 39131536100](https://github.com/nicobouch97/fund100-research/actions/runs/39131536100)
passed 19 no-order/source/chronology tests and measured
a genuine **negative longer-term economic result**:
at 15bps per traded side, quarterly concentrated
R2 produced **11.54595% annual historical CAGR**
vs passive ACWI **12.29808%**, excess **−0.75213
percentage points per year**; at 5bps excess
−0.30171pp/yr and 35bps excess −1.64936pp/yr.
Full-period gross weight turnover **4.02438× NAV/year**
(exceeds precommitted 3×), max R2 drawdown
**−27.85944%**. Descriptively 2020-onward at
15bps it achieved **14.949% CAGR** vs ACWI
**12.18279%**, excess +2.76621pp, but that
period is NOT an independent holdout and cannot
rescue the full-source failure.

**V6-R2 PREDECLARED research gate FAILED. Reject R2
for LIVE migration; do not post-hoc rescue-tune on
the same familiar data.** Candidate demonstrates
that lower turnover / slower trend can reduce
some past disadvantages of weekly V6-R1, but
does not prove higher returns net of costs or
even stay below the 3× annual turnover ceiling.
Full archived result:
`research_lab/results/V6_R2_LOW_TURNOVER_QUARTERLY_REAL_HISTORY_REJECTION_2026_10_18.md`.

Next priority is original acquisition of truly
prospective independent market/issuer sources
and new economically distinct hypotheses, or
an explicitly modest real-money pilot with
clearly stated unproven alpha and separately
approved loss budget. No V5 portfolio liquidation,
order authority, new HIGH risk concentration
or new asset-class release.


## 18 Oct 2026 — V6 transition bridge: real ETF cost preview without unauthorised orders

After several honest FAILED V6 research candidates and the
$130.30 microcapital infeasibility of direct CME futures,
prioritise actual implementation of a **brokerless
original-LIVE-ledger transition preview** instead of
claiming another in-sample fitted strategy is ready.

The user considers current four V5 LIVE ETF holdings
ACWI, EEM, XLE and XLV a temporary investment,
**not the desired aggressive V6 trading experiment**.
Those positions are real, with 5 Oct fills, and
cannot be treated as cash. The historical buy
ledger, original policy and STOP operator are SHA256
verified by a new read-only *offline* CLI:
`fund100_v6_brokerless_transition_preview_v1_0.py`,
`.github/workflows/fund100-v6-no-order-transition-preview.yml`,
`research_lab/V6_LIVE_RESET_READONLY_EXIT_VALUATION_PROTOCOL_2026_10_18.md`.
Until a fresh LIVE account GET (positions/mark/cash/open
orders/settlement) is bound and independently authenticated,
the CLI emits `NO_FRESH_READ_ONLY_MARKS_NO_EXIT_VALUATION`,
actual historical filled share quantities but **NO current
equity, liquidation proceeds or present trade cost estimates**.
The pure test-only hypothetical quote path exercises
5/15/35bps one-way sale friction while clearly noting
input marks are not independently authenticated or
live broker quotes.

The next real funded transition is not authorised just
because the original 5 October LIVE bootstrap already
occurred. It requires a specifically selected active
replacement strategy, explicit user authorisation to
sell original holdings, new versioned HIGH concentration/
risk and capital policy, broker cash settlement/asset
support and separate SELL/BUY release controls.
No account secrets, Alpaca API requests, LIVE orders
or ETF sales were made by V6 research.

The CME route remains source research only. CME DataMine
file API requires credentials/entitlement and official
Daily Bulletin file documentation describes top-of-day
files **overwriting** prior daily bulletins; rotating
/current/ PDF does not provide free historical curve
series. Friday FINAL publication expected Monday is
not an established dated historical sample. No
paid subscription or unauthorised data redistribution.


## 18 October 2026 — explicit operator delegation, autonomous decision: HOLD

The operator explicitly delegated discretion to select
whether/when to sell their existing four LIVE ETFs if
economically appropriate, **without repeated per-decision
chat approval**. Preserve that instruction via
`research_lab/v6_delegated_decision_scope_v1_0.json`
and decision narrative
`research_lab/V6_DELEGATED_OPERATOR_DECISION_2026_10_18.md`.
This supersedes earlier roadmap references to seeking a
separate chat reapproval for every investment decision;
it is **NOT** a waiver of the original $130.30
total-capital limit, no leverage/short/margin policy,
broker account environment controls, or exchange access.

The delegated decision on **18 October is HOLD existing
ACWI/EEM/XLE/XLV** temporarily, NOT to restart V5
or endorse it as V6: original source-verified
V6-R1, V6-E2, V6-C1, C6 and V6-R2 proposed replacements
all failed economic gates or reliable excess-return
evidence. Selling now would create costs and an
unallocated cash position without a better strategy.
There is no market-hours order or queued liquidation.

`fund100_v6_delegated_hold_or_switch_v1_0.py`
cross-checks all five exact Git-blob research rejection
reports and source-bound original LIVE holdings/policy
STOP; its research-only output is
`HOLD_EXISTING_FOUR_ETFS_NO_SELL`, with zero
broker calls/orders and no fake current market values.
Separate execution software/platform permissions and
fresh account reconciliation must exist BEFORE actual
future reallocation; the old bot remains STOPPED and the
broker kill switch's last audited state ENGAGED. The
delegation is permission to exercise investment judgment,
not self-signed replacement for brokerage order controls.


## 18 October 2026 — actual LIVE account GET-only transition readiness

In response to delegated operator discretion to sell old
ETF holdings when economically best, today's investment
decision remains HOLD (5 rejected/unevidenced V6
alternatives). But the next launch critical path is an
ACTUAL broker GET-only validation rather than treating
historical Oct5 fills/Oct14 balances as today's valuation.

`fund100_v6_real_live_getonly_transition_readiness_v1_0.py`
plus
`.github/workflows/fund100-v6-real-live-getonly-transition.yml`
performs a single after-merge account inspection on
LIVE environment restricted to main. Exactly four
HTTP GET requests—account, positions, zero open orders,
market clock—using the original read-only Alpaca client.
Fresh repo STOP and ENGAGED broker kill switch, correct
account binding, HIGH risk and unchanged original
four filled fractional quantities are required.
It reconciles NAV=market-value+cash in transient
runner memory; deliberately prints/persists NO
account IDs, quantities, cash, equity, price, proceeds
or orders. Authentication or changed positions
failing stops safely rather than fabricating spendable
funds. CLI and tests have no SELL/BUY paths.
Protocol: `research_lab/V6_ACTUAL_LIVE_ACCOUNT_READINESS_PROTOCOL_2026_10_18.md`.
One original GET on Sunday is NOT a fresh executable
Monday session quote, and cannot release LIVE trading.


## 18 October 2026 — P4H true post-freeze stock return attribution

P4G historical price lookbacks and SEC quality freeze on
15 October cannot be relabelled historical alpha. The
**original 17 Oct P4G GitHub Action run 39015519726**,
artifact ID **12094995126**, was obtained after
the **16 Oct completed session**. This is an authentic,
fixed market-data observation before the next Monday.
The 8-stock current research cohort and six known
SEC issuer-score names remain frozen; no hindsight
reranking or analyst revision source is fabricated.

P4H now provides a **read-only costed forward ledger**
from that original existing source and future unmodified
P4G snapshots at 03:30 UTC Tuesday-Saturday:
`fund100_stock_forward_return_ledger_p4h_v1_0.py`,
`test_fund100_stock_forward_return_ledger_p4h_v1_0.py`,
`.github/workflows/fund100-p4h-original-forward-equity-ledger.yml`,
`research_lab/stocks/P4H_FROZEN_OCT17_BASELINE_PROSPECTIVE_EQUITY_RETURNS_2026_10_18.md`.
It downloads EXACT baseline original artifact (refuses a
replacement baseline), checks both JSON+CSV SHA256 and
all old overlapping price bars unchanged. Original
selection is P4G as of 16 Oct, simulated first entry
only at the **NEXT session close** (earliest Mon19),
first future earned return earliest Tue20. Until
then it truthfully records **0 future trade returns**
rather than annualising in-sample price lookback.

It measures hypothetical buy-and-hold <=3-name
frozen watchlist vs original 6-name quality cohort
and passive SPY on identical forward dates, each with
5/15/35bps entry AND modelled exit costs. No alpha
forecast or realistic closing-auction fill is implied;
retrospective price revisions, missing original
history or missing new observations stop/abstain.
No LIVE stocks, crypto or futures authorised;
four existing LIVE ETF investments remain HELD,
operator STOPPED, last audited broker kill switch
ENGAGED, HIGH, original USD130.30 ceiling.


## 18 October 2026 — P4I permanent genuine pre-entry market source anchor

Original P4G quality/momentum watchlist **MSFT, KO, PG**
was actually recorded on 17 Oct 2026 after the
**16 Oct Friday** completed close; original source
run **39015519726**, GitHub artifact **12094995126**,
canonical full price CSV SHA256
`9c01c045f6fe9d54f455513249c23433a806ffb350575bef9bfdbde5372d921d`,
P4G original JSON SHA256
`403a6e23ad53ace626cb9663e3889ab9c0b4e58d7c582ad3aab85aa024bdffb7`.
These are now immutably retained WITHOUT copyrighted
original full vendor price series in
`research_lab/stocks/P4I_PERMANENT_2026_10_17_SOURCE_ANCHOR.json`.

The initial original archived GitHub artifact expires
after 90 days. P4I source verified in PR CI against
the still-available ORIGINAL 17 Oct archive first;
later scheduled P4G observations can be processed
against this anchor alone. Each later adjusted close
series must exactly reproduce the original full
pre-17-Oct canonical price CSV SHA256 by truncating
the new source after 16 Oct. Vendor history restatements
fail closed rather than faking vintage-consistent
return data. Hypothetical entry no earlier than
19 Oct next-close, first future earned return
no earlier than 20 Oct; modelled full two-sided
5/15/35bps fees, SPY and fixed six-accounting-score
issuer benchmarks, no backfilled CAGR.

Implementation:
`fund100_stock_forward_permanent_anchor_p4i_v1_0.py`,
`test_fund100_stock_forward_permanent_anchor_p4i_v1_0.py`,
`research_lab/stocks/P4I_PERMANENT_SOURCE_ANCHOR_AND_AGE_OUT_PROOF_2026_10_18.md`
and modified recurring existing P4H workflow.
Original chosen trio is an independent **defensive
watchlist**, not the aggressive user's preferred
V6 strategy. It may underperform and must be
measured honestly, with no LIVE stock order rights.

Separately, CME original Standard Continuous Price
Series has **underlying futures contract ID and
next official roll date**, but data remains license-
gated via DataMine and cannot become fabricated
historical settlement evidence. No trading or data
purchases made. Four original LIVE ETF investments
remain HELD; STOP, HIGH and $130.30 cap unchanged.


## 18 October 2026 — operator-directed FAST LIVE experimental strategy program

**SUPERSEDES any launch criterion that demands weeks/months
of accumulated PAPER or forward PROFIT before real money.**
The user explicitly wants a promptly operational USD130.30
experiment, with empirical strategy research conducted now,
a short mechanical PAPER execution verification, and ongoing
live learning AFTER the strategy becomes executable.
Historical outperformance is never guaranteed alpha.
This amendment updates the 14 October roadmap's older
forward-performance promotion language where it implied
a mandatory months-long wait. Source continuity and
longitudinal research observations STILL matter for
strategy reviews after launch and for honest alpha claims.
No "launch by date" pledge is an order permit.

New standard:
1. Economic mechanism supported by research or
   economically plausible original evidence;
   fixed selected inputs/risks *before* one tested
   historical source study, no endless retuning.
2. Historical *plausibility* across multiple regimes,
   stressed both-sided costs and noncatastrophic drawdown,
   rather than a requirement for reliable positive alpha.
   Disclose in-sample/reused-period limitations, against
   relevant passive benchmark.
3. SHORT PAPER checks **only** of fractional minimum
   notional, broker permissions, order/fill reconciliation,
   trade timeout/idempotency, kill-switch and settlement;
   no requirement for positive PAPER profits.
4. Explicit separately versioned HIGH concentrated
   LIVE risk contract and operator-approved capital
   boundaries, verified original account cash and
   broker-specific asset accessibility. SELL/BUY stages
   must handle T+1 and no margin; new engine must not
   run concurrently with STOPPED V5. Brokerage
   environment release controls remain in force.
5. LIVE deployment with existing approved budget
   becomes a **small unproven experiment**. Observe
   objective fills/performance, stop on losses/breaches,
   and version learning decisions to avoid overfitting.
   The bot never rewrites risk thresholds silently.

First new economic candidate frozen before first test:
`research_lab/V6_L1_FROZEN_AGGRESSIVE_VOL_REGIME_FAST_LAUNCH_2026_10_18.md`,
`fund100_v6_fast_launch_vol_regime_l1_v1_0.py`,
`test_fund100_v6_fast_launch_vol_regime_l1_v1_0.py`,
`.github/workflows/fund100-v6-l1-fast-vol-regime.yml`.
L1 uses fixed market premium exposures **XLK 50%,
XLE 30%, IWM 20%**, half allocated to cash if
prior 20-session annual SPY volatility >30%,
reviewed month-end with 10pp trade band.
It is RISK-regime driven, not another winner-
rotation tweak of failed R1/R2. A single original
SHA-locked 2014–Sep26 history with 5/15/35bps
stressed costs is a *plausibility diagnostic*, not
independent evidence of profitability. Original
HIGH risk V5 max sector weight 25%, so 50% XLK
is strictly RESEARCH until a separately tested
concentrated risk contract and LIVE engine exist.

P4H/P4I individual-stock forward observation and
CME commodities original price/source work
continue **in parallel** as learning research; they
are not prerequisites for the first experimental
LIVE V6. Existing ACWI/EEM/XLE/XLV positions
remain HELD while strategy and broker readiness
are resolved. The operator already delegated
sell/hold discretion; do not seek repetitive
investment-choice approval, but do not bypass
GitHub/broker auth or transfer restrictions.
Original USD130.30 capital ceiling, HIGH selection,
V5 STOP and broker kill switch stay unchanged.


### V6-L1 first original historical return study: feasibility pass, not trading permit

First real original-source locked history:
[GitHub Actions run 39164109643](https://github.com/nicobouch97/fund100-research/actions/runs/39164109643).
At 15bps/traded side, 2014–Sep2026 **V6-L1 CAGR
16.23951% vs ACWI 12.29808%**, excess +3.94143pp/yr;
max drawdown −34.29313%, annual gross turnover
0.67470× NAV; 10 monthly volatility spikes. At
35bps side annual CAGR 16.08258%; original
preregistered PLAUSIBILITY gate **PASS**.
2020-onward L1 15bps CAGR 17.40909%
vs ACWI 12.18279%, a descriptive same-known-history
comparison, NOT independent alpha. Full original run
and study:
`research_lab/results/V6_L1_INITIAL_COSTED_PLAUSIBILITY_RESULT_2026_10_18.md`.

Crucial distinction: Results could be mostly explained
by large technology/energy sector allocations,
rather than vol regime skill. A **fixed same-asset
sector mix diagnostic** should compare performance
without volatility scaling, without changing the
precommitted model. Historical 2014–2026 is already
frequently explored in Fund-100; do not assert
a reliable +3.94pp future advantage, or change
parameters to rescue later results.

L1 is RESEARCH ONLY. 50% XLK exceeds the V5 HIGH
25% satellite concentration limit, so a new
explicit, checked risk policy and execution
controller plus short PAPER mechanics verification
must precede even a micro LIVE release. None
has been approved or deployed. Four original
LIVE holdings unchanged and STOPPED.


### V6-L1 same-assets counterfactual: volatility RULE DOES NOT CREATE THE RETURN

[Source-locked run 39164782847](https://github.com/nicobouch97/fund100-research/actions/runs/39164782847)
compared L1's fixed monthly volatility-managed
XLK/XLE/IWM 50/30/20 basket against the IDENTICAL
sector weights, same monthly trade schedule,
same 10pp band and the exact same 5/15/35bps
cost assumptions **without** any volatility cut.

At 15bps each side, 2014–Sep2026 managed L1
CAGR **16.23951%**, unmanaged fixed-sector
**17.89297%**; the vol rule **detracted
1.65346pp of annualized return** while max
drawdown changed only **−34.29313%** versus
**−34.28854%**. In the known 2020–Sep2026
subset, managed underperformed identical fixed
sectors by 2.67483pp/year. 6 source/no-trade
counterfactual tests passed.

**Reject the supposed incremental volatility-
timing alpha for V6-L1**. Do NOT tune its
cutoff/period to rescue it on this same
history. Most of the appealing original
16% L1 backtest came from historically strong
chosen sector premia and selection/period effects,
not proved algorithmic return skill.
Detailed failure:
`research_lab/results/V6_L1_VOLATILITY_RULE_ATRIBUTION_2026_10_18.md`.

The faster experiment path is STILL in effect:
historical economics and short PAPER execution
mechanics can permit a clearly stated unproven
risk-premium LIVE pilot without waiting months
for paper P&L, once a specific risk-aware
strategy and broker engine are legitimately
released. A more aggressive factor portfolio
is not automatically better than passive
ACWI; nor does another failed rule give permission
to sell the four current LIVE ETFs.


## 19 October 2026 — S1 concentrated risk-contract + actual PAPER ETF eligibility, no profit-wait gate

The operator-approved faster approach is now targeted at **historical economic
plausibility and short PAPER order MECHANICS**, not months of forward PAPER
returns. Original L1 20-session volatility overlay failed its own
same-underlyings attribution; the attractive historical result came
from the fixed 50% XLK / 30% XLE / 20% IWM **sector risk exposures**,
not demonstrated volatility timing alpha. This underexplored fixed
basket is an aggressive **unproven beta/factor experiment**, not an
established return-seeking proprietary bot.

Propose a broker-realistic **S1 HIGH concentrated pilot** with
original pilot capital ceiling USD130.30, **95% gross invested** /
**5% minimum cash reserve** and notional weights XLK 47.5%,
XLE 28.5%, IWM 19%. This 5% cash buffer means S1's own CAGR
has NOT been historically measured; do not promote the original
100%-invested fixed basket's 17.89% exploratory CAGR as
S1 return evidence. Existing V5 HIGH 25% sector position cap
is unaffected. The distinct proposed S1 contract requires
a newly versioned 50% max instrument policy, 6% daily loss
and 20% drawdown / 35% annual vol stops, no margin or
new deposits, and independently tested actual LIVE release
before any order. Original STOP and kill switch preserved.

Implementation:
`research_lab/v6_s1_high_risk_micro_pilot_proposed_manifest.json`,
`fund100_v6_s1_concentrated_risk_and_paper_asset_v1_0.py`,
`test_fund100_v6_s1_concentrated_risk_and_paper_asset_v1_0.py`,
`research_lab/V6_S1_MICROACCOUNT_TRANSITION_CONTRACT_2026_10_19.md`,
`.github/workflows/fund100-v6-s1-paper-asset-readiness.yml`.

After PR acceptance, authentic Alpaca PAPER GET-only asset requests
for all three ETFs run in the pre-existing paper environment to
verify `active`, `tradable`, `fractionable`. That is broker
eligibility investigation, NOT completed S1 PAPER BUY/SELL,
not REAL LIVE asset confirmation, not a release to trade.
Offline risk contract arithmetic only simulates
**$61.89 XLK, $37.13 XLE, $24.75 IWM, $6.53 cash**
if the full $130.30 were already available as settled CASH;
**currently it's not** because four original V5 ETFs remain held.
Any future transition must verify settled cash separately,
prevent V5/V6 concurrent controllers and honor all original
broker STOPs. Independent paper order-mechanics check next;
no profitable paper waiting period.


## 19 Oct 2026 — one-session S1 genuine PAPER fractional share mechanics

The actual authenticated Alpaca PAPER GET-only asset probe
[run 39227661735](https://github.com/nicobouch97/fund100-research/actions/runs/39227661735)
confirmed **XLK, XLE, IWM** all active/tradable/fractionable,
with ZERO broker order creation and LIVE no-change.
S1 remains a **proposed** 95% gross, 5% cash fixed factor
experiment, NOT a proven active alpha engine or approved
LIVE V5-to-V6 migration.

Instead of asking for weeks of PAPER profit, run one
**$2 real Alpaca PAPER buy/restore SELL** to check
market DAY fractional notional, fill quantity,
client-order-ID de-duplication and no unowned
portfolio change. New
`fund100_v6_s1_one_time_paper_fill_probe_v1_0.py`
plus synthetic negative tests and
`.github/workflows/fund100-v6-s1-paper-fill-once.yml`
targets only US trading session **Monday 19 October
2026, 13:43 UTC (9:43 EDT)**. Exact date, main
branch, initial GitHub attempt, risk HIGH, engaged
kill switch and remotely verified LIVE STOP are
hard requirements; no LIVE credential, endpoint,
orders or cash transfers. If broker rejected the
round trip or original PAPER positions were not
fully restored, the workflow must FAIL and require
manual PAPER-only reconciliation (never silently
repeat in later sessions).

Detailed original workflow purpose:
`research_lab/V6_S1_2USD_PAPER_ORDER_MECHANICS_PROTOCOL_2026_10_19.md`.
PAPER success is an execution-mechanics observation,
NOT proof of LIVE permissions, S1 market beating
returns or profitable prediction. After that:
fresh LIVE asset/cash and settlement verification,
a new separately controlled HIGH 50% concentration
policy, transitions in explicit stages from four
current investments, and single live execution
controller. No user reapproval for routine
investment-choice discretion is implied, and no
platform/environment STOP is bypassed.
