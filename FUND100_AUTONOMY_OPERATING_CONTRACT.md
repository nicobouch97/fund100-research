# Fund-100 — autonomy-first operating contract

**Owner requirement reaffirmed 29 October 2026. This is a product acceptance criterion, not a discretionary convenience.**

## Exactly two routine owner controls

1. **Select risk level**: `LOW`, `MEDIUM` or `HIGH`. Current account-wide risk-watch profiles already understand these three options. The present pilot is set to `HIGH`; existing V6 S1 release-specific policies are still HIGH-only, and selecting a different tier must **HOLD an incompatible strategy**, never silently override its limits.
   - Existing operator control: GitHub protected environment `fund100-live-broker`, variable `FUND100_RISK_LEVEL` at [Environment settings](https://github.com/nicobouch97/fund100-research/settings/environments).
   - **Do not** require the owner to set per-trade transaction sizes, choose an asset, or approve individual trading decisions. Trading risk profiles and the pilot's `$130.30` capital ceiling are separate controls. More funding or a higher capital ceiling is **not** implied by switching risk tiers.
2. **Emergency STOP**: [Fund-100 STOP TRADING](https://github.com/nicobouch97/fund100-research/actions/workflows/fund100-live-emergency-stop.yml) > **Run workflow**. This existing workflow sets both current-main STOP latches and attempts cancellation of Fund-100's outstanding Alpaca orders. STOP must remain usable irrespective of research status or selected risk. Operator STOP is fail-closed; it is never an automatic restart signal. A broker-side manual kill is a fallback if GitHub is unavailable.

**After launch, routine operations need zero owner approvals.** There must be no third recurring manual control or typed confirmation for maintenance, market research, strategy selection, rebalancing, trades, broker/ledger reconciliation, safe recovery or periodic monitoring. Notify the owner of material failures; never ask them to babysit routine runs.

## Owner delegates decisions inside a standing, bounded mandate

- The system selects its own eligible assets, strategy candidates, trade directions, size, rotations and rebalances using pre-agreed research and economic controls; the owner does **not** approve each order.
- Preserve the currently authorised `$130.30` LIVE pilot cumulative capital ceiling and `$65` maximum for **new buys and partial sales**, with existing full-position risk-reducing sale exception; 95% gross, 50% per-name and the remaining approved risk limits. Risk level changes may **tighten** exposure limits but must not expand authorised pilot capital or waive signed evidence.
- Brokerage requests require authentic, current account/cash/settlement, risk, order/receipt/fill, signed private HMAC/CAS, immutable anti-rollback and coherent strategy-release evidence. The operator and broker kill switch remain STOP/ENGAGED **until an independently valid standing production release exists**. An already approved standing mandate eliminates *per-trade* approval; it does not convert missing evidence into a trade permission.
- Uncertain write acknowledgements, partial fills, unavailable private state, unverified order history, changed broker holdings, or failed cash checks must **HOLD and reconcile** automatically, with no blind repeat broker POST. Do not weaken fail-closed controls to avoid bothering the user.
- A simple risk selector and emergency STOP must remain available for the owner; all **nontrading maintenance** can otherwise proceed autonomously under narrowly scoped access. Do not ask for per-task confirmation for harmless GitHub workflows and tests.

## Remove unnecessary approval checkpoints

- The extra [draft private audit-only write probe #367](https://github.com/nicobouch97/fund100-research/pull/367) is **CLOSED UNMERGED**. It is **not** a release requirement and must not be resurrected as a manual gate. A standalone audit-file write would establish only Contents(write) at that instant, not actual signed-journal CAS or trading safety.
- The first real **authorised** signed production journal CAS must perform its own precondition check, use an exactly scoped protected writer, independent read-back and permanent fail-closed handling of ambiguous results. It must not trigger a real broker order on an unverified write. This cannot be claimed as implemented or verified until the actual controller is tested and released.
- Do not add an approval UI, GitHub `workflow_dispatch` confirmation phrase, mandatory manual paper-trading inspection, approval-per-trade or second human activation step to ordinary operations. If a genuinely new discretionary authority is required (e.g. **raising the capital ceiling, removing the emergency STOP or loosening authorised mandate bounds**), do not silently exercise it; keep operating inside the existing mandate instead.
- Development and scheduled research are already autonomous through GitHub Actions. This contract is the direction for the **future LIVE order controller**; it does not claim that controller is live today.

## Current verified status (29 October 2026)

- Original first ACWI signed private reservation `seq=1, RESERVED_NO_RETRY` and unclaimed owner fence `seq=0` remain separate. The recurring private journal **now exists as an empty HMAC-signed `seq=0`**, created exactly once on 29 October 2026 and independently read back using the READ principal in [protected main run 40876805816](https://github.com/nicobouch97/fund100-research/actions/runs/40876805816). The first-create workflow was subsequently retired to PR-only, credentialless regression tests; no further private CREATE is authorised by that workflow. This is a real storage milestone, **not** an immutable anti-rollback anchor, production recurring CAS transition, broker fill, standing LIVE release or investment return.
- [Actual seven-GET + signed private HMAC verification](https://github.com/nicobouch97/fund100-research/actions/runs/40846071246) completed successfully on 29 Oct, **no orders and no private writes**.
- Broker kill switch `ENGAGED`, public V5 and V6 operator STOP, and all LIVE orders **not authorised**. LIVE strategy returns/alpha remain unproven.
