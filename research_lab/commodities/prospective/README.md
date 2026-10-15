# Fund-100 commodities — Prospective shadow scorecard v1

**Research only. No Alpaca broker, PAPER orders, LIVE trading, capital
allocation, automatic strategy promotion or permission to change the
original 14-ETF LIVE whitelist.**

## Why record forward observations

The historical 2020–2026 period has already been reviewed while
developing C1 (commodity trend) and C2 (gold real yields / DBC inflation).
It cannot be reused as a fresh untouched holdout. The capped static
GLD20/DBC15/SHY65 reference outperformed both active candidates
historically. The right next experiment is to compare **future observed
sessions** under those ALREADY fixed rules without retroactive refitting.

**Models observed:**
- SHY buy-and-hold short-Treasury ETF benchmark; not cash
- static 20% GLD / 15% DBC / 65% SHY (monthly reference targets)
- C1: unchanged six-month GLD/DBC momentum and volatility rules
- C2: unchanged physical gold real-yield/credit-stress rules and DBC
  breakeven-plus-price inflation gate

The study records a single completed public vendor-adjusted ETF share
close per observation date, SHA256 digests for the downloaded historical
lookback prices and FRED macro input, assumed-publication caveats, model
weights/NAV, costs, SPY/SHY benchmark NAV, research git run ID and a
tamper-detecting SHA256 link to each previous record.

Each new observation's realized close-to-close return is calculated
from the **previously committed close snapshot** and the *new* snapshot,
so later downloaded adjustments cannot silently revise earlier
prospective model NAV. At first observation all models start at 100
notional research NAV in SHY; results *begin only after that date*.
When a month changes, a signal from data available through the
previous completed session is applied at the new session close.
Charge **15 basis points per side**, on absolute total portfolio
weight turnover including funding legs. Hypothetical future public
ETF adjusted closing prices do not guarantee actual execution prices.

## Anti-hindsight constraints

- Never backfill a missed market observation from a present-day history.
  If latest vendor close is not the next trading session after the
  previous committed date, **the workflow fails and requires a manual
  record-integrity review**. Market holidays are naturally supported.
- Never revise existing entries. Repeated jobs on the same session are
  idempotent and do not recompute past NAV. Every appended record binds
  the prior record's SHA256 digest.
- Plausibility checks stop on daily snapshot-to-snapshot changes >25%;
  this is a data-quality circuit-breaker, NOT a loss cap or market hedge.
- The public FRED macro source is still vendor-revised, and 'observation
  +2 weekdays' is an *assumed* availability lag, NOT true ALFRED
  historical vintage/release evidence. Real-time daily macro snapshots
  are recorded by digest but the raw lookback macro histories are not
  stored permanently. Claim only **prospective observational evidence
  with known data limitations**.
- Rebalancing, slippage, spreads, fund roll effects, liquidity and
  taxes remain hypothetical. A future positive forward history alone
  does not grant even PAPER broker authority.
- No model can modify its own frozen logic, tune to the prospective
  ledger, authorize trades, rank itself as LIVE approved or allocate
  the user's actual capital.

## How it runs

`.github/workflows/fund100-commodity-forward-shadow.yml`
uses the repository's read/write permission solely to append an
observation to
`research_lab/commodities/prospective/observations.jsonl`;
**no secrets or trading environment** are provisioned. It runs each
weekday morning UTC after the *prior* US market close, and once on
initial workflow merge. It requires repository identity and
`refs/heads/main`, tests the anti-backfill invariants, fetches
public GLD/DBC/SHY/SPY and FRED DFII10/T10YIE/BAA10Y, and pushes
only the prospective ledger if a new bar is available. A missed run
causes a safely failed job rather than silently rewriting returns.

The initial snapshot is **not a fill or trade** and yields no
prospective performance. Compare the models after enough real
time-stamped observations accumulate; require a new independent
evidence set, portfolio diversification, liquidity and a real
broker PAPER qualification before even proposing LIVE expansion.
