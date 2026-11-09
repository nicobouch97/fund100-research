# Fund-100 private principal ledger CAS — source-independent planning

9 November 2026 | Offline state-protocol foundation only. **No remote state
was created, committed or modified. No brokerage orders or trades.**

## Current account evidence and capital boundary

The protected GET-only real account check #42683146607 observed 3 activities,
queried from before broker-reported account creation and diagnosed
OBSERVED_GROSS_FUNDING_ABOVE_ORIGINAL_PILOT_HOLD. Still missing: independent
settled cash proof, complete all-category transfers/provenance, actual
HMAC/immutable private ledger and an owner-approved enlarged capital mandate.
The original $130.30 pilot and $65 max new ticket remain untouched. No
within-mandate automated additional-funds authorisation exists yet.

## This foundation

fund100_scalable_private_principal_cas_offline_v1_0.py constructs *only*
synthetic PRIVATE HMAC signed content and an optimistic Git Contents CAS plan
for a **future** state namespace. The underlying real source is not read;
the private Git repository is not accessed or automatically initialized.

- Account-binding digest and separate genesis commitment, exact sequence
  and predecessor Git blob SHA. No missing-state auto-init, no 404 fallback.
- Ingestion of a complete, bounded, chronological **synthetic** USD
  non-trade source, with every row included in an HMAC commitment sequence;
  withdrawal and deposit directions/signs and unique source IDs enforced.
- Signed private CUMULATIVE gross deposits and net contributed principal,
  excluding synthetic dividends/fees/interest from contributed owner funds.
  Gross history above $130.30 remains research-only QUARANTINED, even if
  withdrawn and re-deposited.
- A fresh full source MUST preserve every prior commitment in order;
  deleted/reordered/altered old activities HOLD. No lost-source replacement.
- A simulated Contents CAS proposal references the exact expected Git
  blob SHA and increments sequence by one; stale externally supplied
  expected head/sequence refuses. A private signed proposal is not a real
  CAS write or an independently anchored rollback guarantee.
- Public results deliberately omit all private funding amounts, activity
  IDs, account binding digests and raw base64. The proposed private body
  *does* contain signed aggregate dollar totals, so MUST be handled only
  by a future authenticated private-state writer. Never print a proposal.

## Required production work

1. Set up an actually separate immutable principal state namespace,
   HMAC key custody and provider-immutable public anchor with a signed,
   approved initial HEAD. Make read/update/uncertain commit confirmation
   single-writer and strict CAS. No branch-public raw funding amounts.
2. Feed data from the protected Alpaca GET-only funding source in the SAME
   authenticated process, not from its redacted public status; bind
   account-creation time, complete pagination, full source activity types,
   transferred securities, settlements and FX normalization.
3. Persist complete signed account-level principal events PRIVATELY; prove
   genuine USD settlement and real excess-cash attribution, including
   sale proceeds, fees, withdrawals, ACATs and corporate actions.
4. Explicitly authorize a bounded, versioned standing contributed USD
   mandate with independent owner intent, expiry, STOP and acceptable
   risk profile. Future within-cap settled deposits can be automatically
   deployed WITHOUT per-trade/deposit approvals.
5. Integrate at the last original order writer boundary with live STOP,
   HARD locks, 6/20/35 account risk, broker fills/open orders, signed
   pre-POST reservation and at-most-once recovery. The current ACWI first
   sale remains HOLD.

A passing synthetic HMAC/CAS test is never a LIVE source, permission
or order. All existing broker write locks remain unchanged.

## 9 November 2026: cash code attribution correction

Alpaca's current Account Activities API documents that **CSD also includes
returned withdrawals** and **CSW also includes returned deposits**. Therefore
a brokerage-observed CSD credit is **NOT independently proven owner-
contributed capital**, and a CSW debit is not necessarily an owner
withdrawal. Earlier statuses claiming *gross deposits/funding above $130.30*
were overinterpreted: the verified narrower fact is that the observed
**gross CSD cash credits exceed $130.30**, subject to the historical
read-only source coverage and currency checks. No settled cash or owner
capital mandate was ever approved by that status.

The corrected protected diagnostic now returns
CSD_CREDITS_ABOVE_PILOT_OWNER_ATTRIBUTION_HOLD or
CSD_CREDITS_WITHIN_PILOT_OWNER_ATTRIBUTION_HOLD, and always sets
owner_contributed_principal_authenticated=false. It requires independent
bank/transfer provenance (and return linkage, corporate actions, FX and
settlement) before any owner contribution can enter a production
principal ledger. The pilot $130.30 ceiling, $65 ticket and STOP remain.

Authoritative Alpaca account activity types:
https://docs.alpaca.markets/us/reference/getaccountactivities

## 9 November 2026: require separate bank-transfer receipts before principal signing

The actual LIVE Alpaca nontrade history contains CSD and CSW activity
codes but those codes do **NOT** establish owner-contributed principal.
Alpaca specifically documents that CSD can mean a returned withdrawal
and CSW a returned deposit. See:
https://docs.alpaca.markets/us/reference/getaccountactivitiesbytype

This offline source protocol now refuses to sign principal from raw
CSD/CSW codes alone. In the *synthetic-only* fixture, a second explicit
bank evidence source is required for every CSD/CSW activity:
an exact one-to-one matching activity ID, unique bank settlement
reference SHA256, account binding, signed USD amount, direction,
settlement date, status SETTLED and returned=false. Orphaned bank
receipts, returned transfers, wrong currency/binding, unsupported
cash codes, duplicate bank refs, ambiguous sign/direction and a
historically modified receipt all fail closed. Both the cash activity
and the matching receipt fixture are now committed in the private
HMAC row chain, so signed history preserves the provenance link,
not only the broker's cash activity.

The fixture source mode explicitly says SYNTHETIC; users or public CI
can construct fixture receipts and they must **NOT** be treated as
real independently authenticated bank transfer records. A matching
fake bank receipt is not real settlement, is not verified owner
identity and does not establish account provenance. Production must
fetch corroborating confirmed transfers from genuinely independent
bank/broker transport with separate authentication, correct account
ownership, return/reversal linkage, USD FX source and business-time
settlement, within a protected credentialed process before treating
owner principal as real. The existing broker Trading API CSD/CSW
endpoint alone cannot establish this. The separate Alpaca Broker API
requires its own capability/access verification and cannot be
silently assumed available.

A passing new offline test cannot initialise the private capital
ledger or authorise a larger capital envelope. The original pilot
limit, STOP, first ACWI sale HOLD, order cap and no-retry guarantees
remain unchanged.
