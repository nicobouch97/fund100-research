# V6-E1 — active post-earnings price-reaction hypothesis, source audit v1

**Preregistered 17 October 2026. Research only. No authority to sell current holdings or buy stocks.**

## Distinct economic hypothesis

An earnings announcement sometimes contains persistent information about
future results. Investor processing can be gradual, potentially creating
post-earnings-announcement drift (PEAD), but the effect is not a free
profit stream. Our V6-E1 hypothesis is **NOT** earnings-consensus surprise,
because the original analyst consensus feed is absent. It is a
**documented SEC Item 2.02 earnings-catalyst, followed by actual
benchmark-relative price confirmation**, tested with a deliberate
information lag.

Prior research that informed the fixed first screen:
- Ng, Rusticus & Verdi (2008), *Journal of Accounting Research*:
  https://doi.org/10.1111/j.1475-679X.2008.00290.x.
  Trading frictions can materially reduce PEAD profits.
- Chordia, Goyal, Sadka, Sadka & Shivakumar (2009),
  *Financial Analysts Journal*, "Liquidity and the
  Post-Earnings-Announcement Drift":
  https://rpc.cfainstitute.org/research/financial-analysts-journal/2009/liquidity-and-the-post-earnings-announcement-drift.
  Reported historical paper profits can be substantially offset by
  the illiquidity that helps produce the anomaly.
- SEC official public API guide:
  https://www.sec.gov/search-filings/edgar-application-programming-interfaces.
  EDGAR 8-K Item 2.02 identifies release of results of operations,
  not an analyst surprise or a recommendation. The SEC API has no
  authenticated record of initial public dissemination time.
- Recent research disputes the independent risk-adjusted persistence
  of some post-announcement drift. Therefore a robust positive alpha
  claim is NOT established.

## Frozen first-event source design

1. **Source SEC original bytes:** only the eight companies from the
   previously verified authentic P4B 15 October 2026 acquisition
   (run 38756477914, 16 original files); SEC issuer CIK, source URLs,
   file lengths, SHA256, named cohort and original acquisition time
   must all reconcile to the actual archived source.
2. **Source price original bytes:** first genuine independent P4G
   vendor-adjusted close acquisition from run 39015519726 (17 October
   2026). Hash and canonical CSV bytes must reconcile to the original
   timestamped snapshot. These are revisable adjusted public vendor
   closes, NOT independently authenticated trading vintages.
3. **Catalyst:** unique genuine SEC 8-K, NOT 8-K/A or 10-Q; event
   includes exact Item 2.02 in the *original* issuer SEC recent
   submissions. If SEC source was captured prior to a future filing,
   it cannot be used to claim the event. No hypothetical analyst EPS
   surprise, no fabricated real-time dissemination timestamp.
4. **Event eligibility:** filing date must be 15 October 2026 or later
   (P4E quality source has only that 2026 vintage); at least **TWO
   completed US stock market sessions strictly after the filing date**
   are needed; the SEC acquisition must already include the filing
   and the price source must be acquired after the second subsequent
   close. Never compute a signal from same-day after-close data and
   pretend you could have bought earlier.
5. **Preliminary price-confirmation filter:** close before filing to
   second completed close after filing, adjusted stock minus SPY return
   must be **+2 percentage points or better**; no source interpolation.
   Only P4E contemporaneous quality ≥2 is a source-coverage gate.
   File event must be no more than 10 completed subsequent sessions old.
   No quantity of strong price reactions is automatically profitable.
   Produce maximum FOUR distinct issuer descriptive research watchlist
   entries, each with hypothetical future position ceiling 25%.
6. **No actual holdings/returns simulated:** there is currently no
   genuine verified future post-entry holding-period return, no
   bid/ask/volume or guaranteed event open tradability, and only six
   known issuer quality scores among eight contemporary survivor
   companies. Do not rank old 8-K filings as if 2026 quality existed
   years earlier. The sample is tiny, highly biased and inadequate for
   claimed alpha or deployment.
7. **Cost criteria for subsequent strategy research:** genuine
   prospective post-entry returns measured net of 5/15/35bps per
   traded side plus a separately documented source for market spreads,
   minimum order size, and broker-specific fractional stock fills.
   Fees, margin, FX, tax and market impact are not implicitly free.
   A 2% observed relative pre-entry move is NOT a realised return.
8. **Potential future execution spec only:** at most 4 distinct long
   individual stocks, ≤25% total restricted account NAV each, no
   borrow/leverage, 20 trading-session maximum hold after verifiable
   next-session execution, no overlapping doubled signal budget,
   explicit monitor/STOP response; *requires separate independent
   return evidence and source/limit/order-engine version* before
   becoming even a PAPER or LIVE trade plan. Stop losses cannot
   guarantee price in a gap.

## Actual first external evidence

The two original archived observations are independently sourced:
- [Actual eight-company SEC first original acquisition](https://github.com/nicobouch97/fund100-research/actions/runs/38756477914)
- [Actual post-freeze first stock price acquisition](https://github.com/nicobouch97/fund100-research/actions/runs/39015519726)

The automated cross-source verification in
\`.github/workflows/fund100-v6-e1-real-catalyst-source-audit.yml\`
uses existing GitHub Actions artifact access with **read-only**
\`GITHUB_TOKEN\` permissions; it does not use SEC credentials,
Alpaca credentials or write permissions. A completed signal may
correctly be **EMPTY**: we will not fabricate events to create trades.

This is a **new and economically different research avenue** from
the rejected V6-R1 weekly ETF turnover strategy. However, it is
not already a validated high-return strategy. P4F analyst estimates,
a delisting-safe historic security master, and volume/spread provenance
remain missing.

## Required LIVE transition boundary

Original four Alpaca V5 ETF positions still invested; no sale
instruction has been given. Keep \`trading_enabled=false\`,
broker kill switch ENGAGED, HIGH risk and **$130.30** maximum pilot
capital. Current brokerage LIVE whitelist remains ETF-only.
Neither V6-E1 nor its audit workflow can issue a permit, broker
order, or unilateral approval. Any V5 liquidation and any
individually authorised V6-E1 stock buys require a **new explicit
operator decision**, separate source/risk and writer release plus
fresh broker holdings/cash/order reconciliation.
