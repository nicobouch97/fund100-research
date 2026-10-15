# Fund-100 Phase 3 — GLD and DBC commodity ETP preregistered research

**Status: RESEARCH ONLY. NOT approved for PAPER, LIVE, account funding or changes to LOW/MEDIUM/HIGH capital allocation.**

## Asset structures

- **GLD:** physically backed gold bullion trust. GLD's shares track gold bullion price less trust expenses; the fund is not the same as futures prices.
  Product description: https://www.spdrgoldshares.com/usa/gld/
- **DBC:** US-listed futures-based diversified commodity ETP that invests in commodity futures and incorporates Treasury/money-market income. Commodity futures exposure can differ substantially from spot commodity returns because of rolling, collateral, rebalance rules and tracking.
  Product description: https://www.invesco.com/us/en/financial-products/etfs/invesco-db-commodity-index-tracking-fund.html
  2025 10-K: https://www.sec.gov/Archives/edgar/data/1328237/000119312526083563/dbc-20251231.htm
- **SHY:** a short-duration Treasury ETF used ONLY as a defensive historical comparator and residual reference holding, NOT cash or a riskless asset.
- **SPY:** an equity diagnostic series used only to estimate exposure to sharp equity-market falls. The model NEVER trades SPY.

The product structures matter: we **must not** double-count DBC's roll/tracking/fund-fee effects by deducting an arbitrary additional 'roll cost' from historical adjusted DBC share returns. Additional trading slippage/costs apply when rebalancing GLD/DBC/SHY shares. ETF-specific fees, financing, taxes, underlying futures margin, closure/liquidity changes, and future fund structure still require separate study. Price changes are vendor-adjusted and may be retrospectively restated.

## Fixed hypothesis (not tuned to a later evaluation)

At the first trading session close of each calendar month, use only prices completed by the **previous** trading session.

- Examine 126-trading-session relative and absolute momentum against SHY for each GLD/DBC. A product qualifies if its lagged 126-session return exceeds both 0% and SHY.
- Allocate up to **20% GLD** or **15% DBC** if eligible. If annualised trailing 63-session realized volatility exceeds **30% for GLD** or **35% for DBC**, halve its intended sleeve. Total intended commodities <= 35%, and the unused target remains in SHY.
- Monthly targets are long-only and unlevered; actual weights drift between rebalances. ETF value can fall sharply; none of these reference sleeves is insured cash.
- Charge *both sides* of portfolio turnover 5, 15 and 35 basis points per dollar traded. These are illustrative, not verified broker fills or futures rolls.
- Use 70% earlier data to describe behavior and later 30% as a chronological comparison for this one **fixed** model; no candidate parameter selection. This is not investment-grade point-in-time validation. We must NOT repeatedly tune this same later segment.

Compare: **SHY** buy-and-hold and a capped **static GLD 20% / DBC 15% / SHY 65% monthly-rebalanced mix** at identical trading frictions. Report net returns relative to SHY, turnover, volatility, maximum drawdown, daily SPY correlation, and mean commodity strategy return on days when SPY falls at least 2%. Stress-day averages are descriptive, not conditional hedging promises.

## Research and promotion gates

1. Separate immutable, source-hashed public data snapshot for this first evaluation; point-in-time revision concerns remain.
2. Historical results from this test alone do not authorize even PAPER execution. Genuine prospective forward observations and a frozen rule set must validate the result.
3. Before promotion, verify futures-linked roll and tracking, liquidity/market impact on rebalances, diversification across equity crash and inflation regimes, correlation with bond and V5 equity sleeve, concentration budget overlap, trading hours, tax/account details and independent PAPER controls.
4. No direct commodity futures trading or leverage is proposed. A future ETP strategy must fit the ONE combined LOW/MEDIUM/HIGH portfolio risk budget and the existing operator STOP, with explicit human approval for any new LIVE symbol.

Workflow `.github/workflows/fund100-commodity-research.yml` runs credential-free tests on PR, and a single public-data research study when first merged to main. Dataset CSV and JSON are kept as temporary GitHub artifacts rather than added to the LIVE codebase.
