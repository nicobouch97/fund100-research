"""Credential-free real-volume shadow heartbeat regression tests.

Every case is deliberately nontrading and uses only local temporary SQLite.
"""
import sqlite3
from pathlib import Path
import pytest

import fund100_private_stop_shadow_volume_heartbeat_v1_0 as shadow


@pytest.fixture
def mounted(monkeypatch, tmp_path):
    monkeypatch.setattr(shadow, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(shadow, "DB_PATH", str(tmp_path / "heartbeat.sqlite3"))
    monkeypatch.setattr(shadow.os.path, "ismount",
                        lambda path: path == str(tmp_path))
    monkeypatch.setattr(shadow.os, "geteuid", lambda: 10002)
    monkeypatch.setenv("FUND100_STOP_SHADOW_MODE", "NO_BROKER_SHADOW")
    for item in shadow.FORBIDDEN_ENV:
        monkeypatch.delenv(item, raising=False)
    return tmp_path


def test_no_trade_network_or_dispatch_source():
    text = Path(shadow.__file__).read_text()
    assert "NO_GITHUB_IO = True" in text
    assert "NO_BROKER_IO = True" in text
    assert "NO_STOP_DISPATCH = True" in text
    assert "NO_ORDER_AUTHORITY = True" in text
    assert "NO_RISK_PASS = True" in text
    assert "urllib" not in text
    assert "requests" not in text
    assert "http.server" not in text
    assert "api.alpaca.markets" not in text
    assert "actions/workflows/" not in text


def test_no_mount_refuses_to_create_ephemeral_db(monkeypatch, tmp_path):
    monkeypatch.setattr(shadow, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(shadow, "DB_PATH", str(tmp_path / "shadow.sqlite3"))
    monkeypatch.setattr(shadow.os, "geteuid", lambda: 10002)
    monkeypatch.setattr(shadow.os.path, "ismount", lambda path: False)
    monkeypatch.setenv("FUND100_STOP_SHADOW_MODE", "NO_BROKER_SHADOW")
    with pytest.raises(shadow.ShadowHold, match="non-durable"):
        shadow.heartbeat_once()
    assert not (tmp_path / "shadow.sqlite3").exists()


def test_shadow_volume_counter_persists_across_reopen(mounted):
    first = shadow.heartbeat_once()
    second = shadow.heartbeat_once()
    assert first["durable_sequence"] == 1
    assert second["durable_sequence"] == 2
    for result in (first, second):
        assert result["status"] == "HOST_VOLUME_HEARTBEAT_ONLY"
        assert result["broker_risk_pass"] is False
        assert result["stop_verified"] is False
        assert result["order_authorized"] is False
    # Separate SQLite connection simulates a restarted process.
    with sqlite3.connect(mounted / "heartbeat.sqlite3") as db:
        assert db.execute(
            "SELECT sequence FROM heartbeat WHERE singleton=1"
        ).fetchone() == (2,)
    assert shadow.heartbeat_once()["durable_sequence"] == 3


def test_wrong_mode_or_root_or_broker_key_denied(mounted, monkeypatch):
    monkeypatch.setenv("FUND100_STOP_SHADOW_MODE", "STOP_ONLY")
    with pytest.raises(shadow.ShadowHold):
        shadow.heartbeat_once()
    monkeypatch.setenv("FUND100_STOP_SHADOW_MODE", "NO_BROKER_SHADOW")
    monkeypatch.setattr(shadow.os, "geteuid", lambda: 0)
    with pytest.raises(shadow.ShadowHold):
        shadow.heartbeat_once()
    monkeypatch.setattr(shadow.os, "geteuid", lambda: 10002)
    for item in shadow.FORBIDDEN_ENV:
        monkeypatch.setenv(item, "UNEXPECTED_PRIVATE_CREDENTIAL")
        with pytest.raises(shadow.ShadowHold):
            shadow.heartbeat_once()
        monkeypatch.delenv(item, raising=False)
    assert not (mounted / "heartbeat.sqlite3").exists()


def test_clock_reversal_blocks_heartbeat(mounted, monkeypatch):
    monkeypatch.setattr(shadow, "_now_utc",
                        lambda: "2026-11-13T18:20:00Z")
    assert shadow.heartbeat_once()["durable_sequence"] == 1
    monkeypatch.setattr(shadow, "_now_utc",
                        lambda: "2026-11-13T18:19:59Z")
    with pytest.raises(shadow.ShadowHold, match="time reversed"):
        shadow.heartbeat_once()


def test_corrupt_future_or_invalid_counter_denied(mounted):
    assert shadow.heartbeat_once()["durable_sequence"] == 1
    with sqlite3.connect(mounted / "heartbeat.sqlite3") as db:
        db.execute(
            "UPDATE heartbeat SET last_at_utc='2099-01-01T00:00:00Z'"
        )
    with pytest.raises(shadow.ShadowHold, match="time reversed"):
        shadow.heartbeat_once()


def test_dockerfile_has_no_server_broker_or_writer_modules():
    source = Path("Dockerfile.private-stop-shadow").read_text()
    assert "gosu stopshadow python -u" in source
    assert "chown stopshadow:stopshadow /data" in source
    assert "chmod 0700 /data" in source
    assert "EXPOSE" not in source
    assert "ALPACA_" not in source
    assert "GITHUB_TOKEN" not in source
    assert "fund100_private_stop_controller_locked_v1_0.py" not in source
    assert "fund100_railway_risk_watch_http_preflight_v1_0.py" not in source
