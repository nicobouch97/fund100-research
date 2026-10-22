# V6-S1 original ACWI crash/restart triage — 22 October 2026

## Purpose

The first ACWI sale is still NOT LIVE authorized. GitHub's original protected account reads and initial PRIVATE HMAC genesis have been verified, and the separate original source-joined HMAC recovery has run, but original seq1 and seq2 private ledger advances have NEVER been made to production. A broker POST has NEVER been placed under this migration. The signed current private blob remains original seq0. Do not interpret the tests below as real execution, a proof of current broker never-POST, or a release.

This new *offline, pure, injected-source* original restart decision module integrates the existing original signature/canonical SHA/public witness verifiers across seq0, seq1 and seq2, with an original deterministic broker client-ID GET observation and exact existing ACWI fractional order receipt validator. It returns ONLY redacted HOLD/quarantine/reconciliation statuses; never an order payload, a private Git CAS proposal, or an instruction to submit or retry.

## Strict restart outcomes

| Current signed PRIVATE HEAD | Broker GET by deterministic original ACWI client ID | STOP/next human/review state |
| --- | --- | --- |
| `seq=0`, signed empty HMAC + original public genesis comment | 404 | `HOLD_INITIAL_NO_RESERVATION_NO_IMPLIED_ORDER_PERMISSION`: no broker POST or intent permission |
| `seq=0` | matching ID found | `QUARANTINE_BROKER_ORDER_WITHOUT_SIGNED_LEDGER_ENTRY`: inconsistent broker/ledger; no POST |
| `seq=1`, ACWI `RESERVED_NO_RETRY`, signed + exact first public SHA witness | 404 | `HOLD_RESERVED_NO_RESTART_PREPOST_COMMIT`: do not auto-resume seq2 from a new process |
| `seq=1` | ID found | `QUARANTINE_BROKER_ORDER_WITH_ONLY_SIGNED_RESERVATION`: unexpected prior attempt |
| `seq=2`, ACWI `POST_MAY_HAVE_BEEN_SENT`, full signed seq1→2 and third public SHA witness | 404 | `HOLD_SIGNED_PREPOST_UNKNOWN_BROKER_POST_NO_RETRY`: 404 is NOT proof broker never received original POST; never resend |
| `seq=2` | exact matching ACTIVE/PARTIAL broker order | `OBSERVED_EXISTING_ORDER_HOLD_NO_RETRY`: monitor same order only |
| `seq=2` | exact matching FILLED receipt | `OBSERVED_FILLED_RECEIPT_HOLD_FOR_INDEPENDENT_FILL_AND_FLAT`: separately verify cumulative paginated fills, original account flatness, sell activity and later settlement before any new symbol |

Any missing/foreign HMAC, wrong private original account binding, altered raw blob SHA, tampered/foreign public issue comment, new unknown seq3+, malformed receipt, terminal/unsafe broker state, unknown lookup response or unexpected original quantity **fails closed**. A mutable GitHub issue comment is still NOT a genuinely immutable external anti-rollback anchor; a locked broker order transport is still NOT a permission to trade. The original HIGH $130.30 pilot cap and XLE original retention stay unchanged.

## Technical consequences

- No run/entrypoint with PRIVATE PAT, HMAC or Alpaca keys: the module and workflow exercise **synthetic fixtures only**. No new production Git PUT, no Alpaca POST, no external witness. Tests do not even call a fake mutation from this module.
- The source's exact signed HMAC and all public HEAD comments are reusable from existing reviewed primitives, not new parsers or string matches.
- Release prerequisites **remain**: independent external HEAD rollback/watermark, one owner across all future real writer executions, order-time equity and cross-asset HIGH loss/drawdown/volatility, current marketable price and cap, validated signed one-POST context, explicit funded GO and independently witnessed seq1/seq2 progression. Do not run the original intent-only workflow before that pipeline exists.
- This closes a major recovery design gap, but does not claim a broker guarantee or make an autonomous first ACWI sell executable. If forced to choose between missing profit and a potentially duplicated trade, this pathway intentionally HOLDs.

## Acceptance

The dedicated new negative test workflow, original v1.17/v1.18 LIVE static audit and full repository regression tests MUST PASS before merging into main. No original approved credential scope or writer hard-lock file is modified.
