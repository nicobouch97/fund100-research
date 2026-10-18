# C9 — Direct futures are not a micro-pilot route; preserve an actionable universe

**18 October 2026, original Fund-100 LIVE controls read-only.**

## Decision-quality finding

Fund-100's legally authorised LIVE pilot capital ceiling is exactly
**USD $130.30** per checked-in original V5 policy. This ceiling is
**not** spendable cash: four existing LIVE V5 ETFs were purchased
on 5 October 2026, and LIVE operator is presently STOPPED.
This C9 workflow never contacts Alpaca, does not know today's
settled/unsettled available buying power, and cannot authorise
liquidation or new asset classes.

CME's official [WTI crude futures contract comparison]
(https://www.cmegroup.com/markets/energy/wti-crude-oil-futures.html)
published these *indicative* initial margins **as of 7 July 2026**:

| Direct futures contract | Size | Indicative initial margin (not customer's broker quote) | Margin / full authorised pilot |
| --- | ---: | ---: | ---: |
| CL physical-delivery WTI | 1,000 barrels | **$6,826** | 52.39× |
| QM E-mini WTI | 500 barrels | **$3,423** | 26.27× |
| MCL Micro WTI | 100 barrels | **$685** | 5.26× |

All margin estimates exceed the **entire account authorisation**;
that is before transaction costs, margin changes or drawdowns.
The original Fund-100 policy forbids leverage, derivatives and
futures. A CME margin estimate does not demonstrate any account's
futures permissions. MCL is financially settled, but it is still
too large, and the large CL contract has physical-delivery risk.

The CME public September 2026 website references a **future
10-barrel WTI contract** *pending regulatory approval*, so
we have **no proof it is live, available through Alpaca, or
within account margin limits**:
https://www.cmegroup.com/markets/energy/crude-oil/micro-wti-crude-oil.html

## Practical research-to-trading bridge

- **GLD, USO, SHY**: research-specific gold, oil-futures
  roll-exposed and short-duration bond ETFs. None is on the
  ORIGINAL 14-ETF LIVE allowlist. A positive model signal
  cannot be converted to a trade until the user explicitly
  approves new assets, a broker GET confirms availability
  and cash, and a new versioned order/risk policy is released.
  Fractions and minimum trade sizes also need account-specific checks.
- **XLE**: ALREADY on the original 14 ETF allowlist and part
  of V5 holdings. It is **energy company shares**, **not**
  CME WTI crude-oil or direct futures carry. It is not the
  equivalent of a futures yield instrument. Although on
  the whitelist, it is not a free order permit because
  STOP and capital constraints remain.
- **BTC/USD and ETH/USD**: crypto research only; original
  LIVE policy explicitly has crypto_allowed=false and
  has no account-specific permission. Their historical risk
  model V6-C1 did not achieve benchmark-return superiority.
- A different micro-fund could choose more capital, a
  new broker and leveraged futures, but those are outside
  the *current* Fund-100 authorisation and should not be
  proposed as a workaround.

## What this eliminates

Researching real CME expiry-specific curves is still valuable,
but we must **not** build a direct CL/MCL LIVE executor for a
$130.30 unleveraged account, and shouldn't pay for a long-history
CME subscription without a realistic instrument route.
Research priority now: source-real, **low-turnover signals**
whose intended small-notional expression is **actually supported
by the user's LIVE brokerage**, after rechecking fees, minimums,
available funds, and permission. The V5 sector ETF already
allowed to trade does not become the new strategy by default;
the user explicitly rejected a mostly passive ETF portfolio.

There is currently **no replacement V6 strategy with a
demonstrated, independently forward-validated positive net edge**.
Past retrospective returns and several rejected V6 candidates
must remain visible failures. We can proceed with live
strategy operation after a coherent approved hypothesis
and technical release, without waiting months for fictional
paper-performance profits, but not by claiming profits
we have not measured.

## Implementation

Offline source-backed feasibility script:
`fund100_microaccount_instrument_feasibility_c9_v1_0.py`,
plus repo-control mutation/permission tests and
`.github/workflows/fund100-c9-microaccount-feasibility.yml`.
The workflow reads only two **checked-in original policy
files**, hashes them, fails shut if ceiling/allowlist/STOP/
leverage permissions differ, compares the published CME
illustrative margins and marks all asset-class expansions
as unapproved. It neither reads LIVE credentials nor
places or plans orders.

Four live ETF holdings unsold, operator `trading_enabled=false`,
broker kill switch engaged at last audited state, HIGH user
risk selection and USD130.30 cap unchanged.
