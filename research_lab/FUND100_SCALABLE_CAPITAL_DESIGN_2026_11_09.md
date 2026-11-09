# Fund-100 — scalable contributed-capital framework (9 November 2026)

**Design and synthetic offline code only. Not authority to trade or change the current pilot.**

## Owner requirement

Support future £10,000+ deposits, potentially much larger accounts, autonomous
research-based deployment and rebalancing, with just LOW/MEDIUM/HIGH and emergency
STOP as routine controls. No approval for each order or within-mandate deposit.

## Non-negotiable boundary

The present LIVE account is authorised for only **$130.30 cumulative contributed
principal**, with **$65 max new purchase/partial sale**, alongside original HIGH
risk controls, operator STOP and broker kill ENGAGED. Owner discussion of a
possible future £10,000 deposit DOES NOT approve an increased USD cap or enable
the first ACWI sale. Those source-pinned controls remain fully unchanged.

**Deposits are not trading authority.** A future separate, bounded and
independently authenticated **standing capital mandate** must specify the
maximum contributed USD principal to which an autonomous controller may allocate
newly reconciled cash. Once a valid standing mandate exists, later deposits
inside its cap can be eligible without repeated user authorisations. Anything
above the cap, uncertain, duplicated or unsettled must HOLD. GBP funding is not
USD buying power before actual conversion, booking and reconciliation.

## Implemented in this change

- A strictly synthetic USD-only account and cashflow envelope (no real broker
  secrets, no GET/POST, no signed state, no executable orders).
- Separate proposed standing mandate vs unchanged original pilot ceiling.
- Net contributed capital from deposit and withdrawal events; clean account
  equity is measured separately so investment P&L does not raise the cap.
- Hypothetical risk-tier NAV-relative tickets constrained by available
  simulated settled cash, 5%/higher cash reserve, gross and name exposure.
  These tier assumptions are *not approved production risk rules*.
- Fail-closed source completeness, settlement, IDs, pending orders,
  reconciliation and USD currency; synthetic tests and isolated CI.
- Explicitly HOLDs funds over the cap: a *virtual sleeve label* cannot
  segregate extra dollars in one fungible Alpaca account.

## Remaining production-critical work

1. Versioned, separately signed standing USD capital mandate and revocation,
   with audited expansion of the $130.30 capital authority only when explicitly
   granted. No per-trade/per-deposit approvals thereafter within the mandate.
2. Authenticated complete private broker flow ledger, currency conversion,
   withdrawals, cash settlement and signed HMAC/CAS/immutable anti-rollback.
   Establish genuine capital/asset attribution in an omnibus account.
3. Independently reconcile all outstanding orders, holdings, fills, actual
   cash, settlement, profit and loss, and exogenous funding before buying.
4. Mature LOW/MEDIUM/HIGH asset-specific exposure/ticket/liquidity and 6/20/35
   account risk rules; no claim of alpha or risk compliance from this model.
5. Real autonomous controller: stopped operator boundaries, signed pre-order
   attempt journal, at-most-once POST, broker receipt/fill/flat reconciliation,
   settlement verification and safe recovery under the owner's standing mandate.

The existing **ACWI first-sale HOLD caused by excess funding remains in
force**. This offline foundation does not release it.
