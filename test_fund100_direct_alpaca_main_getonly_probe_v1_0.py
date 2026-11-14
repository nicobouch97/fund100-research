"""Offline assertions for direct-key, GET-only main branch readiness probe.

No broker credentials, no network. This test's approval alone does not prove
actual live account connectivity or independent risk monitoring.
"""
from pathlib import Path

import fund100_alpaca_live_readonly_smoke as smoke


def test_existing_smoke_remains_get_only_and_redirect_safe():
    src=Path(smoke.__file__).read_text()
    assert smoke.LIVE_BASE_URL=="https://api.alpaca.markets"
    assert smoke.EXPECTED_LIVE_HOST=="api.alpaca.markets"
    assert "method=\"GET\"" in src
    assert "method=\"POST\"" not in src
    assert "method=\"DELETE\"" not in src
    assert "with build_opener(_NoRedirect()).open(" in src
    assert "response.geturl() != url" in src
    assert "urlopen(" not in src


def test_live_workflow_main_only_no_write_permissions_or_secret_spread():
    workflow=Path(".github/workflows/fund100-alpaca-live-readonly.yml").read_text()
    assert "branches: [main]" in workflow
    assert "environment: fund100-live-broker" in workflow
    assert "permissions:\n  contents: read" in workflow
    assert "persist-credentials: false" in workflow
    assert "github.repository == 'nicobouch97/fund100-research'" in workflow
    assert "github.ref == 'refs/heads/main'" in workflow
    assert "git rev-parse HEAD" in workflow
    assert "GITHUB_WORKFLOW_REF" in workflow
    assert "git hash-object fund100_alpaca_live_readonly_smoke.py" in workflow
    assert "a8cf058595a960d67055a63e65f574530f7074c8" in workflow
    assert "FUND100_LIVE_WRITE_MODE: DISABLED" in workflow
    assert "FUND100_BROKER_KILL_SWITCH: ${{ vars.FUND100_BROKER_KILL_SWITCH }}" in workflow
    assert "FUND100_ENABLE_LIVE_READONLY: YES_READ_ONLY_LIVE" in workflow
    assert "python -B - <<'PY'" in workflow
    assert "smoke.main()" in workflow
    assert "secrets.ALPACA_LIVE_KEY" in workflow
    assert "secrets.ALPACA_LIVE_SECRET" in workflow
    assert "contents: write" not in workflow
    assert "actions: write" not in workflow
    assert "python fund100_live_production_controller" not in workflow
    assert "fund100_live_emergency_stop_v1_0.py" not in workflow
    assert "python fund100_alpaca_live_writer_candidate" not in workflow
    assert "workflow_run:" not in workflow


def test_live_workflow_secret_step_after_source_scope_preflight():
    src=Path(".github/workflows/fund100-alpaca-live-readonly.yml").read_text()
    guard=src.index("Verify main workflow, exact checkout and reviewed GET-only source")
    secret=src.index("ALPACA_LIVE_KEY: ${{ secrets.ALPACA_LIVE_KEY }}")
    assert guard<secret
    assert src.count("secrets.ALPACA_LIVE_KEY")==1
    assert src.count("secrets.ALPACA_LIVE_SECRET")==1
    assert src.count("smoke.main()")==1
