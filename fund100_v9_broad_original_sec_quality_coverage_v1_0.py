"""V9: first bounded, source-dated SEC annual-fundamentals COVERAGE from broad listings.

A deterministic issuer sample is taken from exact current ticker+exchange SEC
associations bearing source name wording for common/ordinary shares. It is
not a validated share class or a survivor-free historical universe. Source
identities and original SEC issuer JSON live only in memory; report counts,
source hashes and a roster commitment, NOT a roster, CIKs or rankings.
Existing filing-lagged P4A annual metrics are COVERAGE diagnostics only.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from datetime import datetime, timezone
import math
from hashlib import sha256
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener
import argparse
import json
import os
import time

import fund100_v9_sec_current_listing_association_v1_0 as link
import fund100_v9_official_current_listing_discovery_v1_0 as listing
import fund100_stock_sec_source_p4b_v1_0 as sec
import fund100_stock_sec_quality_p4a_v1_0 as quality

SCHEMA = "FUND100_V9_DETERMINISTIC_CURRENT_SEC_QUALITY_SOURCE_COVERAGE_V1"
SELECTION_DOMAIN = b"FUND100_V9_20261110_CURRENT_ISSUER_SAMPLE_V1:"
SAMPLE_N = 32
MIN_CURRENT_CIK_POOL = 1000
MAX_TOTAL_JSON_BYTES = 240_000_000
SLEEP_PER_SEC_REQUEST = 0.40
NO_BROKER_READS = NO_BROKER_ORDERS = NO_PRIVATE_WRITES = 0
LIVE_AUTHORIZED = False
CUE = "EXPLICIT_COMMON_OR_ORDINARY_WORDING_REVIEW_ONLY"

class SourceHold(ValueError):
    pass


def eligible_issuer_sample(*, directories, sec_associations, observed,
                           sample_n=SAMPLE_N, min_pool=MIN_CURRENT_CIK_POOL):
    if (type(sample_n) is not int or type(min_pool) is not int
        or not 1 <= sample_n <= SAMPLE_N or min_pool < sample_n):
        raise SourceHold("Unbounded or implausible original issuer sample")
    report = link.inspect(nasdaq_raw=directories, sec_raw=sec_associations,
                          observed=observed, min_directory_rows=1,
                          min_sec_rows=1)
    rows, _ = link.candidate_rows(directories, observed=observed, min_rows=1)
    index, _, _ = link.sec_records(sec_associations, min_rows=1)
    roots = Counter(t for t, _, _ in rows)
    selected_ciks = set()
    for ticker, venue, cue in rows:
        if cue != CUE or roots[ticker] != 1:
            continue
        associations = index.get(ticker)
        if not associations or len(associations) != 1:
            continue
        cik, sec_venue = next(iter(associations))
        if sec_venue == venue:
            selected_ciks.add(cik)
    expected = report["distinct_current_SEC_CIKs_with_explicit_common_wording_only"]
    if len(selected_ciks) != expected:
        raise SourceHold("Live issuer pool did not reconcile with original V9 match")
    if len(selected_ciks) < min_pool:
        raise SourceHold("Original current issuer population too small for source sample")
    # Predeclared and indifferent to fundamentals, filings, prices and returns.
    # Do not re-rank if an issuer later lacks companyfacts; retain 404 coverage.
    sample = sorted(selected_ciks, key=lambda cik: (
        sha256(SELECTION_DOMAIN + str(cik).encode("ascii")).digest(), cik))[:sample_n]
    fingerprint = sha256(
        b"FUND100_V9_SAMPLED_CIK_COMMITMENT_V1\n" +
        b"|".join(str(c).encode("ascii") for c in sample)).hexdigest()
    return sample, fingerprint, report


def _get_sec(cik: int, kind: str, *, agent: str):
    cik_text = f"{cik:010d}"
    url = sec.sec_url(cik_text, kind)
    request = Request(url, method="GET", headers={
        "User-Agent": sec.contact_user_agent(agent),
        "Accept": "application/json", "Accept-Encoding": "identity",
        "Cache-Control": "no-cache",
    })
    try:
        with build_opener(listing._NoRedirect).open(request, timeout=20) as response:
            if response.status != 200 or response.geturl() != url:
                raise SourceHold("SEC official document source mismatch")
            if "json" not in response.headers.get("Content-Type", "").lower():
                raise SourceHold("SEC original response not JSON")
            result = response.read(sec.MAX_JSON_BYTES + 1)
    except HTTPError as err:
        if err.code == 404:  # explicitly absent current SEC XBRL/submissions
            return None
        raise SourceHold("SEC official source transport unavailable; research HOLD") from None
    except (OSError, URLError, TimeoutError, ValueError):
        raise SourceHold("SEC original source unavailable; no sampling report") from None
    if not 2 <= len(result) <= sec.MAX_JSON_BYTES:
        raise SourceHold("SEC issuer source exceeds size bounds")
    return result


# Only potential historical US-GAAP taxonomy ALTERNATIVES to investigate.
# A concept name existing anywhere in today's companyfacts is NOT evidence
# that it matches the financial meaning, current fiscal period or 10-K
# accession of the missing generic metric. Never use these to score.
RESEARCH_ONLY_ALTERNATIVE_CONCEPTS = {
    "revenue": ("Revenues", "SalesRevenueNet"),
    "capital_expenditure": ("PaymentsToAcquireProductiveAssets",),
}


def _has_usd_concept(concepts: dict, tag: str) -> bool:
    concept = concepts.get(tag)
    units = concept.get("units") if type(concept) is dict else None
    usd_rows = units.get("USD") if type(units) is dict else None
    return type(usd_rows) is list and bool(usd_rows)


def _alternative_original_10k_pair_status(*, companyfacts: dict,
                                         submissions: dict, tag: str,
                                         asof: str) -> str:
    """Check original SEC 10-K provenance, NEVER accounting interchangeability.

    A candidate alternative tag existing ANYWHERE in modern SEC companyfacts
    is not equivalent to the generic revenue/capex field. Even a matched
    pair only authorizes REVIEW of the concept's meaning, not an actual
    financial score or past-as-of data vintage. No value leaves memory.
    """
    if not _has_usd_concept(companyfacts["facts"]["us-gaap"], tag):
        return "NO_USD_SOURCE_ROWS"
    day = quality.iso_date(asof, "SEC observation as-of date")
    filings = quality.submissions_index(submissions)
    rows = companyfacts["facts"]["us-gaap"][tag]["units"]["USD"]
    by_end = defaultdict(dict)
    for row in rows:
        if type(row) is not dict:
            raise SourceHold("Invalid alternative SEC concept source row")
        accn = row.get("accn")
        filing = filings.get(accn)
        if (filing is None or filing["form"] != "10-K"
            or row.get("form") != "10-K"
            or row.get("filed") != filing["filed"]
            or row.get("end") != filing["end"]):
            continue
        try:
            end = quality.iso_date(row.get("end"), "alternative fact end")
            start = quality.iso_date(row.get("start"), "alternative fact start")
        except quality.StockSourceStop:
            continue
        if (not quality.MIN_FY_DAYS <= (end-start).days <= quality.MAX_FY_DAYS
            or quality.iso_date(
                quality.availability_day(filing["filed"]), "filing availability") > day
            or end > day):
            continue
        value = row.get("val")
        if (type(value) not in (int, float) or
            not math.isfinite(float(value)) or abs(value) > 1e15):
            raise SourceHold("Invalid original alternative SEC annual USD amount")
        original_period_value = (start, value)
        existing = by_end[end].get(accn)
        if existing is not None and existing != original_period_value:
            return "CONFLICTING_OR_MULTIPLE_10K_SOURCE_VINTAGES"
        by_end[end][accn] = original_period_value
    # Never select an arbitrarily favourable original 10-K amendment or
    # recast and then pretend it was unique first-vintage history.
    if any(len(v) != 1 for v in by_end.values()):
        return "CONFLICTING_OR_MULTIPLE_10K_SOURCE_VINTAGES"
    years = sorted(by_end)
    if len(years) < 2:
        return "FEWER_THAN_TWO_ELIGIBLE_OWN_10K_FISCAL_YEARS"
    prior, latest = years[-2:]
    if (not 330 <= (latest-prior).days <= 400 or
        (day-latest).days > quality.MAX_STALENESS_DAYS):
        return "LATEST_TWO_10K_FY_NOT_CONSECUTIVE_AND_FRESH"
    return "TWO_OWN_ACCESSION_10K_FY_FACTS_REVIEW_ONLY_NOT_EQUIVALENT"


def _joint_four_inputs_same_original_10k_years(*, companyfacts: dict,
                                            submissions: dict,
                                            missing: tuple[str, ...],
                                            asof: str) -> str:
    """Strict original source-COEXISTENCE only, never financial equivalence.

    For each missing generic US-GAAP tag, use solely the preregistered
    alternative tag candidates; never invent sector or select a tag for
    its favourable dollar value. Require all FOUR input tags to cover
    exactly the SAME last two eligible 10-K accession/filing/FY-end keys.
    If multiple candidate alternatives qualify, do not choose one.
    """
    if not missing or any(label not in quality.ANNUAL_TAGS for label in missing):
        raise SourceHold("Joint original-source probe requires a recognised missing tag")
    concepts = companyfacts["facts"]["us-gaap"]
    tag_choices = {}
    for metric, generic in quality.ANNUAL_TAGS.items():
        tags = (RESEARCH_ONLY_ALTERNATIVE_CONCEPTS.get(metric, ())
                if metric in missing else (generic,))
        available = tuple(tag for tag in tags if _has_usd_concept(concepts, tag))
        if not available:
            return "MISSING_ANY_USD_SOURCE_TAG_FOR_ONE_OR_MORE_INPUTS"
        tag_choices[metric] = available

    asof_day = quality.iso_date(asof, "joint source research date")
    ledger = quality.submissions_index(submissions)
    eligible = [
        (accn, data) for accn, data in ledger.items()
        if data["form"] == "10-K"
        and quality.iso_date(data["end"], "10-K FY end") <= asof_day
        and quality.iso_date(
            quality.availability_day(data["filed"]), "10-K public lag") <= asof_day
    ]
    if len(eligible) < 2:
        return "INSUFFICIENT_ORIGINAL_ELIGIBLE_10K_LEDGER_YEARS"
    ends = Counter(row["end"] for _, row in eligible)
    if any(n > 1 for n in ends.values()):
        return "MULTIPLE_ORIGINAL_10K_ACCESSIONS_SAME_FY_UNRESOLVED"
    eligible.sort(key=lambda pair: pair[1]["end"])
    (prior_accn, prior), (latest_accn, latest) = eligible[-2:]
    prior_end = quality.iso_date(prior["end"], "prior FY")
    latest_end = quality.iso_date(latest["end"], "latest FY")
    if (not 330 <= (latest_end-prior_end).days <= 400
        or (asof_day-latest_end).days > quality.MAX_STALENESS_DAYS):
        return "LATEST_TWO_10K_YEARS_STALE_OR_NONCONSECUTIVE"

    period_keys = ((prior_accn, prior), (latest_accn, latest))
    starts_by_metric = {}
    for metric, tags in tag_choices.items():
        qualifying = []
        for tag in tags:
            starts = []
            for accn, filing in period_keys:
                # Require original source, own accession, exact FY,
                # full annual duration and a unique original USD value.
                rows = concepts[tag]["units"]["USD"]
                matching = set()
                for row in rows:
                    if type(row) is not dict:
                        raise SourceHold("Invalid joint original SEC USD fact row")
                    if (row.get("accn") != accn or row.get("form") != "10-K"
                        or row.get("filed") != filing["filed"]
                        or row.get("end") != filing["end"]):
                        continue
                    try:
                        start = quality.iso_date(row.get("start"), "source FY start")
                        end = quality.iso_date(row.get("end"), "source FY end")
                    except quality.StockSourceStop:
                        continue
                    if not quality.MIN_FY_DAYS <= (end-start).days <= quality.MAX_FY_DAYS:
                        continue
                    amount = row.get("val")
                    if (type(amount) not in (int, float)
                        or not math.isfinite(float(amount))
                        or abs(float(amount)) > 1e15):
                        raise SourceHold("Untrusted joint original SEC USD amount")
                    matching.add((start, float(amount)))
                if len(matching) > 1:
                    return "CONFLICTING_ORIGINAL_10K_FACT_AMOUNT_OR_START"
                if not matching:
                    break
                starts.append(next(iter(matching))[0])
            if len(starts) == 2:
                qualifying.append((tag, tuple(starts)))
        if not qualifying:
            return "FOUR_INPUTS_NOT_IN_SAME_TWO_ORIGINAL_10K_ACCESSIONS"
        if len(qualifying) > 1:
            return "MULTIPLE_ALTERNATIVE_TAG_OPTIONS_NO_ARBITRARY_PICK"
        starts_by_metric[metric] = qualifying[0][1]
    if len({starts for starts in starts_by_metric.values()}) != 1:
        return "FOUR_INPUTS_10K_ANNUAL_STARTS_NOT_ALIGNED"
    return "FOUR_SOURCE_INPUTS_SHARE_TWO_ORIGINAL_10KS_REVIEW_ONLY"


def _missing_generic_concepts(companyfacts: dict) -> tuple[str, ...]:
    """Only exact source field presence, independent of historical filing."""
    concepts = companyfacts["facts"]["us-gaap"]
    return tuple(label for label, tag in quality.ANNUAL_TAGS.items()
                 if not _has_usd_concept(concepts, tag))


def _unscored_source_reason(*, companyfacts: dict, submissions: dict,
                            model_state: str) -> tuple[str, bool]:
    """Qualify visible gaps, not their unknowable economic cause.

    Only previously authenticated original documents are inspected. SEC
    submissions 'filings.recent' can truncate older history, and the
    'filings.files' metadata is NOT a downloaded filing archive. Presence
    of generic US-GAAP USD concepts is not proof of 10-K eligible facts.
    """
    recent = submissions["filings"]["recent"]
    # Prior P4A source admission validated the ledger and each accession.
    tenk = sum(form == "10-K" for form in recent["form"])
    old_descriptors = submissions["filings"].get("files", [])
    if type(old_descriptors) is not list:
        raise SourceHold("Untrusted optional original SEC old-file descriptors")
    has_undownloaded_older_files = bool(old_descriptors)
    if model_state == "LAST_ANNUAL_REPORT_TOO_STALE":
        return "LATEST_ANNUAL_TOO_STALE", has_undownloaded_older_files
    if model_state != "MISSING_ELIGIBLE_FULL_YEAR_FILINGS":
        return "OTHER_P4A_UNSCORED_STATE_REVIEW_ONLY", has_undownloaded_older_files
    if tenk == 0:
        return "ZERO_10K_IN_RECENT_SUBMISSIONS_LEDGER", has_undownloaded_older_files
    if tenk == 1:
        return "ONE_10K_IN_RECENT_SUBMISSIONS_LEDGER", has_undownloaded_older_files
    if _missing_generic_concepts(companyfacts):
        return "TWO_PLUS_10K_MISSING_GENERIC_CONCEPT_OR_USD_ROWS", has_undownloaded_older_files
    return "TWO_PLUS_10K_CONCEPTS_PRESENT_BUT_NO_QUALIFIED_PAIR", has_undownloaded_older_files


def annual_coverage(*, directories, sec_associations, observed, fetcher,
                    sample_n=SAMPLE_N, min_pool=MIN_CURRENT_CIK_POOL):
    if (type(observed) is not datetime or observed.tzinfo is None or
        observed.utcoffset() is None or not callable(fetcher)):
        raise SourceHold("Missing actual bounded source time or SEC source loader")
    observed = observed.astimezone(timezone.utc)
    sample, roster_digest, source_report = eligible_issuer_sample(
        directories=directories, sec_associations=sec_associations,
        observed=observed, sample_n=sample_n, min_pool=min_pool)
    outcomes = Counter()
    model_states = Counter()
    unscored_source_reasons = Counter()
    missing_generic_concept_usd_counts = Counter()
    potential_alternative_tag_presence_only = Counter()
    alternative_tag_own_accession_10k_pair_states = Counter()
    joint_four_inputs_same_10k_source_review_states = Counter()
    unscored_with_older_descriptors = 0
    total_bytes = 0
    source_digest = sha256(b"FUND100_V9_ORIGINAL_SEC_DOCUMENT_SOURCE_DIGEST_V1\n")
    for cik in sample:
        original = {}
        for kind in ("companyfacts", "submissions"):
            raw = fetcher(cik, kind)
            if raw is not None and type(raw) is not bytes:
                raise SourceHold("SEC source loader was not bytes or explicit 404")
            source_digest.update(kind.encode("ascii") + b"\x00")
            source_digest.update(f"{cik:010d}".encode("ascii") + b"\x00")
            if raw is None:
                source_digest.update(b"HTTP404\x00")
                original[kind] = None
                continue
            total_bytes += len(raw)
            if total_bytes > MAX_TOTAL_JSON_BYTES:
                raise SourceHold("Combined original SEC source bytes exceed bounds")
            source_digest.update(sha256(raw).digest())
            try:
                original[kind] = sec.decode_source(raw, expected_cik=f"{cik:010d}")
            except sec.SecIntakeStop:
                # A SEC CIK mismatch must not be downgraded to low coverage.
                raise SourceHold("SEC original document identity corrupted") from None
        if any(v is None for v in original.values()):
            outcomes["at_least_one_SEC_document_HTTP_404"] += 1
            continue
        outcomes["both_SEC_documents_received_and_CIK_matched"] += 1
        try:
            observed_quality = quality.asof_quality(
                original["companyfacts"], original["submissions"],
                f"{cik:010d}", observed.date().isoformat())
        except quality.StockSourceStop:
            outcomes["SEC_facts_incompatible_with_generic_industrial_quality_contract"] += 1
            # Differentiate strict P4A rejection from a low quality score.
            # Preserve unknown details; never reinterpret as poor economics.
            unscored_source_reasons["P4A_ORIGINAL_SOURCE_STRICT_VALIDATION_REJECTED"] += 1
            continue
        model_states[observed_quality["state"]] += 1
        if observed_quality.get("score") is not None:
            if (type(observed_quality["score"]) is not int or
                observed_quality["score"] not in range(4)
                or observed_quality["live_authorized"] is not False
                or observed_quality["broker_order_count"] != 0):
                raise SourceHold("Original financial model claimed trading authority")
            outcomes["generic_two_fiscal_year_filing_lagged_score_available"] += 1
        else:
            outcomes["generic_filing_lagged_score_unavailable"] += 1
            reason, archived_descriptor_only = _unscored_source_reason(
                companyfacts=original["companyfacts"],
                submissions=original["submissions"],
                model_state=observed_quality["state"],
            )
            unscored_source_reasons[reason] += 1
            unscored_with_older_descriptors += int(archived_descriptor_only)
            if reason == "TWO_PLUS_10K_MISSING_GENERIC_CONCEPT_OR_USD_ROWS":
                # These are tag-PRESENCE counts among source gaps, NOT
                # source-vetted financial facts, substitute account values,
                # security eligibility, scores or predictions.
                missing = _missing_generic_concepts(original["companyfacts"])
                if not missing:
                    raise SourceHold("Missing-tag census contradicts original source reason")
                concepts = original["companyfacts"]["facts"]["us-gaap"]
                joint_state = _joint_four_inputs_same_original_10k_years(
                    companyfacts=original["companyfacts"],
                    submissions=original["submissions"],
                    missing=missing, asof=observed.date().isoformat())
                joint_four_inputs_same_10k_source_review_states[joint_state] += 1
                for label in missing:
                    missing_generic_concept_usd_counts[label] += 1
                    for alias in RESEARCH_ONLY_ALTERNATIVE_CONCEPTS.get(label, ()):
                        if _has_usd_concept(concepts, alias):
                            tag_key = label + ":" + alias
                            potential_alternative_tag_presence_only[tag_key] += 1
                            status = _alternative_original_10k_pair_status(
                                companyfacts=original["companyfacts"],
                                submissions=original["submissions"],
                                tag=alias, asof=observed.date().isoformat())
                            alternative_tag_own_accession_10k_pair_states[
                                tag_key + ":" + status] += 1
    if (outcomes["at_least_one_SEC_document_HTTP_404"] +
        outcomes["both_SEC_documents_received_and_CIK_matched"] != len(sample)
        or outcomes["both_SEC_documents_received_and_CIK_matched"] !=
        outcomes["SEC_facts_incompatible_with_generic_industrial_quality_contract"] +
        outcomes["generic_two_fiscal_year_filing_lagged_score_available"] +
        outcomes["generic_filing_lagged_score_unavailable"]
        or sum(unscored_source_reasons.values()) !=
        outcomes["SEC_facts_incompatible_with_generic_industrial_quality_contract"] +
        outcomes["generic_filing_lagged_score_unavailable"]
        or unscored_with_older_descriptors >
        outcomes["generic_filing_lagged_score_unavailable"]
        or not (
            unscored_source_reasons.get(
                "TWO_PLUS_10K_MISSING_GENERIC_CONCEPT_OR_USD_ROWS", 0)
            <= sum(missing_generic_concept_usd_counts.values())
            <= 4 * unscored_source_reasons.get(
                "TWO_PLUS_10K_MISSING_GENERIC_CONCEPT_OR_USD_ROWS", 0))
        or any(count >
               missing_generic_concept_usd_counts.get(key.split(":")[0], 0)
               for key, count in potential_alternative_tag_presence_only.items())
        or sum(joint_four_inputs_same_10k_source_review_states.values()) !=
        unscored_source_reasons.get(
            "TWO_PLUS_10K_MISSING_GENERIC_CONCEPT_OR_USD_ROWS", 0)
        or sum(alternative_tag_own_accession_10k_pair_states.values()) !=
        sum(potential_alternative_tag_presence_only.values())
        or any(key.split(":")[-1] not in {
             "NO_USD_SOURCE_ROWS",
             "CONFLICTING_OR_MULTIPLE_10K_SOURCE_VINTAGES",
             "FEWER_THAN_TWO_ELIGIBLE_OWN_10K_FISCAL_YEARS",
             "LATEST_TWO_10K_FY_NOT_CONSECUTIVE_AND_FRESH",
             "TWO_OWN_ACCESSION_10K_FY_FACTS_REVIEW_ONLY_NOT_EQUIVALENT"}
             for key in alternative_tag_own_accession_10k_pair_states)):
        raise SourceHold("Sample source coverage and gap categories did not reconcile")
    return {
        "schema": SCHEMA,
        "status": "PROSPECTIVE_DETERMINISTIC_CURRENT_CIK_QUALITY_COVERAGE_RESEARCH_ONLY",
        "original_three_source_report": source_report,
        "selection_method": "PREDECLARED_SHA256_CIK_SORT_NO_RETURN_OR_FINANCIAL_SELECTION",
        "selection_population_definition": "EXACT_CURRENT_SEC_TICKER_EXCHANGE_WITH_COMMON_NAME_WORDING_ONLY",
        "eligible_current_CIKs_not_security_classes": source_report[
            "distinct_current_SEC_CIKs_with_explicit_common_wording_only"],
        "sample_size": len(sample),
        "sample_roster_SHA256_commitment_only": roster_digest,
        "sample_analyzed_asof_UTC": observed.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "official_SEC_documents_observed_sha256_aggregate": source_digest.hexdigest(),
        "official_SEC_document_bytes_observed": total_bytes,
        "sample_outcome_counts": dict(sorted(outcomes.items())),
        "generic_original_filing_contract_states": dict(sorted(model_states.items())),
        "unscored_original_source_reason_counts": dict(sorted(unscored_source_reasons.items())),
        "missing_exact_generic_usgaap_USD_tag_issuer_counts":
            dict(sorted(missing_generic_concept_usd_counts.items())),
        "possible_alternative_usgaap_tag_presence_NOT_a_substitute":
            dict(sorted(potential_alternative_tag_presence_only.items())),
        "alternative_tag_original_10K_own_accession_pair_diagnostics_NOT_equivalence":
            dict(sorted(alternative_tag_own_accession_10k_pair_states.items())),
        "joint_four_input_same_two_original_10K_years_source_states_NOT_a_score":
            dict(sorted(joint_four_inputs_same_10k_source_review_states.items())),
        "joint_four_input_source_alignment_not_accounting_semantics_verified": True,
        "joint_four_input_source_alignment_never_promotes_original_P4A_score": True,
        "alternative_10K_pair_diagnostic_does_not_make_revenue_capex_interchangeable": True,
        "alternative_tag_exists_in_any_current_companyfacts_not_same_10K_proof": True,
        "no_alternative_tag_applied_to_quality_score": True,
        "generic_unavailable_issuers_with_undownloaded_older_SEC_file_descriptors_only":
            unscored_with_older_descriptors,
        "filings_files_metadata_does_not_prove_archived_10K_or_authorize_backfill": True,
        "generic_tag_presence_is_not_a_validated_own_accession_10K_fact": True,
        "unscored_source_reasons_are_not_company_valuation_judgments": True,
        "full_pool_companyfacts_coverage_verified": False,
        "sample_is_randomly_representative_of_US_common_stocks": False,
        "sample_is_persistently_replayable_without_archived_original_bytes": False,
        "point_in_time_historical_universe_authenticated": False,
        "generic_industrial_model_is_sector_neutral": False,
        "share_class_market_cap_or_valuation_proven": False,
        "analyst_revisions_prices_or_historical_stock_returns_proven": False,
        "live_authorized": False,
        "broker_reads": 0, "broker_orders": 0, "private_state_writes": 0,
    }


def main():
    args = argparse.ArgumentParser()
    args.add_argument("--out", type=Path, required=True)
    settings = args.parse_args()
    if settings.out.exists():
        raise SourceHold("Do not overwrite an original sample coverage receipt")
    if (os.getenv("GITHUB_ACTIONS") != "true" or
        os.getenv("GITHUB_REPOSITORY") != "nicobouch97/fund100-research" or
        os.getenv("GITHUB_REF") != "refs/heads/main"):
        raise SourceHold("Original original-source sampling only on protected main")
    agent = sec.contact_user_agent(os.getenv("SEC_USER_AGENT"))
    nasdaq = {filename:listing._get_official(filename) for filename in listing.FILES}
    sec_raw = link.fetch_sec(agent=agent)
    clock = datetime.now(timezone.utc)
    def get(cik, kind):
        try:
            return _get_sec(cik, kind, agent=agent)
        finally:
            # 2.5 requests/s, well within SEC's fair access guidance.
            time.sleep(SLEEP_PER_SEC_REQUEST)
    output = annual_coverage(directories=nasdaq, sec_associations=sec_raw,
                             observed=clock, fetcher=get)
    settings.out.parent.mkdir(parents=True, exist_ok=True)
    settings.out.write_text(json.dumps(output, indent=2, sort_keys=True)+"\n")
    print("Source-dated original SEC issuer sample complete; issuer roster withheld.")
    print("Sample size:", output["sample_size"],
          "Generic annual coverage:", output["sample_outcome_counts"].get(
              "generic_two_fiscal_year_filing_lagged_score_available", 0))
    print("No broker orders, no investment approval or alpha proof.")


if __name__ == "__main__":
    main()
