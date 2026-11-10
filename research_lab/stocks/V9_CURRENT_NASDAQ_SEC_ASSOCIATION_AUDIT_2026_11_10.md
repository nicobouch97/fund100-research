# Fund-100 V9 — current Nasdaq/SEC issuer association audit

**Registered 10 November 2026 after first broad listing capture. Research only; no selection, LIVE trades, capital mandate or historical backtest.**

## Evidentiary gap

The official V9 Nasdaq directory capture [run 42814396775](https://github.com/nicobouch97/fund100-research/actions/runs/42814396775) recorded 7,445 known-venue non-ETF/non-test listing **records** with 27 other-listed unknown-code records quarantined. It did not authenticate 7,445 common-stock issuers.

The SEC publishes a **current** CIK, EDGAR entity name, ticker and exchange association file at https://www.sec.gov/files/company_tickers_exchange.json . It explicitly warns this periodically updated source does not guarantee coverage or accuracy: https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data .

## Exact original-source audit

- Fetch only TWO approved public Nasdaq Trader directories and ONE current SEC ticker/exchange association document, in one original research-only main job. Bounded HTTPS, no redirect, no broker keys; SEC uses the previously configured real SEC requester identity and does not log it.
- Preserve original source timestamps, SHA256 fingerprints, structures, current-directory category counts and complete documented-market filters; exclude all quarantined market/ETF/test rows.
- Require SEC JSON field order cik/name/ticker/exchange, valid positive issuer IDs and plausible exact ticker strings. Do NOT normalise ticker punctuation, fuzzy match entity names or map a CIK to a confirmed share class. Nasdaq Q/G/S maps to SEC Nasdaq, while other-source N/A/P/Z/V maps conservatively to SEC NYSE/NYSE American/NYSE Arca/Cboe/IEX exact strings. Other SEC exchange spellings remain mismatches.
- A ticker repeated across the two original directories or carrying different SEC CIK/exchange associations is **ambiguous** and cannot be automatically assigned. Classify every candidate: exact ticker/exchange association, no exact SEC ticker association, exchange mismatch, ambiguous SEC association, or duplicate listing ticker. Record independent source integrity and total category coverage.
- Publish only aggregate counts, distinct matched issuer count and original SEC byte length/SHA256, not raw source, names, tickers, CIKs or financial rows. The separate 03:20 UTC Tuesday-Saturday and first-main-push acquisition has READ-ONLY Git permissions, retains a 30-day redacted artifact and no broker connections.
- Offline regression includes stale/damaged directories, ambiguous CIKs, ticker punctuation, missing source rows, wrong exchange, unknown listing flags and privacy. A bad SEC response or rate-limit remains HOLD, not a made-up association.

## 10 November — first protected original SEC read rejects real null exchange

The first genuinely authenticated main-only SEC association capture
[run #42821693954](https://github.com/nicobouch97/fund100-research/actions/runs/42821693954)
completed the no-network regression suite, but stopped with
`Malformed SEC issuer identity` on a real association row. The publisher's
official JSON includes **null** exchange fields for some records; this is
supported by the original SEC source format, rather than missing JSON
columns or evidence of a live stock exchange listing. No matched issuer
coverage was published from the failed run, and no raw security/CIK was
logged.

The narrowly scoped source correction accepts **only explicit JSON null
exchange** as an unqualified row:
`SEC_source_unqualified_rows.null_exchange_unqualified`. Such an entry
never enters a ticker/CIK/exchange association index, never gains a
guessed Nasdaq/NYSE marketplace, and never inflates a distinct issuer
match. Unexpected non-string non-null exchanges, malformed CIK or
ticker, missing/extra SEC fields, bad Nasdaq source and ambiguous
candidate identities still STOP or stay explicit HOLD. Offline
adversarial cases include null alone, null beside a real complete
association and invalid typed non-null values.

A later real capture must still prove a valid SEC association index
and original Nasdaq source. Passing fixtures is not that proof.

## 10 November — actual source: 6,610 exact current issuer associations

The first original Nasdaq/SEC association acquisition
[run #42824385759](https://github.com/nicobouch97/fund100-research/actions/runs/42824385759)
completed successfully, producing 6,610 exact ticker-and-exchange
associations from 7,445 Nasdaq non-ETF/non-test listing rows. Those
associations cover 5,618 distinct current SEC CIKs; 539 had no exact
current SEC ticker association, 296 had exchange mismatches, and
166 *SEC-source rows* had JSON null exchange (a separate SEC source
denominator). This is **not** 6,610 US common stocks or an investable
universe. Official SEC warns its search-association file is not
complete or guaranteed.

## Next prospective coverage dimension: security-name evidence only

Nasdaq's official
[Symbol Directory Definitions](https://www.nasdaqtrader.com/trader.aspx?id=symboldirdefs)
specify a Security Name that can include the type/class, but do not
provide a dedicated authoritative security-class code in the two
public basic directories. Reusing those *same already validated original
directories*, add a **three-way wording audit** inside the existing
Nasdaq+SEC source process, without an extra HTTP request:

1. "EXPLICIT_COMMON_OR_ORDINARY_WORDING_REVIEW_ONLY":
   Security Name explicitly includes "Common Stock", "Common Share(s)"
   or "Ordinary Share(s)" and has **no** conflicting excluded-instrument
   cue. Foreign-domiciled ordinary shares and SPAC common stocks could
   appear here; this is not independent legal identity or quality.
2. "EXPLICIT_ALTERNATIVE_INSTRUMENT_WORDING_REVIEW_ONLY":
   the name includes a word such as preferred, warrant, right, unit,
   depositary, ADR/ADS, note, bond, certificate, convertible or ETN/ETF.
   This **takes precedence** over any common-stock phrase (e.g.,
   "warrants to purchase common stock"). It is a *review flag*,
   **not** a legally validated assertion that the listed security is
   non-common. A bank with "Preferred" in its corporate name could
   be conservatively flagged even if its security is ordinary equity.
3. "UNRESOLVED_SECURITY_NAME_NO_CLASS_INFERENCE":
   no supported explicit cue. Class-A-only, trust/REIT labels, company
   names lacking type details, unusual symbols or novel instrument
   descriptions stay here; never assume they're common shares.

Produce aggregate source-name cue counts for all original known-venue
non-ETF/non-test Nasdaq directory candidates, **and separately only the
subset with exact current SEC ticker/exchange associations**. Also
count distinct SEC issuer CIKs in the explicit-common-wording subset
but never publish identifiers, names, tickers or source bytes.
Preserve original three-source SHA-256, timestamps, 27 unknown Nasdaq
row quarantines, 166 null SEC exchange source rows, independent
ticker/market ambiguity and nontrading locks.

**Zero individuals become eligible for actual brokerage orders from
these cues.** This is a source-qualified *triage measure*, not the
security master, authentic as-reported filing coverage, current float,
delisting history, share-class fundamentals or a five-pillar score.
The next actual qualifying source would need explicit legal security
class / identifier and point-in-time valid corporate action history;
do not call textual cues "verified ordinary shares". Scheduled main
capture records the new counts after merge, but offline fixtures alone
must not be represented as observed market breadth.

## Critical limits

Even a positive original SEC ticker+exchange association is only a **present-day filer link**, not a legal/common-share security master, point-in-time historical stock universe, proof of US domicile, current Alpaca order eligibility, liquidity, dated companyfacts, valuation, forward analyst expectations or demonstrated investment alpha. No backfill or hindsight-selected ranking.

The next economically important step is independent US common-share class/ADR/preferred/warrant/unit screening, later coupled to dated SEC filing availability and genuine liquidity/price sources. Broad historical delistings still require qualified external security master and terminal wealth.

## LIVE boundary

Original LIVE capital ceiling $130.30, $65 new ticket limit, HIGH 6/20/35 account risk, operator STOP, broker kill ENGAGED, original ACWI sell HOLD, private principal attribution and standing-capital mandate are **unchanged**. No owner approvals, broker GET/POST, live order release, private CAS or new capital authority. Merge only after exact-head focused and full safety CI, then inspect genuine source capture separately.
