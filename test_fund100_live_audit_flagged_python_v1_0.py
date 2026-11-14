"""Offline regression: credential allowlist must see Python interpreter switches.

No credentials, network, approval, or release authority.
"""
import audit_fund100_live_boundary as audit


def seen(source):
    return [match.group(1)
            for match in audit.PYTHON_SCRIPT_PATTERN.finditer(source)]


def test_python_interpreter_flags_do_not_hide_python_scripts():
    target = "fund100_live_emergency_stop_v1_0.py"
    for command in (
        f"python {target}", f"python -B {target}",
        f"python -u {target}", f"python -I -B {target}",
        f"python3 -B -u {target}", f"set -e; python -B {target}",
    ):
        assert seen(command) == [target]


def test_scriptless_interpreter_options_do_not_make_up_credential_approval():
    for cmd in ("python -B", "python -u", "python -c 'pass'"):
        assert seen(cmd) == []


def test_credentialed_script_requires_existing_source_pin():
    workflow = ".github/workflows/fund100-live-emergency-stop.yml"
    script = "fund100_live_emergency_stop_v1_0.py"
    assert (workflow, script) in audit.PINNED_LIVE_CREDENTIAL_JOBS
    assert script not in audit.ALLOWED_LIVE_CREDENTIAL_SCRIPTS
    # Tightening the interpreter regex does not change the eligibility pin.
    assert audit.PINNED_LIVE_CREDENTIAL_JOBS[(workflow, script)] == (
        "f990a9edf3357a161d32ff9e37301f2955d13808"
    )


def test_dormant_original_funded_schedules_hold_no_trade_credentials():
    from pathlib import Path
    for path, script in (
        (".github/workflows/fund100-v6-s1-original-first-acwi-funded-once.yml",
         "fund100_v6_s1_original_first_acwi_entry_locked_v1_0.py"),
        (".github/workflows/fund100-v6-s1-first-xlk-buy-funded-once.yml",
         "fund100_v6_s1_first_xlk_buy_original_entry_locked_v1_0.py"),
    ):
        source=Path(path).read_text()
        assert "ALPACA_LIVE_KEY" not in source
        assert "ALPACA_LIVE_SECRET" not in source
        assert "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN" not in source
        assert "FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX" not in source
        assert "secrets." not in source
        assert "GITHUB_TOKEN: " not in source
        assert "if: >-" in source and "REVIEWED_SOURCE_ONLY_ONE_SHOT" in source
        assert script in seen(source)
        assert (path,script) not in audit.PINNED_LIVE_CREDENTIAL_JOBS


def test_integrated_readonly_source_is_exact_pinned_despite_dual_write_capable_principals():
    from pathlib import Path
    workflow=".github/workflows/fund100-v6-integrated-journal-broker-strategy-getonly.yml"
    script="fund100_v6_integrated_journal_broker_strategy_getonly_v1_0.py"
    source=Path(workflow).read_text()
    assert seen(source).count(script)==1
    assert audit.PINNED_LIVE_CREDENTIAL_JOBS[(workflow,script)] == (
        "e21f0adc75454ee625bd2ebc8f9a92c51733a048"
    )
    assert audit.git_blob_digest(Path(workflow))==(
        "9cc579cf0c5c17938214ef6f5ddc32364c9a4aa4"
    )
    assert audit.approved_scoped_live_script(workflow,script,source)
    assert "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN: ${{ secrets.FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN }}" in source
    assert "FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN: ${{ secrets.FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN }}" in source
    assert "contents: write" not in source
    for changed in (
        source.replace("ENGAGED", "DISENGAGED"),
        source.replace("contents: read", "contents: write"),
        source.replace(
            "FUND100_PRIVATE_STATE_READ_TOKEN: ${{ secrets.FUND100_PRIVATE_STATE_READ_TOKEN }}",
            "FUND100_PRIVATE_STATE_READ_TOKEN: ${{ secrets.FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN }}"
        ),
        source.replace("python -B "+script,"python -u "+script),
        source.replace("github.event_name == 'push'",
                       "github.event_name == 'workflow_dispatch'"),
    ):
        assert changed!=source
        assert not audit.approved_scoped_live_script(
            workflow,script,changed
        )
    assert not audit.approved_scoped_live_script(
        ".github/workflows/fund100-live-risk-watch.yml",script,source
    )
