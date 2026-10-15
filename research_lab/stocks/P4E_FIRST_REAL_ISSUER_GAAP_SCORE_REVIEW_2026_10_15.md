# P4E — first real SEC issuer-mapped accounting source outcome

**Reviewed 15 October 2026. Research only. No stock alpha, no orders.**

## Auditable source reproduction

- Fixed eight-issuer source mapping / latest-10-K comparable-year
  rule merged with [PR #36](https://github.com/nicobouch97/fund100-research/pull/36).
- [First real P4E report run 38760165063](https://github.com/nicobouch97/fund100-research/actions/runs/38760165063): **SUCCESS**.
- Already captured 2026 original SEC source artifact:
  `fund100-phase4b-real-sec-snapshot-38756477914`,
  acquired **2026-10-15T15:01:45Z**, 16 original JSON files.
  Revalidated source capture manifest exact SHA256:
  `bafc7a084a6d4deaf7c7b7a5e982d52a8b5ecd6fe1b70a0ebaf3e64a610b1e18`.
- Actual P4E report artifact:
  `fund100-p4e-frozen-eight-company-sec-issuer-quality-38760165063`,
  artifact ID **11984384799**, retained 90 days.
- [Merged-main safety audit 38760164965](https://github.com/nicobouch97/fund100-research/actions/runs/38760164965):
  **907 repository tests PASS**; **36 LIVE boundary safety checks PASS**.

The original P4A/P4C records were neither changed nor backfilled.
Every P4E metric was computed from the identical authentic
SEC JSON capture, requiring current and previous annual
facts within one latest original 10-K accession.

## Observed issuer-specific P4E financial descriptions

| Stock | Revenue YoY | Operating margin | Reported cash FCF margin* | 0–3 source quality |
|---|---:|---:|---:|---:|
| AAPL | +6.43% | 31.97% | 23.73% | **3** |
| MSFT | +17.79% | 46.78% | 20.19% | **3** |
| GOOGL | +15.09% | 32.03% | 18.19% | **3** |
| AMZN | +12.38% | 11.16% | 1.07% | **2** |
| XOM | — | — | — | **UNAVAILABLE** |
| JNJ | — | — | — | **UNAVAILABLE** |
| PG | +3.26% | 22.69% | 17.40% | **3** |
| KO | +1.87% | 28.71% | 11.05% | **3** |

**Measured source coverage: P4A 2/8 → P4E 6/8.**
These scores reflect only data availability and three mechanical
accounting thresholds; no market prices, revenue forecasts,
earnings surprise, analyst consensus, delisting-aware universe,
or stock total return has been evaluated.

* AMZN uses `PaymentsToAcquireProductiveAssets` instead of
  `PaymentsToAcquirePropertyPlantAndEquipment` for its
  issuer-specific spending component. Its reported FCF
  margin is approximately 1.07%, below the predeclared
  5% threshold. This is **not** a proof of identical
  accounting comparability with the PP&E metric other
  issuers use, and is not a prediction that Amazon will
  underperform. Changes in accounting meaning may be
  substantial across industries.
* GOOGL, PG and KO annual revenue uses the US-GAAP
  `Revenues` concept within each issuer's same current
  original annual filing. This avoids mixing GAAP
  revenue tags across reported years at a given
  research date; it does not create a historical
  point-in-time analyst data vintage.
* XOM and JNJ still lack a matching latest original
  annual `OperatingIncomeLoss` fact for both years.
  **NO score** is the correct decision. Replacing
  operating income with pre-tax earnings would change
  the model's meaning and is expressly prohibited.

## Promotion decision

**P4E remains research-only; no PAPER or LIVE promotion.**

Six descriptive quality scores on **eight hand-picked
2026 surviving large-cap companies** do not establish
investable alpha or broad US stock universe results.
There is no independent forward price-performance window,
survivorship/delisting-safe market database, analyst EPS
estimates revision source, trading spread/slippage analysis,
stock-event risk or capital permission.

Next milestones: validate issuer SEC cash-flow labels with
actual 10-K footnotes, source properly timestamped
analyst estimates, and build an unbiased security master
before stock ranker research. Keep original individual
stock symbols out of LIVE and PAPER.

Existing V5 ETF PAPER pilot and commodity forward
comparison unchanged. LIVE operator STOPPED, kill switch
ENGAGED, HIGH risk and $130.30 pilot ceiling unchanged.
