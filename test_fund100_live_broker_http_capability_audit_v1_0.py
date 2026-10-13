"""Offline negative regression for broker transport source capability scanner."""

from pathlib import Path

import pytest

from fund100_live_broker_http_capability_audit_v1_0 import (
    TRANSPORT_BLOBS,
    DORMANT_POST_MODULE,
    read_python_sources,
    scan_capability_sources,
)


def _sources():
    return read_python_sources(Path(__file__).resolve().parent)


def _mutate(filename, old, new):
    sources = _sources()
    assert old in sources[filename]
    sources[filename] = sources[filename].replace(old, new, 1)
    return sources


def test_actual_nonwriter_import_closure_contains_guarded_legacy_post():
    report = scan_capability_sources(_sources())
    assert len(report.credential_read_entrypoints) == 11
    assert DORMANT_POST_MODULE in report.analyzed_modules
    assert "fund100_alpaca_live_readonly_smoke" in report.analyzed_modules
    assert "fund100_live_pilot_prepare_v1_0" in report.analyzed_modules
    assert report.dormant_post_sites == (
        "fund100_alpaca_live_writer_disconnected._post_live_market_order",
    )
    assert report.passed, report.problems


def test_transport_source_hashes_reject_any_changes():
    for filename in TRANSPORT_BLOBS:
        sources = _sources()
        sources[filename] += "\n# revision demands independent source review\n"
        report = scan_capability_sources(sources)
        assert not report.passed
        assert any(
            "reviewed transport source changed" in item
            and filename in item for item in report.problems
        )


def test_removing_first_unconditional_writer_raise_rejected():
    sources = _mutate(
        "fund100_alpaca_live_writer_disconnected.py",
        '    raise LiveWriterDisconnected(',
        '    return None # hypothetical unsafe writer release\n'
        '    raise LiveWriterDisconnected(',
    )
    findings = scan_capability_sources(
        sources, verify_blob_pins=False
    ).problems
    assert any("writer disconnect no longer a hard stop" in x
               for x in findings)


def test_removing_first_legacy_post_guard_rejected():
    sources = _sources()
    filename = "fund100_alpaca_live_writer_disconnected.py"
    prefix, suffix = sources[filename].split(
        "def _post_live_market_order(", 1
    )
    needle = "    require_adapter_connected()\n\n    validate_credentials("
    assert needle in suffix
    suffix = suffix.replace(needle, "    validate_credentials(", 1)
    sources[filename] = prefix + "def _post_live_market_order(" + suffix
    findings = scan_capability_sources(
        sources, verify_blob_pins=False
    ).problems
    assert any("unapproved HTTP POST path" in x for x in findings)


def test_removing_disconnected_batch_guard_rejected():
    sources = _mutate(
        "fund100_alpaca_live_writer_disconnected_v1_1.py",
        "    require_adapter_connected()\n\n\n# ===",
        "    return None\n\n\n# ===",
    )
    findings = scan_capability_sources(
        sources, verify_blob_pins=False
    ).problems
    assert any("writer batch guard missing" in x for x in findings)


def test_new_unapproved_http_post_inside_reader_rejected():
    sources = _sources()
    filename = "fund100_alpaca_live_preflight.py"
    sources[filename] += (
        '\ndef new_network_client():\n'
        '    Request("https://api.alpaca.markets/v2/orders",'
        ' method="POST")\n'
    )
    findings = scan_capability_sources(
        sources, verify_blob_pins=False
    ).problems
    assert any("unapproved HTTP POST path" in x for x in findings)


def test_new_unreviewed_urlopen_in_reader_rejected():
    sources = _sources()
    filename = "fund100_alpaca_live_preflight.py"
    sources[filename] += (
        '\ndef new_network_client():\n'
        '    urlopen("https://api.alpaca.markets/v2/orders")\n'
    )
    findings = scan_capability_sources(
        sources, verify_blob_pins=False
    ).problems
    assert any("unexpected urllib network sink" in x for x in findings)


def test_new_dynamic_import_in_reader_rejected():
    sources = _sources()
    filename = "fund100_alpaca_live_preflight.py"
    sources[filename] += "\ndef surprise():\n    return __import__('requests')\n"
    findings = scan_capability_sources(
        sources, verify_blob_pins=False
    ).problems
    assert any("dynamic execution" in x for x in findings)


def test_new_subprocess_import_in_reader_rejected():
    sources = _sources()
    filename = "fund100_alpaca_live_preflight.py"
    sources[filename] += "\nimport subprocess\n"
    findings = scan_capability_sources(
        sources, verify_blob_pins=False
    ).problems
    assert any("unreviewed network/dynamic import" in x for x in findings)


def test_silent_missing_transitive_file_rejected():
    sources = _sources()
    sources.pop("fund100_alpaca_live_writer_disconnected_v1_1.py")
    report = scan_capability_sources(sources)
    assert not report.passed
    assert any(
        "missing transitive source" in item
        for item in report.problems
    )


def test_no_broker_credentials_read_or_network_called_by_audit():
    code = Path(__file__).resolve().parent.joinpath(
        "fund100_live_broker_http_capability_audit_v1_0.py"
    ).read_text(encoding="utf-8")
    assert "urlopen(" not in code
    assert "subprocess.run(" not in code
    assert "request.get(" not in code
    assert ".write_text(" not in code
    assert ".write_bytes(" not in code
