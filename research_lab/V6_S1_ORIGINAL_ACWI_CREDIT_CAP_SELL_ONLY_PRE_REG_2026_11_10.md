# Original ACWI SELL-only credit-cap separation — 10 November 2026

## Observed blocker

On 9 November the protected original eight-GET replay reported authentic
three-month pre-funding history, full funded NYSE sessions and clean 6/20/35
**research-only** source observations, but the pure ACTIVE first-sell replay
held on the old $130.30 gross CSD cap. The independent protected funding
reader classified gross CSD credits as above the pilot attribution cap and
explicitly did **not** authenticate owner-contributed principal; returned
withdrawals and returned deposits can affect CSD/CSW. These findings are
categorical only. They do not prove a new user deposit or an active mandate.

## Narrow proposed eligibility refinement

The initial full-quantity **ACWI SELL of the originally authenticated,
unchanged holding** is exposure reducing, not a purchase or an instruction
to invest additional funds. The future ACTIVE SELL pure evaluator retains
the account ID binding, four original immutable fill quantities, active
unblocked cash-only account, empty current order set, verified open market,
single positive CSD source, genuine signed original intent, same-process
eight broker GETs, reconciled equity, complete funded NYSE sessions,
authenticated original 1M/3M history and strict funded-era 6/20/35 checks.

This candidate stops treating gross one-time CSD credit above the *new
purchase principal* limit as an independent block to reducing the
already-held original ACWI shares. It returns an explicit source flag
recording credit above original cap. It cannot use the CSD amount to size
the order, grant new BUY principal, lift $130.30 or $65 standing limits,
settle a sale, reinvest proceeds, or activate any branch/workflow.

Any CSD count change, zero/negative/non-finite credit, missing original
holding, account/risk change, 1M/3M mismatch, incomplete XNYS source,
unverified current operator, STOP or lost broker acknowledgment still
HOLDs. Actual new capital remains **nonspendable** until a separate
authenticated and signed owner-principal mandate and settlement
verification. A historical paper/real P&L win is not a substitute.

## Deployment and tests

This is **only a candidate source semantics change** in
fund100_v6_s1_active_high_acwi_sell_risk_v2_0.py. That module remains
ACTIVE_HIGH_SELL_SOURCE_RELEASED=False; owner CAS, immutable release,
broker POST and scheduled one-attempt entry all remain locked. The
credentialless tests assert an above-cap CSD cannot expand buy
permissions and an invalid/multiple source is still rejected. It
requires full LIVE audit and independent production source review
before any separate live activation. This PR must not be used to
interpret gross account cashflow as proof of contributed principal.
