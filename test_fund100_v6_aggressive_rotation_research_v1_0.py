"""V6 aggressive weekly sector relative strength: synthetic negative checks only."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import fund100_v6_aggressive_rotation_research_v1_0 as v6


def prices():
    ix = pd.bdate_range("2021-01-01",periods=880)
    t = np.arange(len(ix),dtype=float)
    growth = {s: .0005 for s in v6.UNIVERSE}
    growth.update({"SPY": .0006, "XLK": .0025, "XLE": .0022, "EEM": .0019, "IWM": -.0003})
    d = {s: 100*(1+q)**t for s,q in growth.items()}
    d[v6.BENCH] = 100*(1+.00065)**t
    return pd.DataFrame(d,index=ix)


def fridays(df):
    return [t for t in range(v6.FIRST_POSSIBLE_T,len(df)) if df.index[t].weekday()==4]


def test_active_3_name_concentration_and_no_acwi_core():
    f=prices()
    d=v6.signal(f,fridays(f)[-1])
    assert d.risk_on is True
    assert list(d.signal_scores) == ["XLK","XLE","EEM"]
    assert d.weights["XLK"]==pytest.approx(.35)
    assert d.weights["XLE"]==pytest.approx(.35)
    assert d.weights["EEM"]==pytest.approx(.30)
    assert sum(d.weights.values())==pytest.approx(1)
    assert "ACWI" not in d.weights


def test_current_session_close_never_changes_predecision_signal():
    f=prices()
    t=fridays(f)[-1]
    before=v6.signal(f,t)
    changed=f.copy()
    changed.loc[changed.index[t],"XLK"] *= 1.10
    changed.loc[changed.index[t],"SPY"] *= .97
    assert v6.signal(changed,t)==before


def test_regime_off_moves_to_cash_but_preserves_long_only():
    f=prices()
    t=fridays(f)[-1]
    # Construct falling benchmark ending before today's date.
    f.loc[f.index[t-80]:,"SPY"] = f["SPY"].iloc[t-80] * (.985 ** np.arange(len(f)-(t-80)))
    # Easier than retro-fitting all past records; retains positive prices.
    d=v6.signal(f,t)
    assert d.risk_on is False
    assert sum(d.weights.values()) <= .35+1e-12
    assert all(0<=a<=.35 for a in d.weights.values())


def test_friday_signal_gate_rejects_weekday_and_insufficient_bars():
    f=prices()
    with pytest.raises(v6.V6ResearchStop):
        v6.signal(f,5)
    weekday=next(i for i in range(v6.FIRST_POSSIBLE_T,len(f)) if f.index[i].weekday()==2)
    with pytest.raises(v6.V6ResearchStop,match="Friday"):
        v6.signal(f,weekday)


def test_high_cost_never_accidentally_adds_equity_returns():
    f=prices()
    a=v6.backtest(f,cost_bps=5)
    b=v6.backtest(f,cost_bps=35)
    assert a["v6_nav"].iloc[-1]>b["v6_nav"].iloc[-1]
    assert a["acwi_nav"].iloc[-1]==pytest.approx(b["acwi_nav"].iloc[-1])
    assert (a["gross_equity_exposure"]<=1+1e-9).all()
    assert (a["cash_weight"]>=0).all()
    assert (a["one_way_turnover"].loc[a.index.weekday!=4]==0).all()


@pytest.mark.parametrize("bad",["missing","unexpected","nan","negative","huge","unsorted","duplicate","tz"])
def test_corrupt_price_source_rejected(bad):
    f=prices()
    if bad=="missing": f=f.drop(columns=["XLK"])
    if bad=="unexpected": f=f.rename(columns={"XLK":"AAPL"})
    if bad=="nan": f.loc[f.index[15],"XLE"]=np.nan
    if bad=="negative": f.loc[f.index[15],"EEM"]=-1
    if bad=="huge": f.loc[f.index[15],"EEM"]*=5
    if bad=="unsorted": f=f.iloc[::-1]
    if bad=="duplicate": f.index=pd.DatetimeIndex([f.index[0],*f.index[:-1]])
    if bad=="tz": f.index=f.index.tz_localize("UTC")
    with pytest.raises(v6.V6ResearchStop):
        v6.validate_prices(f)


def test_unrecognized_cost_and_source_hash_rejected():
    f=prices()
    with pytest.raises(v6.V6ResearchStop):
        v6.backtest(f,cost_bps=0)
    with pytest.raises(v6.V6ResearchStop):
        v6.analyze(f,"NOT-A-SOURCE-HASH")


def test_marginal_live_release_is_impossible_from_results():
    d=v6.analyze(prices(),"0"*64)
    assert d["actual_forward_strategy_returns"]==0
    assert d["risk_profile_rewrite_required_before_any_live_use"]
    assert d["operator_authorised_liquidation"] is False
    assert d["operator_authorised_v6_live"] is False
    assert d["broker_orders"]==0
    assert not d["trading_authorized"] and not d["paper_authorized"] and not d["live_authorized"]


def test_source_file_must_equal_stored_cryptographic_commitment(tmp_path):
    p=tmp_path/"tampered.csv"
    prices().to_csv(p,index_label="date")
    with pytest.raises(v6.V6ResearchStop,match="frozen file bytes changed"):
        v6.load_frozen(p)
