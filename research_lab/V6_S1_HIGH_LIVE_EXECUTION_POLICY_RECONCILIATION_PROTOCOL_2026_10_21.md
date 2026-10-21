# V6-S1 HIGH — executable-policy conflict reconciliation protocol (2026-10-21)

**Preregistered before code. This proposes a revised HIGH-risk release contract, NOT an Alpaca release, brokerage order, or change to frozen research or original V5 LIVE policy.**

## Why needed now
The authentic original private account-bound signed empty ledger is live and independent HMAC/public issue recovery was verified by protected original `main` workflow [#39638576563](https://github.com/nicobouch97/fund100-research/actions/runs/39638576563). Original prior verified genuine LIVE broker 4GET [#39636438731](https://github.com/nicobouch97/fund100-research/actions/runs/39636438731) authenticated ACWI, EEM, XLE and XLV with no open orders. Actual ledger `sequence=0`, entries empty; this is historical evidence and must be refreshed before any funded order.

Two contradictory policies must be reconciled BEFORE one could ever make a LIVE order:
1. The source-pinned V6-S1 exploratory manifest at `research_lab/v6_s1_high_risk_micro_pilot_proposed_manifest.json` erroneously lists XLE as a mandatory *legacy exit*. The later reviewed V6-S1 overlap-aware migration, HIGH ex-ante policy, old fractional SELL adapter and signed ledger ID map all converge on **ONLY ACWI, EEM, XLV** as exits; retain existing XLE if within the 28.5% target, or require explicit new review if above. Do not sell/rebuy XLE solely for taxonomy.
2. Original existing V5 HIGH satellite cap is 25%; separately proposed V6-S1 HIGH concentrated sleeve requires 47.5% XLK target, 50% single-symbol upper cap, 95% gross and 5% cash reserve. Do NOT run original V5 25% per-symbol checker for V6 and then silently override its failures, and do NOT authorize V6 just because the separate offline policy passes. It needs its own explicitly reviewed new live contract/runner, never an in-place mutation to original V5.

## Proposed reconciliation rules
- Account binding MUST come from frozen `live_activation_outputs/v5_002/live_micro_pilot_policy_v1_0.json` and remain pseudonymous; no raw account ID.
- Original HIGH pilot authorized maximum capital USD **$130.30**; no extra funding, margin, crypto, shorts, options, futures, FX or leverage.
- Proposed economic targets on actual whole-account equity: XLK 47.5%, XLE 28.5%, IWM 19%, minimum cash at order-time 5%; gross <=95%; single symbol <=50%; new order <=$65, minimum new BUY >=$1; stop on daily loss at -6%, peak-to-trough drawdown at -20%, estimated realized annual volatility >35%, with ex ante volatility staging independently authenticated.
- Sequence for future staged migration: verify the exact current broker fractional quantities and all order IDs; sell **only** ACWI, EEM, XLV in that order, never sell XLE automatically; independently reconcile full fills/flat positions with the signed private order journal BEFORE advancing; new BUYs only after the separate settled-cash source and 5% cash floor are proved. Do not assume sale proceeds are immediately settled or perform a BUY from legacy paper cash.
- The frozen `research_lab/v6_s1_high_risk_micro_pilot_proposed_manifest.json` and initial public genesis witness file MUST retain identical Git blob SHA so HMAC/genesis proof cannot be invalidated by attempted cleanup.
- Original `fund100_live_operator_control.json` remains `trading_enabled: false`, environment kill `ENGAGED`, V5 `live_order_authorization_present: false`, V6 original status `PROPOSED_NOT_LIVE`, remote trade transport release flags false.
- A new policy candidate must have an explicit `execution_authorized=false`, `broker_sell_authorized=false`, `broker_buy_authorized=false`, `production_ledger_future_state_advances_released=false`, `separately_signed_live_release_present=false`.
- This policy contract is validated offline with source-locked real original signed files and mock risk decisions. It must never read, print or write actual private ledger, HMAC secret, brokerage state or issue-comment raw state.
- Any future promotion requires independent risk/strategy release and a live transport implementation that enforces signed private CAS state reservation pre-POST and uncertainty/no-resubmit; original legacy SELLs remain untouched now.

## Evidence and tests
Check original frozen manifest SHA, V5 policy SHA, independent separate HIGH contract, overlap-aware staged sell adapter and ledger client ID continuity. Reject accidental legacy XLE sale, target sum !=95%, target >50% and cash <5%, unpinned original source, false LIVE STOP, missing external anchored future-head progression, and any claim this proposed policy can dispatch a broker order. All output categorical, no private amounts or holdings sizes. Source contract tests + full LIVE safety audit must pass before merge.

Successful reconciliation is only a precise operational V6 candidate, **NOT permission to liquidate holdings or start actual orders**.
