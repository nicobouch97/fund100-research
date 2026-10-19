# V6-S1 — authentic LIVE XLE reuse and external-funding activity source PASS

**Date observed:** 2026-10-19 18:05:56 UTC; genuine Alpaca LIVE account, zero brokerage writes.

**Immutable source:** [GitHub Actions 39299643300](https://github.com/nicobouch97/fund100-research/actions/runs/39299643300), main push protected `fund100-live-broker` job `real-live-private-six-get`; [source and reviewed credential scope PR #69](https://github.com/nicobouch97/fund100-research/pull/69). Original six provider read-only GET requests include account, positions, open orders, clock, one-month 1D equity history, nontrade activities after 2026-09-01 with strict pagination. Each original broker source was in memory only; no quantities/amounts/IDs saved or printed.

## Authentic observable outcomes

| Privacy-safe original broker fact | Actual result |
| --- | --- |
| Original LIVE account identity bound to original $130.30 pilot | PASS |
| Original ACWI/EEM/XLE/XLV share quantities unchanged | PASS |
| Outstanding LIVE orders | **0** |
| Original held XLE <=28.5% of min(original $130.30 authorized capital, current equity) | **TRUE — `XLE_BELOW_OR_AT_DRAFT_TARGET`** |
| Current CASH >=5% of current equity | **FALSE — `CURRENT_CASH_BELOW_BUY_TIME_FLOOR`** |
| Original 1D broker raw equity-history risk guard | **PASS, NOT CASH-FLOW ADJUSTED** |
| Broker nontrade activity window included external transfers | **TRUE — `EXTERNAL_TRANSFER_TYPES_SEEN_REQUIRES_CASHFLOW_ADJUSTMENT`** |
| Single `page_size=100` nontrade activity result exhaustively paginated | **TRUE** (fewer than 100 entries) |
| Production account risk returns demonstrably adjusted for external financing | **FALSE / NOT VERIFIED** |
| T+1 sale proceeds spendable | **FALSE / NOT VERIFIED** |
| V6-S1 LIVE buys or sells authorized / submitted | **FALSE / 0** |
| Genuine LIVE broker HTTP requests | **6 GET, 0 non-GET** |

The actual original XLE size is now privately verified as *within the proposed draft target*. A future low-turnover V6 migration can therefore prefer keeping XLE, rather than selling it only to repurchase the same ETF. **This does not make 28.5% target an approved strategy allocation** and does not establish the available headroom for a future XLE BUY; even if in-target now, future quote/valuation can change.

Current LIVE cash is below 5% of account equity; this is expected for the original largely invested V5 portfolio. The proposed new V6-S1 rule would require >=5% cash immediately AFTER any new BUY, so no early new buy should be allowed without later sufficient spendable settled cash. The rule is **not** a demand to immediately create costly daily micro-sells of existing holdings because passive NAV moves change the cash percentage.

**Actual external transfer-type events are present in the broker's nontrade account activity source** within the original September/October 2026 window. Raw brokerage equity series cannot be taken at face value as a pure investment return series for this recent history. Before a real risk release, build and verify a source-dated explicit account net external-flow correction; include the semantics of CSD/CSW, journals and any asset transfers, reject unknown activity classes and validate market-close mapping. The activity scan did not record amounts or dates publicly.

## Roadmap decision

- Original V6-S1 asset allocation remains **DRAFT**, not independently validated alpha: XLK 47.5%, XLE 28.5%, IWM 19%, target cash 5% at order. The earlier costed 2014–Sep2026 S1 CAGR is in-sample and does not prove prospective returns.
- Source-based **XLE overlap** concern is resolved favorably for low-turnover retention under current mark (could change). Original ACWI/EEM/XLV remain held and cannot be treated as sold.
- Prior genuine Alpaca PAPER execution: [39269640353](https://github.com/nicobouch97/fund100-research/actions/runs/39269640353). Prior real LIVE raw history: [39297690493](https://github.com/nicobouch97/fund100-research/actions/runs/39297690493).
- Next critical production work: source-backed signed-dollar external-flow adjustment for each daily history observation; complete order ledger and cash equity settlement availability proof; separate audited S1-specific risk/order policy and broker-execution adapter. Do not borrow the hard-locked original V5 14-ETF writer as a hidden new V6 authorization. Do not require weeks of paper-profit testing.
- Original $130.30 committed capital ceiling, HIGH risk, operator `trading_enabled=false` and broker kill `ENGAGED` remain. No live orders, changes to original investment positions, no further funding, leverage, crypto, options, futures or individual-stock live eligibility were granted.

This is a **concrete, successful original LIVE source evidence milestone**, not completed LIVE strategy activation.
