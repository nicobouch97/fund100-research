"""Real-source-bound research signal to costed hypothetical portfolio gate."""
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

import fund100_v6_aggressive_rotation_research_v1_0 as base
import fund100_v6_frozen_signal_to_opportunity_v1_0 as bridge
import fund100_v6_opportunity_rebalance_economics_v1_0 as econ

def fake_prices():
    dates=pd.bdate_range("2022-01-03",periods=880)
    k=np.arange(len(dates),dtype=float)
    rates={symbol:.0002 for symbol in base.UNIVERSE}
    rates.update({"XLK":.0012,"XLE":.0010,"IWM":.0008,
                  "EEM":.00015,"XLV":.00016})
    values={s:100*(1+v)**k for s,v in rates.items()}
    values[base.BENCH]=100*(1+.0004)**k
    return pd.DataFrame(values,index=dates)

def fake_account():
    return {
        "mode":econ.MODE,"signal_status":"UNQUALIFIED_RESEARCH_HYPOTHESIS",
        "open_order_count":0,
        "equity_usd":"120.00","cash_usd":"20.00",
        "settled_cash_usd":"0.00",
        "positions_usd":{"ACWI":"40.00","EEM":"20.00",
                         "XLE":"20.00","XLV":"20.00"},
    }

def assess(f=None,t=700,account=None):
    return bridge.inspect(
        history=fake_prices() if f is None else f,
        source_sha256=bridge.SOURCE_SHA256,decision_index=t,
        synthetic_account=fake_account() if account is None else account)

def test_actual_lagged_research_model_is_joined_to_the_economic_gate():
    r=assess()
    assert r["schema"]==bridge.SCHEMA
    assert r["status"]=="RESEARCH_ONLY_FROZEN_HISTORICAL_SIGNAL_NOT_LIVE"
    assert r["all_signals_lagged_one_complete_session"]
    assert r["decision_session"]!=r["last_price_observation_session"]
    assert r["signal_horizon_sessions"]==21
    assert r["price_session_observations_used"]==253
    assert r["hypothetical_selected_symbols"]==["XLK","XLE","IWM"]
    assert r["hypothetical_target_weights"]=={
        "XLK":"0.475","XLE":"0.285","IWM":"0.190"}
    assert r["forecast_calibration_or_live_alpha_verified"] is False
    assert r["historical_source_independent_holdout"] is False
    assert r["actual_current_broker_snapshot_authenticated"] is False
    assert r["opportunity_order_authorized"] is False
    assert r["decision"]=="HOLD_UNTIL_INDEPENDENT_FORECAST_AND_LIVE_BROKER_VALIDATION"
    econresult=r["hypothetical_economics"]
    assert econresult["strategy_signal_authenticated"] is False
    assert econresult["broker_snapshot_authenticated"] is False
    assert econresult["live_order_submission_authorized"] is False
    assert econresult["real_broker_posts"]==0
    assert r["broker_orders"]==0
    assert econresult["hypothetical_sell_usd_by_symbol"]
    assert econresult["hypothetical_buy_usd_by_symbol"]

def test_decision_bar_mutation_is_excluded_from_prices_and_forecasts():
    f=fake_prices()
    baseline=assess(f=f,t=700)
    modified=f.copy()
    modified.loc[modified.index[700],"XLK"]*=1.05
    modified.loc[modified.index[700],"EEM"]*=.95
    result=assess(f=modified,t=700)
    assert result==baseline

def test_future_sessions_do_not_change_historical_signal_at_older_date():
    f=fake_prices()
    a=assess(f=f,t=700)
    f2=f.copy()
    f2.loc[f2.index[720]:,"XLE"]*=1.08
    assert assess(f=f2,t=700)==a

def test_late_research_prices_cannot_be_claimed_as_today_broker_quotes():
    history,digest=base.load_frozen(Path("research_lab/frozen_history_v2.csv"))
    z=bridge.inspect(
        history=history,source_sha256=digest,
        decision_index=len(history)-1,synthetic_account=fake_account())
    assert z["source_sha256"]==base.FROZEN_FILE_SHA256
    assert z["source_price_last_session_never_live_freshness"] is True
    assert z["historical_source_independent_holdout"] is False
    assert z["opportunity_order_authorized"] is False
    assert z["broker_orders"]==0
    assert z["decision"] in {
        "HOLD_UNTIL_INDEPENDENT_FORECAST_AND_LIVE_BROKER_VALIDATION",
        "HOLD_UNQUALIFIED_OR_EXCESSIVELY_UNCERTAIN_SIGNAL",
    }
    assert z["last_price_observation_session"]<z["decision_session"]

@pytest.mark.parametrize("bad",[
    "9"*64, "0"*64,"","INVALID"
])
def test_changed_or_missing_frozen_sha_stops_without_forecasts(bad):
    with pytest.raises(bridge.SourceSignalStop,match="commitment"):
        bridge.inspect(history=fake_prices(),source_sha256=bad,
                       decision_index=700,synthetic_account=fake_account())

@pytest.mark.parametrize("t",[-1,0,2,252,253,880,True,"700"])
def test_too_early_future_or_malformed_decision_stop(t):
    with pytest.raises(bridge.SourceSignalStop):
        assess(t=t)

@pytest.mark.parametrize("change",[
    {"mode":"REAL_LIVE"},
    {"signal_status":"CERTIFIED_ALPHA"},
    {"positions_usd":{"AAPL":"10.00"}},
])
def test_synthetic_source_cannot_inject_authenticated_portfolio(change):
    account=fake_account();account.update(change)
    with pytest.raises(bridge.SourceSignalStop):
        assess(account=account)

def test_weak_or_negative_trend_cannot_force_a_new_candidate():
    f=fake_prices()
    k=np.arange(len(f),dtype=float)
    for col in list(bridge.PRICE_COLUMN.values()):
        f[col]=100*(1-.0004)**k
    z=assess(f=f)
    assert z["hypothetical_selected_symbols"]==[]
    assert z["hypothetical_economics"] is None
    assert z["decision"]=="HOLD_UNQUALIFIED_OR_EXCESSIVELY_UNCERTAIN_SIGNAL"

def test_tampered_complete_source_bytes_block_verification(tmp_path):
    file=tmp_path/"tampered.csv"
    fake_prices().to_csv(file,index_label="date")
    with pytest.raises(bridge.SourceSignalStop,match="genuinely verified"):
        bridge.inspect_original_frozen(
            decision_index=700,synthetic_account=fake_account(),file=file)

def test_no_live_writer_credentials_or_network_in_lagged_research_bridge():
    source=Path(bridge.__file__).read_text()
    assert not bridge.LIVE_SIGNAL_APPROVED
    assert bridge.REAL_BROKER_ORDERS==0
    for prohibited in ("import requests","import urllib","import socket",
                       "ALPACA_LIVE_KEY","ALPACA_LIVE_SECRET",
                       "FUND100_BROKER_KILL_SWITCH","method=\"POST\"",
                       "def main(", "import os"):
        assert prohibited not in source
