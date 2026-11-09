# Fund-100 commodity research: restart after an unobserved forward gap

9 November 2026. Commodity research only; no paper or live orders.

## Observed failure

The scheduled public research workflow
https://github.com/nicobouch97/fund100-research/actions/runs/42687488669
failed after fetching vendor price and macro histories. Unit tests passed,
but the forward observer stopped when the last **committed** prospective
session was 2026-10-29 and the latest completed vendor session was
2026-11-06. Its previous rule required the most recent previous
vendor session to equal the last committed session. The intervening
session observations did not occur and must not be fabricated.

The original append-only JSONL ledger has 12 signed-by-content SHA256
linked public entries ending 29 October. These are historical frozen
PROSPECTIVE observations and must remain intact.

## Safe automatic recovery protocol

Version 2 of the public prospective record adds research_epoch,
epoch_reset_due_to_observation_gap, skipped_vendor_sessions, and
epoch_reset_reason. Legacy V1 records remain valid and are NEVER
rewritten. On exactly the next genuinely observed COMPLETED vendor
session after a gap, the scheduler appends ONE new V2 observation
whose previous_record_sha256 references the original end of the
ledger, but whose reference NAVs are all reset to 100 and invested
initially in SHY. The new epoch has period_return_observed=false,
model_start_session set to the actual newly observed session and
an explicit number of skipped vendor observations.

No price-to-price or strategy return is calculated for the missed
interval. No missed sessions are backfilled. Subsequent real observed
sessions may compound only within the new epoch. Any replay of the
same session is idempotent. An absent original vendor date, too-large
gap (>260 vendor sessions), corrupted hash, malformed epoch,
falsely continuous period return or non-reset model wealth HOLDs.
The new schema cannot regress to V1 after V2 appears in the chain.

## Reporting discipline

Returns across different research epochs are NOT comparable as if
one continuous realised or forward-tested track record. Every gap
is retained in the immutable hash chain, and the reset cannot
whitewash or retrospectively fill lost performance. The V1
historical 12 observations remain part of the audit chain. These
research models are benchmarks only, not a trading candidate,
liquidity proof, investable fund NAV, verified vintage or approval.

The existing 09:17 UTC weekdays schedule can automatically resume
next time the source has a settled completed vendor bar; it must
not need the owner to repair a research-only gap by hand. This PR
does NOT dispatch the workflow or claim that a future observation
has already occurred.

No Alpaca API requests, no broker secrets, no paper or LIVE orders;
all owner risk, STOP and capital controls unchanged.
