# Phase 4G — forward-only US stock SEC quality x momentum observer

Frozen on 15 October 2026 before first eligible close. RESEARCH ONLY; no stock orders.

## Provenance and motivation

P4E checked real SEC eight-issuer source archives in GitHub Actions 38756477914. First eight-company capture: 2026-10-15T15:01:45Z. Original SEC source manifest SHA256:
bafc7a084a6d4deaf7c7b7a5e982d52a8b5ecd6fe1b70a0ebaf3e64a610b1e18.

P4E individual issuer/accounting mapping review: GitHub Actions 38760165063. Frozen October 2026 descriptive scores: AAPL=3, MSFT=3, GOOGL=3, AMZN=2, PG=3, KO=3; XOM=UNKNOWN and JNJ=UNKNOWN. Company-specific reported GAAP tags are NOT standardised sector-neutral predictors. The 2026 quality state was NOT available in 2015. P4F separate vendor-analyst revision source is still absent. Do not fabricate it from SEC or momentum.

## Preregistered candidate and prospective comparison

1. Use exactly AAPL MSFT GOOGL AMZN XOM JNJ PG KO and read-only benchmarks SPY SHY. Yahoo Finance/yfinance vendor-adjusted daily closes are convenient but revisable. No price-vintage or dividend/delisting authority is claimed. Include all ten symbols, no missing interior sessions or interpolation; preserve canonical original research input and SHA256 at each capture.
2. Earliest eligible completed stock session 15 October 2026; capture must be on a following UTC calendar date no more than five days later. Require at least 127 complete historical sessions. Older price series supply lookback context ONLY, never a historical stock backtest with current quality.
3. To qualify for a **descriptive** watchlist a ticker must have known P4E quality >=2/3, trailing 126-session adjusted-close return >0 and trailing 63-session adjusted-close return minus SPY 63-session adjusted-close return >0. Rank descending by 63-session SPY-relative return, alphabetical ticker on ties. Retain at most three; zero matches is a valid empty watchlist. Do not treat this list as a buy allocation.
4. Future independent comparison cohorts: six firms with existing 2026 P4E quality, equal-weight reference, SPY benchmark and optional SHY cash proxy. The first watchlist snapshot has zero future performance observations. A separate later forward ledger must measure subsequent *new* sessions with turnover/slippage and corporate action concerns; prior downloaded bars are never measured as post-freeze returns.
5. No threshold optimisation on already explored history; change hypothesis only by versioned protocol and future independent comparison. No trader rights may be inferred from watched tickers, source completeness or a favorable scorecard.

## Actual operation

A GitHub Actions workflow runs synthetic offline negative tests on commits/PRs; with schedule 03:30 UTC Tuesday-Saturday (following US Monday-Friday closes) or explicit dispatch, fetches public close data and archives the input CSV plus descriptive JSON in a 90-day artifact. If the provider is down, source format is wrong, holiday means stale data or timestamps are uncertain, it can fail without inventing prices. Repeated last-session snapshots do not count as extra prospective sessions. Archive source artifacts durably before 90-day expiry; there is no append-only forward return ledger yet.

No yfinance brokerage access, Alpaca secrets, SEC identity secret, order capability or live environment is used.

Original ETF-only LIVE boundary remains: operator STOPPED, kill switch ENGAGED, HIGH risk profile, USD 130.30 maximum pilot authorisation, frozen 14 approved equity ETFs; V5 real Alpaca PAPER automation independent. No stock PAPER/LIVE, no licensed analyst feed, no historical survivorship/delisting safe evidence.

Next meaningful research step: from two or more distinct prospective captures, build explicit hash-linked forward cost-adjusted return comparisons versus equal-weight six-name basket and SPY/SHY, not fake retrospective validation. Seek real delisting-inclusive security master and Phase4F genuine source rights in parallel; continue commodity forward research independently.