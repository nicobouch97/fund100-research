"""P4Z offline adversarial tests; synthetic rows only, no vendor downloads."""
from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path
from zipfile import ZipFile, ZIP_STORED

import pytest

import fund100_stock_delisted_sample_p4z_v1_0 as p4z


def _rows(symbol):
    rows = []
    for stamp in p4z._sessions(p4z.LAST[symbol]):
        row = {key: "" for key in p4z.COLUMNS}
        row.update(date=stamp, open="300", high="301", low="299",
                   close="300", volume="10000", vwap="300",
                   transactions="100", adj_open="300", adj_high="301",
                   adj_low="299", adj_close="300", adj_volume="10000",
                   adj_vwap="300")
        if symbol == "TSLA" and stamp == "2022-08-24":
            row.update(close="891.29", adj_close="297.0967")
        if symbol == "TSLA" and stamp == "2022-08-25":
            row.update(close="296.07", adj_close="296.07", split="1:3")
        if symbol == "KO" and stamp in ("2022-09-15", "2022-11-30"):
            row.update(dividend="0.44", dividend_type="CD")
        if symbol == "SPY" and stamp in ("2022-09-16", "2022-12-16"):
            row.update(dividend="1.50", dividend_type="CD")
        rows.append(row)
    return rows


def _zip(tmp_path, mutate=None, *, missing=None, bad_name=False):
    dest = tmp_path / "source.zip"
    with ZipFile(dest, "w", compression=ZIP_STORED) as archive:
        for symbol, filename in p4z.FILES.items():
            if symbol == missing:
                continue
            rows = _rows(symbol)
            if mutate is not None:
                mutate(symbol, rows)
            stream = StringIO()
            writer = csv.DictWriter(stream, fieldnames=p4z.COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
            if bad_name and symbol == "TWTR":
                filename = "TWTR_day.csv"
            archive.writestr("stocks_sample_2022H2/day_by_symbol/" + filename,
                             stream.getvalue())
    return dest


def test_full_synthetic_source_preserves_terminal_unknown(tmp_path):
    report = p4z.audit_zip(_zip(tmp_path))
    assert report["schema"] == p4z.SCHEMA
    assert [r["daily_rows"] for r in report["listings"]] == [127, 127, 127, 83]
    assert report["twtr_last_trading_bar"] == "2022-10-27"
    assert report["twtr_source_delisting_label"] == "2022-10-31"
    assert report["twtr_terminal_shareholder_proceeds_usd"] is None
    assert report["twtr_post_delisting_total_return"] is None
    assert report["twtr_position_cannot_be_dropped_or_valued_at_zero_by_default"]
    assert report["tsla_split_raw_close_return_pct"] < -60
    assert abs(report["tsla_split_adjusted_close_return_pct"]) < 1
    assert not report["historical_stock_alpha_backtest_eligible"]
    assert report["broker_orders"] == report["broker_gets"] == report["broker_posts"] == 0
    assert report["trading_authorized"] is False


def test_missing_or_renamed_delisted_listing_fails_closed(tmp_path):
    with pytest.raises(p4z.DelistedSampleStop, match="listing-specific"):
        p4z.audit_zip(_zip(tmp_path, missing="TWTR"))
    with pytest.raises(p4z.DelistedSampleStop, match="listing-specific"):
        p4z.audit_zip(_zip(tmp_path, bad_name=True))


def test_delisted_history_must_not_be_forward_filled(tmp_path):
    def extend(symbol, rows):
        if symbol == "TWTR":
            rows.append({**rows[-1], "date": "2022-10-28"})
    with pytest.raises(p4z.DelistedSampleStop, match="dates missing"):
        p4z.audit_zip(_zip(tmp_path, extend))


def test_missing_split_or_cash_distribution_fails(tmp_path):
    def split_missing(symbol, rows):
        if symbol == "TSLA":
            next(r for r in rows if r["date"] == "2022-08-25")["split"] = ""
    with pytest.raises(p4z.DelistedSampleStop, match="split marker"):
        p4z.audit_zip(_zip(tmp_path, split_missing))
    def dividend_missing(symbol, rows):
        if symbol == "KO":
            next(r for r in rows if r["date"] == "2022-09-15")["dividend"] = ""
    with pytest.raises(p4z.DelistedSampleStop, match="distribution"):
        p4z.audit_zip(_zip(tmp_path, dividend_missing))


def test_bad_price_and_duplicate_session_rejected(tmp_path):
    def zero(symbol, rows):
        if symbol == "SPY":
            rows[0]["adj_close"] = "0"
    with pytest.raises(p4z.DelistedSampleStop, match="Nonpositive"):
        p4z.audit_zip(_zip(tmp_path, zero))
    def duplicate(symbol, rows):
        if symbol == "KO":
            rows.insert(1, rows[0].copy())
    with pytest.raises(p4z.DelistedSampleStop, match="dates missing"):
        p4z.audit_zip(_zip(tmp_path, duplicate))


def test_research_boundary_does_not_download_or_execute(tmp_path):
    source = Path(p4z.__file__).read_text()
    for forbidden in ("alpaca.markets", "TradingClient", "submit_order",
                      "ALPACA_LIVE_KEY", "requests.post", "urlopen("):
        assert forbidden not in source
    assert p4z.BROKER_GETS == p4z.BROKER_POSTS == p4z.BROKER_ORDERS == 0
    with pytest.raises(p4z.DelistedSampleStop, match="missing"):
        p4z.audit_zip(tmp_path / "absent.zip")
