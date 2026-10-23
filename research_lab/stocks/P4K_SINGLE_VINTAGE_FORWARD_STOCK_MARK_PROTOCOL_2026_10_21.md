# P4K: single-vintage forward stock marks, pre-registered 2026-10-21

Purpose: restore verifiable **observed** post-selection stock-price comparisons in the presence of historical adjusted-close revisions. This is NOT a new strategy, ex-ante alpha proof, brokerage implementation, paper fill, or live return record.

## Frozen inputs and eligibility
- Authentic original P4G GitHub artifact from run **39015519726**, captured 17 October 2026, completed market cutoff **16 October**, frozen selection **MSFT/KO/PG**. Original JSON SHA256 **403a6e23ad53ace626cb9663e3889ab9c0b4e58d7c582ad3aab85aa024bdffb7** and original CSV SHA256 **9c01c045f6fe9d54f455513249c23433a806ffb350575bef9bfdbde5372d921d** MUST verify against the original permanent P4I anchor. Original signals cannot be re-ranked by the later source.
- Later authentic P4G artifact: FIRST eligible known post-freeze snapshot captured 21 Oct, run **39571738927**, independently checked through self-authenticating JSON and exact canonical CSV SHA. Do not search dates/sources for the winner.
- First possible simulated entry session: **19 October 2026** (first source session *after* 16 Oct freeze); no earlier historical prices are returns. Earliest possible exit observation: **20 October**. If the new snapshot lacks both, return a clear `NO_TWO_POST_FREEZE_SESSIONS`, not invented profit.
- Crucially, use **both entry and exit adjusted-close marks from the SAME later archived CSV vintage**, never mix original 17-Oct baseline marks with later adjusted data. The earlier prefix can have revision and still serve only as a record of the original signal's timestamp/identity. Include P4J's measured historical-prefix revision state as **provenance metadata** without silently changing P4I's fail-closed legacy algorithm.
- Guard that the source capture date is later than the latest completed market session, and later than 17 Oct. Guard calendar chronology, baseline original session identity, original actual source SHA, same 10-symbol frozen universe, no missing original historical sessions (no new knowledge inserted into original signal), and no reverse date ordering.
- Return exact anchored fixed-selection equal-weight chosen stocks versus original equal-weight six-company reference and SPY. Research entry-to-exit gross return (19 Oct close to the later final completed session close) and flat **5 / 15 / 35 basis-point** one-way costs on both hypothetical entry and exit, using existing P4H formula. No daily rebalancing, leverage, margin, trading signal update, compounding of rounded daily changes, or back-filled side effects. Benchmark costs matched.
- **Caveat:** Same-vintage adjusted-close marks can be retrospectively recalculated by the provider, and are not independently verified dividend, split, fill, currency-converted or broker transactions. They are reproducible `AS_CAPTURED_ADJUSTED_CLOSE_RETURN_MARK`, *not first-seen closing bid/ask, verified total return, forward alpha, actual account P&L or a permanent revision-free daily mark*. Source SHA and run IDs must accompany every result.
- New methodology ID P4K; never overwrite/relax original P4I fail-closed source-vintage requirement. Real observations remain possible but limited; report sample sizes and no annualization/significance.
- Tests: no eligible session, one eligible session, first correct two sessions, original hash forgery, later self-hash tamper, illegal source shape, divergence in historical prefix while later data remains self-consistent, no additional strategy names, costs monotonic, no URLs/HTTP/order/private token capabilities.
- This work never alters Fund-100 account holdings, original MAX USD **130.30**, risk profile HIGH, existing V6-S1 95% proposed initial exposure, `trading_enabled=false` or the ENGAGED kill switch. No brokerage API transport, passwords, buy/sell orders, or public republishing of vendor-owned raw price series.

## Next engineering decision
P4K may allow research to continue without waiting months of PAPER observations. It does NOT fix market-vintage quality or prove profitability. Eventually prefer exchange-authenticated or first-seen independent close/total-return feeds for cross-asset strategy selection. The central multi-asset allocator must not treat this exploratory result as proven asset-class advantage.


## 23 October 2026 — rolling, source-consistent forward marks (research only)

The initial one-session 19–20 October 2026 result remains a frozen historic
observation, not a standing estimate of performance. The existing P4K engine
now accepts the GitHub run/artifact IDs of a later, original P4G price capture.
The read-only P4K workflow selects the **newest completed scheduled P4G run on
main, regardless of observed return**; if that run failed or its expected
artifact is unavailable, the study fails closed instead of choosing a better
or older result. The original 17 October archive and selection are still
hash-verified, never re-ranked. The later as-captured adjusted-price CSV
provides both 19 October entry and the latest completed-session exit; no
original/later adjusted-price vintages are spliced into a return.

All intervening sessions are checked against the actual XNYS exchange
calendar, including holidays. Missing market sessions or extra nontrading
dates invalidate the entire mark; they cannot quietly inflate or shorten
holding-period returns. The report records the actual source run and artifact
IDs, observed completed sessions and 5/15/35bp-per-side cumulative marks
against matched-cost SPY and the frozen six-name equal-weight reference.
It does **not** compound separate daily round trips, report annualised alpha,
or claim original execution prices were tradable. A future failed scheduled
capture cannot be silently replaced with a convenient earlier winner.

This is one *frozen cohort*, not an expanding survivorship-safe universe or
a tested self-improving stock strategy. The next substantive research gate
remains broader historical point-in-time issuer membership, independently
audited corporate actions and delistings, authentic dated quality/revisions
and a credible cost-aware strategy benchmark. All LIVE capital, operator
STOP, environment kill switch and trading release controls remain unchanged.

## 23 October 2026 — same-vintage path downside, no strategy change

For each eligible frozen-selection forward window, P4K now also measures the
**gross daily buy-and-hold wealth path** of the original three stocks, the
frozen six-stock comparison, SPY and the three-stock portfolio relative to SPY.
All path points start at the original 19 October *post-selection* close, use
only actual verified intervening NYSE sessions, and come from the same later
archived source vintage. The study reports worst observed session return,
maximum observed peak-to-trough drawdown and positive-session counts. It does
not interpolate prices, rebalance the names, change the frozen selection or
claim intraday execution. One entry close without a later mark produces no
risk statistics. The 5/15/35bp entry/exit cost scenarios remain separate:
path downside is explicitly **gross**, not an after-cost NAV drawdown.

A few sessions cannot justify annualized volatility, Sharpe ratios, risk
significance, predictive alpha or automatic strategy promotion. This is
research-only downside diagnostics, not a wider issuer universe or evidence
of a durable trading edge. No LIVE/PAPER order capability or risk permissions
are introduced.
