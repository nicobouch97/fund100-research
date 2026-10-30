# V8-Q2: first original SEC source coverage — 30 October 2026

**Research only. Frozen selection is unchanged; no broker, LIVE release, or new factor promotion.**

Original-source evidence: [main acquisition run 41025137794](https://github.com/nicobouch97/fund100-research/actions/runs/41025137794), artifact `fund100-v8-q2-new-original-first` (ID `12962884465`, 90-day retention, expires 28 January 2027). GitHub artifact ZIP digest: `sha256:ecc9182c1576987e0a9c440139c693b00fe44445f499b1b9c5822586de8d8628`. Original source report SHA-256: `c027ab01672ea70b0c5a150862e59d0b14bd39d38da203c87fa2361920fa670b`. Source acquired `2026-10-30T08:16:19Z`; latest completed market close `2026-10-29`.

## Actual first-source gap attribution

The source selection recorded 20/24 matched positive same-10K `NetIncomeLoss / Assets` companies and excluded four from the registered 8-stock basket. I inspected the exact original SEC `companyfacts` and `submissions` files in the archived artifact. All amounts below are from the **same original 10-K accession** and have not been inserted into the registered Q2 selector.

| Issuer | Frozen gap | Latest original 10-K accession | Same-10K `ProfitLoss` (USD) | Same-10K `Assets` (USD) |
|---|---|---|---:|---:|
| AVGO | `NetIncomeLoss` absent in this accession; `ProfitLoss` present | `0001730168-25-000121` (filed 2025-12-18) | 23,126,000,000 | 171,092,000,000 |
| CAT | `NetIncomeLoss` absent in this accession; `ProfitLoss` present | `0000018230-26-000008` (filed 2026-02-13) | 8,882,000,000 | 98,585,000,000 |
| MA | `NetIncomeLoss` absent in this accession; `ProfitLoss` present | `0001141391-26-000013` (filed 2026-02-11) | 14,968,000,000 | 54,157,000,000 |
| XOM | Original issuer identity quarantined: current SEC ticker registry maps XOM to CIK `0002115436`, `ExxonMobil Holdings Corp`, not the original frozen issuer CIK | Not eligible under original issuer binding | Not used | Not used |

**Interpretation:** AVGO, CAT and MA have an *accounting taxonomy coverage* gap under the exact predeclared `NetIncomeLoss` concept, not proof of absent profitability. `ProfitLoss` is a different GAAP concept and may include noncontrolling interests; it is **not an interchangeable substitute** without a new preregistered economic definition and independent validation. The observed CAT `NetIncomeLossAvailableToCommonStockholdersBasic` is also a different concept and is not used. XOM is an issuer-identity/continuity problem; neither CIK may be spliced into the original basket retrospectively.

## Reproducibility and next research decisions

The original report, SEC raw receipts, price panel and frozen eight-stock selection remain unchanged. The new read-only audit rederives the original selection and all 48 original SEC receipts before explaining gaps; it emits a **separate diagnostic** alongside the existing nightly forward mark. The audit must never turn an excluded issuer into a selected one or infer alpha from unobserved forward returns.

For a future **separately registered** source vintage, evaluate a principled `ProfitLoss`/noncontrolling-interest reconciliation and an issuer succession/ordinary-share continuity mapping *before* freezing a new selection. Maintain a separate, genuinely independent historical universe with delisted returns; this 24-company contemporary cohort is not survivorship-safe historical evidence. The 90-day source artifact remains a durability risk even with weekly hashed carryforward; a provider-immutable independent archive would improve long-run provenance but must not be represented as completed.

This source investigation does not authorize trading, modify capital or risk controls, or validate expected returns.
