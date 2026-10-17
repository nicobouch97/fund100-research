"""V6-C1 synthetic-only negative gates; not real crypto alpha."""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
import numpy as np
import pandas as pd
import pytest

import fund100_v6_crypto_trend_c1_v1_0 as v6


def prices():
    index=pd.date_range("2018-01-01",periods=3200,freq="D")
    x=np.arange(len(index),dtype=float)
    btc=18000*np.exp(x*.00085+np.sin(x/85)*.10)
    eth=1100*np.exp(x*.0007+np.sin(x/100)*.11)
    return pd.DataFrame({"BTC-USD":btc,"ETH-USD":eth},index=index)


def signal_sunday(prices):
    return next(i for i,x in enumerate(prices.index) if i>900 and x.weekday()==6)


def test_expected_weekly_signal_and_24_7_cash_weight():
    p=prices()
    i=signal_sunday(p)
    result=v6.signal(p,i)
    assert result["decision_session"]==p.index[i].date().isoformat()
    assert result["last_signal_session"]==(p.index[i]-pd.Timedelta(days=1)).date().isoformat()
    assert 0<=result["volatility_scale"]<=1
    assert result["target_weights"]["BTC-USD"]<=.65
    assert result["target_weights"]["ETH-USD"]<=.45
    assert sum(result["target_weights"].values())+result["cash_weight"]==pytest.approx(1)


def test_no_same_day_signal_lookahead():
    p=prices()
    i=signal_sunday(p)
    expected=v6.signal(p,i)
    changed=p.copy()
    changed.iloc[i,0]*=1.35
    changed.iloc[i,1]*=.83
    assert v6.signal(changed,i)==expected


def test_no_trading_on_weekday_and_requires_history():
    p=prices()
    for index in (50,100):
        with pytest.raises(v6.CryptoResearchStop):
            v6.signal(p,index)
    w=next(i for i in range(900,len(p)) if p.index[i].weekday()==3)
    with pytest.raises(v6.CryptoResearchStop,match="Sunday"):
        v6.signal(p,w)


def test_price_source_24_7_no_gap_and_no_vintage_forgery():
    p=prices()
    with pytest.raises(v6.CryptoResearchStop,match="Missing UTC"):
        v6.validate_prices(p.drop(p.index[7]))
    with pytest.raises(v6.CryptoResearchStop):
        v6.validate_prices(p.assign(**{"ETH-USD":float("nan")}))
    bad=p.copy()
    bad.iloc[5,0]=p.iloc[5,0]*2
    with pytest.raises(v6.CryptoResearchStop,match="discontinuity"):
        v6.validate_prices(bad)


@pytest.mark.parametrize("kind",["duplicate","sorted","extra","missing","negative","zero","tz"])
def test_source_abuse_blocks(kind):
    p=prices()
    if kind=="duplicate":p.index=pd.DatetimeIndex([p.index[0],*p.index[:-1]])
    if kind=="sorted":p=p.iloc[::-1]
    if kind=="extra":p["SOL-USD"]=1.
    if kind=="missing":p=p.drop(columns="BTC-USD")
    if kind=="negative":p.iloc[1,0]=-12.
    if kind=="zero":p.iloc[1,1]=0.
    if kind=="tz":p.index=p.index.tz_localize("UTC")
    with pytest.raises(v6.CryptoResearchStop):
        v6.validate_prices(p)


def test_cost_deduction_both_sides_and_backtest_never_leverages():
    p=prices()
    nav={c:v6.simulate(p,cost_bps=c) for c in v6.COST_BPS}
    assert nav[25]["strategy_nav"].iloc[-1]>nav[35]["strategy_nav"].iloc[-1]>nav[60]["strategy_nav"].iloc[-1]
    assert nav[25]["btc_hold_nav"].iloc[-1]==pytest.approx(nav[60]["btc_hold_nav"].iloc[-1])
    for cost,v in nav.items():
        assert (v["crypto_gross_weight"]<=1+1e-10).all()
        assert (v["cash_weight"]>=0).all()
        assert (v.loc[v.index.weekday!=6,"gross_weight_turnover"]==0).all()
        assert v["gross_weight_turnover"].sum()>0


def test_cost_range_must_be_preregistered():
    with pytest.raises(v6.CryptoResearchStop):
        v6.simulate(prices(),cost_bps=0)


def test_actual_source_hash_chronology_and_never_live():
    data=prices()
    h=sha256(v6.canonical_csv(data).encode()).hexdigest()
    with pytest.raises(v6.CryptoResearchStop,match="source timing"):
        v6.analyze(data,capture_utc="2026-10-17T10:15:00Z",
                   price_hash=h,source_url="https://finance.yahoo.com/test")
    # Synthetic series ends years earlier, so no arbitrary capture clock can
    # represent a fresh real-market observation.


def test_unknown_source_never_licenses_live_trading():
    data=prices()
    with pytest.raises(v6.CryptoResearchStop):
        v6.analyze(data,capture_utc="2026-10-17T10:15:00Z",
                   price_hash="0"*64,source_url="https://finance.yahoo.com/test")
