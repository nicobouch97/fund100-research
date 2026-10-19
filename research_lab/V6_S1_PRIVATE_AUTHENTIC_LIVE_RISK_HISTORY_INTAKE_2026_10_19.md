# V6-S1 — actual LIVE risk-history evidence intake; NO orders

**19 October 2026. Original research and API source contract locked before first authenticated five-GET study.**

This is the first V6 phase to **privately inspect actual LIVE account risk-history data**, after the genuine completed $2 Alpaca PAPER fractional BUY/SELL and the independently reconciled original four LIVE holdings. It does not release trade permissions, submit a SELL, switch investment strategy, or claim measurable alpha.

## Original source data, identity and limited API

Existing verified facts remain pinned:
- Genuine PAPER round trip with starting holdings restored: [run 39269640353](https://github.com/nicobouch97/fund100-research/actions/runs/39269640353), 19 Oct 14:31 UTC.
- Actual authenticated LIVE account original four holdings/zero orders: [run 39272813574](https://github.com/nicobouch97/fund100-research/actions/runs/39272813574), 19 Oct 14:52 UTC.
- Overlap-aware V6-S1 DRAFT v2: retain original XLE when compatible, hypothetical legacy exits only ACWI, EEM, XLV. Executable staged V6-S1 candidate controller remains disconnected [PR 65](https://github.com/nicobouch97/fund100-research/pull/65).

This observer runs only on exact repository **main** inside the already protected `fund100-live-broker` environment. It first requires original operator `trading_enabled=false`, remote GitHub main STOP, HIGH profile, broker kill `ENGAGED`, fresh GET-only arm and the existing correctly bound 2026 original live policy. It reads **exactly five endpoints**, in order:

1. `GET /v2/account`
2. `GET /v2/positions`
3. `GET /v2/orders?status=open&limit=100`
4. `GET /v2/clock`
5. `GET /v2/account/portfolio/history?period=1M&timeframe=1D`

The first four reuse the **previously successful exact-original-quantity V5 account authentication/reconciliation**. The fifth checks whether genuine broker **raw equity history** is available and passes the already versioned account loss/drawdown/realised-volatility *raw-history* validator at HIGH tier. The account API's `multiplier` field is inspected only as a boolean diagnostic for potential margin features; no margin use is authorised.

**Critical difference:** raw Alpaca daily account equity returns are **not necessarily cash-flow adjusted**. Prior deposits, withdrawals, account fees, late history publication, missing data and brokerage value interpretations may invalidate a raw return/volatility comparison. Therefore a successful raw history computation is NOT a V6 risk release. It does not prove trading-day continuous monitoring, a valid pre-trade 6% daily-loss/20% drawdown/35% volatility check, a corrected account cashflow ledger or an intrinsic value model.

**Cash settlement is NOT proven by `cash`, `buying_power` or `multiplier` fields alone.** No LIVE sells have occurred, so there can be no proven T+1 proceeds to spend. No quotes, executable ask prices, order history reconstruction or V6 write release are included in this job.

## Privacy and fail-closed contract

Do not print, save, upload or expose account IDs, share quantities, mark-to-market values, cash amounts, historic equity numbers or private broker error bodies. The source report uses booleans and closed vocabulary status, with `account_id=None`, `equity_usd=None`, `cash_usd=None`, `share_quantities=None` and `executable_order_payload=None`. No GitHub Actions financial artifact.

- If original four holdings, original filled quantities, account identity, no-open-order condition or account/equity marks mismatch: **fail**, not interpret as permission to liquidate.
- If raw 1D equity history is insufficient, stale, unrealistically cash-flow-affected or exceeds raw risk guard thresholds: return `RAW_BROKER_EQUITY_HISTORY_INSUFFICIENT_OR_RISK_STOP`, and **no real-money instruction**.
- If raw history passes: `RAW_BROKER_EQUITY_HISTORY_PASS_NOT_CASHFLOW_ADJUSTED`, **still no real-money instruction**.
- The separate versioned V6 staged-controller remains in **fake broker mode only**. This observation does not expose reusable live credentials to the disconnected controller or import any order writer.

## Acceptance criteria

- Synthetic tests protect original source/cash identity, forged ID, active pending orders, invalid/short equity-history data, risky raw daily moves and privacy on PR.
- Any authenticated LIVE run uses only the original read-only Alpaca network implementation with GET-only method; the existing remote STOP is checked BEFORE and AFTER broker reads, then report excludes private figures.
- No new deposits, margin, leverage, stocks, futures, FX, crypto, options or outgoing order API requests.
- $130.30 original capital cap, HIGH pilot and all original holdings unchanged.

**Next stage after results:** Broker-fresh comprehensive risk history adjusted for actual account cashflows and open/filled orders, original reusable XLE weight measured privately, then separate live adapter plus actual T+1 settlement proof. The goal remains a small genuine LIVE risk-premium experiment without months of forward PAPER strategy-returns testing.
