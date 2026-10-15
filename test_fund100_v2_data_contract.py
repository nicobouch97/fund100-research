"""V2 point-in-time contract tests: synthetic fixtures, no data vendor or broker."""

from __future__ import annotations

import csv
from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from fund100_v2.data_contract import BUNDLE_SCHEMA, load_research_bundle
from fund100_v2.walkforward import WalkForwardPlan, walk_forward


NEW_YORK = ZoneInfo("America/New_York")
UTC = timezone.utc
PRICE_COLUMNS = (
    "session", "symbol", "total_return_close", "spread_bps",
    "price_known_at_utc",
)
MEMBERSHIP_COLUMNS = (
    "session", "symbol", "eligible", "membership_known_at_utc",
)


def _dates(n=210):
    rows = []
    day = date(2025, 1, 2)
    while len(rows) < n:
        if day.weekday() < 5:
            rows.append(day)
        day += timedelta(days=1)
    return rows


def _write_csv(path, columns, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def make_bundle(folder, n=210):
    folder.mkdir(parents=True, exist_ok=True)
    dates = _dates(n)
    prices = []
    members = []
    for index, session in enumerate(dates):
        close = datetime.combine(
            session, time(16), tzinfo=NEW_YORK
        ).astimezone(UTC)
        for symbol, multiplier in (("UP", 1.002), ("DOWN", 0.999)):
            prices.append(dict(
                session=session.isoformat(),
                symbol=symbol,
                total_return_close=str(100 * multiplier ** index),
                spread_bps="3.5",
                price_known_at_utc=(
                    close + timedelta(minutes=20)
                ).isoformat().replace("+00:00", "Z"),
            ))
            members.append(dict(
                session=session.isoformat(),
                symbol=symbol,
                eligible="TRUE",
                membership_known_at_utc=(
                    close - timedelta(hours=1)
                ).isoformat().replace("+00:00", "Z"),
            ))

    _write_csv(folder / "prices.csv", PRICE_COLUMNS, prices)
    _write_csv(folder / "membership.csv", MEMBERSHIP_COLUMNS, members)
    manifest = {
        "schema": BUNDLE_SCHEMA,
        "source_vendor": "TEST_DATA_NOT_A_REAL_PROVIDER",
        "snapshot_id": "synthetic-fixture-v1",
        "source_record": "LOCAL_FAKE_METADATA_ONLY",
        "price_basis": "SPLIT_AND_DIVIDEND_ADJUSTED_TOTAL_RETURN",
        "membership_basis": "HISTORICAL_POINT_IN_TIME",
        "includes_delisted_instrument_history": True,
    }
    resync_hashes(folder, manifest)
    return dates, prices, members, manifest


def resync_hashes(folder, manifest):
    manifest["prices_sha256"] = sha256(
        (folder / "prices.csv").read_bytes()
    ).hexdigest()
    manifest["membership_sha256"] = sha256(
        (folder / "membership.csv").read_bytes()
    ).hexdigest()
    (folder / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8"
    )


def modify_price(folder, fn):
    rows = list(csv.DictReader((folder / "prices.csv").open(encoding="utf-8")))
    fn(rows)
    _write_csv(folder / "prices.csv", PRICE_COLUMNS, rows)
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    resync_hashes(folder, manifest)


def modify_member(folder, fn):
    rows = list(csv.DictReader((folder / "membership.csv").open(encoding="utf-8")))
    fn(rows)
    _write_csv(folder / "membership.csv", MEMBERSHIP_COLUMNS, rows)
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    resync_hashes(folder, manifest)


def modify_manifest(folder, changes):
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    manifest.update(changes)
    (folder / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8"
    )


def test_valid_synthetic_bundle_can_feed_offline_walkforward(tmp_path):
    days, _, _, _ = make_bundle(tmp_path)
    bundle = load_research_bundle(tmp_path, as_of=days[-1])
    assert len(bundle.panel.sessions) == len(days)
    assert len(bundle.panel.adjusted_prices) == 2
    assert bundle.panel.eligible_symbols[0] == frozenset({"UP", "DOWN"})
    assert bundle.evidence.eligible_observations == 2 * len(days)
    assert bundle.evidence.source_verification == (
        "SELF_ATTESTED_NOT_INDEPENDENTLY_VERIFIED"
    )
    report = walk_forward(
        bundle.panel,
        WalkForwardPlan(
            min_train_decisions=30, test_decisions_per_fold=12,
            benchmark_symbol="UP",
        ),
    )
    assert len(report.folds) > 1
    assert len(report.audit_sha256) == 64


def test_data_bundle_is_reproducible(tmp_path):
    days, _, _, _ = make_bundle(tmp_path)
    a = load_research_bundle(tmp_path, as_of=days[-1])
    b = load_research_bundle(tmp_path, as_of=days[-1])
    assert a.evidence == b.evidence


def test_any_price_file_edit_with_original_manifest_fails_checksum(tmp_path):
    days, _, _, _ = make_bundle(tmp_path)
    with (tmp_path / "prices.csv").open("ab") as handle:
        handle.write(b"\n")
    with pytest.raises(ValueError, match="checksum"):
        load_research_bundle(tmp_path, as_of=days[-1])


def test_any_membership_file_edit_with_original_manifest_fails_checksum(tmp_path):
    days, _, _, _ = make_bundle(tmp_path)
    with (tmp_path / "membership.csv").open("ab") as handle:
        handle.write(b"\n")
    with pytest.raises(ValueError, match="checksum"):
        load_research_bundle(tmp_path, as_of=days[-1])


@pytest.mark.parametrize("updates,error", [
    ({"price_basis": "UNADJUSTED_CLOSE"}, "Total-return-adjusted"),
    ({"membership_basis": "TODAY_ONLY"}, "point-in-time"),
    ({"includes_delisted_instrument_history": False}, "Delisted-history"),
    ({"source_vendor": ""}, "provenance"),
    ({"source_record": ""}, "provenance"),
    ({"schema": "VERSION_2"}, "schema mismatch"),
    ({"prices_sha256": "bad"}, "SHA256"),
])
def test_fake_or_incomplete_vendor_declarations_fail(tmp_path, updates, error):
    days, _, _, _ = make_bundle(tmp_path)
    modify_manifest(tmp_path, updates)
    with pytest.raises(ValueError, match=error):
        load_research_bundle(tmp_path, as_of=days[-1])


def test_same_day_membership_after_close_is_lookahead(tmp_path):
    days, _, _, _ = make_bundle(tmp_path)
    modify_member(
        tmp_path,
        lambda rows: rows[0].update(
            membership_known_at_utc=(
                datetime.combine(
                    days[0], time(16), tzinfo=NEW_YORK
                ).astimezone(UTC) + timedelta(minutes=1)
            ).isoformat()
        )
    )
    with pytest.raises(ValueError, match="Lookahead"):
        load_research_bundle(tmp_path, as_of=days[-1])


def test_price_available_before_market_close_is_rejected(tmp_path):
    days, _, _, _ = make_bundle(tmp_path)
    modify_price(
        tmp_path,
        lambda rows: rows[0].update(
            price_known_at_utc="2025-01-02T15:00:00Z"
        )
    )
    with pytest.raises(ValueError, match="vintage"):
        load_research_bundle(tmp_path, as_of=days[-1])


def test_price_restatement_known_days_late_rejected(tmp_path):
    days, _, _, _ = make_bundle(tmp_path)
    modify_price(
        tmp_path,
        lambda rows: rows[0].update(
            price_known_at_utc="2025-01-04T18:00:00Z"
        )
    )
    with pytest.raises(ValueError, match="vintage"):
        load_research_bundle(tmp_path, as_of=days[-1])


@pytest.mark.parametrize("field", ["price_known_at_utc", "membership_known_at_utc"])
def test_naive_timestamp_rejected(tmp_path, field):
    days, _, _, _ = make_bundle(tmp_path)
    fn = modify_price if field.startswith("price") else modify_member
    fn(tmp_path, lambda rows: rows[0].update(**{field: "2025-01-02T19:00:00"}))
    with pytest.raises(ValueError, match="UTC"):
        load_research_bundle(tmp_path, as_of=days[-1])


@pytest.mark.parametrize("field", [
    "total_return_close", "spread_bps",
])
def test_invalid_numeric_fields_fail(tmp_path, field):
    days, _, _, _ = make_bundle(tmp_path)
    modify_price(tmp_path, lambda rows: rows[0].update(**{field: "nan"}))
    with pytest.raises(ValueError, match="Invalid"):
        load_research_bundle(tmp_path, as_of=days[-1])


def test_missing_membership_date_symbol_cannot_be_forward_filled(tmp_path):
    days, _, _, _ = make_bundle(tmp_path)
    modify_member(tmp_path, lambda rows: rows.pop(0))
    with pytest.raises(ValueError, match="Incomplete"):
        load_research_bundle(tmp_path, as_of=days[-1])


def test_missing_price_date_symbol_cannot_be_forward_filled(tmp_path):
    days, _, _, _ = make_bundle(tmp_path)
    modify_price(tmp_path, lambda rows: rows.pop(0))
    with pytest.raises(ValueError, match="Incomplete"):
        load_research_bundle(tmp_path, as_of=days[-1])


def test_duplicate_membership_row_fails(tmp_path):
    days, _, _, _ = make_bundle(tmp_path)
    modify_member(tmp_path, lambda rows: rows.append(dict(rows[0])))
    with pytest.raises(ValueError, match="Duplicate"):
        load_research_bundle(tmp_path, as_of=days[-1])


def test_duplicate_price_row_fails(tmp_path):
    days, _, _, _ = make_bundle(tmp_path)
    modify_price(tmp_path, lambda rows: rows.append(dict(rows[0])))
    with pytest.raises(ValueError, match="Duplicate"):
        load_research_bundle(tmp_path, as_of=days[-1])


def test_future_session_prices_are_rejected(tmp_path):
    days, _, _, _ = make_bundle(tmp_path)
    future_day = days[-1] + timedelta(days=7)
    while future_day.weekday() > 4:
        future_day += timedelta(days=1)
    modify_price(tmp_path, lambda rows: rows[0].update(
        session=future_day.isoformat()
    ))
    with pytest.raises(ValueError, match="Future"):
        load_research_bundle(tmp_path, as_of=days[-1])


def test_future_session_membership_is_rejected(tmp_path):
    days, _, _, _ = make_bundle(tmp_path)
    future_day = days[-1] + timedelta(days=7)
    while future_day.weekday() > 4:
        future_day += timedelta(days=1)
    modify_member(tmp_path, lambda rows: rows[0].update(
        session=future_day.isoformat()
    ))
    with pytest.raises(ValueError, match="Future"):
        load_research_bundle(tmp_path, as_of=days[-1])


def test_membership_false_is_preserved_for_that_date_only(tmp_path):
    days, _, _, _ = make_bundle(tmp_path)
    modify_member(tmp_path, lambda rows: rows[0].update(eligible="FALSE"))
    bundle = load_research_bundle(tmp_path, as_of=days[-1])
    assert "UP" not in bundle.panel.eligible_symbols[0]
    assert "UP" in bundle.panel.eligible_symbols[1]


def test_no_broker_or_order_output(tmp_path):
    days, _, _, _ = make_bundle(tmp_path)
    result = load_research_bundle(tmp_path, as_of=days[-1])
    assert not hasattr(result, "orders")
    assert not hasattr(result, "target_weights")
    assert not hasattr(result, "live_execution_authorized")
