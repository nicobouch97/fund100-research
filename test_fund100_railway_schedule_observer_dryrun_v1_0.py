"""Offline/no-network tests for isolated Railway schedule observation only."""
from datetime import datetime, timezone, timedelta
from io import BytesIO
import json
from pathlib import Path

import pytest

import fund100_railway_schedule_observer_dryrun_v1_0 as observer


NOW = datetime(2026, 11, 11, 17, 0, tzinfo=timezone.utc)
BASE = {
    "id": 456, "path": observer.EXPECTED_WORKFLOW_PATH,
    "event": "schedule", "head_branch": "main",
    "created_at": "2026-11-11T16:50:00Z",
}


def sample(**overrides):
    return {"workflow_runs": [dict(BASE, **overrides)], "total_count": 1}


class FakeResponse:
    status = 200
    def __init__(self, body):
        self.body = BytesIO(body)
    def __enter__(self):
        return self
    def __exit__(self, *exc):
        return False
    def read(self, count):
        return self.body.read(count)


def test_recent_schedule_is_not_a_broker_risk_pass():
    result = observer.classify(sample(), now=NOW)
    assert result == {"observation": "SCHEDULE_RUN_RECORDED_NOT_RISK_PASS",
                      "seconds_since_last_recorded_run": 600}


def test_stale_source_is_not_safe():
    result = observer.classify(
        sample(created_at="2026-11-11T12:09:16Z"), now=NOW)
    assert result["observation"] == "SCHEDULE_ACTIVITY_STALE"
    assert result["seconds_since_last_recorded_run"] == 17444


def test_empty_source_never_claims_observed_run():
    assert observer.classify(
        {"workflow_runs": [], "total_count": 0}, now=NOW
    )["observation"] == "NO_RECORDED_SCHEDULE_RUN"


@pytest.mark.parametrize("bad", [
    None, [], {}, {"workflow_runs": "fake", "total_count": 1},
    {"workflow_runs": [], "total_count": 4},
    {"workflow_runs": [BASE, BASE], "total_count": 2},
    {"workflow_runs": [123], "total_count": 1},
    {"workflow_runs": [dict(BASE, event="workflow_dispatch")], "total_count": 1},
    {"workflow_runs": [dict(BASE, path="any.yml")], "total_count": 1},
    {"workflow_runs": [dict(BASE, head_branch="untrusted")], "total_count": 1},
    {"workflow_runs": [dict(BASE, created_at="2026-11-11T17:15:00Z")], "total_count": 1},
    {"workflow_runs": [dict(BASE, created_at="yesterday")], "total_count": 1},
    {"workflow_runs": [dict(BASE, id=True)], "total_count": 1},
])
def test_ambiguous_or_untrusted_evidence_rejected(bad):
    with pytest.raises(observer.ScheduleObservationError):
        observer.classify(bad, now=NOW)


def test_naive_time_rejected():
    with pytest.raises(observer.ScheduleObservationError):
        observer.classify(sample(), now=datetime(2026,11,11,17,0))


def test_get_request_is_one_public_noauth_no_trade_request():
    calls = []
    def fake(request, timeout):
        calls.append((request, timeout))
        return FakeResponse(json.dumps(sample()).encode())
    result = observer.observe_once(now=NOW, transport=fake)
    assert len(calls) == 1
    req, timeout = calls[0]
    assert timeout == 12
    assert req.full_url == observer.API
    assert req.get_method() == "GET"
    assert req.get_header("Authorization") is None
    assert req.get_header("Apca-api-key-id") is None
    assert result["observation"] == "SCHEDULE_RUN_RECORDED_NOT_RISK_PASS"
    assert result["broker_requests"] == 0
    assert result["github_writes"] == result["order_posts"] == 0
    assert result["risk_pass_attested"] is False
    assert result["trading_authorized"] is False


def test_unavailable_github_or_json_is_diagnostic_only():
    for failure in ("timeout", "json", "oversized"):
        def fake(request, timeout):
            if failure == "timeout":
                raise TimeoutError("fictional interruption")
            if failure == "json":
                return FakeResponse(b"not-json")
            return FakeResponse(b"x" * (observer.MAX_RESPONSE_BYTES + 1))
        result = observer.observe_once(now=NOW, transport=fake)
        assert result["observation"] == "SOURCE_UNAVAILABLE"
        assert result["risk_pass_attested"] is False
        assert result["trading_authorized"] is False


def test_future_timestamp_never_claims_scheduled_pass():
    def future(request, timeout):
        return FakeResponse(json.dumps(sample(
            created_at="2026-11-11T17:10:00Z")).encode())
    out = observer.observe_once(now=NOW, transport=future)
    assert out["observation"] == "SOURCE_UNAVAILABLE"
    assert out["risk_pass_attested"] is False


def test_source_contains_no_live_trading_or_api_secret_access():
    source = Path(observer.__file__).read_text()
    assert "ALPACA_LIVE_KEY" not in source
    assert "ALPACA_LIVE_SECRET" not in source
    assert "api.alpaca.markets" not in source
    assert "Authorization" not in source
    assert "method=\"POST\"" not in source
    assert "method=\"PUT\"" not in source
    assert "method=\"DELETE\"" not in source
    assert "trading_authorized" in source
    assert observer.NO_BROKER and observer.NO_AUTH and observer.NO_WRITE
    assert observer.NO_TRADE
    assert observer.POLL_SECONDS >= 300


def test_container_isolated_from_repo_and_no_creds():
    docker = Path("Dockerfile").read_text()
    assert "fund100_railway_schedule_observer_dryrun_v1_0.py" in docker
    assert "COPY ." not in docker
    assert "ENV ALPACA" not in docker
    assert "USER observer" in docker
    assert "HEALTHCHECK" not in docker
    assert "python" in docker
