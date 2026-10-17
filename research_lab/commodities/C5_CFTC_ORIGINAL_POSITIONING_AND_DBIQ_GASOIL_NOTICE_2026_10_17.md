# C5: original CFTC gold/oil positioning, and DBIQ gasoil notice

**Registered 17 October 2026. Research only, no trades or promotion.**

## New official source facts

CFTC's [Historical Compressed](https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalCompressed/index.htm)
contains 2026 *Disaggregated Futures Only* reports in an official ZIP
(link from page: `https://www.cftc.gov/files/dea/history/fut_disagg_txt_2026.zip`).
The [official variable-name list](https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalViewable/CFTC_023168.html)
specifies market identities, open interest and managed-money long and
short **futures** positions. Official contract identifiers:
- `088691`: gold, Commodity Exchange Inc. (COMEX).
- `067651`: light sweet crude oil, New York Mercantile Exchange (NYMEX).

CFTC [release calendar](https://www.cftc.gov/MarketReports/CommitmentsofTraders/ReleaseSchedule/index.htm):
reports ordinarily reflect prior Tuesday positions and release Friday
3:30pm US Eastern. October 2026 release dates include **October 2,
9, 16, 23 and 30**; holiday/special changes require specific proof.
Crucially, the [CFTC historical special announcement](https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalSpecialAnnouncements/index.htm)
shows late-2025 US government funding lapses caused *months* of delayed
report releases. A blanket Tuesday+3-day backtest is **lookahead**.
Today's historical annual ZIP is a **current compilation** that can
contain post-release corrections, not an independently archived release
vintage. It CANNOT backtest historical tradable signals without a
separate verified *actual original publication* timeline.

On the [DBIQ official publications page](https://index.db.com/dbiq-web/publications),
a special issuer notice **listed 9 October 2026 at 11:18
(website timezone unspecified)** states:
- DBIQ Optimum Yield Diversified Commodity Index Excess Return, `DBLCDBCE`.
- Extraordinary gasoil weight trigger observed **1 October 2026**.
- Resulting index rebalance took effect **8 October 2026**.
- Issuer amendment was published **9 October 2026** following original
  October 1 Selection Report; the October 9 amendment cannot be assumed
  available before October 8. This is a **retrospective index-event
  observation**, NOT an advance trade signal.
- The issuer JS app and website T&C prevent us from claiming the original
  indexed 2026 monthly selection PDF or guide has been acquired.
  Exact index contract selection, weights and DBC actual ETF fills remain
  unavailable. An original DBC futures-carry P&L is **not calculable**.

## C5 source acquisition, no proxying

- Attempt one **read-only official CFTC 2026 futures-only ZIP GET**
  through the GitHub runner; fail closed on network error, malformed ZIP,
  wrong filename/schema/market identity, missing observations,
  negative/invalid positions and impossible time chronology.
- Preserve SHA256 original ZIP, exact observation and acquisition
  timestamps, never invent missing market positions. Check no
  accidental combined futures+options use.
- Report last two weekly Gold and WTI **managed money net = longs -
  shorts** and net/open-interest concentration and week-to-week change.
  This measures trader category positioning, **not market return,
  futures curve, roll yield, or evidence of active profit**.
- No source price or cross-market signal is available yet. Do not
  call this a complete commodity *carry* strategy. Distinct
  potential future hypothesis: whether crowding/position changes
  help filter trend, tested only when original weekly release
  timestamp + genuine market prices + execution costs exist.
- A 2026 report whose preceding Tuesday date is after the acquisition
  time fails, and **never** claim a release Friday datetime solely
  from the archival report date. Historical CFTC full source is
  revised/compiled as-of current capture.

No change to the four existing LIVE ETF positions, STOPPED operator,
ENGAGED kill switch, HIGH profile, USD130.30 capital limit or 14 ETF
whitelist. No futures, DBC, GLD, or new-asset PAPER/LIVE permission.
