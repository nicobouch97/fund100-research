# Fund-100: separating original ETF inventory from excess account deposits

9 November 2026 | Original pilot provenance decision, research only.

## Verified observations

The new protected main-only read-only Alpaca funding-history job succeeded:
https://github.com/nicobouch97/fund100-research/actions/runs/42679295396

Its deliberately redacted public status was
OBSERVED_GROSS_FUNDING_ABOVE_ORIGINAL_PILOT_HOLD.
It examined 3 nontrade activities on 1 page and used only 3 GET requests;
it made zero writes/orders. Source coverage from actual inception, cash
settlement and the private signed ledger remain unverified. No raw USD
deposits, broker identities or quantities are published.

The ORIGINAL V5 bootstrap document contains four FILLED original ETF orders
(ACWI, EEM, XLE and XLV). The original pilot source still independently
requires a $130.30 cap and **additional_deposits_automatically_usable=false**.
This change checks the precise fill face-cost sum (filled shares * filled
average price) against the original cap WITHOUT treating any excess
broker deposit as spendable or increasing the mandate. It also verifies
in synthetic fixtures that the exact original positions and quantities
remain unchanged, the origin/account binding agrees and there are no
pending broker orders.

## Economic distinction

A current account that has more than $130.30 contributed cash need not
imply the *original four historically bought ETF lots* cost >$130.30.
For a strictly risk-reducing SELL of authenticated ORIGINAL ETF shares,
a bounded inventory-based permission **might eventually** be possible
without using any surplus cash or increasing original pilot authority.

But historical fill face-cost alone is not evidence of who funded which
shares inside the omnibus account, and price*quantity omits independent
fees, tax, corporate actions and cash movements. A live SELL is NOT
automatically permitted by this comparison. The first ACWI active writer
still requires authenticated funding, HIGH 6/20/35 risk and all signed
attempt/recovery safeguards; no change to that code is in this PR.

The research-only stage:
RESEARCH_ONLY_ORIGINAL_FILLED_INVENTORY_WITHIN_CAP_NO_CASH_ATTRIBUTION
means exactly that. It does not mean any excess cash was quarantined,
any position or cash settlement was validated live, or any permission
was granted.

## Production completion path

1. Authenticated, time-consistent original account current shares,
   open orders, and all deposit/corporate action/cash funding records
   from inception. Don't combine separate stale public summaries
   into a source of live authorisation.
2. A true original-asset and cashflow provenance ledger with exact
   HMAC/CAS signed private state and independently immutable/anti-rollback
   revision history. Do not label fungible extra cash as isolated without
   a defensible, reconcilable attribution rule and matching account totals.
3. Conservative sale-only source rule: a risk-reducing original inventory
   disposal could be considered within existing mandate if separately
   qualified; it must never authorise any new BUY or use surplus funding.
4. A distinctly approved future standing capital envelope can allow
   qualified future USD settled deposits, corresponding GBP conversion
   and NAV-based sizing without repeated user confirmations. That
   production scope is NOT yet authorised, signed or live.

Current $130.30 cumulative pilot cap, $65 max new purchase/partial sale,
operator STOP, broker kill ENGAGED and all active SELL/BUY locks unchanged.
