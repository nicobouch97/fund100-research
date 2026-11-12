"""Offline SQLite atomic CSRF tests; no credentials, no network, no broker."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os
import sqlite3
import stat

import pytest
import fund100_v6_oauth_atomic_sqlite_csrf_v1_0 as state

KEY = b"f100-mock-private-hmac-key-for-offline-test-not-production"


@pytest.fixture()
def db(tmp_path):
    return state.SingleUseCSRF(db_path=str(tmp_path/"session.sqlite3"),hmac_key=KEY)


def test_persistent_single_use_validity(db):
    raw = db.issue(now_epoch=1_800_000_000)
    assert len(raw) >= 40
    assert db.consume(state=raw,now_epoch=1_800_000_001) is True
    assert db.consume(state=raw,now_epoch=1_800_000_001) is False


def test_state_not_stored_in_plaintext_even_on_reopen(db):
    raw=db.issue(now_epoch=1_800_000_000)
    disk=Path(db.path).read_bytes()
    assert raw.encode() not in disk
    assert KEY not in disk
    again=state.SingleUseCSRF(db_path=db.path,hmac_key=KEY)
    assert again.consume(state=raw,now_epoch=1_800_000_010)
    assert stat.S_IMODE(os.stat(db.path).st_mode) == 0o600


def test_expiry_boundaries_and_clock_regressions(db):
    raw=db.issue(now_epoch=1_800_000_000)
    assert not db.consume(state=raw, now_epoch=1_799_999_999)
    assert db.consume(state=raw, now_epoch=1_800_000_299)

    next_state=db.issue(now_epoch=1_800_000_000)
    assert not db.consume(state=next_state,now_epoch=1_800_000_300)
    assert not db.consume(state=next_state,now_epoch=1_800_000_301)


def test_second_session_cancels_first(db):
    a=db.issue(now_epoch=1_800_000_000)
    b=db.issue(now_epoch=1_800_000_001)
    assert a != b
    assert db.consume(state=a,now_epoch=1_800_000_002) is False
    assert db.consume(state=b,now_epoch=1_800_000_002) is True


def test_atomic_replay_under_concurrency(db):
    token=db.issue(now_epoch=1_800_000_000)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results=list(pool.map(
            lambda _:db.consume(state=token,now_epoch=1_800_000_050),
            range(8)))
    assert results.count(True)==1
    assert results.count(False)==7


def test_missing_or_bad_hmac_key_denies(tmp_path):
    for bad in (None,b"",b"short","not bytes",KEY*4):
        with pytest.raises(state.OneTimeStateStop):
            state.SingleUseCSRF(db_path=str(tmp_path/"store.sqlite3"),
                                hmac_key=bad)


def test_bad_storage_path_denies(tmp_path):
    for path in ("relative.sqlite3",str(tmp_path/"missing"/"store.sqlite3"),
                 str(tmp_path/"other.db")):
        with pytest.raises(state.OneTimeStateStop):
            state.SingleUseCSRF(db_path=path,hmac_key=KEY)


def test_symlink_and_world_readable_db_denied(tmp_path):
    actual=tmp_path/"real.sqlite3"
    db=state.SingleUseCSRF(db_path=str(actual),hmac_key=KEY)
    other=tmp_path/"link.sqlite3"
    other.symlink_to(actual)
    with pytest.raises(state.OneTimeStateStop):
        state.SingleUseCSRF(db_path=str(other),hmac_key=KEY)
    actual.chmod(0o644)
    with pytest.raises(state.OneTimeStateStop,match="permissions"):
        state.SingleUseCSRF(db_path=str(actual),hmac_key=KEY)


@pytest.mark.parametrize("epoch",[-1,True,0,1_000_000_000,4_000_000_000,
                                  None,"1800000000",1.8e9])
def test_invalid_clock_denied(db,epoch):
    with pytest.raises(state.OneTimeStateStop,match="clock"):
        db.issue(now_epoch=epoch)
    token=db.issue(now_epoch=1_800_000_000)
    with pytest.raises(state.OneTimeStateStop,match="clock"):
        db.consume(state=token,now_epoch=epoch)


@pytest.mark.parametrize("value",["",None,"A"*39,"z"*129,"a b",True,"a="*22])
def test_untrusted_callback_state_denied(db,value):
    with pytest.raises(state.OneTimeStateStop):
        db.consume(state=value,now_epoch=1_800_000_000)


def test_hmac_key_rotation_cannot_validate_old_pending_session(db):
    raw=db.issue(now_epoch=1_800_000_000)
    changed=state.SingleUseCSRF(
        db_path=db.path,hmac_key=b"another-mock-private-hmac-key-for-rotation-test")
    assert not changed.consume(state=raw,now_epoch=1_800_000_002)
    assert db.consume(state=raw,now_epoch=1_800_000_002)


def test_no_network_no_token_storage_no_order_code():
    path=Path(state.__file__)
    source=path.read_text()
    assert "NO_NETWORK = True" in source
    assert "NO_TOKEN_STORAGE = True" in source
    assert "NO_TRADE_RELEASE = True" in source
    assert "urlopen(" not in source
    assert "/v2/orders" not in source
    assert "access_token" not in source
