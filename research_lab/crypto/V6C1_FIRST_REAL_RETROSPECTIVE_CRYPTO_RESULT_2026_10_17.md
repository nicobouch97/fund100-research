# V6-C1 — first authentic BTC/ETH public-price trend research

**17 October 2026 — predeclared first run complete. Decision:
DO NOT PROMOTE THIS V6-C1 VERSION TO LIVE.**

## Actual original public historical data and reproducible run

- Protocol frozen first:
  \`research_lab/crypto/V6C1_CRYPTO_24_7_TREND_PROTOCOL_2026_10_17.md\`.
- [Actual authenticated workflow execution run 39027912139](https://github.com/nicobouch97/fund100-research/actions/runs/39027912139).
- Original public Yahoo/yfinance BTC-USD / ETH-USD daily bar snapshot;
  original canonical CSV SHA256:
  \`ae796a3141a4fe52453af8aa83e879b95841dc28b11b4294b1e0f43077e9f22f\`.
  Source archives and exact capture UTC timestamp are retained in
  GitHub Actions artifact
  \`fund100-v6c1-original-btc-eth-cost-review\` for 90 days.
  The vendor source is **revisable**, not historical executable
  bid/ask quotes or independently certified acquisition vintage.
- **15** dedicated chronology/leveraging/cost/source fixture tests passed.
- Comparisons start 1 January 2020 after historical indicator warmup;
  the 2020–2022 and 2023–current splits are descriptive post-hoc
  *evaluation of a preregistered strategy* using published market
  history, **not truly unobserved future live tests**.
- Crypto figures are USD, not GBP; no real-world FX conversion,
  funding interest, tax, custodian fees or venue-specific execution
  price was authenticated. Cash earns 0%.

## Net descriptive historical results

The strategy combines slower positive absolute momentum,
BTC/ETH 180-day SMA gates, 30-day realized portfolio volatility
target 50%, conservative position size, an assumed Sunday-close
weekly rebalance and 5pp minimum target deviation.

Cost applied to **total gross BUY + SELL traded notional**, each
side 25/35/60bps. Lowest tier Alpaca quoted taker fee 25bps is
NOT a guaranteed all-in bid/ask+impact cost. 35/60bps stress
also may understate actual market cost.

**Full studied 2020–latest completed historical session:**

| Strategy | Historical annualised compound return | Historical maximum drawdown |
| --- | ---: | ---: |
| BTC-only buy-and-hold reference | **+42.9567%** | −76.6346% |
| Passive initial 65% BTC / 35% ETH buy-and-hold reference | **+47.2411%** | −76.9412% |
| V6-C1 at 25bps/side | **+30.8591%** | −48.3535% |
| V6-C1 at 35bps/side | **+30.0175%** | −48.4349% |
| V6-C1 at 60bps/side | **+27.9349%** | −48.6382% |

V6-C1 **lost materially versus both simple passive references on
annual compound return** across the same historical comparison.
It reduced maximum drawdown, partly by holding cash in unfavorable
regimes. But a roughly 48% historical drawdown is still extremely
large for an account. A historical CAGR is not an expected future
rate or a reliable forecast.

**Recent 2023–latest (35bps/side):** V6-C1 +29.6544%
annualized vs BTC passive +52.1256% and passive initial
65/35 BTC/ETH +32.8525%. V6-C1's maximum drawdown
was −33.2414% vs BTC −53.06% and passive blend −60.2447%
for the same subperiod.

Actual modeled V6-C1 annual **gross notional turnover** from 2020
onward was **6.43953 × NAV**, with 101 historical trade dates.
That EXCEEDS the preregistered **5 × NAV maximum**.
The strategy's proxy CAGR/max-drawdown ratio was slightly better
than BTC-only, but it did NOT pass the whole predeclared
economic viability gate.

## Why there is no LIVE crypto authorisation

Alpaca's official public documentation identifies BTC/USD and
ETH/USD trading, 24/7 order types and tiered fees, but we have NOT
verified user-specific account/jurisdiction permission, actual
asset availability or market spreads, available cash, live min order
quantities, or any existing executor able to enforce 24/7 risk.
The current LIVE Fund-100 14-ETF whitelist excludes crypto.
The historical source is Yahoo/yfinance revised daily closes,
not live Alpaca exchange order book prices or realizable fills.
The independent paper BTC/GBP synthetic bot is unrelated and
cannot be used to claim V6-C1 provenance or GBP results.

**Decision: V6-C1 is useful crash-risk evidence, NOT a strong active
return-excess winner for the operator's desired experiment; no
automatic promotion.** Do not adjust 180/63/30 SMA/return/vol
thresholds, Sunday schedule, 65/35 caps or 5pp trade band on this
same studied market period to manufacture a winning backtest.
Future distinct strategies require their own source and historical
precommitment. Continuing genuine commodity dated futures-carry
source acquisition is a stronger independent next-research direction;
meanwhile a low-turnover diversified active risk strategy could be
considered from independently preregistered future data.

**Existing LIVE portfolio unchanged:** four V5 ETFs not sold,
operator STOPPED, broker kill switch ENGAGED, HIGH risk,
USD130.30 maximum capital, no BTC/ETH orders.
