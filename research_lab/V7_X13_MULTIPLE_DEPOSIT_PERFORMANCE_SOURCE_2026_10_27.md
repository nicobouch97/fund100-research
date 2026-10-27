# V7 X13 — actual broker cash contributions must not be reported as investment return

**Registered 27 October 2026.** User expects to fund the pilot above
the original USD130.30 capital authorisation eventually and wants
scalable fully autonomous management. This is **read-only performance-
provenance groundwork**, NOT authorisation to increase the pilot,
rebalance ACWI, or trade. Original operator STOP / kill remain ENGAGED.

## Proven original-source limitation

Existing original LIVE seven-GET diagnostics retrieve the approved
private account, positions, open orders, market clock, one-month 1D
portfolio NAV series, nontrade-activity page (from 2026-09-01) and
the second cashflow_types=NONE broker historical P&L shape. The account
cash transfers have been observed with *date-only* booking and no
independently authenticated intra-day economic timestamp. Neither
Alpaca account gross equity nor cashflow_types=NONE has yet passed an
independent fully flow-neutral performance reconciliation. X7's flow-
neutral benchmark experiment therefore remains SYNTHETIC only.

The already established one-external-flow HIGH risk sensitivity is
deliberately narrow. New capital may produce two or more CSD/CSW
transfers and cannot be treated as asset-selection profit.

## Fixed new approach

Reuse the original **seven private GET results in memory, no extra GET**.
Validate the signed known CSD/CSW and all other nontrade activity
types, unique IDs, bounded page, query start covering the sampled NAV
history, finite positive brokerage 1D marks and reconciliation
between the last original mark and original account.last_equity.

For **any count of external contributions and withdrawals**, find the
latest source BOOKING calendar date D. Do not infer the real
transaction/settlement timestamp from that date; exclude all sampled
NAV marks until the first daily source observation on or after D+2
calendar days. Even then require six consecutive positive daily
observations without another external transfer, a recent marked
broker close and no unexplained >25% daily NAV discontinuity.
Evaluate return-path drawdown, worst daily loss, realized volatility
*only within this post-transfer interval* in memory. Do not inspect
pre-transfer growth as fund profit and do not create a one-time
cashflow adjusted performance claim. Reject unknown transfer types,
100-row incomplete source, missing dates, stale account closes and
insufficient post-transfer history. A subsequent new deposit will
automatically restart the descriptive observation window rather than
introduce a fake gain.

Only categorical risk/source statuses and a coarsely bucketed interval
count may leave private memory. No account balances, NAV history,
transfer amounts/IDs/dates, precise returns or source broker
credentials are persisted or output. Both potential source pass and
observed risk breach leave historical account-level STOP **latched**.
Previously observed hard risk losses cannot be erased by restarting
after a new deposit.

## What this is NOT

- Not exact lifetime true time-weighted return, X7 benchmark comparison,
  independent return forecast, a funded strategy performance scorecard,
  certified broker fill data, or annual audited fund returns.
- Not a new HIGH 6/20/35 account-risk clearance; original V6 seven-GET
  staging and independent signed ledger/settlement requirements
  remain binding.
- Not proof that deposits or sale proceeds are currently settled cash.
- Not a new LIVE reader, brokerage call or open trading permission.
  A future authorised £1k deposit requires its own broker verification
  and explicitly increased capital authorisation. Original pilot
  ceiling remains **USD130.30** until that occurs.

This bounded capability belongs within the *existing* protected
read-only seven-GET source path; there is no need to introduce a new
credential-bearing workflow or clone the broker API code. Offline
tests use fictitious numbers and test that private values never leak.
