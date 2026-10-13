"""No-network regression of real LIVE writer terminal HTTP sink contract.

Expected baseline is FAIL-CLOSED for release, not a safe trading proof.
The in-memory fixed source is review evidence only; no protected writer
files are changed and no Alpaca requests are sent.
"""

from pathlib import Path

import pytest

import fund100_live_bootstrap_v1_0 as bootstrap
from fund100_live_terminal_write_guard_audit_v1_0 import (
    BOOTSTRAP, PRODUCTION,
    read_terminal_sources,
    scan_terminal_write_sources,
)


def _actual():
    return read_terminal_sources(Path(__file__).resolve().parent)


def _simulated_repair():
    original = _actual()
    anchor = "    data = None\n\n    if body is not None:"
    assert original[BOOTSTRAP].count(anchor) == 1
    strict_guard = (
        '    if method == "POST":\n'
        '        if path != "/v2/orders":\n'
        '            raise LiveBootstrapStop("Unsupported LIVE POST path")\n'
        '        if os.environ.get('
        '"FUND100_BROKER_KILL_SWITCH", ""'
        ').strip().upper() != "DISENGAGED":\n'
        '            raise LiveBootstrapStop("LIVE kill switch engaged")\n'
        '\n'
    )
    original[BOOTSTRAP] = original[BOOTSTRAP].replace(
        anchor, strict_guard + anchor, 1
    )
    return original


def test_actual_http_sink_is_not_released_by_higher_level_kill_checks():
    audit = scan_terminal_write_sources(_actual())
    assert audit.baseline_pinned is True
    assert audit.guarded_approved_order_path_count == 2
    assert audit.raw_network_sink_count == 2
    assert not audit.passed
    assert any(
        "bootstrap POST transport needs direct pre-HTTP gate" in p
        for p in audit.problems
    )


def test_reviewed_in_memory_sink_guard_satisfies_explicit_release_contract():
    virtual = _simulated_repair()
    report = scan_terminal_write_sources(
        virtual, verify_pins=False
    )
    assert report.passed, report.problems
    assert report.baseline_pinned is False
    # Changed production code must be independently reviewed and repinned.
    assert not scan_terminal_write_sources(virtual).passed


def test_omitting_in_memory_post_path_restriction_fails_closed():
    virtual = _simulated_repair()
    needle = (
        '        if path != "/v2/orders":\n'
        '            raise LiveBootstrapStop("Unsupported LIVE POST path")\n'
    )
    assert virtual[BOOTSTRAP].count(needle) == 1
    virtual[BOOTSTRAP] = virtual[BOOTSTRAP].replace(needle, "", 1)
    issues = scan_terminal_write_sources(
        virtual, verify_pins=False
    ).problems
    assert "POST endpoint unrestricted" in issues


def test_omitting_final_in_memory_kill_gate_fails_closed():
    virtual = _simulated_repair()
    needle = (
        '        if os.environ.get('
        '"FUND100_BROKER_KILL_SWITCH", ""'
        ').strip().upper() != "DISENGAGED":\n'
        '            raise LiveBootstrapStop("LIVE kill switch engaged")\n'
    )
    assert virtual[BOOTSTRAP].count(needle) == 1
    virtual[BOOTSTRAP] = virtual[BOOTSTRAP].replace(needle, "", 1)
    issues = scan_terminal_write_sources(
        virtual, verify_pins=False
    ).problems
    assert "POST sink has no final kill-switch check" in issues


def test_changed_source_requires_reviewed_blob_repin():
    sources = _actual()
    sources[PRODUCTION] += "\n# unreviewed source revision\n"
    issues = scan_terminal_write_sources(sources).problems
    assert any("reviewed LIVE order writer source changed" in s for s in issues)


def test_extra_live_post_endpoint_is_not_auto_authorized():
    sources = _simulated_repair()
    sources[PRODUCTION] += (
        '\ndef unsafe_candidate():\n'
        '    return live.live_request(method="POST", '
        'path="/v2/orders/cancel", body={})\n'
    )
    report = scan_terminal_write_sources(sources, verify_pins=False)
    assert not report.passed
    assert "production has unreviewed order POST destination" in report.problems


def test_guard_conditional_false_cannot_pass_contract():
    sources = _simulated_repair()
    sources[BOOTSTRAP] = sources[BOOTSTRAP].replace(
        '    if method == "POST":\n',
        '    if False and method == "POST":\n',
        1,
    )
    issues = scan_terminal_write_sources(
        sources, verify_pins=False
    ).problems
    assert "bootstrap POST transport needs direct pre-HTTP gate" in issues


def test_current_transport_with_engaged_process_switch_reaches_fake_post(
    monkeypatch,
):
    """Demonstrate missing sink-level check without any real network call."""
    received = []

    class StubResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return b'{"test":"stubbed_only"}'

    def fake_urlopen(req, *, timeout):
        received.append((req.get_method(), req.full_url, timeout))
        return StubResponse()

    monkeypatch.setenv("ALPACA_LIVE_KEY", "synthetic-test-key-only")
    monkeypatch.setenv("ALPACA_LIVE_SECRET", "synthetic-test-secret-only")
    monkeypatch.setenv("FUND100_BROKER_KILL_SWITCH", "ENGAGED")
    monkeypatch.setattr(bootstrap, "urlopen", fake_urlopen)
    result = bootstrap.live_request(
        method="POST",
        path="/v2/orders",
        body={"test": "nontrading_stub"},
    )
    assert result == {"test": "stubbed_only"}
    assert received == [
        ("POST", "https://api.alpaca.markets/v2/orders", 20)
    ]
    # A higher-level controller would have stopped a normal order path,
    # but the raw transport itself reached the FAKE network sink.


def test_current_transport_does_not_restrict_fake_post_endpoint(monkeypatch):
    received = []

    class StubResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return b"{}"

    def fake_urlopen(req, *, timeout):
        received.append(req.full_url)
        return StubResponse()

    monkeypatch.setenv("ALPACA_LIVE_KEY", "synthetic-test-key-only")
    monkeypatch.setenv("ALPACA_LIVE_SECRET", "synthetic-test-secret-only")
    monkeypatch.setenv("FUND100_BROKER_KILL_SWITCH", "ENGAGED")
    monkeypatch.setattr(bootstrap, "urlopen", fake_urlopen)
    assert bootstrap.live_request(
        method="POST",
        path="/v2/positions",
        body={"test": "nontrading_stub"},
    ) == {}
    assert received == ["https://api.alpaca.markets/v2/positions"]


@pytest.mark.parametrize("invalid", [None, 1, object()])
def test_missing_or_invalid_source_inputs_refused(invalid):
    with pytest.raises(TypeError):
        scan_terminal_write_sources(invalid)
