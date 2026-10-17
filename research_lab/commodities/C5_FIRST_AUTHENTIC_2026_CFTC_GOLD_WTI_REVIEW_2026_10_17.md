# C5 actual official CFTC source and first verified gold/WTI futures positioning

**Verified 17 October 2026. ORIGINAL CFTC SOURCE RECEIVED. Not carry; not an alpha test.**

## Evidence

- Repository preregistered source intake and defensive negative suite:
  `fund100_cftc_official_positioning_c5_v1_0.py`,
  `test_fund100_cftc_official_positioning_c5_v1_0.py`.
- Original 2026 CFTC Disaggregated *Futures Only* ZIP from
  [official annual historical archive](https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalCompressed/index.htm),
  dated as a **17 Oct 2026 GitHub runner acquisition**.
- [Successful original-data run 39030028357](https://github.com/nicobouch97/fund100-research/actions/runs/39030028357):
  ZIP fetched, officially published actual 2026 field
  `Report_Date_as_YYYY-MM-DD` accepted, code `067651`
  identified by the actual official 2026 market name
  **WTI-PHYSICAL - NEW YORK MERCANTILE EXCHANGE**,
  gold code `088691`, all raw rows/bounds/identity passed.
  **10 synthetic guard/negative fixture tests PASS**.
- Uploaded original official ZIP bytes **plus SHA256-linked original
  capture JSON** under GitHub Actions artifact
  `fund100-c5-original-cftc-futures-only-2026`,
  **artifact ID 12100485342**, 90-day retention.

## Real original reported observations: Tuesday 13 October 2026

| Futures only market | Managed money long-minus-short (contracts) | Net/open interest | Change in net positions vs previous original week |
| --- | ---: | ---: | ---: |
| COMEX GOLD / CFTC 088691 | **+107,089** | **+0.2701914 / 27.02%** | **−3,898 contracts** |
| NYMEX WTI PHYSICAL / CFTC 067651 | **+40,574** | **+0.0213527 / 2.14%** | **−13,024 contracts** |

**Net** = aggregate managed-money *long contracts minus short contracts*;
spreading is a distinct report category, not part of this subtraction.
These are not physical inventories or futures cash returns. The 2026
annual compilation captured Saturday 17 October contains the
Tuesday 13 October positions, for which the official CFTC calendar
lists **Friday 16 October** as the ordinary intended release date.
The original individual Friday release bytes/timestamp and any
subsequent source revisions are **not** independently authenticated,
so no historic executable signal timestamp can be inferred from
the record. Note CFTC published extraordinary historical catch-up
dates during the 2025 US funding lapse—do not blindly apply
Tuesday-plus-three-day lag as a universal backtesting rule.

## Clear boundaries

CFTC open-interest category changes reveal *positioning*, not
the price of an identified WTI December futures contract, nor
a rolling long-return, DBC's exact index fund position or
the correct futures settlement/roll transaction costs.
No futures carry/backwardation return has been calculated.
No market prediction, ETF/stock positive alpha or order intention
was generated. One observed latest weekly net position
is not a trading strategy. A cautious next research step is
a separately preregistered weekly **positioning × trend**
candidate comparing after-cost returns with static commodity ETF
references *only after correctly sourced ETF prices and original
CFTC release vintages*. Current annual CFTC compilation can be
used for descriptive historical research with source-time caveats.

The **9 October Deutsche Bank DBIQ extraordinary gasoil-weight
amendment** confirmed a rebalance effective **8 October**; never
use the later notice for a simulated trade before the index rebalance.
Original issuer PDF/download permissions and actual selected
futures maturities remain blocked and carry work is not promoted.

Original four V5 LIVE ETFs remain invested, operator `trading_enabled:
false`, kill switch ENGAGED, HIGH risk, USD130.30 ceiling, original
14 ETF allowlist, no CFTC-connected LIVE credentials and zero
broker POST/order requests.
