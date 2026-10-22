# V7-E4 — unattended SEC Item 2.02 evidence snapshots, constrained event screen

**Registered 22 October 2026, after the successful V7-E3 real-source historical-timing audit. Research only. No Alpaca / LIVE / PAPER / brokerage permissions.**

## What changes

The existing P4B official SEC source collector already captures all eight SEC issuers, but only on explicit manual dispatch. V7-E4 adds a **separate, small, read-only official SEC submissions-only collection** for the identical frozen CIK cohort. All original response bytes, complete SHA256 provenance per issuer, and capture times recorded **after each GET** are archived in a distinct GitHub Actions artifact. The real `FUND100_SEC_USER_AGENT` requester-identity secret is mandatory; never create, print, infer, or spoof contact details. No SEC network access occurs on PRs.

An independent P4G public adjusted-close snapshot is captured later in the *same scheduled run*, with its own original SHA, dates, and byte-preserving artifact. If the price provider fails, the SEC archive already exists; no price or signal is fabricated. Source-derived events are unamended original Form 8-K, exact Item 2.02 in recent submissions, and original filing date 15 Oct 2026 onward. These are **filings in the current response**, NOT events necessarily discovered that day, verified earnings-consensus surprises, or authenticated first news dissemination times.

## Scheduled acquisition

- **09:15 UTC, Monday-Friday**, including the next main-branch push after merging this change. Each run has the original source bytes and distinct run-ID artifact names; source bundles are retained for **90 days**, NOT indefinitely immutable.
- Dated T+1 price capture may yield no complete market session on holidays, weekends or vendor outages. Let it fail with explicit missing data. Missing, stale, revised or disputed market prices do not imply signals.
- Reuse the original frozen October 15 P4E issuer quality scores for **at most 90 calendar days**; after that, the observer must refuse to promote any signal even to a research-candidate state until a genuinely contemporaneous refreshed quality provenance is engineered. Current cohort is handpicked 2026 survivors; NOT historical unbiased.
- Match ONLY eight frozen issuer CIK identities. All source raw bytes and observed events must reproduce from the manifest. No acceptance timestamp proves whether a news release was first public at the filing time.

## Fixed first descriptive event-reaction diagnostic

A potential observation needs genuine original item 2.02 source available by capture, contemporaneous issuer quality >=2, **exactly two completed market sessions strictly after filing and ending with the latest observed close**, a preceding close, the **current original price vendor snapshot acquired the following UTC morning before 12:00**, and stock-minus-SPY pre-entry reaction >=2 percentage points. The third trading session is **NOT inferred**; no market open/fill price is claimed. Captures after the second-session window are too late and **must not be backdated to claim a trade**.

Emit diagnostic JSON including no-signal and source-failure states, 5/15/35 bps per side reserved for subsequent independent *post-entry* evaluation. This routine has **no order sizing, portfolio allocation, broker credentials or execution API**. No alpha significance, settlement or real returns implied.

## Boundaries and next dependency

Research is not a licence to replace original frozen P4I vendor history after its observed revision failure. Every original GitHub Actions artifact is source-specific and has finite retention. Eventually persist a stronger append-only durable vault, expand SEC beyond eight survivor firms with point-in-time CIK identities, and add independent forward price acquisition to evaluate entry-to-exit returns net of transaction costs without looking forward.

Preserve operator `trading_enabled=false`, HIGH account risk, existing $130.30 pilot ceiling, ACWI original signed ledger / broker stop gates, original ETFs, and all old live controls.
