# P4Z — real delisted-price and corporate-action sample intake

**Predeclared 27 October 2026, before Fund-100's first retrieval of this independent third-party sample. Research only; no orders.**

## Why this work is different from another stock-momentum prototype

The P4L/M1 24-name portfolio contains contemporary survivors, while the historical SEC P4T/P4U/P4Y filing work does not supply security-level prices, dividend/split events or terminal shareholder proceeds. We cannot claim representative historical stock alpha. This task checks a concrete, publicly available **free source sample containing an actual delisted ticker**, rather than repeatedly running strategy variants on the same 24 surviving companies.

Original source: [HistoricalData.net stock sample](https://historicaldata.net/samples.html), free July–December 2022 ZIP at `https://historicaldata.net/file/stocks_sample_2022H2.zip`. Its documented daily sample includes TSLA, KO, SPY and TWTR. The source claims 127 trading sessions for the first three, 83 for TWTR ending 27 October 2022, a 3-for-1 TSLA split on 25 August, KO cash distributions on 15 September and 30 November, and SPY distributions on 16 September and 16 December. TWTR's source filename labels 31 October 2022 as the delisting date; this is **not** the same as its last trade date or verified final shareholder settlement.

## Frozen checks before downloading

- Download only the free 8 MB ZIP with no credentials or purchase. Read the four listing-specific daily CSVs **without extracting or executing downloaded code**. Enforce a bounded archive and the documented 17-column schema, exact July–December 2022 NYSE sample dates, positive finite raw and adjusted closing prices, unique original filenames and SHA256 of the ZIP and four daily files.
- Check TSLA's 25 August 1:3 split and distinguish its misleading raw close return from its adjusted close return; check KO and SPY dated distributions. Keep a separate TWTR listing identity and refuse to extend its 27 October final bar into later sessions.
- Report TWTR terminal proceeds and post-delisting total return as **null/UNKNOWN**, never zero, last-close liquidation, or an automatic deletion of the position. Missing prices cannot silently turn into zero return or an investable cash balance.
- Only publish a compact aggregate JSON audit and SHA256 fingerprints in GitHub Actions. **Do not upload, commit, redistribute or expose the vendor ZIP/CSV**. The provider's terms restrict redistribution of underlying files; cite the provider in any published report.
- Use a synthetic offline test ZIP to exercise source failure, split/dividend errors, duplicate dates and terminal outcome semantics. Then run the real free-source workflow and the full LIVE static audit on the exact PR head before merging.

## Limits and next decision

Four retrospectively chosen securities over six months do not make a historical investable universe, do not support a strategy backtest or prove alpha. Vendor adjustments can be revised; the sample does not prove historical issuer/share-class identities, point-in-time membership, corporate-action completeness, or the value of TWTR merger consideration. A full study still needs a representative **dated security master**, delisted-inclusive adjusted total-return panel, independently verified terminal outcomes and realistic costs. A paid archive is a separate operator purchasing decision, not authorised by this work.

All original LIVE controls remain untouched: **USD 130.30 ceiling**, operator STOP, ENGAGED environment kill switch, HARD LOCKED writer and separate release approvals. No broker requests, funded orders, holdings changes, protected risk-control changes or private-state mutations.


## 27 October 2026 follow-up — independently documented TWTR merger consideration

The original P4Z sample deliberately leaves TWTR terminal cash proceeds unknown. A
separate, **later** primary-source event document is now checked alongside the
original vendor price series: [Twitter's October 2022 SEC Form 8-K](https://www.sec.gov/Archives/edgar/data/1418091/000119312522272772/d411753d8k.htm)
(CIK 1418091; original accession 0001193125-22-272772). The filing reports
that the merger became effective **27 October 2022**, ordinary TWTR shares
(except specified excluded/appraisal categories) converted into a
**contractual right to $54.20 cash without interest**, and NYSE trading was
suspended before the **28 October 2022** open. The vendor file's
31 October delisting *label* is not the same as suspension or the merger
effective date.

The audit checks issuer, common-share class, ticker/exchange, merger
completion, amount and suspension from the original filing bytes. It
preserves the source SHA256 and URL, but not the filing HTML in the
published research artifact. The source acquisition must succeed with
the configured SEC contact; missing/contradictory evidence fails closed.

**Do not misclassify $54.20 as a verified broker deposit or as an
investable after-close sale price.** The filing proves a contractual
conversion right for eligible ordinary shares, not the payment date,
investor-specific exceptions, tax, broker settlement or availability of
cash for reinvestment. Accordingly, the existing fields for **actual
terminal shareholder proceeds and post-delisting realised total return
remain null**. The 8-K is subsequent event evidence and cannot be
used as a trading signal at the 27 October close. This is one
independently sourced corporate-action outcome, not a representative
historical universe or proof of investment alpha.
