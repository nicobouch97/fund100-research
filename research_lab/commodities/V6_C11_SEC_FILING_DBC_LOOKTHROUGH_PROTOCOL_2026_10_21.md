# V6-C11 — SEC-filed DBC futures look-through for cross-asset risk (21 October 2026)

**Pre-registered before implementation and tests. This is an original filing-availability and exposure-classification analysis, NOT an investment strategy, carry return, trading target, or claim of today's DBC holdings.**

## Objective

A multi-asset allocator must not mark commodity futures, oil producers' stocks, and an issuer's theoretical index basket as interchangeable. The existing shared capital arbiter accepts coarse factor tags; it lacks verified source-specific look-through. V6-C11 starts building that evidence layer using the Fund-100 SEC-transcribed holdings datasets already preserved in the repository.

## Locked original SEC sources

Use only pre-existing `research_lab/commodities/dbc_sec_futures_holdings_2025_q4_postchange.csv` and `.../dbc_sec_futures_holdings_2026_q1_q2.csv`. Both contain dated SEC futures positions; their source filing URLs and accession numbers must match each complete 28-instrument filing. Pin Git blob SHA1 of the original CSV bytes:
- 2025-12-31 as filed 2026-03-02, conservative available **2026-03-03**, 28 names, USD **1,223,550,999** gross notional. Blob `315fbfab8f95c3290bd156a7eba2ad3bac2e4ac7`.
- 2026-03-31 as filed 2026-05-07, conservative available **2026-05-08**, 28 names, USD **1,689,474,972** gross notional.
- 2026-06-30 as filed 2026-08-07, conservative available **2026-08-10**, 28 names, USD **1,576,215,941** gross notional. Combined 2026 source blob `68953f0f122d00e1d06f893cc879d0ec71117287`.

The original data were human-transcribed from SEC disclosure and previously source-linked. The exact SEC HTML original-byte hash has not been authenticated in this code; original CSV blob integrity protects these *research transcriptions* from silent edits. The original filing/accession must remain visible.

## Mandatory semantics

- Choose ONLY the latest original statement that had become **publicly available** at or before a hypothetical research decision date; never substitute a quarter-end reporting date for actual public availability. For a date before 2026-03-03 return `NO_KNOWN_SNAPSHOT`. For 2026-05-07, December is still latest; for 2026-08-09, March is latest; from 2026-08-10, June becomes latest.
- Compute commodity sector shares only as fraction of **DBC's SEC-reported gross open-futures notional**, never as equity securities, collateral, portfolio NAV, realised carry or unhedged beta. June's energy fraction should be about **47.00%**; March **48.85%**, December **37.40%**. Changes are not roll P&L.
- Separately display, for a *hypothetical* 15% DBC research sleeve, a proportional sector **illustration** (~7.05% of that hypothetical whole portfolio in June for energy futures), but explicitly label it **NOT portfolio factor beta, today's fund weight, actual holdings, broker allocation or an executable order**. A future real allocator needs actual instrument position, exposure multipliers and up-to-date holdings.
- XLE energy-company stocks are distinct from DBC energy futures; do not equate the two exposures to the same security, or assert that different instruments diversify just because their names differ. The DBIQ index webpage's October **53.27% energy theoretical indexed sector mix** is not the June SEC fund's actually held 47% figure. Do not splice issuer index with fund actual holdings.
- Mark the SEC information as **stale quarter-end look-through** for an October trade, with actual session age, not as fresh daily weights.
- The code is a pure, offline diagnostic. It must not import Alpaca, request market data, fetch any URL, change the V6-S1 frozen 95% proposal, or make anyone eligible for LIVE. Reject source tampering, missing contracts, malformed negative notional, duplicate positions, chronology errors, unknown or excessive hypothetical DBC fraction.

## Decision consequence

Recognise that a DBC commodity sleeve could carry substantial energy risk even alongside XLE equity energy, but **do not invent correlation, beta or futures roll returns**. This tool is a useful ground-truth input for later evidence-quality-driven cross-asset allocator improvements, not itself a standalone alpha signal. The original $130.30 LIVE pilot, HIGH risk, STOP and ENGAGED broker kill switch stay unchanged.
