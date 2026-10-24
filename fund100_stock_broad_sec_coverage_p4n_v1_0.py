"""P4N: original SEC source coverage for the 16 NEW P4L contemporary issuers.

The eight original P4E issuers retain their own frozen accounting contract.
The additional 16 are resolved from the CURRENT official SEC ticker registry
and captured prospectively. A current SEC API response is not a historical
point-in-time database; generic P4A quality is descriptive, not sector-neutral.
No broker connectivity, trading authority, or historic stock alpha claim.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import fund100_stock_broad_momentum_p4l_v1_0 as p4l
import fund100_stock_sec_quality_p4a_v1_0 as p4a
import fund100_stock_sec_source_p4b_v1_0 as p4b
import fund100_stock_sec_issuer_quality_p4e_v1_0 as p4e

SCHEMA = "FUND100_P4N_BROAD_SEC_SOURCE_COVERAGE_V1"
REGISTRY_URL = "https://www.sec.gov/files/company_tickers.json"
REGISTRY_LIMIT = 6_000_000
MAX_NEW = 16


class BroadSecStop(ValueError):
    pass



# Accounting-concept candidates checked against the original 24-Oct-2026
# P4N SEC companyfacts capture (run 40065283660). These are SOURCE-MATCHED
# descriptive tags, NOT reviewed cash economics, normalized FCF or a trading
# quality model. In particular no cross-sector rank is defensible yet.
# Four other issuers are intentionally unresolved: CVX lacks the standard
# operating-income concept; LLY likewise; NEE's capex cash concept is not
# established; JPM's bank economics require a different model.
SOURCE_MATCHED_TAGS = {
    "AVGO": ("RevenueFromContractWithCustomerExcludingAssessedTax", "PaymentsToAcquirePropertyPlantAndEquipment"),
    "CAT": ("Revenues", "PaymentsToAcquirePropertyPlantAndEquipment"),
    "COST": ("RevenueFromContractWithCustomerExcludingAssessedTax", "PaymentsToAcquirePropertyPlantAndEquipment"),
    "DIS": ("Revenues", "PaymentsToAcquirePropertyPlantAndEquipment"),
    "HD": ("RevenueFromContractWithCustomerExcludingAssessedTax", "PaymentsToAcquireProductiveAssets"),
    "MA": ("Revenues", "PaymentsToAcquirePropertyPlantAndEquipment"),
    "MCD": ("Revenues", "PaymentsToAcquirePropertyPlantAndEquipment"),
    "META": ("RevenueFromContractWithCustomerExcludingAssessedTax", "PaymentsToAcquirePropertyPlantAndEquipment"),
    "NVDA": ("Revenues", "PaymentsToAcquireProductiveAssets"),
    "PEP": ("Revenues", "PaymentsToAcquireProductiveAssets"),
    "V": ("RevenueFromContractWithCustomerExcludingAssessedTax", "PaymentsToAcquireProductiveAssets"),
    "WMT": ("RevenueFromContractWithCustomerExcludingAssessedTax", "PaymentsToAcquirePropertyPlantAndEquipment"),
}
UNRESOLVED_ACCOUNTING = {
    "CVX": "STANDARD_OPERATING_INCOME_MISSING_AND_OIL_GAS_CAPEX_REVIEW_REQUIRED",
    "JPM": "BANK_NET_INTEREST_AND_CASH_FLOW_MODEL_REQUIRED",
    "LLY": "STANDARD_OPERATING_INCOME_MISSING",
    "NEE": "CASH_CAPEX_NOT_ESTABLISHED_FOR_UTILITY",
}


# A deposit-funded bank cannot be evaluated using industrial free cash flow:
# deposits/loans are its operating inventory, not excess working capital.
# Keep these source-matched BANK metrics separate from the 0-3 industrial
# diagnostic; no cross-sector rank, valuation, or trade approval is implied.
JPM_BANK_TAGS = {
    "net_interest_income": "InterestIncomeExpenseNet",
    "noninterest_income": "NoninterestIncome",
    "noninterest_expense": "NoninterestExpense",
    "net_revenue": "RevenuesNetOfInterestExpense",
}


def jpm_bank_annual_diagnostics(facts: dict, submissions: dict,
                                cik: str, asof: str) -> dict:
    """Bank efficiency and revenue composition from ONE eligible 10-K.

    All current and comparative amounts must come from that same filing,
    and the SEC net-revenue identity must reconcile in BOTH years.
    """
    p4a.validate_identity(facts, submissions, cik)
    now = p4a.iso_date(asof, "bank research as-of")
    out = {
        "state": "BANK_10K_UNAVAILABLE",
        "latest_10k_accession": None,
        "latest_10k_available_date": None,
        "current_efficiency_ratio": None,
        "prior_efficiency_ratio": None,
        "efficiency_ratio_change_percentage_points": None,
        "net_revenue_growth_yoy": None,
        "current_net_interest_revenue_share": None,
        "net_revenue_identity_reconciled_both_years": False,
        "comparatives_from_same_accession": True,
        "bank_specific_diagnostic_not_industrial_fcf_score": True,
        "cross_sector_comparison_approved": False,
        "for_trading_approved": False,
    }
    if not submissions["filings"]["recent"]:
        return out
    filings = p4a.submissions_index(submissions)
    ready = sorted(
        [(acc, f) for acc, f in filings.items()
         if f["form"] == "10-K"
         and p4a.iso_date(f["end"], "bank FY end") <= now
         and p4a.iso_date(p4a.availability_day(f["filed"]), "bank availability") <= now],
        key=lambda item: (item[1]["end"], item[1]["filed"], item[0]),
        reverse=True,
    )
    if len(ready) < 2:
        return out
    (acc, latest), (_, previous) = ready[:2]
    out["latest_10k_accession"] = acc
    out["latest_10k_available_date"] = p4a.availability_day(latest["filed"])
    latest_end = p4a.iso_date(latest["end"], "bank FY end")
    previous_end = p4a.iso_date(previous["end"], "bank prior FY end")
    if (now - latest_end).days > p4a.MAX_STALENESS_DAYS:
        out["state"] = "BANK_LATEST_10K_STALE"
        return out
    if not 330 <= (latest_end - previous_end).days < 400:
        out["state"] = "BANK_NONCONSECUTIVE_FISCAL_YEARS"
        return out
    concepts = facts["facts"]["us-gaap"]
    amounts = {}
    for period, end in (("current", latest["end"]), ("prior", previous["end"])):
        amounts[period] = {
            name: p4e.annual_value(concepts, tag, acc, latest["filed"], end)
            for name, tag in JPM_BANK_TAGS.items()
        }
    if any(value is None for row in amounts.values() for value in row.values()):
        out["state"] = "BANK_MISSING_SAME_ACCESSION_COMPARATIVE"
        return out
    for row in amounts.values():
        revenue = row["net_revenue"]
        if (revenue <= 0 or row["noninterest_expense"] < 0
            or row["net_interest_income"] < 0 or row["noninterest_income"] < 0):
            out["state"] = "BANK_INVALID_REVENUE_OR_EXPENSE"
            return out
        if abs(row["net_interest_income"] + row["noninterest_income"] - revenue) > max(1.0, .005 * revenue):
            out["state"] = "BANK_NET_REVENUE_IDENTITY_MISMATCH"
            return out
    current, prior = amounts["current"], amounts["prior"]
    cur_eff = current["noninterest_expense"] / current["net_revenue"]
    prior_eff = prior["noninterest_expense"] / prior["net_revenue"]
    out.update(
        state="BANK_LATEST_10K_DESCRIPTIVE_ONLY",
        current_efficiency_ratio=round(cur_eff, 8),
        prior_efficiency_ratio=round(prior_eff, 8),
        efficiency_ratio_change_percentage_points=round(100 * (cur_eff - prior_eff), 6),
        net_revenue_growth_yoy=round(current["net_revenue"] / prior["net_revenue"] - 1, 8),
        current_net_interest_revenue_share=round(
            current["net_interest_income"] / current["net_revenue"], 8),
        net_revenue_identity_reconciled_both_years=True,
    )
    return out


def source_matched_annual_quality(facts: dict, submissions: dict,
                                  cik: str, ticker: str, asof: str) -> dict:
    """Latest eligible 10-K, same-accession FY and comparative, never fallback.

    This source-matched three-test diagnostic cannot be promoted to trading
    or interpreted as cross-sector normalized quality/valuation.
    """
    p4a.validate_identity(facts, submissions, cik)
    now = p4a.iso_date(asof, "source-matched research as-of")
    result = {
        "state": "SOURCE_MATCHED_ANNUAL_FACTS_UNAVAILABLE",
        "score": None, "score_max": 3,
        "latest_10k_accession": None,
        "latest_10k_fiscal_end": None,
        "latest_10k_available_date": None,
        "revenue_source_tag": None, "capex_source_tag": None,
        "revenue_growth_yoy": None, "operating_margin": None,
        "free_cash_flow_margin": None,
        "comparative_from_same_latest_accession": True,
        "cross_sector_economics_reviewed": False,
        "for_trading_approved": False,
    }
    if ticker in UNRESOLVED_ACCOUNTING:
        result["state"] = UNRESOLVED_ACCOUNTING[ticker]
        if ticker == "JPM":
            result["bank_diagnostics"] = jpm_bank_annual_diagnostics(
                facts, submissions, cik, asof)
        return result
    if ticker not in SOURCE_MATCHED_TAGS:
        raise BroadSecStop("Unknown source-matched SEC issuer")
    revenue_tag, capex_tag = SOURCE_MATCHED_TAGS[ticker]
    result.update(revenue_source_tag=revenue_tag, capex_source_tag=capex_tag)
    filings = p4a.submissions_index(submissions)
    ready = sorted(
        [(acc, filing) for acc, filing in filings.items()
         if filing["form"] == "10-K"
         and p4a.iso_date(filing["end"], "annual FY end") <= now
         and p4a.iso_date(p4a.availability_day(filing["filed"]), "availability") <= now],
        key=lambda item: (item[1]["end"], item[1]["filed"], item[0]),
        reverse=True,
    )
    if len(ready) < 2:
        result["state"] = "INSUFFICIENT_10K_CHRONOLOGY"
        return result
    (acc, latest), (_, previous) = ready[:2]
    result.update(
        latest_10k_accession=acc,
        latest_10k_fiscal_end=latest["end"],
        latest_10k_available_date=p4a.availability_day(latest["filed"]),
    )
    if (now - p4a.iso_date(latest["end"], "FY end")).days > p4a.MAX_STALENESS_DAYS:
        result["state"] = "LATEST_10K_STALE"
        return result
    years_apart = (p4a.iso_date(latest["end"], "FY end") -
                   p4a.iso_date(previous["end"], "prior FY end")).days
    if not 330 <= years_apart < 400:
        result["state"] = "NONCONSECUTIVE_10K_PERIODS"
        return result
    tags = {
        "revenue": revenue_tag,
        "operating_income": p4e.OPERATING,
        "operating_cash_flow": p4e.CFO,
        "capital_expenditure": capex_tag,
    }
    concepts = facts["facts"]["us-gaap"]
    current, prior = {}, {}
    for key, tag in tags.items():
        current[key] = p4e.annual_value(concepts, tag, acc, latest["filed"], latest["end"])
        prior[key] = p4e.annual_value(concepts, tag, acc, latest["filed"], previous["end"])
    if any(v is None for v in (*current.values(), *prior.values())):
        result["state"] = "LATEST_10K_MISSING_SAME_ACCESSION_COMPARATIVE"
        return result
    if (current["revenue"] <= 0 or prior["revenue"] <= 0
        or current["capital_expenditure"] < 0 or prior["capital_expenditure"] < 0):
        result["state"] = "INVALID_REVENUE_OR_CAPEX"
        return result
    growth = current["revenue"] / prior["revenue"] - 1
    op_margin = current["operating_income"] / current["revenue"]
    fcf_margin = (current["operating_cash_flow"] -
                  current["capital_expenditure"]) / current["revenue"]
    result.update(
        state="SOURCE_MATCHED_LATEST_10K_DESCRIPTIVE_ONLY",
        score=int(growth >= 0) + int(op_margin >= .10) + int(fcf_margin >= .05),
        revenue_growth_yoy=round(growth, 8),
        operating_margin=round(op_margin, 8),
        free_cash_flow_margin=round(fcf_margin, 8),
    )
    return result


def registry_bytes(user_agent: str) -> bytes:
    """Only official SEC registry, no anonymous request or redirect."""
    p4b.contact_user_agent(user_agent)
    req = Request(REGISTRY_URL, headers={
        "User-Agent": user_agent, "Accept": "application/json",
        "Accept-Encoding": "identity",
    }, method="GET")
    try:
        with urlopen(req, timeout=25) as response:
            if (response.status != 200 or response.geturl() != REGISTRY_URL
                or "json" not in response.headers.get("Content-Type", "").lower()):
                raise BroadSecStop("Official SEC ticker registry response invalid")
            data = response.read(REGISTRY_LIMIT + 1)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise BroadSecStop("Official SEC ticker registry unavailable") from exc
    if not 2 <= len(data) <= REGISTRY_LIMIT:
        raise BroadSecStop("SEC ticker registry byte length invalid")
    return data


def resolve_registry(raw: bytes, *, allow_frozen_drift: bool = False) -> dict[str, str]:
    """Fail closed if any of the 24 contemporary tickers cannot be identified."""
    if type(raw) is not bytes or not 2 <= len(raw) <= REGISTRY_LIMIT:
        raise BroadSecStop("Missing or oversized official registry")
    try:
        registry = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise BroadSecStop("Invalid official SEC ticker registry JSON") from exc
    if not isinstance(registry, dict):
        raise BroadSecStop("Official SEC ticker registry must be an object")
    expected = set(p4l.SECTORS)
    result: dict[str, str] = {}
    for entry in registry.values():
        if not isinstance(entry, dict):
            raise BroadSecStop("Malformed SEC ticker entry")
        ticker = entry.get("ticker")
        if ticker not in expected:
            continue
        cik = entry.get("cik_str")
        if (type(cik) is not int or not 0 < cik < 10**10
            or not isinstance(entry.get("title"), str)
            or not entry["title"].strip()):
            raise BroadSecStop("Malformed official SEC ticker/CIK identity")
        if ticker in result:
            raise BroadSecStop("Duplicate SEC ticker identity")
        result[ticker] = f"{cik:010d}"
    if set(result) != expected or len(set(result.values())) != len(expected):
        raise BroadSecStop("Incomplete or ambiguous 24-issuer SEC identity map")
    original = {row["ticker"]: row["cik_10_digit"] for row in p4b.read_cohort()}
    if any(result[ticker] != cik for ticker, cik in original.items()):
        if not allow_frozen_drift:
            raise BroadSecStop("Official SEC registry conflicts with frozen original eight")
    return result


def capture(*, user_agent: str, registry: bytes,
            loader=None, captured_utc: str | None = None,
            limit: int = MAX_NEW) -> tuple[dict, dict[str, bytes]]:
    """Acquire official source bytes for NEW issuers, without rewriting P4E."""
    p4b.contact_user_agent(user_agent)
    if type(limit) is not int or not 1 <= limit <= MAX_NEW:
        raise BroadSecStop("New SEC cohort limit must be 1 through 16")
    # SEC ticker identities can change after a corporate reorganization.
    # Keep frozen P4E CIKs unchanged; quarantine any discrepancy rather than
    # mislabelling a current ticker identity as the original 2026 issuer.
    mapping = resolve_registry(registry, allow_frozen_drift=True)
    frozen = {row["ticker"]: row["cik_10_digit"] for row in p4b.read_cohort()}
    drift = [
        {"ticker": ticker, "frozen_p4e_cik": cik,
         "current_sec_registry_cik": mapping[ticker]}
        for ticker, cik in sorted(frozen.items()) if mapping[ticker] != cik
    ]
    original = set(frozen)
    new = sorted(set(p4l.SECTORS) - original)
    if len(new) != MAX_NEW:
        raise BroadSecStop("P4L roster unexpectedly changed")
    clock = captured_utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        dt = datetime.strptime(clock, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if dt.strftime("%Y-%m-%dT%H:%M:%SZ") != clock:
            raise ValueError("noncanonical")
    except (TypeError, ValueError) as exc:
        raise BroadSecStop("Canonical source acquisition UTC clock required") from exc
    getter = loader or p4b.fetch_one
    files: dict[str, bytes] = {}
    observations = []
    for ticker in new[:limit]:
        cik = mapping[ticker]
        paths = {kind: p4b.sec_url(cik, kind)
                 for kind in ("companyfacts", "submissions")}
        raws = {}
        for kind, url in paths.items():
            raw = getter(url, user_agent)
            p4b.decode_source(raw, expected_cik=cik)
            raws[kind] = raw
            if loader is None:
                time.sleep(0.35)
        facts = p4b.decode_source(raws["companyfacts"], expected_cik=cik)
        subs = p4b.decode_source(raws["submissions"], expected_cik=cik)
        p4a.validate_identity(facts, subs, cik)
        quality = p4a.asof_quality(facts, subs, cik, dt.date().isoformat())
        source_matched = source_matched_annual_quality(
            facts, subs, cik, ticker, dt.date().isoformat())
        if quality["paper_authorized"] or quality["live_authorized"]:
            raise BroadSecStop("SEC descriptive quality attempted broker promotion")
        provenance = {}
        for kind, raw in raws.items():
            filename = f"raw/CIK{cik}-{ticker}-{kind}.json"
            files[filename] = raw
            provenance[kind] = {
                "official_url": paths[kind],
                "raw_sha256": hashlib.sha256(raw).hexdigest(),
                "source_file": filename, "byte_count": len(raw),
            }
        observations.append({
            "ticker": ticker, "cik_10_digit": cik,
            "contemporary_sector": p4l.SECTORS[ticker],
            "generic_p4a_quality_state": quality["state"],
            "generic_p4a_quality_score": quality["score"],
            "source_matched_latest_10k_quality": source_matched,
            "generic_p4a_score_not_issuer_tag_reviewed": True,
            "issuer_specific_gaap_mapping_reviewed": False,
            "fundamental_quality_for_trading_approved": False,
            "missing_generic_quality_remains_missing": quality["score"] is None,
            "source_provenance": provenance,
            "paper_authorized": False, "live_authorized": False,
        })
    report = {
        "schema": SCHEMA,
        "status": "CONTEMPORARY_SEC_SOURCE_COVERAGE_RESEARCH_ONLY",
        "capture_timestamp_utc": clock,
        "original_p4e_eight_issuer_accounting_contract_unchanged": True,
        "official_registry_url": REGISTRY_URL,
        "official_registry_sha256": hashlib.sha256(registry).hexdigest(),
        "original_eight_ciks_checked_against_official_registry": True,
        "original_eight_registry_identity_all_match": not drift,
        "original_eight_identity_drift_quarantined": drift,
        "drifted_original_eight_issuer_scores_not_joined_to_current_cik": True,
        "p4l_roster_size": len(p4l.SECTORS),
        "new_issuers_in_roster": MAX_NEW,
        "new_issuers_captured": len(observations),
        "new_issuers_generic_score_available": sum(
            row["generic_p4a_quality_score"] is not None for row in observations),
        "new_issuers_source_matched_score_available": sum(
            row["source_matched_latest_10k_quality"]["score"] is not None
            for row in observations),
        "new_issuers_bank_diagnostics_available": sum(
            row["source_matched_latest_10k_quality"]
               .get("bank_diagnostics", {}).get("state")
            == "BANK_LATEST_10K_DESCRIPTIVE_ONLY" for row in observations),
        "new_issuer_source_matched_scores_are_descriptive_not_trade_ready": True,
        "new_issuer_specific_accounting_review_complete": False,
        "historical_point_in_time_universe_or_fundamentals_verified": False,
        "analyst_revisions_available": False,
        "sector_neutral_quality_comparison_validated": False,
        "historic_stock_alpha_backtest_eligible": False,
        "source_count": len(files),
        "observations": observations,
        "broker_orders": 0, "paper_authorized": False,
        "live_authorized": False, "trading_authorized": False,
    }
    files["official-sec-ticker-registry.json"] = registry
    return report, files


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--limit", type=int, default=MAX_NEW)
    args = parser.parse_args()
    agent = p4b.contact_user_agent(os.environ.get("SEC_USER_AGENT", ""))
    # Acquire into memory before writing anything, including the registry.
    registry = registry_bytes(agent)
    report, files = capture(user_agent=agent, registry=registry, limit=args.limit)
    root = args.output_dir
    if root.exists() and any(root.iterdir()):
        raise BroadSecStop("Refuse to overwrite existing source archive")
    for name, raw in files.items():
        dest = root / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
    (root / "manifest.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("P4N official SEC prospective coverage:", report["new_issuers_captured"],
          "of 16 new issuers; generic scores:",
          report["new_issuers_generic_score_available"],
          "source-matched descriptive scores:",
          report["new_issuers_source_matched_score_available"])
    print("Original eight P4E untouched; SEC registry identity drift quarantined:",
          [row["ticker"] for row in report["original_eight_identity_drift_quarantined"]])
    print("No historical alpha or stock orders.")


if __name__ == "__main__":
    main()
