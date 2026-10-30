"""Synthetic frozen Q2 source risk attribution, no future bars or broker."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import fund100_stock_broad_momentum_p4l_v1_0 as cohort
import fund100_v8_q2_first_original_preentry_risk_v1_0 as risk
import fund100_v8_q2_frozen_forward_63_marks_v1_0 as frozen
from test_fund100_v8_q2_frozen_forward_63_marks_v1_0 import (
    archive,_synthetic_independent_original_pin,subsequent,
)


def setup_source(tmp_path):
    frame,report=archive(tmp_path)
    pin=_synthetic_independent_original_pin(tmp_path,report)
    return frame,report,pin


def test_exact_original_8_stock_risk_source_and_all_preentry_windows(tmp_path):
    _,report,pin=setup_source(tmp_path)
    ans=risk.analyze(tmp_path,pin_path=pin)
    assert ans["schema"]==risk.SCHEMA
    assert ans["original_selected_8_names"]==report[
        "source_derived_research_selection"]["selection_candidate"]["symbols"]
    assert ans["original_24_issuer_source_coverage"]==24
    assert ans["first_original_sec_price_source_pin_confirmed"][
        "separate_git_pin_agrees_with_original_source"]
    assert set(ans["trailing_completed_source_windows"])=={"63","126","252"}
    assert ans["maximum_sector_share_of_total_NAV"]<=.2375
    assert abs(sum(ans["original_sector_weight_of_total_NAV"].values())-.95)<1e-8
    for key,window in ans["trailing_completed_source_windows"].items():
        assert window["price_return_window_sessions"]==int(key)
        assert window["through_frozen_completed_price_session"]==(
            report["last_completed_market_session"])
        assert set(window["fixed_95pct_risky_5pct_cash_reference_risk"])=={
            "frozen_q2_eight_equal",
            "same_sector_original_24_cohort",
            "passive_95_spy_5_cash",
        }
        assert window["risk_metrics_selection_conditioned_on_same_window"]
        assert window["effective_issuer_correlation_dimensions"] is None or (
            0<window["effective_issuer_correlation_dimensions"]<=8)
        assert window["spy_worst_5pct_session_count"]==int(
            np.ceil(int(key)*.05))
        assert all(v["proxy_gross_return_rebalanced_daily_not_tradable"]
                   for v in window["fixed_95pct_risky_5pct_cash_reference_risk"].values())
    assert ans["lookback_selection_conditioned_not_independent_or_prospective_alpha"]
    assert not ans["live_authorized"]
    assert ans["broker_gets"]==ans["broker_posts"]==ans["broker_orders"]==0


def test_changed_frozen_yahoo_original_price_rejected_even_with_valid_csv(tmp_path):
    _,_,pin=setup_source(tmp_path)
    path=tmp_path/frozen.ORIGINAL_PRICE_CSV
    doc=path.read_text()
    path.write_text(doc.replace("100.", "101.",1))
    with pytest.raises(frozen.MarkHold,match="Independent original Q2 source digest mismatch"):
        risk.analyze(tmp_path,pin_path=pin)


def test_pretend_new_selected_basket_not_accepted_by_external_pin(tmp_path):
    _,_,pin=setup_source(tmp_path)
    entry=json.loads(pin.read_text())
    entry["original_stock_selection"][0]="FICTITIOUS"
    pin.write_text(json.dumps(entry))
    with pytest.raises(frozen.MarkHold,match="Independent original issuer/source selection pin mismatch"):
        risk.analyze(tmp_path,pin_path=pin)


def test_original_sec_companyfacts_byte_change_stops_covariance(tmp_path):
    _,_,pin=setup_source(tmp_path)
    file=next((tmp_path/"raw").glob("*companyfacts.json"))
    file.write_bytes(file.read_bytes()+b" ")
    with pytest.raises(frozen.MarkHold,match="source bytes changed"):
        risk.analyze(tmp_path,pin_path=pin)


def test_6pct_loss_and_high_35pct_volatility_flags_are_historical_only():
    index=pd.bdate_range("2026-06-01",periods=63)
    names=list(cohort.SECTORS)[:8]
    data={s:np.linspace(-.002,.002,63) for s in cohort.SECTORS}
    data.update({"SPY":np.linspace(-.002,.002,63),"SHY":np.zeros(63)})
    for s in names:
        arr=data[s].copy()
        arr[8:20:2]=-.10
        data[s]=arr
    ret=pd.DataFrame(data,index=index)
    result=risk._one_window(ret,names)
    state=result["historical_flags_not_forward_guarantees"]
    assert state["q2_observed_any_daily_loss_6pct_or_worse"]
    assert state["q2_volatility_above_existing_high_35pct"]
    assert result["fixed_95pct_risky_5pct_cash_reference_risk"][
        "frozen_q2_eight_equal"]["worst_observed_daily_return"]<-.09
    assert result["risk_metrics_selection_conditioned_on_same_window"]


def test_identical_issuer_returns_cannot_fake_eight_independent_risk_factors():
    idx=pd.bdate_range("2026-06-01",periods=63)
    names=list(cohort.SECTORS)[:8]
    shared=.001+.004*np.sin(np.arange(63)/7)
    ret=pd.DataFrame({s:shared for s in cohort.SECTORS},index=idx)
    ret["SPY"]=shared
    ret["SHY"]=0.
    analysis=risk._one_window(ret,names)
    assert analysis["effective_issuer_correlation_dimensions"]==pytest.approx(1,abs=1e-6)
    assert analysis["issuer_pair_max_correlation"]==pytest.approx(1)
    assert analysis["q2_eight_spy_beta"]==pytest.approx(1)


def test_missing_prices_and_invalid_rebalance_weights_fail_closed():
    idx=pd.bdate_range("2026-06-01",periods=63)
    names=list(cohort.SECTORS)[:8]
    ret=pd.DataFrame({s:np.full(63,.0001) for s in cohort.SECTORS},index=idx)
    ret["SPY"]=.0002
    ret["SHY"]=0.
    ret.loc[idx[0],names[0]]=np.nan
    with pytest.raises(risk.RiskHold,match="Missing finite"):
        risk._one_window(ret,names)
    ret.loc[idx[0],names[0]]=.0001
    with pytest.raises(risk.RiskHold,match="Unexpected hypothetical"):
        risk._path_metrics(ret,{names[0]:.80,names[1]:.25})


def test_preentry_risk_program_never_imports_broker_or_is_promotion():
    assert risk.BROKER_GETS==risk.BROKER_POSTS==risk.BROKER_ORDERS==0
    assert not risk.LIVE_AUTHORIZED
    module=Path(risk.__file__).read_text()
    workflow=Path(
        ".github/workflows/fund100-v8-q2-first-original-preentry-risk.yml"
    ).read_text()
    audit=Path(".github/workflows/fund100-live-static-audit.yml").read_text()
    for forbidden in ("ALPACA_LIVE_KEY","PRIVATE_STATE_PRODUCTION_WRITE_TOKEN",
                      'method="POST"','submit_order('):
        assert forbidden not in module
    assert "secrets.ALPACA_LIVE_KEY" not in workflow
    assert "secrets.FUND100_SEC_USER_AGENT" not in workflow
    assert "  workflow_dispatch:" not in workflow
    assert "contents: write" not in workflow
    assert "actions: read" in workflow
    assert "frozen.verify_independent_first_source_pin" in module
    assert "github.event_name == 'push'" in workflow
    assert "fund100-live-broker" not in workflow
    for path in ("fund100_v8_q2_first_original_preentry_risk_v1_0.py",
                 "test_fund100_v8_q2_first_original_preentry_risk_v1_0.py",
                 ".github/workflows/fund100-v8-q2-first-original-preentry-risk.yml"):
        assert '      - "'+path+'"' in audit




def _sector_test_names():
    return ["AAPL","MSFT","GOOGL","META","JNJ","LLY","KO","PG"]


def test_sector_repair_exact_minimum_post_fee_and_no_unrelated_sales():
    names=_sector_test_names()
    positions={s:5. for s in names}
    positions["AAPL"]=30.
    positions["MSFT"]=30.
    # NAV=100, gross=90; technology alone is 60% of NAV.
    wanted,cash,fee_paid,sold=risk._sector_aware_sell_only_repair(
        positions,10.,.0015)
    exact=(60.-.25*100.)/(1.-.25*.0015)
    assert sold==pytest.approx(exact,abs=1e-8)
    assert cash==pytest.approx(10.+sold-fee_paid)
    assert fee_paid==pytest.approx(sold*.0015)
    assert all(wanted[s]==positions[s] for s in names if s not in ("AAPL","MSFT"))
    nav=cash+sum(wanted.values())
    assert (wanted["AAPL"]+wanted["MSFT"])/nav==pytest.approx(.25,abs=1e-9)
    assert max(wanted.values())/nav<.5


def test_sector_repair_gross_only_and_recovered_breach_do_not_overtrade():
    names=_sector_test_names()
    positions={s:12. for s in names}
    wanted,cash,charged,sold=risk._sector_aware_sell_only_repair(
        positions,4.,.0015)
    assert sold==pytest.approx((96.-95.)/(1.-.95*.0015),abs=1e-8)
    assert sum(wanted.values())/(cash+sum(wanted.values()))==pytest.approx(.95)
    assert charged==pytest.approx(sold*.0015)
    unchanged,cash2,charged2,sold2=risk._sector_aware_sell_only_repair(
        {s:10. for s in names},20.,.0015)
    assert sold2==charged2==0.
    assert cash2==20.
    assert unchanged=={s:10. for s in names}


def test_next_close_repair_waits_one_bar_and_charges_real_sell_cost():
    names=_sector_test_names()
    idx=pd.bdate_range("2026-06-01",periods=63)
    returns=pd.DataFrame(0.,index=idx,columns=names)
    returns.loc[idx[0],["AAPL","MSFT"]]=.30
    weights={s:1/8 for s in names}
    base=risk._next_close_sector_repair_path(returns,weights,15,.95)
    buffer=risk._next_close_sector_repair_path(returns,weights,15,.90)
    assert base["sector_breach_close_count_before_repair"]>=1
    assert base["sector_breach_close_count_after_repair"]==1
    assert base["additional_sell_only_repair_dates"]==1
    assert base["additional_sell_only_turnover_usd_per_100"]>0
    assert base["total_entry_and_repair_fees_usd_per_100"] > (
        100.-100./(1.+.95*.0015))
    assert base["gross_breach_close_count_after_repair"]<=1
    assert buffer["additional_sell_only_repair_dates"]>=0
    assert base["research_only_no_live_execution"]


def test_next_close_terminal_breach_never_trades_future_close():
    names=_sector_test_names()
    idx=pd.bdate_range("2026-06-01",periods=63)
    returns=pd.DataFrame(0.,index=idx,columns=names)
    returns.loc[idx[-1],["AAPL","MSFT"]]=.40
    out=risk._next_close_sector_repair_path(
        returns,{s:1/8 for s in names},15,.95)
    assert out["sector_breach_close_count_after_repair"]==1
    assert out["additional_sell_only_repair_dates"]==0
    assert out["last_close_queued_repair_not_executed"]
    assert out["additional_sell_only_turnover_usd_per_100"]==0


def test_new_repair_comparison_is_source_pinned_and_costed(tmp_path):
    _,_,pin=setup_source(tmp_path)
    report=risk.analyze(tmp_path,pin_path=pin)
    for window in report["trailing_completed_source_windows"].values():
        by_buffer=window["next_close_sector_repair_cash_buffer_comparison"]
        assert set(by_buffer)=={"95pct_initial_invested","90pct_initial_invested"}
        for label,by_cost in by_buffer.items():
            assert set(by_cost)=={"5","15","35"}
            for item in by_cost.values():
                assert item["initial_invested_fraction"]==(
                    .90 if label.startswith("90") else .95)
                assert item["next_completed_close_only_no_intraday_guarantee"]
                assert item["selected_on_same_historical_prices_not_alpha"]
                assert item["terminal_exit_fee_not_charged"]
                assert item["research_only_no_live_execution"]
                assert item["additional_sell_only_repair_dates"]>=0


def test_sector_repair_invalid_inputs_fail_closed():
    names=_sector_test_names()
    with pytest.raises(risk.RiskHold,match="Invalid sector-aware"):
        risk._sector_aware_sell_only_repair({names[0]:-1.},100.,.0015)
    with pytest.raises(risk.RiskHold,match="Invalid sector-aware"):
        risk._sector_aware_sell_only_repair({names[0]:10.},90.,.02)
    idx=pd.bdate_range("2026-06-01",periods=63)
    ret=pd.DataFrame(0.,index=idx,columns=names)
    ret.iloc[2,0]=np.nan
    with pytest.raises(risk.RiskHold,match="Invalid original close"):
        risk._next_close_sector_repair_path(
            ret,{s:1/8 for s in names},15,.95)

def test_buy_once_entry_costs_and_no_rebalance_are_separate_from_daily_proxy(tmp_path):
    _,_,pin=setup_source(tmp_path)
    result=risk.analyze(tmp_path,pin_path=pin)
    assert result["buy_once_costed_risk_is_selection_conditioned_not_a_live_gate"]
    for window in result["trailing_completed_source_windows"].values():
        observed=window["buy_once_costed_no_rebalance_close_risk"]
        assert set(observed)=={
            "frozen_q2_eight_equal",
            "same_sector_original_24_cohort",
            "passive_95_spy_5_cash",
        }
        for comparator,by_cost in observed.items():
            assert set(by_cost)=={"5","15","35"}
            for bp in (5,15,35):
                item=by_cost[str(bp)]
                assert item["entry_cost_bps_per_traded_side"]==bp
                assert item["no_rebalance_or_additional_turnover"]
                assert item["terminal_exit_cost_not_charged"]
                assert item["entry_fee_in_initial_high_water_drawdown"]
                assert item["not_an_executable_intraday_risk_control"]
                assert 0<=item["max_observed_gross_exposure_fraction"]<=1
                assert 0<=item["max_observed_single_issuer_fraction"]<=1
                assert 0<=item["gross_over_95pct_completed_close_count"]<=(
                    window["price_return_window_sessions"])
                if comparator=="passive_95_spy_5_cash":
                    assert item["max_observed_sector_fraction"] is None
                    assert item["sector_over_25pct_completed_close_count"] is None
                else:
                    assert item["max_observed_sector_fraction"] is not None
            assert by_cost["5"]["marked_unrealized_return_after_entry_cost_pct"] > (
                by_cost["15"]["marked_unrealized_return_after_entry_cost_pct"])
            assert by_cost["15"]["marked_unrealized_return_after_entry_cost_pct"] > (
                by_cost["35"]["marked_unrealized_return_after_entry_cost_pct"])


def test_buy_once_cash_and_entry_fee_accounting_without_rebalance():
    idx=pd.bdate_range("2026-06-01",periods=63)
    names=list(cohort.SECTORS)[:8]
    ret=pd.DataFrame({s:np.full(63,.01) for s in names},index=idx)
    fee=15/10000
    answer=risk._buy_once_costed_risk(ret,{s:1/8 for s in names},15)
    entry_nav=100/(1+.95*fee)
    final_nav=entry_nav*(.05+.95*1.01**63)
    assert answer["initial_entry_cost_usd_per_100"]==pytest.approx(
        100-entry_nav,abs=1e-8)
    assert answer["marked_unrealized_return_after_entry_cost_pct"]==pytest.approx(
        final_nav-100,abs=1e-8)
    assert answer["gross_over_95pct_completed_close_count"]==63
    assert answer["max_observed_gross_exposure_fraction"]>.95
    assert answer["single_issuer_over_50pct_completed_close_count"]==0


def test_buy_once_drifting_position_detects_gross_name_and_sector_breaches():
    idx=pd.bdate_range("2026-06-01",periods=63)
    names=list(cohort.SECTORS)[:8]
    ret=pd.DataFrame({s:np.zeros(63) for s in names},index=idx)
    ret.loc[idx[0],names[0]]=9.
    result=risk._buy_once_costed_risk(ret,{s:1/8 for s in names},15)
    assert result["gross_over_95pct_completed_close_count"]==63
    assert result["single_issuer_over_50pct_completed_close_count"]==63
    assert result["sector_over_25pct_completed_close_count"]==63
    assert result["max_observed_single_issuer_fraction"]>.5
    assert result["no_rebalance_or_additional_turnover"]


def test_buy_once_invalid_cost_and_missing_source_fail_closed():
    idx=pd.bdate_range("2026-06-01",periods=63)
    names=list(cohort.SECTORS)[:8]
    ret=pd.DataFrame({s:np.zeros(63) for s in names},index=idx)
    weights={s:1/8 for s in names}
    with pytest.raises(risk.RiskHold,match="Invalid buy-once"):
        risk._buy_once_costed_risk(ret,weights,50)
    with pytest.raises(risk.RiskHold,match="Invalid buy-once"):
        risk._buy_once_costed_risk(ret,{names[0]:.6,names[1]:.5},15)
    ret.loc[idx[0],names[0]]=np.nan
    with pytest.raises(risk.RiskHold,match="Invalid buy-once original"):
        risk._buy_once_costed_risk(ret,weights,15)
