"""V6 live critical-path reporting tests; no broker credentials."""
import json
from pathlib import Path
import pytest
import fund100_v6_launch_critical_path_v1_0 as m

def test_real_main_is_locked_and_no_authority_conferred():
    report = m.snapshot()
    assert report["schema"] == m.SCHEMA
    assert report["status"] == "NOT_LIVE_AUTHORIZATION"
    assert report["live_order_authorized"] is False
    assert report["broker_requests"] == report["private_git_requests"] == 0
    assert report["per_trade_user_approval_added"] is False
    assert report["checked_in_controls"]["v5_trading_enabled"] is False
    assert report["checked_in_controls"]["v6_trading_enabled"] is False
    assert report["checked_in_controls"]["v6_first_acwi_sell_enabled"] is False
    assert report["checked_in_controls"]["v6_risk_level"] == "HIGH"
    assert report["checked_in_controls"]["v6_pilot_capital_ceiling_usd"] == "130.30"
    assert set(report["stages"]) == {"first_acwi_sell", "first_xlk_buy", "recurring_automation"}
    assert all(s["code_status"] == "CODE_LOCKED" for s in report["stages"].values())
    assert all(s["locked_flags"] for s in report["stages"].values())
    assert all(s["live_runtime_verified"] is False for s in report["stages"].values())

def _copy(tmp_path: Path):
    for p in m.source_paths():
        target = tmp_path / p
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((m.ROOT / p).read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path

def test_missing_flag_holds(tmp_path):
    root = _copy(tmp_path)
    f = root / "fund100_v6_s1_original_first_acwi_entry_locked_v1_0.py"
    f.write_text(f.read_text().replace(
        "ORIGINAL_ACWI_ENTRYPOINT_RELEASED=False", "RENAMED_FLAG=False"), encoding="utf-8")
    with pytest.raises(m.LaunchHold, match="Missing release flag"):
        m.snapshot(root)

def test_runtime_flag_replacement_holds(tmp_path):
    root = _copy(tmp_path)
    f = root / "fund100_v6_s1_original_first_acwi_entry_locked_v1_0.py"
    f.write_text(f.read_text().replace(
        "ORIGINAL_ACWI_ENTRYPOINT_RELEASED=False",
        "ORIGINAL_ACWI_ENTRYPOINT_RELEASED=bool(__import__('os').getenv('X'))"),
        encoding="utf-8")
    with pytest.raises(m.LaunchHold, match="Dynamic"):
        m.snapshot(root)

def test_true_code_flag_still_not_a_broker_permit(tmp_path):
    root = _copy(tmp_path)
    f = root / "fund100_v6_s1_original_first_acwi_entry_locked_v1_0.py"
    f.write_text(f.read_text().replace(
        "ORIGINAL_ACWI_ENTRYPOINT_RELEASED=False",
        "ORIGINAL_ACWI_ENTRYPOINT_RELEASED=True"), encoding="utf-8")
    report = m.snapshot(root)
    assert report["live_order_authorized"] is False
    assert report["stages"]["first_acwi_sell"]["code_status"] == "CODE_LOCKED"

def test_shared_account_writer_mutex_change_holds(tmp_path):
    root = _copy(tmp_path)
    f = root / ".github/workflows/fund100-v6-s1-first-xlk-buy-funded-once.yml"
    f.write_text(f.read_text().replace(
        "fund100-alpaca-live-account-writer", "unsafe-other-writer"), encoding="utf-8")
    with pytest.raises(m.LaunchHold, match="workflow launch contract"):
        m.snapshot(root)

def test_changed_checked_in_go_never_attests_remote_controls(tmp_path):
    root = _copy(tmp_path)
    f = root / "fund100_v6_s1_operator_control.json"
    d = json.loads(f.read_text(encoding="utf-8"))
    d["trading_enabled"] = True
    f.write_text(json.dumps(d), encoding="utf-8")
    report = m.snapshot(root)
    assert report["checked_in_controls"]["v6_trading_enabled"] is True
    assert report["live_order_authorized"] is False
    assert report["current_broker_private_head_immutable_and_environment_state"] == "NOT_VERIFIED_OFFLINE"
