# Fund-100 V2: isolated research universe screen

Status: **research-only, disconnected from execution**. This directory must not read Alpaca credentials, access a trading account, create orders, change the V5 baseline, or define LIVE risk permissions.

## First deliverable

`universe.py` accepts a caller-supplied sequence of dated instrument observations and returns:
- a reproducible and liquidity-ranked set of equity/ETF **research candidates**
- explicit rejection reasons for non-tradable, insufficient-history, stale, future-dated, low-liquidity, low-price, and wide-spread observations
- a deterministic SHA256 audit fingerprint of the selection and research policy

No ticker list is frozen. The caller supplies candidate assets; the code applies the policy on each call. The default screen is equities and ETFs **only**, excluding crypto, options, futures, shorts, and non-equity spot assets. An asset's `tradable` research input is not proof of availability in the specific live Alpaca account or jurisdiction.

## Research-only default screens

Minimum 252 historical sessions, USD price at least $5, average 20-day dollar volume at least $5 million, quoted spread at most 40 basis points, observed snapshot at most five **calendar** days old, and the top 250 passing symbols by dollar volume. These are *exploratory universe defaults*, not LIVE exposure, risk or order bounds.

## Critical data and risk limitations

1. **No data provider implemented.** This module receives observations, not a broker-feed request. To avoid survivorship and lookahead bias, V2 needs a historical point-in-time constituent/eligibility data source, delisting records, date-aligned volume/spreads, and adjusted OHLCV data. Merely setting `observed_on` cannot make a present-day asset catalog historically unbiased.
2. **No alpha model.** Selection by liquidity is not a buy/sell signal. No backtest, fees/slippage calibration, market regimes, factor scoring, or walk-forward selection is claimed.
3. **No execution.** No trading permissions, portfolio weights, position sizing, stop losses, or orders are emitted. Any future LIVE eligibility must be checked with contemporaneous broker asset permissions and operator-approved risk bounds.
4. **Crypto remains a separate research workstream.** Venue, session/calendar, min notional and spread/market-depth semantics are different; 24/7 crypto is not supported by the current equity scheduler.
5. **No V5 coupling.** V5 production, its kill switch, locked capital ceiling and release process remain entirely unchanged.

## Next build gates

Source verified point-in-time US-equity/ETF membership and price/volume data; connect a *read-only research adapter*; measure data freshness and coverage; introduce signal families; run survivorship-aware walk-forward tests with realistic costs; then design a Master Risk Engine and shadow comparison. Paper and LIVE are separate later approval gates.
