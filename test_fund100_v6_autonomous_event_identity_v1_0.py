"""Offline original-vs-recurring event ID, HOLD, no per-trade approval tests."""
from pathlib import Path
import pytest
import fund100_v6_autonomous_event_identity_v1_0 as cycle

VALID={
    "strategy_id":"V6_S1_CONCENTRATED_ETF",
    "signal_time_utc":"2026-10-26T11:15:00Z",
    "signal_sha256":"1"*64,
    "deployed_strategy_release_sha256":"2"*64,
    "standing_mandate_sha256":"3"*64,
}

def test_repeatable_event_identity_across_same_signal_and_mandate():
    first=cycle.key(**VALID)
    second=cycle.key(**dict(reversed(list(VALID.items()))))
    assert first==second
    assert first.startswith("V6EV-") and len(first)==45
    assert first!="fund100-original-ACWI-owner-client-id-v1"
    assert "ACWI" not in first
    assert not first.startswith("SIM-v6s1-")

@pytest.mark.parametrize("changed",[
    ("strategy_id","V6_S2_ANOTHER_SIGNAL"),
    ("signal_time_utc","2026-10-27T11:15:00Z"),
    ("signal_sha256","9"*64),
    ("deployed_strategy_release_sha256","8"*64),
    ("standing_mandate_sha256","7"*64),
])
def test_identity_namespaced_for_change_of_signal_or_standing_mandate(changed):
    k,v=changed
    assert cycle.key(**VALID)!=cycle.key(**dict(VALID,**{k:v}))

@pytest.mark.parametrize("field,bad",[
    ("strategy_id","V5_OLD"),
    ("strategy_id","V6_FAKE_STRATEGY"),
    ("strategy_id","V6_RANDOM_RESEARCH"),
    ("strategy_id","V6_BAD / INJECTION"),
    ("signal_time_utc","2026-10-26T11:15:01Z"),
    ("signal_time_utc","2026-02-30T11:15:00Z"),
    ("signal_time_utc","2026-10-26T11:15:00+00:00"),
    ("signal_sha256","ABCDEF"*10+"1111"),
    ("signal_sha256","z"*64),
    ("signal_sha256",""),
    ("deployed_strategy_release_sha256","f"*40),
    ("standing_mandate_sha256","not signed"),
])
def test_bad_identity_inputs_cannot_be_assigned_an_event(field,bad):
    with pytest.raises(cycle.IdentityStop):
        cycle.key(**dict(VALID,**{field:bad}))

def test_no_event_journal_never_trades_without_fresh_mandate_or_broker():
    e=cycle.key(**VALID)
    result=cycle.classify(current_event_id=e,observed_prior_event_ids=set())
    assert result["status"]=="HOLD_NEW_EVENT_AWAITS_AUTHENTICATED_APPROVED_STRATEGY_AND_BROKER"
    assert result["previous_event_known"] is False
    assert result["source_signal_authenticated"] is False
    assert result["standing_mandate_authenticated"] is False
    assert result["broker_reconciliation_proved"] is False
    assert result["broker_order_authorized"] is False
    assert result["broker_posts"]==0
    assert result["manual_per_trade_approval_required"] is False

def test_repeated_event_requires_reconciliation_not_a_second_send():
    e=cycle.key(**VALID)
    result=cycle.classify(current_event_id=e,observed_prior_event_ids={e})
    assert result["status"]=="HOLD_PRIOR_EVENT_RECONCILIATION"
    assert result["previous_event_known"] is True
    assert result["retry_old_event_authorized"] is False
    assert result["broker_posts"]==0

@pytest.mark.parametrize("value",[
    None,[],{},["V6EV-"+"0"*40],{"bad"},set(["V6EV-"+"g"*40]),
])
def test_ambiguous_or_malformed_journal_snapshot_stops(value):
    with pytest.raises(cycle.IdentityStop):
        cycle.classify(current_event_id=cycle.key(**VALID),
                       observed_prior_event_ids=value)

def test_no_live_order_credential_network_or_rebalance_policy_implemented():
    s=Path(cycle.__file__).read_text()
    assert cycle.ORDER_WRITER_RELEASED is False
    assert cycle.NO_BROKER_OR_CREDENTIAL_HOOKS is True
    assert cycle.NO_STRATEGY_RANKING_OR_REBALANCING is True
    assert 'import os' not in s
    assert 'import requests' not in s
    assert 'import urllib' not in s
    assert 'ALPACA_LIVE_KEY' not in s
    assert "method=\"POST\"" not in s
    assert "def main(" not in s
