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
        arr[8]=-.10
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
    ret=pd.Data({s:np.full(63,.0001) for s in cohort.SECTORS},index=idx)
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
