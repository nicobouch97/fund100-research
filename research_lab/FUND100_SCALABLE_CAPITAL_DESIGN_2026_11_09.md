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

## 10 November 2026 — cumulative cap anti-recycling correction

The original standalone synthetic NAV/ticket preview checked only *net*
cash-code contributions against the hypothetical capital ceiling. In an
invented withdraw/redeposit sequence, net principal could be at or below
the ceiling even as lifetime gross CSD credits exceeded it. The preview
now separately accumulates *gross lifetime modeled CSD credits*, and
HOLDs with `HOLD_LIFETIME_CREDITS_EXCEED_STANDING_CAP` whenever the
gross total exceeds the proposed cap, even if current net principal fits.
Regression cases cover both the original $130.30 pilot and a $10,000
hypothetical mandate, plus the allowed gross-equals-cap boundary.

This is strictly a **synthetic modeling correction**. Actual Alpaca CSD
and CSW activity codes can include returned transfers, so neither the
gross model count nor the fixture's `settled=True` authenticates an
owner-funded deposit, settlement or bank transaction. The independent
bank/source evidence, separate signed principal ledger, immutable
head and one-time new capital mandate remain absent. No live release,
broker connection, orders, changes to original caps, or owner actions.

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
