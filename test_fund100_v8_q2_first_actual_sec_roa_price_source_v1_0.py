"""Offline synthetic SEC provenance checks for new, strictly post-registration Q2."""
from datetime import timedelta
from hashlib import sha256
import json
from pathlib import Path

import pytest

import fund100_stock_broad_sec_coverage_p4n_v1_0 as sec
import fund100_v8_qm_first_original_sec_price_capture_v1_0 as original
import fund100_v8_q2_first_actual_sec_roa_price_source_v1_0 as app
from test_fund100_v8_qm_first_original_sec_price_capture_v1_0 import inputs

NEW = "2026-10-30T08:00:00Z"

def sources():
    registry,raw,panel=inputs()
    mapping=sec.resolve_registry(registry)
    for i,(ticker,cik) in enumerate(sorted(mapping.items())):
        key=f"raw/CIK{cik}-{ticker}-companyfacts.json"
        doc=json.loads(raw[key])
        gross=doc["facts"]["us-gaap"]["GrossProfit"]["units"]["USD"][0]
        ni={k:v for k,v in gross.items()}
        ni["val"]=12_000_000+i*500_000
        doc["facts"]["us-gaap"]["NetIncomeLoss"]={
            "units":{"USD":[ni]}}
        raw[key]=json.dumps(doc).encode()
    return registry,raw,panel

def evaluate(**kwargs):
    registry,source_files,price_panel=sources()
    params=dict(registry=registry,source_files=source_files,
                price_panel=price_panel,acquired_utc=NEW)
    params.update(kwargs)
    return app.analyze_sources(**params)

def test_new_original_sec_10k_roa_source_and_completed_prices_research_only():
    result,prices_bytes=evaluate()
    assert result["schema"]==app.SCHEMA
    assert result["source_acquired_utc"]==NEW
    assert result["last_completed_market_session"]=="2026-10-28"
    assert result["completed_original_price_panel_sha256"]==sha256(prices_bytes).hexdigest()
    assert len(result["complete_current_original_24_sec_source_receipts"])==24
    selected=result["source_derived_research_selection"]
    assert selected["matched_positive_annual_net_income_assets"]==24
    assert selected["selection_candidate"] is not None
    assert len(selected["selection_candidate"]["symbols"])==8
    assert not selected["live_order_authorized"]
    assert not result["live_order_authorized"]
    assert result["broker_gets"]==result["broker_posts"]==result["broker_orders"]==0
    assert result["original_archive_not_yet_permanently_immutable"]
    assert not selected["source_inputs_authenticated_by_external_receipt"]

def test_old_original_pre_registered_vintage_cannot_be_rebranded_new_q2():
    with pytest.raises((app.Q2SourceHold,ValueError)):
        evaluate(acquired_utc="2026-10-29T23:59:59Z")

def test_signed_net_income_is_preserved_but_loss_is_not_positive_quality():
    reg,raw,prices=sources()
    cik=sec.resolve_registry(reg)["AAPL"]
    path=f"raw/CIK{cik}-AAPL-companyfacts.json"
    doc=json.loads(raw[path])
    doc["facts"]["us-gaap"]["NetIncomeLoss"]["units"]["USD"][0]["val"]=-1_000_000
    raw[path]=json.dumps(doc).encode()
    report,_=evaluate(registry=reg,source_files=raw,price_panel=prices)
    screen=report["source_derived_research_selection"]
    assert screen["matched_positive_annual_net_income_assets"]==23
    assert screen["observed_nonpositive_annual_net_income"]==["AAPL"]
    assert "AAPL" not in screen["selection_candidate"]["symbols"]
    assert report["source_rows"][0]["matched_annual_net_income_usd"] is not None

def test_unavailable_same_filing_net_income_never_backfills_from_older_10k():
    reg,raw,prices=sources()
    cik=sec.resolve_registry(reg)["AAPL"]
    path=f"raw/CIK{cik}-AAPL-companyfacts.json"
    obj=json.loads(raw[path])
    obj["facts"]["us-gaap"].pop("NetIncomeLoss")
    raw[path]=json.dumps(obj).encode()
    report,_=evaluate(registry=reg,source_files=raw,price_panel=prices)
    s=report["source_derived_research_selection"]
    assert s["matched_positive_annual_net_income_assets"]==23
    assert s["source_gaps"]==["AAPL"]
    assert not report["live_order_authorized"]

def test_cross_accession_and_nonannual_comparative_rows_cannot_be_eligible():
    reg,raw,prices=sources()
    cik=sec.resolve_registry(reg)["MSFT"]
    key=f"raw/CIK{cik}-MSFT-companyfacts.json"
    obj=json.loads(raw[key])
    obj["facts"]["us-gaap"]["NetIncomeLoss"]["units"]["USD"][0]["accn"]="0123456789-26-123456"
    raw[key]=json.dumps(obj).encode()
    out,_=evaluate(registry=reg,source_files=raw,price_panel=prices)
    assert "MSFT" in out["source_derived_research_selection"]["source_gaps"]

def test_conflicting_duplicate_original_10k_net_income_fails_closed():
    reg,raw,prices=sources()
    cik=sec.resolve_registry(reg)["KO"]
    key=f"raw/CIK{cik}-KO-companyfacts.json"
    obj=json.loads(raw[key])
    annual=obj["facts"]["us-gaap"]["NetIncomeLoss"]["units"]["USD"]
    row=dict(annual[0]);row["val"]+=1
    annual.append(row)
    raw[key]=json.dumps(obj).encode()
    with pytest.raises(app.Q2SourceHold, match="Conflicting"):
        evaluate(registry=reg,source_files=raw,price_panel=prices)

def test_current_registry_cik_drift_quarantined_with_all_current_raw_receipts():
    reg,raw,prices=sources()
    mapping=sec.resolve_registry(reg)
    ticker="XOM"
    old=mapping[ticker]
    current="0099999988"
    assert current not in mapping.values()
    doc=json.loads(reg)
    for entry in doc.values():
        if entry["ticker"]==ticker:
            entry["cik_str"]=int(current)
            break
    for kind in ("companyfacts","submissions"):
        oldkey=f"raw/CIK{old}-{ticker}-{kind}.json"
        newkey=f"raw/CIK{current}-{ticker}-{kind}.json"
        data=json.loads(raw.pop(oldkey))
        data["cik"]=int(current)
        if kind=="companyfacts":
            for tag in ("GrossProfit","NetIncomeLoss","Assets"):
                data["facts"]["us-gaap"][tag]["units"]["USD"][0]["accn"]=f"{current}-26-000001"
        else:
            data["filings"]["recent"]["accessionNumber"]=[f"{current}-26-000001"]
        raw[newkey]=json.dumps(data).encode()
    report,_=evaluate(registry=json.dumps(doc).encode(),
                      source_files=raw,price_panel=prices)
    assert report["quarantined_historical_issuer_identity_drift"]==["XOM"]
    screen=report["source_derived_research_selection"]
    assert screen["matched_positive_annual_net_income_assets"]==23
    assert "XOM" in screen["source_gaps"]
    assert "XOM" not in screen["selection_candidate"]["symbols"]
    assert len(report["complete_current_original_24_sec_source_receipts"])==24

@pytest.mark.parametrize("corruption",[
    "missing_sec","mismatched_cik","missing_price","stale_session","same_day_bar",
])
def test_all_source_gaps_fail_closed_without_partial_snapshot(corruption):
    reg,raw,prices=sources()
    if corruption=="missing_sec":
        raw.pop(next(iter(raw)))
    elif corruption=="mismatched_cik":
        key=next(k for k in raw if "companyfacts" in k)
        doc=json.loads(raw[key]);doc["cik"]=999999999
        raw[key]=json.dumps(doc).encode()
    elif corruption=="missing_price":
        prices=prices.iloc[:200]
    elif corruption=="stale_session":
        prices.index=prices.index-timedelta(days=10)
    elif corruption=="same_day_bar":
        ix=prices.index
        prices.index=ix[:-1].append(type(ix)(["2026-10-30"]))
    with pytest.raises((app.Q2SourceHold,ValueError)):
        evaluate(registry=reg,source_files=raw,price_panel=prices)

def test_deployed_source_workflow_has_only_public_get_and_existing_sec_identity():
    assert all((app.NO_BROKER_HTTP,app.NO_PRIVATE_GITHUB_WRITES,
                app.NO_PUBLIC_GITHUB_RELEASES,app.NO_TRADING))
    code=Path(app.__file__).read_text()
    for bad in ('method="POST"','method="PUT"','method="PATCH"',
                "ALPACA_LIVE_KEY","PRIVATE_STATE_PRODUCTION_WRITE_TOKEN"):
        assert bad not in code
    workflow=Path(".github/workflows/fund100-v8-q2-first-new-sec-price-source.yml").read_text()
    assert "contents: read" in workflow and "actions: read" in workflow
    assert "contents: write" not in workflow
    assert "secrets.FUND100_SEC_USER_AGENT" in workflow
    assert "secrets.ALPACA_LIVE_KEY" not in workflow
    assert "fund100-live-broker" not in workflow
    assert "  workflow_dispatch:" not in workflow
    # A reviewed push to main is an idempotent first-source fallback if the
    # scheduled GitHub Actions event is delayed. PRs cannot acquire sources.
    assert ("if: (github.event_name == 'schedule' || "
            "github.event_name == 'push') && "
            "github.ref == 'refs/heads/main'") in workflow
    assert 'if: steps.first.outputs.acquire == \'true\'' in workflow
    assert '"20261030"' in workflow and '"20261106"' in workflow
    assert 'actions/artifacts?name=fund100-v8-q2-new-original-first' in workflow
    assert 'cancel-in-progress: false' in workflow
    assert 'fund100-v8-q2-new-original-first' in workflow
    audit=Path(".github/workflows/fund100-live-static-audit.yml").read_text()
    for p in (
        "fund100_v8_q2_first_actual_sec_roa_price_source_v1_0.py",
        "test_fund100_v8_q2_first_actual_sec_roa_price_source_v1_0.py",
        ".github/workflows/fund100-v8-q2-first-new-sec-price-source.yml",
    ):
        assert '      - "'+p+'"' in audit


def _write_frozen_audit_archive(root, registry, raw, panel):
    """Synthetic first-source archive, byte-for-byte like the original layout."""
    report, prices = app.analyze_sources(
        registry=registry, source_files=raw, price_panel=panel,
        acquired_utc=NEW)
    root.mkdir(parents=True, exist_ok=True)
    (root/"current-official-sec-registry.json").write_bytes(registry)
    (root/"original-24-issuer-completed-adjusted-prices.csv").write_bytes(prices)
    (root/"first-new-vintage-q2-source-coverage-and-candidate-NO-LIVE.json").write_text(
        json.dumps(report, sort_keys=True, indent=2)+"\n")
    for name, data in raw.items():
        path=root/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return report


def test_frozen_gap_audit_has_no_new_selection_or_source_changes(tmp_path):
    registry, raw, panel = sources()
    report = _write_frozen_audit_archive(tmp_path, registry, raw, panel)
    before = (tmp_path/"first-new-vintage-q2-source-coverage-and-candidate-NO-LIVE.json").read_bytes()
    audit = app.audit_frozen_source_coverage(tmp_path)
    assert audit["source_gap_count"] == 0
    assert audit["original_source_report_sha256"] == sha256(before).hexdigest()
    assert audit["original_frozen_selection_symbols"] == report[
        "source_derived_research_selection"]["selection_candidate"]["symbols"]
    assert audit["frozen_selection_and_original_source_unchanged"]
    assert not audit["live_order_authorized"]
    assert audit["broker_gets"] == audit["broker_posts"] == audit["broker_orders"] == 0
    assert (tmp_path/"first-new-vintage-q2-source-coverage-and-candidate-NO-LIVE.json").read_bytes() == before


def test_frozen_gap_audit_reports_profitloss_without_retroactive_substitution(tmp_path):
    registry, raw, panel = sources()
    cik = sec.resolve_registry(registry)["AVGO"]
    key = f"raw/CIK{cik}-AVGO-companyfacts.json"
    obj = json.loads(raw[key])
    same_10k = dict(obj["facts"]["us-gaap"]["NetIncomeLoss"]["units"]["USD"][0])
    obj["facts"]["us-gaap"]["ProfitLoss"] = {"units": {"USD": [same_10k]}}
    del obj["facts"]["us-gaap"]["NetIncomeLoss"]
    raw[key] = json.dumps(obj).encode()
    report = _write_frozen_audit_archive(tmp_path, registry, raw, panel)
    assert "AVGO" in report["source_derived_research_selection"]["source_gaps"]
    frozen_symbols = report["source_derived_research_selection"][
        "selection_candidate"]["symbols"]
    assert "AVGO" not in frozen_symbols
    audit = app.audit_frozen_source_coverage(tmp_path)
    assert audit["source_gap_count"] == 1
    gap = audit["source_gaps"][0]
    assert gap["symbol"] == "AVGO"
    assert gap["reason"] == "MISSING_SAME_10K_NET_INCOME_LOSS"
    assert gap["same_filing_profit_loss_usd"] == str(same_10k["val"])
    assert gap["same_filing_assets_usd"] is not None
    assert gap["profit_loss_is_not_substituted_for_frozen_net_income_loss"]
    assert audit["original_frozen_selection_symbols"] == frozen_symbols


def test_frozen_gap_audit_explicit_nci_and_common_income_are_diagnostic_only(tmp_path):
    registry, raw, panel = sources()
    cik = sec.resolve_registry(registry)["AVGO"]
    key = f"raw/CIK{cik}-AVGO-companyfacts.json"
    obj = json.loads(raw[key])
    gaap = obj["facts"]["us-gaap"]
    annual = dict(gaap["NetIncomeLoss"]["units"]["USD"][0])
    del gaap["NetIncomeLoss"]
    gaap["ProfitLoss"] = {"units": {"USD": [dict(annual)]}}
    nci = dict(annual, val=2_000_000)
    common = dict(annual, val=annual["val"] - nci["val"])
    gaap["NetIncomeLossAttributableToNoncontrollingInterest"] = {
        "units": {"USD": [nci]}}
    gaap["NetIncomeLossAvailableToCommonStockholdersBasic"] = {
        "units": {"USD": [common]}}
    raw[key] = json.dumps(obj).encode()
    report = _write_frozen_audit_archive(tmp_path, registry, raw, panel)
    frozen = report["source_derived_research_selection"]["selection_candidate"]["symbols"]
    assert "AVGO" not in frozen
    audit = app.audit_frozen_source_coverage(tmp_path)
    gap = audit["source_gaps"][0]
    assert gap["same_filing_profit_loss_usd"] == str(annual["val"])
    assert gap["same_filing_noncontrolling_income_usd"] == "2000000"
    assert gap["same_filing_common_stockholder_income_usd"] == str(common["val"])
    assert gap["profit_less_reported_nci_usd_diagnostic_only"] == str(common["val"])
    assert gap["partial_nci_bridge_not_certified_parent_income"]
    assert gap["missing_nci_never_assumed_zero"]
    assert audit["original_frozen_selection_symbols"] == frozen
    assert not audit["live_order_authorized"]


def test_frozen_gap_audit_missing_nci_is_not_implicitly_zero(tmp_path):
    registry, raw, panel = sources()
    cik = sec.resolve_registry(registry)["AVGO"]
    key = f"raw/CIK{cik}-AVGO-companyfacts.json"
    obj = json.loads(raw[key])
    gaap = obj["facts"]["us-gaap"]
    annual = dict(gaap["NetIncomeLoss"]["units"]["USD"][0])
    gaap["ProfitLoss"] = {"units": {"USD": [annual]}}
    del gaap["NetIncomeLoss"]
    raw[key] = json.dumps(obj).encode()
    _write_frozen_audit_archive(tmp_path, registry, raw, panel)
    gap = app.audit_frozen_source_coverage(tmp_path)["source_gaps"][0]
    assert gap["same_filing_noncontrolling_income_usd"] is None
    assert gap["same_filing_common_stockholder_income_usd"] is None
    assert gap["profit_less_reported_nci_usd_diagnostic_only"] is None


def test_frozen_gap_audit_conflicting_nci_facts_fail_closed(tmp_path):
    registry, raw, panel = sources()
    cik = sec.resolve_registry(registry)["AVGO"]
    key = f"raw/CIK{cik}-AVGO-companyfacts.json"
    obj = json.loads(raw[key])
    gaap = obj["facts"]["us-gaap"]
    annual = dict(gaap["NetIncomeLoss"]["units"]["USD"][0])
    gaap["ProfitLoss"] = {"units": {"USD": [annual]}}
    del gaap["NetIncomeLoss"]
    gaap["NetIncomeLossAttributableToNoncontrollingInterest"] = {
        "units": {"USD": [dict(annual, val=1), dict(annual, val=2)]}}
    raw[key] = json.dumps(obj).encode()
    _write_frozen_audit_archive(tmp_path, registry, raw, panel)
    with pytest.raises(app.Q2SourceHold, match="Conflicting same-10K"):
        app.audit_frozen_source_coverage(tmp_path)


def test_frozen_gap_audit_preserves_identity_quarantine(tmp_path):
    registry, raw, panel = sources()
    mapping = sec.resolve_registry(registry)
    original_cik = mapping["XOM"]
    replacement = "0099999988"
    reg = json.loads(registry)
    for entry in reg.values():
        if entry["ticker"] == "XOM":
            entry["cik_str"] = int(replacement)
            break
    for kind in ("companyfacts", "submissions"):
        oldkey = f"raw/CIK{original_cik}-XOM-{kind}.json"
        newkey = f"raw/CIK{replacement}-XOM-{kind}.json"
        data = json.loads(raw.pop(oldkey))
        data["cik"] = int(replacement)
        if kind == "companyfacts":
            for tag in ("GrossProfit", "NetIncomeLoss", "Assets"):
                data["facts"]["us-gaap"][tag]["units"]["USD"][0]["accn"] = (
                    f"{replacement}-26-000001")
        else:
            data["filings"]["recent"]["accessionNumber"] = [
                f"{replacement}-26-000001"]
        raw[newkey] = json.dumps(data).encode()
    _write_frozen_audit_archive(tmp_path, json.dumps(reg).encode(), raw, panel)
    audit = app.audit_frozen_source_coverage(tmp_path)
    assert audit["source_gap_count"] == 1
    assert audit["source_gaps"][0]["reason"] == "ORIGINAL_ISSUER_CIK_DRIFT_QUARANTINED"
    assert audit["source_gaps"][0]["same_filing_profit_loss_usd"] is None
    assert "XOM" not in audit["original_frozen_selection_symbols"]


def test_frozen_gap_audit_rejects_changed_original_sec_bytes(tmp_path):
    registry, raw, panel = sources()
    _write_frozen_audit_archive(tmp_path, registry, raw, panel)
    file = next((tmp_path/"raw").glob("*companyfacts.json"))
    file.write_bytes(file.read_bytes()+b"\n")
    import fund100_v8_q2_frozen_forward_63_marks_v1_0 as marks
    with pytest.raises(marks.MarkHold, match="source bytes changed"):
        app.audit_frozen_source_coverage(tmp_path)


def test_frozen_gap_audit_is_research_only_and_wired_to_existing_forward_run():
    workflow = Path(".github/workflows/fund100-v8-q2-frozen-forward-mark.yml").read_text()
    assert "--audit-original-dir /tmp/q2-first" in workflow
    assert "q2-original-sec-gap-audit.json" in workflow
    assert "contents: write" not in workflow
    assert "secrets.ALPACA_LIVE_KEY" not in workflow
    assert "fund100-live-broker" not in workflow
    assert "  workflow_dispatch:" not in workflow
