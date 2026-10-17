# C7 first exchange PDF source probe — source available, FINAL still unavailable

**17 October 2026. Exchange original reached, but the retrieved
document is PRELIMINARY. No original final settlement curve was admitted.**

## What the actual GitHub runner did

- [Read-only CME source probe 39039186006](https://github.com/nicobouch97/fund100-research/actions/runs/39039186006)
  installed public PDF extraction utilities, ran **9 defensive tests**
  and executed ONE bounded GET of CME's official rotating
  [Section 61 Energy Futures Products PDF](https://www.cmegroup.com/daily_bulletin/current/Section61_Energy_Futures_Products.pdf).
- The obtained **original PDF**, as decoded directly in that runner
  with pdftotext -layout, bore a printed heading:
  **PG61 BULLETIN #200@ Fri, Oct 16, 2026**
  and unambiguously displayed **PRELIMINARY**.
- The source rejected the PDF with the exact error:
  **PRELIMINARY original CME bulletin cannot become FINAL settlement source.**
  This is a **correct fail-closed acceptance decision**, not a
  verified settlement curve. The original rejected PDF is NOT
  published into Fund-100 as a viable research input.
- Earlier unaffiliated retrieval of the same rotating URL displayed
  a different Oct 8 FINAL image versus Oct 16 PRELIMINARY text.
  Therefore a GET body is not an immutable publication identity;
  store SHA256 of accepted original dated FINAL bytes rather than
  'current' address alone.

## What source field can be extracted once a genuine FINAL is obtained

Official first page has a named `CL FUT NYMEX CRUDE OIL (PHYSICAL)`
table, with delivery-month tokens such as NOV26, DEC26 and JAN27;
each row has actual settlement USD/bbl and contract open interest.
C7 tests require a complete unambiguous CL table, at least 12
unique listed months, positive settlements, two adjacent front
months, full open-interest summation matching printed
`TOTAL CL FUT`, actual trade date, original PDF SHA,
acquisition UTC, and literal FINAL source status.

**This run did not reach settlement/market-data admission**, so it
does NOT prove that the actual first-page 2026 PDF parser's
remaining contract/OI validations will succeed. Tests passed
on **synthetic document-format fixtures** only; exact real FINAL
source matching must be verified later, rather than invented.

### New important clarification on viable commodity trading alpha

A single cross-sectional **contango/backwardation spread is
NOT an achieved roll return**. It can be affected by scarcity,
storage and delivery economics, especially amid 2026 geopolitical
volatility. Realising net long-only total returns requires
successive original dated settlement observations, known
roll/expiry conventions, actually available investment
instruments and their fee/slippage/FX/size limits.
CME historic settle data / delayed API access can require
paid DataMine licences; **no subscription may be purchased
for this $130.30-funded research pilot without separate user
consent and a compelling economic rationale**.

**Status: OFFICIAL SOURCE LOCATED / ORIGINAL PDF GET WORKS /
NO FINAL CURVE ACCEPTED / NO INVESTABLE STRATEGY SIGNAL.**
No LIVE positions sold, no V6 buy authorisation, no
change in Fund-100 controls, HIGH risk or pilot ceiling.
