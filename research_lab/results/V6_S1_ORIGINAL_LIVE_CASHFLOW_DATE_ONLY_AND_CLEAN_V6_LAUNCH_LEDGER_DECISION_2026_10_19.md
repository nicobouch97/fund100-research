# V6-S1 — genuine cash-transfer source limitation and clean LIVE performance-ledger decision

**Source observation: 19 October 2026 at ~18:31:48 UTC**, authenticated original Alpaca LIVE only.

## Evidence proved, never inferred

- Original verified seven-GET broker run: [GitHub Actions 39303201301](https://github.com/nicobouch97/fund100-research/actions/runs/39303201301). Read-only on reviewed protected `main`, with original HIGH, remote STOP and kill ENGAGED.
- Independent original source/credential release [PR #72](https://github.com/nicobouch97/fund100-research/pull/72) passed the entire LIVE static audit before merge, and post-merge static safety [39303201394](https://github.com/nicobouch97/fund100-research/actions/runs/39303201394) succeeded.
- Account identity and original held ACWI/EEM/XLE/XLV reconciled, original XLE within proposed draft 28.5% target, cash below proposed new 5% post-buy floor, zero open orders.
- Nontrade original account activities include external transfers. Actual cash-transfer records were **date only for the purposes of intraday signed-flow accounting**, so our exact-timestamp Modified Dietz fixture model cannot be applied to real account history; program emitted `CASH_TRANSFER_SOURCE_DATE_ONLY_NO_DIETZ`.
- Alpaca native portfolio history with `cashflow_types=NONE` had the **same** `profit_loss_pct` series as the original 1D query: `BROKER_NATIVE_NONE_PNL_SERIES_SAME`. This is an observed equality, NOT evidence that original equity and returns are cash-flow adjusted or that the NONE parameter guarantees investor returns.
- Raw equity history still `RAW_BROKER_EQUITY_HISTORY_PASS_NOT_CASHFLOW_ADJUSTED`; genuine account-adjusted 6% daily-loss/20% drawdown/35% annualized vol protection NOT validated from this history.
- Exactly **seven GETs and zero non-GETs / orders**, no signed dollar amounts, transaction dates, account identifiers, personal financial figures or fill IDs saved publicly.

## Launch accounting decision: clean NEW V6 risk/performance baseline, not false backdated V5 returns

**We need NOT make the V6 launch depend on retrospectively reconstructing exact time-weighted gains for V5's old funded period**. The external-flow ambiguity is historic, and V6 is a prospective investment experiment. Record two distinct time boundaries in *privately protected, authenticated* live-source evidence:

1. **Migration start boundary**: authenticated V5 starting equity/cash/all existing holdings and zero open orders immediately BEFORE any sale; never call migration P&L a V6 stock-selection result. Every old ACWI/EEM/XLV exit and original XLE retention must reconcile real fills and settlement; stop if an unexpected external transfer appears.
2. **V6 strategy performance start boundary**: authenticated post-transition cash and new XLK/IWM/XLE positions, exact fill ledger, no open/unreconciled orders, original V5 unwanted positions flat, sufficient spendable cash and all risk controls. Start the V6 account-unitized performance index at **1.000000** at this first eligible trading-close/account boundary. Explicitly exclude old V5 prelaunch return data from V6 performance and future alpha claims.
3. For every subsequent V6 return interval, collect original broker equity/positions, all fills, funding/journal/asset-transfer activity and timing; if any external cashflow or ambiguous noncash transfer occurs, **HOLD and rebase only after authenticated ledger reconciliation**, not silently call it market P&L.
4. During the first days V6 can measure daily account return/drawdown from that clean known source baseline. A statistically stable account-level realized-volatility estimator needs more observations. **Do not mislabel absent V6 returns as a passing historical 35% annual volatility stop.** The separate approved launch policy must specify conservative prelaunch exposure/volatility evidence and an explicit short warm-up state, or fail closed until equivalent acceptable risk data exists. Guardrails cannot guarantee gaps.
5. Benchmark future V6 net account return against a comparably funded price/cash benchmark from the same launch timestamp and same fees. Do not compare mismatched 2026 account return windows to 2014–2026 retrospectively researched S1 17.08743% CAGR. Distinguish future net genuine account returns from XLE/static concentrated beta exposures.
6. No extra funding, derivatives, borrowing, crypto or individual stocks. Original cap **$130.30**, risk HIGH, target XLK 47.5%, XLE 28.5%, IWM 19%, cash 5% at-order minimum; these S1 draft weights are not an independent alpha proof.

This is an **accounting and evidence-handling architecture decision only**. It does not retroactively enable original V5 LIVE writer or new V6 REAL order posting. Actual investor-funded holdings remain ACWI/EEM/XLE/XLV at last source GET, broker kill ENGAGED and operator STOPPED.

## Most direct launch-engineering priority

Build a narrowly separately reviewed, idempotent V6 **LIVE SELL/reconciliation transport** that:
- acquires fresh original account/position/order identity on every action, including historic broker order receipts and client-order ID duplicate protection;
- never sells original XLE merely to buy it again unless the original position breaches an approved cap;
- exits ACWI/EEM/XLV only after approved launch risk policy, exact position quantity verification and original STOP/release workflow;
- uses exact prior SELL receipts and shares-flat evidence before proceeding;
- waits for genuine applicable settled cash and original account read reconciliation before ANY replacement BUY;
- maintains the 5% **post-buy** cash floor with quote/fee/spread buffer, $1 minimum, $65 maximum new order and combined account loss/exposure/volatility limits.

Do not repeat $2 PAPER fills or wait for weeks of forward simulated returns: those mechanics genuinely passed [39269640353](https://github.com/nicobouch97/fund100-research/actions/runs/39269640353). The clean V6 forward ledger starts only when new genuine V6 order execution and risk source are fully reconciled. The user has delegated selection of the replacement portfolio; broker technical release and safety controls remain independently enforced.
