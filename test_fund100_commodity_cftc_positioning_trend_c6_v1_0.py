"""C6 original CFTC, scheduled-release and offline ETF-source anti-lookahead tests.

All numbers in this test are SYNTHETIC. The GitHub workflow fetches and
revalidates the authentic original C5 ZIP separately.
"""
from __future__ import annotations
from io import BytesIO
import json
import zipfile

import numpy as np
import pandas as pd
import pytest

import fund100_cftc_official_positioning_c5_v1_0 as c5
import fund100_commodity_cftc_positioning_trend_c6_v1_0 as c6


def sample_prices():
    idx=pd.bdate_range("2025-08-01","2026-10-16")
    t=np.arange(len(idx),dtype=float)
    return pd.DataFrame({
        "GLD":120*np.exp(.0009*t+.07*np.sin(t/40)),
        "USO":70*np.exp(.0006*t+.10*np.sin(t/35)),
        "SHY":81*np.exp(.00008*t),
    },index=idx)


def sample_cftc(*,bullish=True):
    data=[]
    for t,day in enumerate(pd.date_range("2026-01-06","2026-10-13",freq="W-TUE")):
        for code,name in [
            ("088691","GOLD - COMMODITY EXCHANGE INC."),
            ("067651","WTI-PHYSICAL - NEW YORK MERCANTILE EXCHANGE"),
        ]:
            data.append({
                "Market_and_Exchange_Names":name,
                "Report_Date_as_YYYY-MM-DD":day.date().isoformat(),
                "CFTC_Contract_Market_Code":code,
                "Open_Interest_All":"400000",
                "M_Money_Positions_Long_All":str(90000+ (t*450 if bullish else -t*150)),
                "M_Money_Positions_Short_All":"20000",
                "FutOnly_or_Combined":"FutOnly",
            })
    for t in range(140):
        data.append({
            "Market_and_Exchange_Names":"OTHER PRODUCT - OTHER EXCHANGE",
            "Report_Date_as_YYYY-MM-DD":"2026-10-13",
            "CFTC_Contract_Market_Code":"023651",
            "Open_Interest_All":"100000",
            "M_Money_Positions_Long_All":"1000",
            "M_Money_Positions_Short_All":"100",
            "FutOnly_or_Combined":"FutOnly",
        })
    raw=BytesIO()
    with zipfile.ZipFile(raw,"w",zipfile.ZIP_DEFLATED) as out:
        out.writestr("fut_disagg_txt_2026.txt",pd.DataFrame(data).to_csv(index=False))
    blob=raw.getvalue()
    manifest=c5.audit(blob,acquired_utc="2026-10-17T11:45:00Z")
    return blob,manifest


def test_source_replay_same_raw_sha_and_disallows_changing_zip():
    raw,manifest=sample_cftc()
    f=c6.read_authenticated_c5(raw,manifest)
    assert set(f[c5.FIELDS["code"]])=={"088691","067651"}
    broken=dict(manifest,original_archive_sha256="0"*64)
    with pytest.raises(c6.C6Stop,match="SHA"):
        c6.read_authenticated_c5(raw,broken)
    broken=dict(manifest,contract_markets={})
    with pytest.raises(c6.C6Stop,match="differs"):
        c6.read_authenticated_c5(raw,broken)


def test_cftc_scheduled_release_lags_and_holiday_are_frozen():
    raw,manifest=sample_cftc()
    f=c6.read_authenticated_c5(raw,manifest)
    r=c6.cftc_publication_schedule(f)
    assert len(r)==len(c6.OFFICIAL_SCHEDULE)
    june=next(x for x in r if x["cftc_tentative_release_date"]=="2026-06-22")
    july=next(x for x in r if x["cftc_tentative_release_date"]=="2026-07-06")
    assert june["report_asof_tuesday"]=="2026-06-16"
    assert july["report_asof_tuesday"]=="2026-06-30"
    assert all(x["scheduled_publication_NOT_original_vintage_verified"] for x in r)


def test_first_after_publication_decision_excludes_same_close_and_future_price():
    p=sample_prices()
    i=p.index.get_loc(pd.Timestamp("2026-05-04"))
    fake={"cftc_tentative_release_date":"2026-05-01",
          "position_share_4wk_rising":{"GLD":True,"USO":False}}
    expected=c6.decision_targets(p,i,fake)
    changed=p.copy()
    changed.iloc[i,0]*=1.20
    changed.iloc[i,1]*=.88
    assert c6.decision_targets(changed,i,fake)==expected
    with pytest.raises(c6.C6Stop,match="strictly earlier"):
        c6.decision_targets(p,p.index.get_loc(pd.Timestamp("2026-05-01")),fake)


def test_no_positions_if_no_rising_cftc_share():
    p=sample_prices()
    i=p.index.get_loc(pd.Timestamp("2026-05-04"))
    source={"cftc_tentative_release_date":"2026-05-01",
            "position_share_4wk_rising":{"GLD":False,"USO":False}}
    assert c6.decision_targets(p,i,source)=={"GLD":0.,"USO":0.,"SHY":1.}


def test_cost_charges_both_etf_legs_and_no_weekend_trading():
    raw,manifest=sample_cftc()
    f=c6.read_authenticated_c5(raw,manifest)
    p=sample_prices()
    frames={bp:c6.compare(p,f,cost_bps=bp) for bp in c6.ONE_WAY_BPS}
    assert frames[15]["c6_nav"].iloc[-1] >= frames[35]["c6_nav"].iloc[-1] >= frames[60]["c6_nav"].iloc[-1]
    assert frames[15]["static_50_50_nav"].iloc[-1]==pytest.approx(frames[60]["static_50_50_nav"].iloc[-1])
    for frame in frames.values():
        assert not any(d.weekday()>4 for d in frame.index)
        assert (frame[["gld_weight","uso_weight","shy_weight"]].sum(axis=1)-1).abs().max()<1e-8
        assert (frame[["gld_weight","uso_weight","shy_weight"]]>=0).all().all()
        assert frame["decision"].sum()>=c6.MIN_RELEASE_DECISIONS
        assert (frame["gross_turnover"]>=0).all()


@pytest.mark.parametrize("error",["bad-column","nan","negative","future","duplicate","missing-days","weekend","reorder"])
def test_untrusted_etf_source_strictly_rejected(error):
    p=sample_prices()
    if error=="bad-column":p=p.rename(columns={"USO":"USO_FAKE"})
    if error=="nan":p.iloc[5,0]=np.nan
    if error=="negative":p.iloc[5,2]=-4.
    if error=="future":p.index=p.index.shift(900,freq="D")
    if error=="duplicate":p.index=pd.DatetimeIndex([p.index[0],*p.index[:-1]])
    if error=="missing-days":p=p.drop(p.index[100:130])
    if error=="weekend":p.index=pd.DatetimeIndex([*p.index[:-1],pd.Timestamp("2026-10-17")])
    if error=="reorder":p=p.iloc[::-1]
    with pytest.raises(c6.C6Stop):
        c6.validate_etfs(p)


def test_missing_cftc_week_or_invalid_release_blocks_study():
    raw,manifest=sample_cftc()
    data=c6.read_authenticated_c5(raw,manifest)
    x=data.copy()
    drop=x[(x[c5.FIELDS["code"]]=="088691")
           & (x[c5.FIELDS["date"]]=="2026-04-28")].index
    x=x.drop(drop)
    with pytest.raises(c6.C6Stop,match="missing scheduled report"):
        c6.cftc_publication_schedule(x)


def test_source_bound_real_currency_research_never_approves_orders():
    raw,manifest=sample_cftc()
    report=c6.analyze(raw,manifest,sample_prices(),source_acquired_utc="2026-10-17T11:55:00Z")
    assert report["status"]=="C6_EXPLORATORY_2026_ISSUER_POSITIONING_PRICE_DATA_NOT_LIVE_ALPHA"
    assert report["source_c5_original_acquired_at_utc"]=="2026-10-17T11:45:00Z"
    assert report["cftc_original_weekly_release_vintages_not_independently_verified"]
    assert report["uso_fund_total_returns_are_not_cftc_single_contract_futures_carry"]
    assert report["broker_orders"]==0
    assert report["live_promoted"] is False and report["alpha_verified"] is False
    assert report["operator_authorized_old_position_sales"] is False
    assert not report["operator_authorized_asset_expansion"]
    assert not report["paper_authorized"] and not report["live_authorized"]
    assert not report["trading_authorized"]


def test_invalid_cost_and_postfreeze_price_sample_fail():
    raw,manifest=sample_cftc()
    data=c6.read_authenticated_c5(raw,manifest)
    with pytest.raises(c6.C6Stop):
        c6.compare(sample_prices(),data,cost_bps=0)
    p=sample_prices()
    p.index=p.index+pd.Timedelta(days=7)
    with pytest.raises(c6.C6Stop):
        c6.compare(p,data,cost_bps=35)
