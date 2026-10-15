# Phase 3 C3B — Contract-level futures dataset acceptance (15 October 2026)

**Status: SOURCE SCHEMA READY / NO REAL SETTLEMENT DATA RECEIVED / NO TRADING SIGNAL.**

## What changed since C3A

The public EIA WTI nearby-contract series returned HTTP 403 in the
GitHub runner and ends historically on 5 April 2024. Even if accessible,
rank-one and rank-two futures do not establish a contract expiry or
DBC's constituent selection, trading costs or realized rolling P&L.

C3B has a stricter, **provider-neutral** importer requiring exchange,
specific futures contract IDs, delivery/expiry dates, an observation
session, timestamp of publication, timestamp of capture, quote units
and volume/open interest. It measures only the contemporaneous
near/far futures settlement spread and an explicitly labelled
**annualised log price-curve slope**. That slope is NOT the expected or
earned return of a holding or roll, and it is NOT DBC's actual index
roll profit.

An explicit SHA256-bound manifest identifies provider, source URL,
rights to process historical data and actual dataset acquisition
timestamp. Manifest claims alone never constitute independent
verification of historical release vintages. Quotes for expired
contracts, missing expiries, mismatched exchange units, contracts
with shifting identities, duplicate revisions, unavailable timestamps
and fake negative-price logarithms fail closed. Negative settlement
prices remain intact in the raw input and produce only absolute
price differences.

The importer currently supports commodity/product identities for
NYMEX crude oil CL, natural gas NG; COMEX gold GC, copper HG; and
CBOT corn ZC. Adding any further commodity requires a reviewed
exchange-specific unit and contract specification; it is **not** an
authorization to trade it.

## Source options assessed

| Possible input | Documented access | Can satisfy C3B today? |
|---|---|---|
| **CME website daily settlement pages** | CME says displayed settlement quotes become freely viewable after midnight Central Time | Potential source of *future snapshots*, but no validated machine interface or historical archive acquired; do not imply licensed redistribution |
| **CME DataMine contract settlements** | CME officially offers exchange futures settlement history with licensing/fees and contractual rights | Possible after licence, verified export mapping and affordability review |
| **CME official enhanced continuous energy price series** | Has contract expiry, roll switch and volume/open interest, but series is either *one* Active or *one* Front contract per time | Useful for mapping/roll research; cannot substitute for two simultaneous outright expiries unless both are truly distinct dated contracts |
| **CME delayed-snapshot settlement REST API** | OAuth, entitled API ID and Public Website (Delayed) Redistribution licence; recent settlement history seven days | Not an anonymous, zero-cost API |
| **US EIA NYMEX RCLC1/RCLC2** | Public historical feed discontinued April 2024; first Fund-100 request returned HTTP 403 | No |
| **DBC issuer disclosures** | Fund pages / SEC filings show product structure, annual index weighting and some periodic investments | Support historical composition/structure, not full daily underlying roll P&L by themselves |

Official source documentation:
- CME DataMine: https://www.cmegroup.com/datamine.html
- CME continuous price series: https://www.cmegroup.com/market-data/cme-group-continuous-price-series.html
- CME settlement FAQ: https://www.cmegroup.com/articles/faqs/access-to-cme-group-settlement-data-faq.html
- CME settlement API entitlement: https://cmegroupclientsite.atlassian.net/wiki/spaces/EPICSANDBOX/pages/1892122625/CME+Group+Public+Website+Distribution+REST+API
- DBC fund overview & documents: https://www.invesco.com/us/en/financial-products/etfs/invesco-db-commodity-index-tracking-fund.html

**Economic decision:** The LIVE Fund-100 pilot ceiling is $130.30 and
no commodity strategy is even PAPER-approved. Buying an expensive data
subscription now is not justified. No subscription or connector account
has been opened, and no credentials/charges were incurred. Keep forward
C1/C2/static research running on public ETF data as a parallel benchmark.

## Offline usage after legitimately acquiring a dataset

Supply a CSV file with EXACT columns:

```text
observation_date,published_at_utc,captured_at_utc,exchange_mic,product_code,contract_id,delivery_month,expiry_date,settlement_price,quote_unit,volume,open_interest
```

Every row must represent a **distinct exchange contract and real
dated settlement**. Do not invent a release timestamp or contract
expiry to pass the importer. Dates must be ISO YYYY-MM-DD; timestamps
must use `YYYY-MM-DDTHH:MM:SSZ` in UTC. Accepted `source_type` values:
`public_delayed`, `licensed_vendor`, `archived_exchange`.
Each acquired dataset must be paired with a manifest JSON with the
following exact keys:

```json
{
  "schema": "FUND100_C3B_IDENTIFIED_FUTURES_SETTLEMENTS_V1",
  "provider_name": "ACTUAL LICENSED OR PUBLIC PROVIDER",
  "source_type": "licensed_vendor",
  "source_url": "https://actual-provider.example/documentation",
  "data_license_note": "Actual applicable use and redistribution rights",
  "dataset_sha256": "actual 64-character SHA256 of the raw CSV bytes",
  "acquired_at_utc": "2026-10-15T16:00:00Z",
  "contract_expiries_source_note": "Actual market/product reference source",
  "data_release_verification": false,
  "dbc_index_constituent_weights_included": false
}
```

*The manifest above describes structure, not a real acquired dataset.*
For a genuine dataset, populate fields truthfully from actual
licence/provenance; `data_release_verification=true` is only a
provider claim, never a substitute for independent source auditing.

Run, **locally and offline only**, from the repository root:

```bash
python fund100_commodity_contract_curves_c3b_v1_0.py \
  --contracts-csv /private/licensed/identified_futures.csv \
  --source-manifest-json /private/licensed/provenance.json \
  --output-report-json /private/results/c3b-report.json \
  --output-pairs-csv /private/results/c3b-curve-pairs.csv
```

Do not commit or upload licensed raw data, provider credentials,
expiry-rights documents or source secrets to the repository; observe
licence terms for storage and output distribution.

## Next prerequisite before C3 trading research

1. Acquire a legally accessible dated set of actual specific
   futures contracts/expiry quotes. Confirm release timestamps and
   data coverage without using inaccessible EIA endpoints as fallback.
2. Separately acquire DBC's contemporaneous index constituents,
   actual selected contract expiry and roll method on both sides
   of the **10 November 2025** methodology change.
3. Verify exchange-specific contract multipliers, seasonal commodity
   effects, bid/ask spreads, implied curve relationship vs realized
   rolling P&L and collateral-yield treatment, *without* adding a
   second roll-fee deduction to historic DBC ETF adjusted closes.
4. Freeze a genuinely new strategy before comparing with the static
   GLD20/DBC15/SHY65 champion and collecting subsequent independent
   forward observations. No backtest or imported dataset can auto-promote
   a commodity symbol into V5 PAPER or LIVE.

**Trading controls remain unchanged:** original 14 US ETFs only in
LIVE permission universe, operator STOP, engaged kill switch, HIGH risk
selected, and $130.30 pilot ceiling.
