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
| **1: ETF pilot** | US-listed global/sector equity ETFs (V5-002) | ACWI benchmark core plus relative momentum satellite, threshold-based rebalance, constrained exposure | **CURRENT:** synthetic end-to-end paper acceptance passes; next is broker-connected paper rehearsal, then explicit small LIVE activation only if approved |
| **2: Bond ETFs** | TLT, IEF, SHY, TIP, LQD (research universe, not LIVE-whitelisted) | Duration / yield-curve regimes, inflation surprise and credit-spread compensation; protect capital when equities struggle | Research-specific data, duration and correlation checks; independent out-of-sample and paper performance before allowlisting |
| **3: Commodity ETPs** | GLD, DBC (research universe, not LIVE-whitelisted) | Trend / inflation regimes / curve carry where applicable; ETF tracking, roll costs and concentration matter | Distinguish futures-backed from physically held products; ETF-specific costs, liquidity, volatility and regime validation |
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
