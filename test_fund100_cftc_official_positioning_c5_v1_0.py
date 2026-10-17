"""C5 strict CFTC ZIP source / market identity guards; all numbers synthetic."""
from __future__ import annotations

from datetime import datetime,timezone
from io import BytesIO
import zipfile

import pandas as pd
import pytest

import fund100_cftc_official_positioning_c5_v1_0 as c5


def rows():
    records=[]
    for i in range(120):
        records.append({
            "As_of_Date_Form_YYYY-MM-DD":"2026-10-06",
            "CFTC_Contract_Market_Code":"023651",
            "Market_and_Exchange_Names":"NATURAL GAS - NEW YORK MERCANTILE EXCHANGE",
            "Open_Interest_All":"999999",
            "M_Money_Positions_Long_All":"100",
            "M_Money_Positions_Short_All":"99",
            "FutOnly_or_Combined":"FutOnly",
        })
    for code,name in [("088691","GOLD - COMMODITY EXCHANGE INC."),
                      ("067651","CRUDE OIL, LIGHT SWEET - NEW YORK MERCANTILE EXCHANGE")]:
        for d in ["2026-10-06","2026-10-13"]:
            records.append({
                "As_of_Date_Form_YYYY-MM-DD":d,
                "CFTC_Contract_Market_Code":code,
                "Market_and_Exchange_Names":name,
                "Open_Interest_All":"400000",
                "M_Money_Positions_Long_All":"100000" if d.endswith("13") else "95000",
                "M_Money_Positions_Short_All":"20000",
                "FutOnly_or_Combined":"FutOnly",
            })
    return pd.DataFrame(records)


def zipped(frame=None,filename="fut_disagg_txt_2026.txt"):
    frame=rows() if frame is None else frame
    out=BytesIO()
    with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED) as z:
        z.writestr(filename,frame.to_csv(index=False))
    return out.getvalue()


def test_truly_zipped_source_and_dated_features_only():
    raw=zipped()
    report=c5.audit(raw,acquired_utc="2026-10-17T11:40:00Z")
    assert report["schema"]==c5.SCHEMA
    assert report["original_archive_size_bytes"]==len(raw)
    assert len(report["contract_markets"])==2
    assert report["broker_orders"]==0
    assert report["trading_authorized"] is False
    assert report["live_authorized"] is False
    assert not report["independently_measured_futures_roll_yield"]
    gold=report["contract_markets"]["COMEX_GOLD"]
    assert gold["last_position_date"]=="2026-10-13"
    assert gold["net_contract_change_last_week"]==5000
    assert gold["last_week"]["managed_money_net_share_of_oi"]==.20


def test_source_rejects_missing_markets_and_schema():
    data=rows()
    with pytest.raises(c5.CFTCStop):
        c5.original_annual_zip(zipped(data.drop(columns=["M_Money_Positions_Short_All"])))
    with pytest.raises(c5.CFTCStop):
        c5.original_annual_zip(zipped(data[data.CFTC_Contract_Market_Code!="088691"]))


def test_source_blocks_combined_options_unexpected_archive_and_corruption():
    f=rows()
    f["FutOnly_or_Combined"]="Combined"
    with pytest.raises(c5.CFTCStop,match="Combined"):
        c5.original_annual_zip(zipped(f))
    with pytest.raises(c5.CFTCStop):
        c5.original_annual_zip(b"not a ZIP"*15)
    with pytest.raises(c5.CFTCStop):
        c5.original_annual_zip(zipped(filename="../2026.txt"))


def test_wrong_instrument_identity_and_spoofed_tuesday_rejected():
    frame=c5.original_annual_zip(zipped())
    corrupt=frame.copy()
    corrupt.iloc[0,corrupt.columns.get_loc("Market_and_Exchange_Names")]="SPY ETF"
    with pytest.raises(c5.CFTCStop,match="mismatch"):
        c5.position_records(corrupt,"2026-10-17T11:40:00Z")
    corrupt=frame.copy()
    corrupt.loc[corrupt.index[0],"As_of_Date_Form_YYYY-MM-DD"]="2026-10-16"
    with pytest.raises(c5.CFTCStop,match="Tuesday"):
        c5.position_records(corrupt,"2026-10-17T11:40:00Z")


@pytest.mark.parametrize("field,value",[
    ("M_Money_Positions_Long_All","-5"),
    ("M_Money_Positions_Short_All","NaN"),
    ("Open_Interest_All","0"),
    ("M_Money_Positions_Long_All","999999"),
])
def test_spoofed_positions_rejected(field,value):
    f=c5.original_annual_zip(zipped())
    f.iloc[0,f.columns.get_loc(field)]=value
    with pytest.raises(c5.CFTCStop):
        c5.position_records(f,"2026-10-17T11:40:00Z")


def test_future_report_denied_and_no_tuesday_means_no_release_claim():
    f=c5.original_annual_zip(zipped())
    with pytest.raises(c5.CFTCStop,match="earlier than"):
        c5.position_records(f,"2026-10-13T11:40:00Z")
    rep=c5.audit(zipped(),acquired_utc="2026-10-17T11:40:00Z")
    assert not rep["actual_historical_report_publication_times_verified"]
    assert not rep["historical_2025_cftc_funding_shutdown_release_delays_accounted_for"]
    assert not rep["actual_futures_expiry_settlements_captured"]
    assert not rep["dbc_etf_positions_mapped_to_cftc_contracts"]
    assert not rep["stock_or_etf_alpha_measured"]


def test_no_network_fallback_on_unsupported_archive():
    with pytest.raises(c5.CFTCStop):
        c5.audit(b"synthetic source invalid",acquired_utc="2026-10-17T11:40:00Z")
