# P4K: first authenticated same-vintage stock forward price mark — 21 Oct 2026

**Result: one source-consistent observed post-selection closing-price interval, 19 to 20 Oct 2026, with no outperformance after the 15bp/side cost assumption. No LIVE investment action.**

## Authentication, scope and method

- [Successful actual GitHub P4K read-only main run **39590766346**](https://github.com/nicobouch97/fund100-research/actions/runs/39590766346), **34 tests passed**; artifact `fund100-p4k-authenticated-one-vintage-observed-stock-marks`, artifact ID **12341736462**, 90-day retention. The public GitHub Action used no Alpaca account or private repository token.
- The original 17-Oct signal from original run **39015519726**, source JSON SHA256 `403a6e23ad53ace626cb9663e3889ab9c0b4e58d7c582ad3aab85aa024bdffb7` and CSV SHA256 `9c01c045f6fe9d54f455513249c23433a806ffb350575bef9bfdbde5372d921d`, was reverified against immutable P4I anchor SHA256 `ea1513d9064574f3abfff5c87cd4ad34e4a05663c5bfbf9dfe6ab9e9dd4b783f`.
- Frozen research watchlist **MSFT/KO/PG**, originally selected following completed 16-Oct close; never reselected using the later price source. Comparison benchmark **SPY**; six-stock equal-weight reference **AAPL/AMZN/GOOGL/KO/MSFT/PG**.
- Later archived genuine P4G run **39571738927** captured `2026-10-21T08:46:35Z`, last completed date `2026-10-20`, original snapshot JSON SHA256 `76a11030f8d6d5a0fbf7f38ee97a50b6cd7c5a49f69d822fa20e2b7d5c67b9a1` and canonical price CSV SHA256 `97abb309dcd094fdddb9a8c0450682a0fb8d83925626ddcec039c99f897092b8`.
- **Same later captured CSV** supplies both 19-Oct entry mark and 20-Oct exit mark. Does not splice incompatible 17-Oct and 21-Oct vendor-adjusted historical price vintages. P4J independently confirmed older adjusted-price rows **differ**. This is a *reproducible as-captured mark*, NOT an independently exchange-audited originally visible quote, actual total-return ledger, dividend/corporate-action reconciliation, broker fill or realized P&L.
- Hypothetical long-only buy and hold of equal-weight selected names across one completed price interval; entry and exit transaction-cost sensitivities fixed at **5/15/35 basis points per side** (same friction for benchmarks). No daily stock trading, annualization or claimed statistical alpha.

## Direct observed marks — 19 to 20 October 2026

| Assumed per-side cost | MSFT/KO/PG gross | MSFT/KO/PG net | SPY net | Six-company net | MSFT/KO/PG minus SPY net |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 5 bp | +0.266445% | +0.166204% | +0.234990% | −0.311147% | −0.068786 percentage points |
| 15 bp | +0.266445% | **−0.034129%** | **+0.034520%** | −0.510525% | **−0.068648 percentage points** |
| 35 bp | +0.266445% | −0.434192% | −0.365818% | −0.908681% | −0.068374 percentage points |

One observational interval means NO annualized return, Sharpe ratio, hit rate, significance, economic edge or forward selection. The gross gain on the selected three companies did not cover the hypothetical 15 bp on each side. The comparison with SPY is slightly negative at matched costs; the comparison with six stock reference is positive for this one interval, but cannot be extrapolated.

## Decision and next work

1. **Do not promote V6-Q1 individual equities or P4G/P4K to LIVE** based on this tiny price observation.
2. Keep original P4I strict history-hash fail-closed behavior unchanged. P4K is a newly versioned *alternative source-consistent mark* with explicit vendor and adjusted-close caveats.
3. Next: extend source-vintage tracking as fresh archived completed-session files become available; secure first-seen or independently verifiable unadjusted closes and actual corporate actions for a stronger total-return metric. Prefer genuine cost-after-spread signals before live active equities.
4. Preserve the unified multi-asset mandate, but do not pretend the commodity, bond, crypto and FX candidates are live-approved based on this result.
5. The proposed V6-S1 95% initial gross /5% entry cash, LIVE original $130.30 capital cap, operator `trading_enabled=false`, engaged kill switch and original Alpaca holdings are **unchanged**. Zero actual LIVE/PAPER orders or broker calls from P4K.
