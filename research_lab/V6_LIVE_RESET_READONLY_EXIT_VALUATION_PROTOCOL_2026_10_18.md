# V6 real-money strategy migration: brokerless transition preview

**18 October 2026. No brokerage client, no LIVE orders, no liquidation.**

## Why this is not another strategy backtest

The operator's goal remains a genuinely active, concentrated and
potentially higher-return **real-money experiment**, not an ongoing
passive 14-ETF allocation. Fund-100 already has four REAL LIVE
filled positions purchased on **5 October 2026**: ACWI, EEM,
XLE and XLV. They consume the pilot's investment capital
and cannot be treated as available cash for new buys.

No V6 candidate has satisfied its precommitted economic gate
across relevant tested periods (V6-R1, post-earnings, V6-C1,
C6 and V6-R2). We must not market the favorable 2020–2026
R2 subset as a reliable independent alpha result, or make
the operator wait for months of simulated paper money before
offering a properly risk-disclosed hypothesis.

The live policy's **$130.30 is the maximum original authorised
capital**, not the current equity, available buying power,
cash balance or a promise that this amount can be deployed.
The original portfolio's October 5 fill prices, quantities
and equity calculations are HISTORICAL: a fresh read-only
account GET must establish the actual current securities,
quantities, cash, open orders, settlement status and quotes.

## Deliverable

`fund100_v6_brokerless_transition_preview_v1_0.py`,
`test_fund100_v6_brokerless_transition_preview_v1_0.py`,
`.github/workflows/fund100-v6-no-order-transition-preview.yml`.

The output JSON preserves SHA256 for the exact original
LIVE bootstrap, corresponding micro-pilot policy and
STOP operator control. It lists only those **historical
filled share quantities** and explicitly emits
`NO_FRESH_READ_ONLY_MARKS_NO_EXIT_VALUATION` and
null sale proceeds when no new genuine broker data
have been supplied. No current return, net liquidation
proceeds, deposit amount or basis gain/loss is
made up.

A deliberately separate pure `preview()` function
can accept a *caller-supplied* read-only GET-mark snapshot
to construct HYPOTHETICAL 5/15/35bps sell friction
values. It requires bounded freshness, four exact
original positions, matching original account binding,
no open orders, declared GET-only source and no
new broker orders. That schema is **not a proof of
authentication** merely because the caller sets a flag;
a future real GET-only broker integration must supply
cryptographically/source-traceable evidence, reviewed
account binding and actual quote timestamps before
any live planning. This code does NOT fetch quotes,
generate executable Alpaca orders or tell the operator
which V6 strategy to buy.

With no fresh broker marks available on Sunday,
18 Oct 2026, **no financial/current valuation
is computed**. In particular a hypothetical sale of
four fractional ETF positions does not guarantee
their proceeds can be immediately reused:
US brokerage account buying power, margin/cash
account status and T+1 equity cash settlement
and minimum order sizes must be confirmed on
the customer's actual account before re-entry.

## Separation of decisions and authority

A real V6 reset later requires in order:

1. A specific new strategy, economic/risk hypothesis,
   sized universe and written owner acceptance
   of possible total losses (not claims of guaranteed alpha).
2. A **fresh LIVE GET-only brokerage account** verification
   showing actual quantities, current marks and settled
   cash after accounting for any intervening deposits,
   transfers, dividends or corporate actions.
3. An explicit **separate operator authorisation
   to liquidate or modify** the current four LIVE
   investments, with anticipated taxes and spreads
   acknowledged and account holdings reconciled.
4. A new versioned LIVE risk policy covering the
   specific concentrated allocation, permitted securities,
   maximum loss and liquidation controls, plus correctly
   staged SELL and subsequently permitted BUY only
   after cash/settlement checks. The current HIGH
   setting does not automatically authorise the
   60%-single-ETF V6-R2 hypothetical concentration.
5. New broker-minimum/fractional support checks,
   kill-switch state read and separate order
   release. The original V5 automation must never
   silently trade in parallel with a new strategy.

CME source research meanwhile continues in parallel:
CME confirms ordinary daily settlement file publication
can be free after midnight CT, but its DataMine API
requires credentials and specific access entitlements.
The [CME Daily Bulletin dataset documentation]
(https://cmegroupclientsite.atlassian.net/wiki/spaces/EPICSANDBOX/pages/457420037)
states its available files are *top-of-day only* and
older daily files are overwritten on next generation.
Hence the rotating Section 61 file is NOT a historical
contract-level curve archive, even if each final
snapshot were immediately accessible. No data
purchase, account creation or unauthorised
archive scraping is approved.
Official:
https://www.cmegroup.com/datamine/datamine-api.html
https://www.cmegroup.com/notices/clearing/2023/09/Chadv23-272.html

**Current account status last known:** four original
V5 ETFs historically filled, operator STOPPED,
broker kill switch ENGAGED at last verified audit,
HIGH chosen profile, original USD130.30 cap.
Fresh present account state was NOT checked by
this purely offline research workflow.
