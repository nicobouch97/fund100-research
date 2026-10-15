# Fund-100 Phase 3 — C3 actual WTI term-structure data protocol

**Date fixed:** 15 October 2026
**Status:** RESEARCH-ONLY / data-science milestone, not a new trading candidate.

## Real instrument exposure, not synthetic carry

DBC is a futures-based commodity investment, not a spot basket. Its
DBIQ Optimum Yield Diversified Commodity Index underwent a
**methodology change effective 10 November 2025** (new expanded
selection, eligible futures liquidity checks and weight management).
Under the updated methodology, broad basket, contract selection and
rolling mechanics are material. Historical DBC adjusted-share returns
already reflect its actual fund-level exposure and costs; do NOT
double count the futures-roll effect as a second expense.

Sources:
- Official Invesco DBC product information:
  https://www.invesco.com/us/en/financial-products/etfs/invesco-db-commodity-index-tracking-fund.html
- Invesco DBC 2026 10-Q (index constituent/method descriptions):
  https://www.sec.gov/Archives/edgar/data/1328237/000119312526338697/dbc-20260630.htm
- EIA WTI contract-one public source:
  https://www.eia.gov/dnav/pet/hist/rclc1m.htm
- EIA WTI contract-two public source:
  https://www.eia.gov/dnav/pet/hist/rclc2A.htm
- EIA NYMEX historical feed:
  https://www.eia.gov/opendata/browser/petroleum/pri/fut

## Phase C3A: bounded WTI contract-rank observation

EIA's free historical NYMEX futures feed supplies contract-one
`RCLC1` and contract-two `RCLC2` daily prices, BUT **futures
prices after 5 April 2024 are unavailable from EIA**. These are
*continuously-ranked* near-contract observations; EIA's ranking
records are not individually identified monthly expiry contracts
or documented DBC basket weights.

We can truthfully measure only:

- `RCLC1 > RCLC2` when both prices positive: observed WTI
  *backwardation* in this two-ranked-contract proxy.
- `RCLC1 < RCLC2` when both prices positive: observed WTI
  *contango* in this proxy.
- Price difference `RCLC1 - RCLC2` (dollars per barrel) and
  normalized `RCLC1 / RCLC2 - 1` for positive quotes only.
- For any zero or negative quote, retain the actual dollar spread
  but explicitly classify the relative-price feature as **invalid**.
  Negative WTI front-month settlements occurred in 2020; treating
  all prices as positive would silently drop a major stress event.
- Describe monthly median historical relative spreads and usable
  sample counts as empirical features only.

**Do not annualize this ratio as an earned futures yield:** ranked
maturities change during expiry/roll and timestamps/maturity
identifiers are missing. Spread changes do not equal a realized
roll-P&L. This WTI-only proxy cannot be represented as DBC's
diversified commodity basket, and the data cannot be extended
to 2026 by extrapolation.

The public EIA API download is optional and may fail due to public
source restrictions. Report an unavailable source honestly rather
than fabricating prices. Require a complete page count and exact
observation/source tags; pair same-date RCLC1/RCLC2 only,
never forward fill gaps; all data source hashes stored.

An `observation_date + 2 US WEEKDAYS` assumed available date is
a research latency **proxy**, NOT validated release times or
ALFRED-style real-time data. Vendor histories may be revised.

## Phase C3B: what we must acquire BEFORE actual DBC carry testing

The next hypothesis requires **licensed or authenticated dated
per-contract futures term structure** with:

1. Specific commodity, exchange, contract month and expiry dates
   (not nearby contract rank only).
2. Settlement publication timestamp and revision/vintage provenance.
3. Adequate volume/open interest; tradability and contract-selection
   constraints, including the November 2025 methodology change.
4. Contemporaneous DBC index constituent weights, contract roll
   schedules, cash collateral/T-bill income and fund-level ETP tracking.
5. Purchase/roll slippage, funding, mark-to-market and no-leverage
   portfolio risk budgets.

Only then can a separate preregistered hypothesis compute
date-available implied carry or realized futures P&L and test
correlations to DBC share returns. It MUST compare after costs
against static GLD/DBC/SHY, SHY alone, C1/C2 and realistic portfolio
stress exposures using a fresh prospective evaluation set.

The existing hash-chained daily prospective C1/C2/static scorecard
remains separate and unchanged; C3 is not silently added to it.
**No order APIs, paper permits, LIVE allowlisting, leverage, or
change to the user's HIGH risk setting and $130.30 LIVE pilot cap.**
