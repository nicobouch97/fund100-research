# C8 — CME original source freshness, provenance and $130 pilot feasibility

**18 October 2026; research only. No CME subscription, real orders, or ETF liquidation.**

## Why C8 was needed

C7 established that an original CME daily bulletin can be fetched without
Alpaca credentials, but on 17 October the exact CME PDF actually served
was marked **PRELIMINARY** for the Friday 16 October trading session
(Bulletin 200). C7 correctly rejected it. There is no verified
FINAL original futures curve from C7 to trade or backtest.

The [CME Daily Bulletin page](https://www.cmegroup.com/market-data/daily-bulletin.html)
states the *preliminary* bulletin updates at approximately **midnight
Central Time the next business day** and the **FINAL** update at
approximately **10 a.m. Central Time the next business day**.
For Friday 16 October, the **next US business day is Monday 19 October
2026**. Ten a.m. Chicago local time then corresponds to
**4 p.m. BST**, subject to exchange publication delays, US holidays,
unexpected maintenance and caching. Publication *schedule* is not
proof of the actual final document's existence.

A single Sunday retry will likely repeat the same preliminary.
It is unproductive to treat that failure as a market-data anomaly
or repeatedly scrape until a parser looks profitable.

## New C8 original-source state machine

Implementation:
`fund100_cme_source_state_c8_v1_0.py`.
Dedicated tests:
`test_fund100_cme_source_state_c8_v1_0.py`.
One-off original-source GitHub research workflow:
`.github/workflows/fund100-c8-cme-source-status.yml`.

- ONE original CME Section 61 GET with no-cache HTTP request headers,
  bounded byte length and request deadline. The header is an **attempted
  cache bypass**, not proof the CDN served a new publication.
- A deterministic original-byte **SHA256**, acquired-at UTC, printed
  date/status/bulletin number and explicit source-admission state are
  recorded whether the original was FINAL or PRELIMINARY.
- PRELIMINARY is rejected *before* any settlement/contract parsing,
  no market quote or derived curve is published from it. A rejected
  original PDF is NOT archived to GitHub. The SHA metadata remains
  useful to compare against a future repeated cached copy.
- An apparently FINAL original goes through all C7 tests
  (dated correct trading calendar, physical NYMEX CL source identity,
  named delivery-month contracts, >12 unique rows, reported TOTAL
  CL FUT OI reconciled to sum of individual maturities, plausible
  settlement bounds). Only then may its raw PDF and identified
  curve data be archived.
- A network failure leaves a truthful REJECT_SOURCE_UNAVAILABLE
  status with no original-body hash and no futures data. An invalid
  FINAL remains rejected. All branches have paper/live permission
  FALSE, zero orders and no liquidation authority.
- An accepted dated source is one **cross-sectional futures curve**,
  NOT net carry return, backtested alpha, independent release
  timestamp, or a verified fill quote.

This is not an unattended website scraper. The GitHub Actions
workflow is manually dispatchable or runs once when its dedicated
source-code PR changes; there is **no new scheduled recurring GET**.
Future repetitions require attention to CME data terms and should
not be used to work around paid entitlements.

## Genuine potential *free* CME data path, without assuming access

A [CME notice about daily-settlement publication]
(https://www.cmegroup.com/notices/electronic-trading/2024/03/20240304.html)
says daily settlement files moved from retired FTP endpoints
to CME **DataMine**, and that daily settlement files published
at midnight Central remain **available free of charge**.
This does **not** mean all historical files, API access,
automated redistribution or extended curve series are
free or available anonymously. The [official Historical
Daily Bulletin link](https://www.cmegroup.com/market-data/daily-bulletin.html)
leads into DataMine's catalog and may need registration or
separate entitlements. No account was created, payment made,
entitlement claimed, or historical settlement series obtained.

Before requesting any paid subscriptions, investigate official
free file entitlement and the ability to obtain **actual
dated contract months, expiry calendar and at least two successive
final observations**, with authentic timestamps and licence.
If login/approval/payment is required, ask the operator rather
than misrepresent it as accessible.

## Real-world instrument sizing / financial decision

Even if CME WTI futures term structure eventually exhibits a
historical carry anomaly, *physical-delivery* CL futures,
their margin/leverage, expiry handling and delivery risk are
not a feasible direct starting trade for the authorised
**USD $130.30 micro-pilot**. This is not an account permission,
and using **USO or DBC** to express a futures curve signal
introduces underlying roll/tracking divergences and expenses.
No assumption that a positive futures-curve slope earns
a positive ETF return is acceptable.

Candidate successor should be **low-turnover, capital-size viable,
with precommitted entry/exit and credible original public data**,
not another high-turnover retrospective fitted winner.
Previous V6-R1, V6-E2, V6-C1 and C6 candidate outcomes are
preserved as unsuccessful / unvalidated. No automatic LIVE
promotion.

**Existing real-money account unchanged:** four V5 ETF
positions intact, V5 operator STOPPED, broker kill switch
ENGAGED, selected risk HIGH, capital ceiling USD130.30 and
current 14-ETF LIVE authorisation intact.
