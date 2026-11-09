# Fund-100 — independent latest-head requirement for scalable capital

9 November 2026 | Offline anchored-CAS contract; NO LIVE new capital.

## Evidence so far

PRs #591 through #597 on main provide (a) scalable capital scenario sizing,
(b) an unapproved signed standing mandate fixture, (c) bounded Alpaca
nontrade CSD/CSW pagination and independent account creation window,
(d) original ETF historical lot attribution and (e) a synthetic PRIVATE
HMAC funding CAS protocol. The protected real-account read-only GET run
#42683146607 confirmed 3 non-trade activities and visible gross funding
above original pilot USD $130.30; it did NOT authenticate settled USD
cash or owner-authorised new capital.

Private repository nicobouch97/fund100-state-private exists and contains
prior signed trading-state files. Its NEW capital namespace
state/scalable_contributed_principal.json was NOT created at this stage.

## Gap this module addresses

A private funding ledger can have a mathematically correct HMAC
while representing an *old* or maliciously rolled-back Git file.
The private CAS expected current blob SHA must come from an
**independently trusted latest immutable HEAD** and include a
monotonically increasing sequence bound to the same brokerage account
and ledger genesis.

fund100_scalable_principal_head_anchor_offline_v1_0.py now models
strictly synthetic, separately keyed HEAD fixtures with:
- Exact account/genesis binding, original Git blob SHA and ledger sequence.
- Signed revision, prior anchor digest, issue/expiry clock and bounded
  source staleness.
- A separate caller-provided expected latest anchor SHA: mismatch stops.
- Strict MAC, duplicate JSON detection and exact schema validation.
- An in-memory join to the private principal HMAC/CAS source. Wrong
  private blob or sequence stops; matching source may generate only a
  *synthetic PRIVATE CAS proposal*, not an actual Git write or a trade.
- A separate public_status view that never exposes source account
  bindings, cashflow IDs, real amounts or the private CAS proposal.

CRITICAL: a caller-supplied expected head is not a provider-immutable,
anti-rollback anchor. It may be independently fetched and held in a
trusted provider later. This module explicitly returns
real_head_anchor_authenticated=False, private_ledger_written=False,
live_orders_authorized=False. Synthetic fixture keys are NOT production
owner authorisation.

## Remaining production blocker order

1. Provision and independently authenticate a trusted latest-head
   provider / immutable audit trail, with separate key custody.
2. Bootstrap the actual private capital ledger from COMPLETE authenticated
   Alpaca account activity records inside a protected secret-bearing process,
   never a public CI artifact. No remote current file exists yet.
3. Verify production broker settlement and USD currency conversion,
   account fill/corporate action/cash attribution and full rollover.
4. Obtain owner's **one-time explicit bounded standing capital expansion**;
   mere discussion of a future GBP 10k deposit is not an approved USD cap.
5. Reconcile real account risk/STOP before one-attempt order-time
   BUY/SELL authorisation and partial/fill recovery. Existing first ACWI
   SELL remains HOLD, broker kill ENGAGED, risk HIGH, original $130.30
   cap and $65 ticket unchanged.

No broker GET/POST, private Git file writes or manual trader action
is required by this research-only pull request.
