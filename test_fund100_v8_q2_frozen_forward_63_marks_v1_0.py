"""Q2 original-artifact integrity, forward-entry causality and 63-session cost tests."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
from hashlib import sha256
from decimal import Decimal
import json

import exchange_calendars as xcals
import numpy as np
import pandas as pd
import pytest

import fund100_stock_broad_momentum_p4l_v1_0 as cohort
import fund100_v8_q2_first_actual_sec_roa_price_source_v1_0 as original
import fund100_v8_q2_frozen_forward_63_marks_v1_0 as marks
from test_fund100_v8_q2_first_actual_sec_roa_price_source_v1_0 import sources, NEW

def archive(tmp_path, *, hold=False):
    registry, raws, panel = sources()
    if hold:
        for k,bytes_ in list(raws.items()):
            if k.endswith("companyfacts.json"):
                data=json.loads(bytes_)
                data["facts"]["us-gaap"].pop("NetIncomeLoss",None)
                raws[k]=json.dumps(data).encode("utf-8")
    report, prices = original.analyze_sources(
        registry=registry,source_files=raws,price_panel=panel,
        acquired_utc=NEW)
    (tmp_path/marks.FIRST_SOURCE_REPORT).write_text(
        json.dumps(report,sort_keys=True,indent=2)+"\n")
    (tmp_path/marks.ORIGINAL_REGISTRY).write_bytes(registry)
    (tmp_path/marks.ORIGINAL_PRICE_CSV).write_bytes(prices)
    for name,bytes_ in raws.items():
        dest=tmp_path/name
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(bytes_)
    return panel,report


def subsequent(panel, last="2026-11-05"):
    index=xcals.get_calendar("XNYS").sessions_in_range(
        panel.index[-1],pd.Timestamp(last)).tz_localize(None).normalize()
    new=index[index>panel.index[-1]]
    future=pd.DataFrame(index=new,columns=panel.columns,dtype=float)
    for s in panel.columns:
        base=float(panel[s].iloc[-1])
        future[s]=base*(1+np.arange(1,len(new)+1)*
                        (.0005 if s=="SPY" else .0006))
    return pd.concat([panel,future])


def test_immutable_original_source_all_24_sec_bytes_and_frozen_q2_hashes(tmp_path):
    panel,record=archive(tmp_path)
    parsed,screen,raw,clock=marks._read_source(tmp_path)
    assert parsed==record
    assert clock==NEW
    assert raw==(tmp_path/marks.ORIGINAL_PRICE_CSV).read_bytes()
    assert screen["selection_candidate"]["symbols"]==record[
        "source_derived_research_selection"]["selection_candidate"]["symbols"]


def test_original_future_entry_excludes_pre_source_close_and_charges_entry_fee(tmp_path):
    panel,_=archive(tmp_path)
    result=marks.evaluate(
        original_root=tmp_path,
        later_prices=subsequent(panel,last="2026-10-30"),
        observed_at_utc="2026-10-30T23:45:00Z")
    assert result["forward_close_sessions_observed"]==1
    assert result["hypothetical_entry_close"]=="2026-10-30"
    assert result["completed_close_to_close_intervals_since_entry"]==0
    assert not result["complete_horizon"]
    for item in result["performance"]["15"].values():
        assert item["net_value_per_100_original_usd"]<100
        assert not item["terminal_exit_charged_only_at_63rd_following_close"]
    assert not result["strategy_live_released"]
    assert result["real_broker_orders"]==0


def test_63_future_close_horizon_is_locked_and_exit_fees_not_charged_early(tmp_path):
    panel,_=archive(tmp_path)
    cal=xcals.get_calendar("XNYS")
    days=cal.sessions_in_range(
        pd.Timestamp("2026-10-30"),pd.Timestamp("2027-04-01"))
    final=days[62].date().isoformat()
    extra=days[66].date().isoformat()
    end_clock=(pd.Timestamp(extra)+pd.Timedelta(days=1)).strftime(
        "%Y-%m-%dT10:00:00Z")
    d=marks.evaluate(original_root=tmp_path,
                     later_prices=subsequent(panel,last=extra),
                     observed_at_utc=end_clock)
    assert d["forward_close_sessions_observed"]==63
    assert d["last_63_close_checkpoint"]==final
    assert d["completed_close_to_close_intervals_since_entry"]==62
    assert d["complete_horizon"]
    assert d["status"]=="63_FOLLOWING_CLOSES_DESCRIPTIVE_COMPLETE_NOT_ALPHA"
    assert set(d["performance"]["15"])=={
        "frozen_q2_eight_equal","same_sector_original_24_cohort",
        "passive_95_spy_5_cash"}
    for name in d["performance"]["5"]:
        assert d["performance"]["5"][name]["net_return_pct"]>(
            d["performance"]["35"][name]["net_return_pct"])
        assert d["performance"]["15"][name][
            "terminal_exit_charged_only_at_63rd_following_close"]
    assert not d["proven_statistical_alpha"]


def test_original_all_missing_source_is_hold_without_fabricated_performance(tmp_path):
    panel,_=archive(tmp_path,hold=True)
    r=marks.evaluate(original_root=tmp_path,
                     later_prices=subsequent(panel,last="2026-11-05"),
                     observed_at_utc="2026-11-05T23:45:00Z")
    assert r["status"]=="ORIGINAL_Q2_SOURCE_HOLD_NO_BASKET"
    assert r["performance"] is None
    assert r["source_coverage"]==0


def test_first_forward_entry_waits_for_later_close(tmp_path):
    panel,_=archive(tmp_path)
    r=marks.evaluate(original_root=tmp_path,later_prices=panel,
                     observed_at_utc="2026-10-30T08:45:00Z")
    assert r["status"]=="WAITING_FOR_FIRST_POST_CAPTURE_NYSE_CLOSE"
    assert r["forward_close_sessions_observed"]==0
    assert r["performance"] is None


def test_raw_sec_mutation_cannot_rewrite_first_source(tmp_path):
    archive(tmp_path)
    name=next((tmp_path/"raw").glob("*companyfacts.json"))
    name.write_bytes(name.read_bytes()+b"\n")
    with pytest.raises(marks.MarkHold,match="source bytes changed"):
        marks._read_source(tmp_path)


def test_original_source_report_mutation_disagrees_with_reproduced_selector(tmp_path):
    archive(tmp_path)
    path=tmp_path/marks.FIRST_SOURCE_REPORT
    doc=json.loads(path.read_text())
    doc["source_derived_research_selection"]["selection_candidate"]["symbols"][0]="FAKE"
    path.write_text(json.dumps(doc))
    with pytest.raises(marks.MarkHold,match="selection"):
        marks._read_source(tmp_path)


def test_forged_roa_and_recomputed_selector_cannot_replace_raw_sec_facts(tmp_path):
    # Report + its selector are internally consistent, and the original raw
    # SEC receipts/hashes have NOT changed. Earlier verification accepted
    # this invented financial statement because it only re-ranked report rows.
    panel, report = archive(tmp_path)
    row = next(r for r in report["source_rows"]
               if r["matched_annual_net_income_usd"] is not None
               and int(r["matched_annual_net_income_usd"]) > 0)
    row["matched_annual_net_income_usd"] = str(
        int(row["matched_annual_net_income_usd"]) * 10)
    snap = lambda n: format(Decimal(str(n)), ".8f")
    report["source_derived_research_selection"] = marks.q2.select(
        rows=report["source_rows"],
        benchmark_minus252=snap(panel["SPY"].iloc[
            -1-marks.q2.LOOKBACK_SESSIONS]),
        benchmark_minus42=snap(panel["SPY"].iloc[
            -1-marks.q2.SKIP_RECENT_SESSIONS]),
        decision_utc=NEW,
        price_session=report["last_completed_market_session"],
        source_mode=marks.q2.SOURCE_MODE)
    (tmp_path/marks.FIRST_SOURCE_REPORT).write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n")
    with pytest.raises(marks.MarkHold, match="diverged from raw sources"):
        marks._read_source(tmp_path)


def test_future_session_intraday_is_never_accepted_as_close(tmp_path):
    panel,_=archive(tmp_path)
    with pytest.raises(marks.MarkHold,match="Later original vendor"):
        marks.evaluate(original_root=tmp_path,
                       later_prices=subsequent(panel,last="2026-10-30"),
                       observed_at_utc="2026-10-30T13:00:00Z")


def test_no_broker_static_workflow_and_first_source_stays_read_only():
    module=Path(marks.__file__).read_text()
    workflow=Path(".github/workflows/fund100-v8-q2-frozen-forward-mark.yml").read_text()
    audit=Path(".github/workflows/fund100-live-static-audit.yml").read_text()
    assert marks.BROKER_GETS==marks.BROKER_POSTS==marks.BROKER_ORDERS==0
    assert not marks.LIVE_AUTHORIZED
    assert "ALPACA_LIVE_KEY" not in (module+workflow)
    assert "contents: write" not in workflow
    assert "actions: read" in workflow
    assert "fund100-live-broker" not in workflow
    assert "method=\"POST\"" not in module
    assert "  workflow_dispatch:" not in workflow
    push_paths, pr_paths = audit.split("  pull_request:\n", 1)
    for path in (
        "fund100_v8_q2_frozen_forward_63_marks_v1_0.py",
        "test_fund100_v8_q2_frozen_forward_63_marks_v1_0.py",
        ".github/workflows/fund100-v8-q2-frozen-forward-mark.yml",
        "fund100_v8_q2_first_actual_sec_roa_price_source_v1_0.py",
    ):
        expected = '      - "'+path+'"'
        assert expected in push_paths
        assert expected in pr_paths.split("\npermissions:", 1)[0]


def test_frozen_historical_overlap_accepts_unchanged_original_returns(tmp_path):
    panel,_=archive(tmp_path)
    later=subsequent(panel,last="2026-11-05")
    r=marks.evaluate(original_root=tmp_path,later_prices=later,
                     observed_at_utc="2026-11-05T23:45:00Z")
    assert r["original_price_overlap_return_shape_verified"]
    assert r["frozen_original_price_overlap_sessions"]==len(panel)
    assert r["max_frozen_overlap_relative_adjustment_drift_bps"]<0.001


def test_frozen_overlap_accepts_uniform_adjusted_price_rebasing(tmp_path):
    panel,_=archive(tmp_path)
    later=subsequent(panel,last="2026-11-05")
    # A later corporate action can multiply all earlier adjusted prices
    # by the same factor without changing any historical daily return.
    later.loc[panel.index,"AAPL"]*=0.995
    r=marks.evaluate(original_root=tmp_path,later_prices=later,
                     observed_at_utc="2026-11-05T23:45:00Z")
    assert r["uniform_corporate_action_rebasing_allowed"]
    assert r["max_frozen_overlap_relative_adjustment_drift_bps"]<0.001


def test_frozen_overlap_rejects_revised_historical_selection_returns(tmp_path):
    panel,_=archive(tmp_path)
    later=subsequent(panel,last="2026-11-05")
    # Valid-looking, modest retroactive vendor change inside the original
    # signal lookback must not be silently accepted as the frozen source.
    later.loc[panel.index[-20],"SPY"]*=1.002
    with pytest.raises(marks.MarkHold,match="returns revised across vintages"):
        marks.evaluate(original_root=tmp_path,later_prices=later,
                       observed_at_utc="2026-11-05T23:45:00Z")


def test_frozen_overlap_rejects_missing_old_history_even_if_later_complete(tmp_path):
    panel,_=archive(tmp_path)
    later=subsequent(panel,last="2026-11-05").iloc[10:]
    with pytest.raises(marks.MarkHold,match="omits original frozen"):
        marks.evaluate(original_root=tmp_path,later_prices=later,
                       observed_at_utc="2026-11-05T23:45:00Z")


def test_costed_forward_risk_matches_each_net_nav_and_is_not_annualized(tmp_path):
    panel,_=archive(tmp_path)
    result=marks.evaluate(
        original_root=tmp_path,later_prices=subsequent(panel,last="2026-11-05"),
        observed_at_utc="2026-11-05T23:45:00Z")
    for fee, portfolios in result["performance"].items():
        for name, outcome in portfolios.items():
            risk=outcome["observed_close_path_risk"]
            assert risk["observed_completed_close_marks"]==result[
                "forward_close_sessions_observed"]
            assert risk["last_costed_close_nav_per_100_original_usd"]==outcome[
                "net_value_per_100_original_usd"]
            assert risk["max_costed_close_drawdown_pct"]>=0
            assert risk["minimum_costed_close_nav_per_100_original_usd"]<=risk[
                "last_costed_close_nav_per_100_original_usd"]
            assert risk["entry_cost_included_in_initial_drawdown"]
            assert risk["risk_is_close_only_not_intraday_or_executable"]
            assert not risk["terminal_exit_fee_included_only_if_horizon_complete"]
    assert result["proven_statistical_alpha"] is False


def test_forward_risk_detects_intermediate_loss_even_when_terminal_recovers(tmp_path):
    panel,report=archive(tmp_path)
    later=subsequent(panel,last="2026-11-05")
    selected=report["source_derived_research_selection"][
        "selection_candidate"]["symbols"][0]
    original=marks.evaluate(
        original_root=tmp_path,later_prices=later,
        observed_at_utc="2026-11-05T23:45:00Z")
    # A one-session loss in a selected name reverses before the endpoint.
    # Terminal returns alone cannot reveal the intervening drawdown.
    second=later.index[later.index>pd.Timestamp(
        original["hypothetical_entry_close"])][0]
    later.loc[second,selected]*=.88
    stressed=marks.evaluate(
        original_root=tmp_path,later_prices=later,
        observed_at_utc="2026-11-05T23:45:00Z")
    a=original["performance"]["15"]["frozen_q2_eight_equal"]
    b=stressed["performance"]["15"]["frozen_q2_eight_equal"]
    assert b["net_value_per_100_original_usd"]==a[
        "net_value_per_100_original_usd"]
    assert b["observed_close_path_risk"]["max_costed_close_drawdown_pct"]>a[
        "observed_close_path_risk"]["max_costed_close_drawdown_pct"]+.5
    assert b["observed_close_path_risk"][
        "worst_observed_close_to_close_return_pct"]<-.5


def test_costed_forward_risk_includes_terminal_fee_only_on_close_63(tmp_path):
    panel,_=archive(tmp_path)
    cal=xcals.get_calendar("XNYS")
    days=cal.sessions_in_range(
        pd.Timestamp("2026-10-30"),pd.Timestamp("2027-04-01"))
    extra=days[66].date().isoformat()
    result=marks.evaluate(
        original_root=tmp_path,later_prices=subsequent(panel,last=extra),
        observed_at_utc=(pd.Timestamp(extra)+pd.Timedelta(days=1)).strftime(
            "%Y-%m-%dT10:00:00Z"))
    assert result["complete_horizon"]
    for portfolios in result["performance"].values():
        for outcome in portfolios.values():
            risk=outcome["observed_close_path_risk"]
            assert risk["observed_completed_close_marks"]==63
            assert risk["terminal_exit_fee_included_only_if_horizon_complete"]
            assert risk["last_costed_close_nav_per_100_original_usd"]==outcome[
                "net_value_per_100_original_usd"]


def test_relative_path_risk_detects_drawdown_hidden_by_terminal_tie():
    # Two hypothetical paths finish at identical wealth, but one suffers
    # a 20% relative trough en route. Compare costed NAV ratios, not
    # differences of standalone drawdown percentages.
    frame = pd.DataFrame({
        "AAPL": [100., 80., 100.],
        "SPY": [100., 100., 100.],
    }, index=pd.date_range("2026-11-02", periods=3, freq="B"))
    active = marks._relative_costed_close_risk(
        frame, {"AAPL": 1.}, {"SPY": 1.}, 15, horizon_done=False)
    assert active["observed_completed_close_marks"] == 3
    assert abs(active["last_net_relative_wealth_return_pct"]) < 1e-7
    assert active["max_net_relative_close_drawdown_pct"] > 18
    assert active["worst_observed_relative_close_to_close_return_pct"] < -18
    assert active["not_a_tradeable_hedge_or_independent_alpha_test"]


def test_relative_path_reconciles_to_costed_terminal_benchmark_ratios(tmp_path):
    panel, _ = archive(tmp_path)
    result = marks.evaluate(
        original_root=tmp_path,
        later_prices=subsequent(panel, last="2026-11-05"),
        observed_at_utc="2026-11-05T23:45:00Z")
    for bps, portfolios in result["performance"].items():
        active = result["relative_observed_close_path_risk"][bps]
        for label, benchmark in (
            ("versus_same_sector_original_24_cohort",
             "same_sector_original_24_cohort"),
            ("versus_passive_95_spy_5_cash", "passive_95_spy_5_cash"),
        ):
            expected = 100. * (
                portfolios["frozen_q2_eight_equal"][
                    "net_value_per_100_original_usd"] /
                portfolios[benchmark]["net_value_per_100_original_usd"] - 1.)
            assert abs(active[label][
                "last_net_relative_wealth_return_pct"] - expected) < 1e-7
            assert active[label]["observed_completed_close_marks"] == result[
                "forward_close_sessions_observed"]
            assert active[label]["max_net_relative_close_drawdown_pct"] >= 0
            assert not active[label][
                "terminal_exit_fee_only_if_horizon_complete"]
    assert not result["proven_statistical_alpha"]
    assert result["real_broker_orders"] == 0


def test_relative_path_detects_recovered_selected_stock_loss(tmp_path):
    panel, report = archive(tmp_path)
    later = subsequent(panel, last="2026-11-05")
    selected = report["source_derived_research_selection"][
        "selection_candidate"]["symbols"][0]
    original_result = marks.evaluate(
        original_root=tmp_path, later_prices=later,
        observed_at_utc="2026-11-05T23:45:00Z")
    second = later.index[later.index > pd.Timestamp(
        original_result["hypothetical_entry_close"])][0]
    later.loc[second, selected] *= .80
    stressed = marks.evaluate(
        original_root=tmp_path, later_prices=later,
        observed_at_utc="2026-11-05T23:45:00Z")
    name = "versus_passive_95_spy_5_cash"
    a = original_result["relative_observed_close_path_risk"]["15"][name]
    b = stressed["relative_observed_close_path_risk"]["15"][name]
    assert a["last_net_relative_wealth_return_pct"] == b[
        "last_net_relative_wealth_return_pct"]
    assert b["max_net_relative_close_drawdown_pct"] > a[
        "max_net_relative_close_drawdown_pct"] + 1.



def _synthetic_independent_original_pin(tmp_path, record):
    """Construct an external commitment for an offline synthetic source."""
    screen=record["source_derived_research_selection"]
    values={
        "schema":"FUND100_V8_Q2_INDEPENDENT_ORIGINAL_SOURCE_PIN_V1",
        "recorded_after_source_capture":True,
        "research_only_no_live_orders":True,
        "original_63_session_future_marks_not_yet_observed":True,
        "original_report_sha256":sha256(
            (tmp_path/marks.FIRST_SOURCE_REPORT).read_bytes()).hexdigest(),
        "original_sec_ticker_registry_sha256":sha256(
            (tmp_path/marks.ORIGINAL_REGISTRY).read_bytes()).hexdigest(),
        "original_price_panel_sha256":sha256(
            (tmp_path/marks.ORIGINAL_PRICE_CSV).read_bytes()).hexdigest(),
        "original_source_acquired_utc":record["source_acquired_utc"],
        "original_last_completed_market_session":
            record["last_completed_market_session"],
        "original_issuer_count":24,
        "original_positive_matched_net_income_assets_count":
            screen["matched_positive_annual_net_income_assets"],
        "original_source_missing_or_quarantined":screen["source_gaps"],
        "original_stock_selection":screen["selection_candidate"]["symbols"],
        "frozen_original_sector_count":
            screen["selection_candidate"]["sector_count"],
        "original_selection_source_fingerprint_sha256":
            screen["selection_candidate"]["source_fingerprint_sha256"],
        "original_source_workflow_run_id":1234,
    }
    path=tmp_path/"separate-original-pin.json"
    path.write_text(json.dumps(values,sort_keys=True)+"\n")
    return path


def test_independent_first_original_git_pin_accepts_exact_source_and_issuer_roster(tmp_path):
    _,report=archive(tmp_path)
    pin=_synthetic_independent_original_pin(tmp_path,report)
    result=marks.verify_independent_first_source_pin(tmp_path,pin)
    assert result["separate_git_pin_agrees_with_original_source"]
    assert result["source_first_public_run_id"]==1234
    assert result["not_a_prior_to_source_or_third_party_notarization"]
    assert not marks.LIVE_AUTHORIZED


def test_independent_pin_rejects_carryforward_copy_with_changed_report(tmp_path):
    _,report=archive(tmp_path)
    pin=_synthetic_independent_original_pin(tmp_path,report)
    path=tmp_path/marks.FIRST_SOURCE_REPORT
    doc=json.loads(path.read_text())
    # Even a self-consistent *different* research report cannot pass an
    # externally committed first-source report SHA256. Not just JSON parse.
    doc["source_acquired_utc"]="2026-10-31T08:16:19Z"
    path.write_text(json.dumps(doc,sort_keys=True,indent=2)+"\n")
    with pytest.raises(marks.MarkHold,match="Independent original Q2 source digest mismatch"):
        marks.verify_independent_first_source_pin(tmp_path,pin)


def test_independent_pin_rejects_issuer_substitution_even_with_recomputed_pin_digest(tmp_path):
    _,report=archive(tmp_path)
    pin=_synthetic_independent_original_pin(tmp_path,report)
    doc=json.loads(pin.read_text())
    doc["original_stock_selection"][0]="UNAUTHORIZED_TICKER"
    pin.write_text(json.dumps(doc))
    with pytest.raises(marks.MarkHold,match="Independent original issuer/source selection pin mismatch"):
        marks.verify_independent_first_source_pin(tmp_path,pin)


def test_real_first_source_pin_committed_before_future_marks_and_not_trade_authority():
    manifest=json.loads(marks.FIRST_SOURCE_INDEPENDENT_PIN.read_text())
    assert manifest["schema"]=="FUND100_V8_Q2_INDEPENDENT_ORIGINAL_SOURCE_PIN_V1"
    assert manifest["original_source_workflow_run_id"]==41025137794
    assert manifest["original_source_artifact_id"]==12962884465
    assert manifest["original_source_acquired_utc"]=="2026-10-30T08:16:19Z"
    assert manifest["original_report_sha256"]==(
        "c027ab01672ea70b0c5a150862e59d0b14bd39d38da203c87fa2361920fa670b")
    assert manifest["original_price_panel_sha256"]==(
        "c425b79b978304c1dee3628428cf2cc6a527b117253f83f106f0712f7f61f7a0")
    assert manifest["original_stock_selection"]==[
        "LLY","JNJ","GOOGL","AAPL","KO","CVX","AMZN","JPM"]
    assert manifest["original_positive_matched_net_income_assets_count"]==20
    assert manifest["original_source_missing_or_quarantined"]==[
        "AVGO","CAT","MA","XOM"]
    assert manifest["research_only_no_live_orders"]
    assert manifest["source_report_not_equivalent_to_authenticated_executable_trade"]
    workflow=Path(".github/workflows/fund100-v8-q2-frozen-forward-mark.yml").read_text()
    assert "verify_independent_first_source_pin" in workflow
    assert workflow.index("Verify separately committed first source") < workflow.index(
        "Audit original SEC coverage gaps")
    assert "contents: write" not in workflow
    assert "fund100-live-broker" not in workflow
