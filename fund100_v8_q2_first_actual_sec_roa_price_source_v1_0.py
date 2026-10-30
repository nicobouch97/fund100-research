"""V8-Q2 original *new* SEC annual net-income + completed-price source capture.

Research ONLY. No PAPER/LIVE broker, trade, private state, release, signing,
or source-based live promotion. Historical original gross-profit V8-QM and
original P4B issuer CIKs are not overwritten. The new Q2 hypothesis was
registered on Oct 29 *after* seeing the original gross-profit gaps.

Actual acquisition needs real SEC User-Agent and takes place from Oct 30,
2026 onward. A source-derived candidate is not independently proven share
eligibility, causal adjusted price vintage, repeatable alpha, or live authority.
"""
from __future__ import annotations

from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
import json
import os
import time

import fund100_stock_broad_momentum_p4l_v1_0 as cohort
import fund100_stock_broad_sec_coverage_p4n_v1_0 as sec
import fund100_stock_sec_quality_p4a_v1_0 as quality
import fund100_stock_sec_source_p4b_v1_0 as intake
import fund100_v7_m1_original_24stock_momentum_forward_v1_0 as prices
import fund100_v8_qm_first_original_sec_price_capture_v1_0 as prior
import fund100_v8_q2_net_income_roa_momentum_v1_0 as q2

SCHEMA = "FUND100_V8_Q2_FIRST_NEW_OFFICIAL_SEC_ROA_AND_COMPLETED_PRICE_SOURCE_V1"
NO_BROKER_HTTP = NO_PRIVATE_GITHUB_WRITES = NO_TRADING = True
NO_PUBLIC_GITHUB_RELEASES = True
MIN_NEW_SOURCE = q2.PREDECLARED_EARLIEST_SOURCE_UTC
MAX_COMPANIES = 24

class Q2SourceHold(RuntimeError):
    pass


def _same_filing_usd(facts: dict, accession: str, filed: date, end: date,
                     tag: str, *, annual: bool):
    """Only original 10-K's annual flow or its matching instant balance.

    Missing concept is absent source, not estimated zero. True negative
    net income is preserved as a signed integer, and conflicts STOP.
    """
    concepts = facts.get("facts", {}).get("us-gaap", {})
    if type(concepts) is not dict:
        raise Q2SourceHold("Official GAAP source malformed")
    data = concepts.get(tag)
    if data is None:
        return None
    try:
        items = data["units"]["USD"]
    except (KeyError, TypeError):
        return None
    if type(items) is not list:
        raise Q2SourceHold("Original annual USD concept malformed")
    matched = []
    for row in items:
        if type(row) is not dict:
            raise Q2SourceHold("SEC annual financial fact not a row")
        if (row.get("accn") != accession or row.get("filed") != filed.isoformat()
            or row.get("end") != end.isoformat() or row.get("form") != "10-K"):
            continue
        if annual:
            try:
                start = date.fromisoformat(row["start"])
            except (ValueError, KeyError, TypeError):
                continue
            if not 330 <= (end-start).days <= 400:
                continue
        elif row.get("start") is not None:
            continue
        val = row.get("val")
        if type(val) is not int:
            raise Q2SourceHold("Unverifiable SEC integer annual USD fact")
        matched.append(val)
    if len(set(matched)) > 1:
        raise Q2SourceHold("Conflicting same-10K original USD annual facts")
    return matched[0] if matched else None


def latest_original_10k_roa(facts, submissions, *, cik: str, asof: datetime):
    """Use latest eligible 10-K, never backfill from a convenient older 10-K.

    SEC filing date is treated available after full next UTC date, not
    claimed independently as exact XBRL publication timestamp.
    """
    try:
        quality.validate_identity(facts, submissions, cik)
        index = quality.submissions_index(submissions)
    except Exception:
        raise Q2SourceHold("Real original 10-K accession/issuer index invalid") from None
    eligible = []
    for accession, row in index.items():
        if row["form"] != "10-K":
            continue
        try:
            filed = date.fromisoformat(row["filed"])
            end = date.fromisoformat(row["end"])
        except (ValueError, TypeError):
            raise Q2SourceHold("Malformed SEC report/filing chronology") from None
        available = datetime.combine(
            filed + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
        if end <= filed and (asof.date() > filed) and (
            asof - timedelta(days=540) <= available <= asof):
            eligible.append((end, filed, accession))
    if not eligible:
        return None
    end, filed, accession = max(eligible)
    income = _same_filing_usd(facts, accession, filed, end,
                             "NetIncomeLoss", annual=True)
    assets = _same_filing_usd(facts, accession, filed, end,
                             "Assets", annual=False)
    if income is None or assets is None or assets <= 0:
        return None
    # Keep signed loss/zero facts to distinguish source coverage from quality.
    return {
        "matched_annual_net_income_usd": str(income),
        "matched_annual_assets_usd": str(assets),
        "original_10k_filed_available_utc":
            (filed + timedelta(days=1)).isoformat() + "T00:00:00Z",
        "source_accession": accession,
    }


def analyze_sources(*, registry: bytes, source_files: dict[str, bytes],
                    price_panel, acquired_utc: str):
    clock = q2._utc(acquired_utc)
    if clock < q2._utc(MIN_NEW_SOURCE):
        raise Q2SourceHold("Original Oct 29 source cannot become next-vintage Q2")
    try:
        names = prior._cohort()
        ciks, drift = prior._current_registry_with_original_identity_quarantine(registry)
        frame = cohort.validate_prices(price_panel)
        cohort.p4g.verify_original_nyse_source_sessions(frame.index)
    except Exception:
        raise Q2SourceHold("Actual new-vintage company identity or NYSE source invalid") from None
    if set(ciks) != set(names) or len(frame) < q2.LOOKBACK_SESSIONS+1:
        raise Q2SourceHold("Missing original 24-issuer registered source panel")
    session = frame.index[-1].date()
    if not 1 <= (clock.date() - session).days <= 5:
        raise Q2SourceHold("No actually completed source session")
    prices_bytes = cohort.canonical_csv(frame).encode("utf-8")
    psha = sha256(prices_bytes).hexdigest()
    snap = lambda n: format(Decimal(str(n)), ".8f")
    rows, receipts = [], []
    for ticker in names:
        cik = ciks[ticker]
        prefix = f"raw/CIK{cik}-{ticker}"
        keyfacts = prefix + "-companyfacts.json"
        keysubs = prefix + "-submissions.json"
        if (keyfacts not in source_files or keysubs not in source_files
            or type(source_files[keyfacts]) is not bytes
            or type(source_files[keysubs]) is not bytes):
            raise Q2SourceHold("Missing complete official original SEC bytes")
        try:
            facts = intake.decode_source(source_files[keyfacts], expected_cik=cik)
            subs = intake.decode_source(source_files[keysubs], expected_cik=cik)
        except Exception:
            raise Q2SourceHold("Raw SEC source identity mismatch") from None
        digest_f = sha256(source_files[keyfacts]).hexdigest()
        digest_s = sha256(source_files[keysubs]).hexdigest()
        receipts.append({
            "symbol": ticker, "current_registry_cik": cik,
            "official_companyfacts_sha256": digest_f,
            "official_submissions_sha256": digest_s,
        })
        proof = sha256((digest_f+digest_s).encode("ascii")).hexdigest()
        is_drift = ticker in drift
        result = None if is_drift else latest_original_10k_roa(
            facts, subs, cik=cik, asof=clock)
        accession_digest = (sha256(
            (result["source_accession"]+digest_f+digest_s).encode("ascii")
        ).hexdigest() if result is not None else None)
        rows.append({
            "symbol": ticker, "sector": prior._label(cohort.SECTORS[ticker]),
            # The original contemporary cohort asserts this; actual listing
            # eligibility requires independent venue proof, still UNVERIFIED.
            "ordinary_share_asof": True,
            "frozen_issuer_identity_status": (
                "QUARANTINED_ID_DRIFT" if is_drift else "FROZEN_ORIGINAL_ID_MATCH"),
            "original_raw_sec_receipt_sha256": proof,
            "matched_annual_net_income_usd": (
                result["matched_annual_net_income_usd"] if result else None),
            "matched_annual_assets_usd": (
                result["matched_annual_assets_usd"] if result else None),
            "original_10k_filed_available_utc": (
                result["original_10k_filed_available_utc"] if result else None),
            "original_10k_accession_sha256": accession_digest,
            "adjusted_close_minus252": snap(frame[ticker].iloc[
                -1-q2.LOOKBACK_SESSIONS]),
            "adjusted_close_minus42": snap(frame[ticker].iloc[
                -1-q2.SKIP_RECENT_SESSIONS]),
            "original_price_panel_sha256": psha,
        })
    if len(receipts) != MAX_COMPANIES:
        raise Q2SourceHold("Incomplete original-source receipt set")
    try:
        selection = q2.select(
            rows=rows, benchmark_minus252=snap(frame["SPY"].iloc[
                -1-q2.LOOKBACK_SESSIONS]),
            benchmark_minus42=snap(frame["SPY"].iloc[
                -1-q2.SKIP_RECENT_SESSIONS]),
            decision_utc=acquired_utc,
            price_session=session.isoformat(),
            source_mode=q2.SOURCE_MODE)
    except q2.Q2Hold as exc:
        raise Q2SourceHold("Original SEC/price selection malformed: "+str(exc)) from exc
    return {
        "schema": SCHEMA,
        "status": "ACTUAL_PUBLIC_ORIGINAL_Q2_SOURCE_ACQUIRED_RESEARCH_ONLY",
        "first_eligible_new_source_not_before_utc": MIN_NEW_SOURCE,
        "source_acquired_utc": acquired_utc,
        "last_completed_market_session": session.isoformat(),
        "current_original_registry_sha256": sha256(registry).hexdigest(),
        "completed_original_price_panel_sha256": psha,
        "complete_current_original_24_sec_source_receipts": receipts,
        "quarantined_historical_issuer_identity_drift": sorted(drift),
        "source_rows": rows,
        "source_derived_research_selection": selection,
        "source_mode_actual_http_only_in_main_workflow": True,
        "source_input_proof_not_independent_listing_or_vendor_authentication": True,
        "original_archive_not_yet_permanently_immutable": True,
        "forward_63_sessions_not_observed": True,
        "live_order_authorized": False,
        "broker_gets": 0, "broker_posts": 0, "broker_orders": 0,
    }, prices_bytes



def audit_frozen_source_coverage(original_root: Path) -> dict:
    """Explain first-source gaps without changing the frozen selection.

    This is a separately dated, reproducible *diagnostic*, not a substitute
    taxonomy for the preregistered NetIncomeLoss / Assets Q2 factor. First
    independently rederive the exact original report from its 48 SEC files.
    """
    import fund100_v8_q2_frozen_forward_63_marks_v1_0 as marks

    report, screen, _, captured = marks._read_source(original_root)
    receipts = {r["symbol"]: r for r in
                report["complete_current_original_24_sec_source_receipts"]}
    rows = {r["symbol"]: r for r in report["source_rows"]}
    gaps = screen["source_gaps"]
    if (type(gaps) is not list or len(set(gaps)) != len(gaps)
        or any(s not in receipts or s not in rows for s in gaps)):
        raise Q2SourceHold("Frozen Q2 gap roster inconsistent with original SEC archive")
    observations = []
    now = q2._utc(captured)
    for symbol in sorted(gaps):
        row, receipt = rows[symbol], receipts[symbol]
        cik = receipt["current_registry_cik"]
        entry = {
            "symbol": symbol,
            "frozen_issuer_identity_status": row["frozen_issuer_identity_status"],
            "current_registry_cik": cik,
            "original_raw_sec_receipt_sha256": row["original_raw_sec_receipt_sha256"],
            "diagnostic_only_not_retroactive_eligibility": True,
        }
        if row["frozen_issuer_identity_status"] == "QUARANTINED_ID_DRIFT":
            # Never use facts from a new CIK as the original issuer's facts.
            entry["reason"] = "ORIGINAL_ISSUER_CIK_DRIFT_QUARANTINED"
            entry["latest_eligible_10k_accession"] = None
            entry["same_filing_profit_loss_usd"] = None
            entry["same_filing_common_stockholder_income_usd"] = None
            entry["same_filing_noncontrolling_income_usd"] = None
            entry["profit_less_reported_nci_usd_diagnostic_only"] = None
            observations.append(entry)
            continue
        if row["frozen_issuer_identity_status"] != "FROZEN_ORIGINAL_ID_MATCH":
            raise Q2SourceHold("Unknown frozen issuer status in source gap")
        prefix = original_root / f"raw/CIK{cik}-{symbol}"
        try:
            facts = intake.decode_source(
                (Path(str(prefix) + "-companyfacts.json")).read_bytes(),
                expected_cik=cik)
            subs = intake.decode_source(
                (Path(str(prefix) + "-submissions.json")).read_bytes(),
                expected_cik=cik)
            quality.validate_identity(facts, subs, cik)
            index = quality.submissions_index(subs)
        except Exception as exc:
            raise Q2SourceHold("Original SEC diagnostic issuer facts invalid") from exc
        eligible = []
        for accession, item in index.items():
            if item["form"] != "10-K":
                continue
            try:
                filed = date.fromisoformat(item["filed"])
                end = date.fromisoformat(item["end"])
            except (TypeError, ValueError) as exc:
                raise Q2SourceHold("Original diagnostic 10-K chronology invalid") from exc
            available = datetime.combine(
                filed + timedelta(days=1), datetime.min.time(),
                tzinfo=timezone.utc)
            if (end <= filed and now.date() > filed
                and now - timedelta(days=540) <= available <= now):
                eligible.append((end, filed, accession))
        if not eligible:
            entry.update({
                "reason": "NO_ELIGIBLE_ORIGINAL_10K",
                "latest_eligible_10k_accession": None,
                "same_filing_profit_loss_usd": None,
                "same_filing_common_stockholder_income_usd": None,
                "same_filing_noncontrolling_income_usd": None,
                "profit_less_reported_nci_usd_diagnostic_only": None,
            })
            observations.append(entry)
            continue
        end, filed, accession = max(eligible)
        income = _same_filing_usd(
            facts, accession, filed, end, "NetIncomeLoss", annual=True)
        assets = _same_filing_usd(
            facts, accession, filed, end, "Assets", annual=False)
        alternative = _same_filing_usd(
            facts, accession, filed, end, "ProfitLoss", annual=True)
        # Independent accounting concepts, never substituted into Q2.
        # Common-stockholder earnings may differ from parent earnings due
        # to preferred dividends. Reported NCI can be incomplete (e.g.
        # redeemable NCI), so even an arithmetic bridge is not certified
        # parent net income. Never treat an absent NCI fact as zero.
        common_income = _same_filing_usd(
            facts, accession, filed, end,
            "NetIncomeLossAvailableToCommonStockholdersBasic", annual=True)
        noncontrolling_income = _same_filing_usd(
            facts, accession, filed, end,
            "NetIncomeLossAttributableToNoncontrollingInterest", annual=True)
        partial_bridge = (
            alternative - noncontrolling_income
            if alternative is not None and noncontrolling_income is not None
            else None)
        if income is not None and assets is not None and assets > 0:
            raise Q2SourceHold("SEC diagnostic contradicts frozen source gap")
        missing = []
        if income is None:
            missing.append("NET_INCOME_LOSS")
        if assets is None or assets <= 0:
            missing.append("POSITIVE_ASSETS")
        entry.update({
            "reason": "MISSING_SAME_10K_" + "_AND_".join(missing),
            "latest_eligible_10k_accession": accession,
            "latest_eligible_10k_filed": filed.isoformat(),
            "latest_eligible_10k_report_end": end.isoformat(),
            "same_filing_net_income_loss_usd": (
                str(income) if income is not None else None),
            "same_filing_assets_usd": (
                str(assets) if assets is not None else None),
            "same_filing_profit_loss_usd": (
                str(alternative) if alternative is not None else None),
            "same_filing_common_stockholder_income_usd": (
                str(common_income) if common_income is not None else None),
            "same_filing_noncontrolling_income_usd": (
                str(noncontrolling_income)
                if noncontrolling_income is not None else None),
            "profit_less_reported_nci_usd_diagnostic_only": (
                str(partial_bridge) if partial_bridge is not None else None),
            "missing_nci_never_assumed_zero": True,
            "partial_nci_bridge_not_certified_parent_income": True,
            "profit_loss_is_not_substituted_for_frozen_net_income_loss": True,
        })
        observations.append(entry)
    return {
        "schema": "FUND100_V8_Q2_FROZEN_ORIGINAL_SEC_GAP_DIAGNOSTIC_V1",
        "original_source_acquired_utc": captured,
        "original_source_report_sha256": sha256(
            (original_root / marks.FIRST_SOURCE_REPORT).read_bytes()).hexdigest(),
        "source_gap_count": len(observations),
        "source_gaps": observations,
        "original_frozen_selection_symbols": (
            screen["selection_candidate"]["symbols"]
            if screen["selection_candidate"] is not None else None),
        "frozen_selection_and_original_source_unchanged": True,
        "alternative_taxonomy_not_approved_for_original_selection": True,
        "survivorship_safe_or_alpha_proven": False,
        "live_order_authorized": False,
        "broker_gets": 0, "broker_posts": 0, "broker_orders": 0,
    }


def main():
    from argparse import ArgumentParser
    parser = ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--output-dir", type=Path)
    mode.add_argument("--audit-original-dir", type=Path)
    parser.add_argument("--audit-output", type=Path)
    args = parser.parse_args()
    if not (NO_BROKER_HTTP and NO_PRIVATE_GITHUB_WRITES and
            NO_PUBLIC_GITHUB_RELEASES and NO_TRADING):
        raise Q2SourceHold("Original research-only no-broker source policy changed")
    if args.audit_original_dir is not None:
        if args.audit_output is None:
            raise Q2SourceHold("Original archive diagnostic requires output path")
        audit = audit_frozen_source_coverage(args.audit_original_dir)
        args.audit_output.parent.mkdir(parents=True, exist_ok=True)
        args.audit_output.write_text(
            json.dumps(audit, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        print("Q2 frozen original SEC coverage audited; original basket unchanged.")
        return
    if args.audit_output is not None:
        raise Q2SourceHold("Source acquisition cannot write diagnostic output")
    now = datetime.now(timezone.utc)
    if now < q2._utc(MIN_NEW_SOURCE):
        raise Q2SourceHold("Cannot acquire pre-registration Q2 evidence")
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise Q2SourceHold("Never overwrite first-seen source bytes")
    agent = intake.contact_user_agent(os.environ.get("SEC_USER_AGENT",""))
    registry = sec.registry_bytes(agent)
    ciks, drift = prior._current_registry_with_original_identity_quarantine(registry)
    raw = {}
    for ticker in prior._cohort():
        cik = ciks[ticker]
        for kind in ("companyfacts","submissions"):
            response = intake.fetch_one(intake.sec_url(cik,kind),agent)
            intake.decode_source(response,expected_cik=cik)
            raw[f"raw/CIK{cik}-{ticker}-{kind}.json"] = response
            time.sleep(.18)
    panel = prices._later_original_public_prices()
    if len(panel) and panel.index[-1].date() >= now.date():
        panel = cohort.validate_prices(panel.iloc[:-1])
    observed = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report, price_bytes = analyze_sources(
        registry=registry, source_files=raw,
        price_panel=panel, acquired_utc=observed)
    root = args.output_dir
    root.mkdir(parents=True,exist_ok=True)
    (root/"current-official-sec-registry.json").write_bytes(registry)
    (root/"original-24-issuer-completed-adjusted-prices.csv").write_bytes(price_bytes)
    for path, data in raw.items():
        destination=root/path
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_bytes(data)
    (root/"first-new-vintage-q2-source-coverage-and-candidate-NO-LIVE.json").write_text(
        json.dumps(report,sort_keys=True,indent=2)+"\n", encoding="utf-8")
    result=report["source_derived_research_selection"]
    print("Q2 ACTUAL NEW-VINTAGE SEC and COMPLETED PRICE SOURCE CAPTURED.")
    print("24 original current ticker raw SEC receipts:",len(raw))
    print("Positive same-10K NetIncome/Assets source:",result[
        "matched_positive_annual_net_income_assets"])
    print("Frozen CIK identity quarantine:",len(drift))
    print("Q2 after-source selection status:",result["status"])
    print("Research ONLY, no signed strategy promotion or broker orders.")


if __name__=="__main__":
    main()
