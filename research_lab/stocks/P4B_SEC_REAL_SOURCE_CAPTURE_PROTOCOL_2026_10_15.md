# Fund-100 Phase 4B — SEC raw-source prospective capture

**Design frozen 15 October 2026. STATUS: read-only real-source
collector implemented; original issuer source bytes not yet acquired.
No historic alpha, stock PAPER, or LIVE.**

## Why this milestone exists

Phase 4A built accession-linked, conservative filing-date quality
features from official SEC XBRL CompanyFacts and filing submissions.
Synthetic source fixtures passed, but those alone don't prove source
coverage for actual US issuers. The Phase 4B collector obtains both
**current official** public JSON source files, checks the original CIK
identities, stores raw UTF-8 payloads and SHA256 hashes, and creates a
strictly contemporary quality research observation.

Official SEC reference:
- [SEC EDGAR API documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
- [SEC developer/fair access](https://www.sec.gov/about/developer-resources)
- [SEC webmaster fair-access FAQ](https://www.sec.gov/about/webmaster-frequently-asked-questions)

**No API key or payment** is needed, but SEC **requires a declared
requester User-Agent identifying a real organization/person and
email contact** and currently limits usage to 10 requests/sec.
Do not invent an email, impersonate an institution, or silently
request anonymously. Our client sends at most **16 GETs** on manual
full-cohort invocation, with a 0.3-second per-document delay,
and never follows redirects to nonmatching endpoints. It uses only:

```text
https://data.sec.gov/api/xbrl/companyfacts/CIK{10digit}.json
https://data.sec.gov/submissions/CIK{10digit}.json
```

SEC may return 403/429 and terms/access policies can change. The
script stops visibly rather than treating missing/blocked data as
financial records.

## Operator setup: once, with no broker credentials

1. In GitHub repository `nicobouch97/fund100-research`, open
   **Settings → Secrets and variables → Actions → Secrets**.
2. Create the *repository secret* **`FUND100_SEC_USER_AGENT`**
   containing **your own real requester label and contact email**,
   in the SEC's format `Actual Organization ActualContact@yourdomain.tld`.
   This is only an illustrative syntax, **not a proposed identity**.
   Do not enter any Alpaca key, password, phone, trading account
   number, private API token or fabricated email as SEC contact.
3. On `main`, go to **Actions → Fund-100 Phase 4B SEC Prospective
   Stock Snapshot (NO BROKER) → Run workflow**. Select
   `capture_prospective_sec`, then a company count of 1, 2, 4
   or 8. Start with **2**; larger sets can be collected later.
4. The contact is only injected into the explicit capture step on
   `workflow_dispatch`; it is **not printed**, not present in
   reports and not given to PR jobs. The repository workflow has
   `contents: read`, no broker environment and no trade routes.
5. The successful run creates a GitHub Actions artifact
   `fund100-phase4b-real-sec-snapshot-<run-id>`, retained for
   90 days, containing exact SEC JSON input bytes and a
   `manifest-and-quality.json` with two SHA256 hashes per
   company, acquisition UTC, cohort identity, source
   10-K accession/filing date, score or *MISSING*, and explicit
   research/no-promotion flags. The historical source manifest
   is **only for the current capture time**, never retroactively
   historical trading snapshots.

**Automatic PR/push CI uses synthetic SEC fixtures and never
attempts network access or reads the SEC contact secret.** The
manual real-fetch mode will FAIL if the SEC user-agent secret
isn't provided; this is intentional, not a broken strategy.

## What this collector does NOT prove

- It is a **2026 contemporaneous cohort**, not a historic
  survivorship-free universe. AAPL/MSFT/GOOGL/AMZN/XOM/JNJ/PG/KO
  were chosen from currently available companies; backtesting
  them in 2010 would bias results by excluding failed firms.
- A current SEC CompanyFacts feed contains later comparative
  or corrected XBRL disclosures. Accession-bound annual facts
  reduce leakage but do not reconstruct independent archived
  historical API vintages. Its 2-weekday-after-filing lag is
  a conservative calendar proxy, NOT verified historical
  market timestamp or US-holiday-adjusted execution time.
- Differences in annual company-reported earnings/revenue
  are NOT sell-side **analyst EPS consensus revisions**.
  Those remain absent (`null`) and need a separate
  point-in-time licensed estimates source.
- Revenue/XBRL tags vary across companies; missing revenue,
  cash flow or capex tag ⇒ MISSING quality observation, not
  a zero or arbitrarily substituted concept.
- No stock prices, delisted company universe, bid/ask
  spreads, limit-up/down shocks, splits, ticker changes,
  sector-relative forecasts, historical returns, order
  sizing, capital authorization or broker execution.

**Failure is useful evidence.** Some issuer 10-K sources may lack
the four required fixed P4A tags. Report their missing
coverage. Do not relax feature validation based solely on
today's selected survivors. A separate reviewed issuer-specific
tag equivalence map and fresh prospective experiment are
required before extending coverage.

## What happens next

After the first real capture, assess individual company coverage,
SEC source timestamps and latest eligible filing accessions.
Add a source-hashed, immutable prospective observation series,
not a retroactive history; repeat on new filings using an
approved periodic cadence only after the operator has elected
to collect SEC data. Seek a legitimate analyst revision
source and a delisting-aware historical security master
before attempting any US-stock strategy backtest.

**Original V5 US ETF PAPER pilot only; LIVE trading remains
operator STOPPED and kill switch ENGAGED, HIGH risk selected,
$130.30 pilot ceiling and 14 US-ETF LIVE allowlist unchanged.**
