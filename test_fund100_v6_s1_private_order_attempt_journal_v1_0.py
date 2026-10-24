"""Research-only SQLite order journal: crashes, concurrency and no-resubmit."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os
import sqlite3
import stat
import subprocess
import sys
import pytest

import fund100_v6_s1_private_order_attempt_journal_v1_0 as j
import fund100_v6_s1_frac_live_sell_writer_candidate_v1_0 as sell

BINDING="a"*64
KEY=b"INVENTED_UNIT_TEST_PRIVATE_HMAC_KEY_00000000000000000000000000"
Q="0.123456789"

def disk(tmp_path):
    parent=tmp_path/"private"
    parent.mkdir(mode=0o700)
    assert stat.S_IMODE(parent.stat().st_mode)==0o700
    return parent/"attempts.sqlite"

def launch(path,*,key=KEY,binding=BINDING):
    return j.PrivateJournal(path=path,account_binding_sha256=binding,
                            private_hmac_key=key)

def fake_receipt(symbol="ACWI",qty=Q,status="filled",filled=None):
    return {"id":"FAKE-ALPACA-ORDER",
       "client_order_id":sell._id(symbol),"symbol":symbol,
       "side":"sell","type":"market","time_in_force":"day",
       "qty":qty,"notional":None,"filled_qty":filled if filled is not None else qty,
       "status":status,"filled_at":"2026-10-19T18:00:00Z"}

def fake_full_exit(db,symbol,qty=Q):
    a=db.reserve_next(symbol=symbol,original_qty=qty)
    assert a["stage"]=="NEW_PRIVATE_RESERVATION_NO_BROKER_AUTHORITY"
    b=db.mark_possible_post(symbol=symbol,original_qty=qty)
    assert b["stage"]=="POST_BOUNDARY_JOURNALED_NO_REAL_POST"
    c=db.observe_synthetic_receipt(symbol=symbol,original_qty=qty,
        receipt=fake_receipt(symbol=symbol,qty=qty),currently_held_qty="0")
    assert c["stage"]=="SIM_FULL_FILL_AND_POSITION_FLAT"
    assert c["live_order_authorized"] is False
    return c

def no_broker(result):
    assert result["broker_get_requests"]==result["broker_order_posts"]==0
    assert not result["live_order_authorized"]
    assert not result["broker_404_is_safe_to_retry"]
    assert not result["order_may_be_resubmitted"]
    assert result["private_quantity"] is None
    assert result["account_identifier"] is None
    assert result["order_payload"] is None
    assert not result["externally_anchored_persistent_volume"]
    assert not result["survives_new_ephemeral_actions_runner"]

def test_atomic_reserve_survives_reopening_and_is_not_resubmitted(tmp_path):
    path=disk(tmp_path)
    with launch(path) as db:
        a=db.reserve_next(symbol="ACWI",original_qty=Q)
        assert a["stage"]=="NEW_PRIVATE_RESERVATION_NO_BROKER_AUTHORITY"
        assert a["revision"]==1
        no_broker(a)
    assert stat.S_IMODE(path.stat().st_mode)==0o600
    with launch(path) as reopened:
        same=reopened.reserve_next(symbol="ACWI",original_qty=Q)
        assert same["stage"]=="ALREADY_RESERVED_NEVER_DUPLICATE"
        no_broker(same)
        assert reopened.current(symbol="ACWI",original_qty=Q)["stage"]=="RESERVED_NO_RETRY"

def test_restart_after_maybe_post_boundary_never_reposts(tmp_path):
    path=disk(tmp_path)
    with launch(path) as db:
        db.reserve_next(symbol="ACWI",original_qty=Q)
        db.mark_possible_post(symbol="ACWI",original_qty=Q)
    with launch(path) as restarted:
        assert restarted.current(symbol="ACWI",original_qty=Q)["stage"]=="POST_MAY_HAVE_BEEN_SENT"
        no_broker(restarted.reserve_next(symbol="ACWI",original_qty=Q))
        stop=restarted.mark_possible_post(symbol="ACWI",original_qty=Q)
        assert stop["stage"]=="EXISTING_UNCERTAIN_ATTEMPT_NO_RESUBMIT"

def test_original_order_is_sequential_and_xle_never_sold(tmp_path):
    with launch(disk(tmp_path)) as db:
        assert db.reserve_next(symbol="EEM",original_qty=Q)["stage"]=="WAIT_PRIOR_LEGACY_EXIT_RECONCILIATION"
        fake_full_exit(db,"ACWI")
        assert db.reserve_next(symbol="XLV",original_qty=Q)["stage"]=="WAIT_PRIOR_LEGACY_EXIT_RECONCILIATION"
        fake_full_exit(db,"EEM")
        fake_full_exit(db,"XLV")
        for bad in ("XLE","XLK","IWM","AAPL","acwi"):
            with pytest.raises(j.JournalStop):
                db.reserve_next(symbol=bad,original_qty=Q)
        for sym in sell.LEGACY_TO_EXIT:
            assert db.current(symbol=sym,original_qty=Q)["stage"]=="SIM_FILLED_AND_FLAT_RECONCILED"

def test_private_db_never_persists_raw_quantity_hmac_key_or_account_id(tmp_path):
    path=disk(tmp_path)
    with launch(path) as db:
        db.reserve_next(symbol="ACWI",original_qty=Q)
    contents=path.read_bytes()
    assert Q.encode() not in contents
    assert KEY not in contents
    assert b"account-number" not in contents
    assert sell._id("ACWI").encode() in contents  # identity is nonsecret metadata
    assert b"ACWI" in contents

def test_external_account_binding_or_lost_key_cannot_reopen_order(tmp_path):
    path=disk(tmp_path)
    with launch(path) as db:
        db.reserve_next(symbol="ACWI",original_qty=Q)
    with pytest.raises(j.JournalStop):
        launch(path,binding="b"*64)
    with launch(path,key=b"DIFFERENT_PRIVATE_KEY_"*3) as db:
        with pytest.raises(j.JournalStop,match="Different quantity"):
            db.reserve_next(symbol="ACWI",original_qty=Q)
    with launch(path) as db:
        with pytest.raises(j.JournalStop,match="Different quantity"):
            db.reserve_next(symbol="ACWI",original_qty="0.123456788")

def test_existing_reservation_denies_change_of_share_qty(tmp_path):
    with launch(disk(tmp_path)) as db:
        db.reserve_next(symbol="ACWI",original_qty="12.125")
        with pytest.raises(j.JournalStop):
            db.mark_possible_post(symbol="ACWI",original_qty="12.126")
        with pytest.raises(j.JournalStop):
            db.observe_synthetic_receipt(symbol="ACWI",original_qty="12.126",receipt=None,
                                         currently_held_qty="12.125")

def test_missing_position_snapshot_even_with_filled_receipt_cannot_complete_offline_exit(tmp_path):
    path=disk(tmp_path)
    with launch(path) as db:
        db.reserve_next(symbol="ACWI",original_qty=Q)
        db.mark_possible_post(symbol="ACWI",original_qty=Q)
        held=db.observe_synthetic_receipt(
            symbol="ACWI",original_qty=Q,
            receipt=fake_receipt(),currently_held_qty=None)
        assert held["stage"]=="NO_RETRY_BROKER_RECONCILIATION_HOLD"
        assert not held["live_order_authorized"]
        assert db.reserve_next(symbol="EEM",original_qty=Q)["stage"]=="WAIT_PRIOR_LEGACY_EXIT_RECONCILIATION"


def test_missing_or_404_receipt_after_attempt_is_still_uncertain(tmp_path):
    path=disk(tmp_path)
    with launch(path) as db:
        db.reserve_next(symbol="ACWI",original_qty=Q)
        db.mark_possible_post(symbol="ACWI",original_qty=Q)
        hold=db.observe_synthetic_receipt(symbol="ACWI",original_qty=Q,
                    receipt=None,currently_held_qty=Q)
        assert hold["stage"]=="NO_RETRY_BROKER_RECONCILIATION_HOLD"
        assert db.reserve_next(symbol="EEM",original_qty=Q)["stage"]=="WAIT_PRIOR_LEGACY_EXIT_RECONCILIATION"
    with launch(path) as db:
        again=db.reserve_next(symbol="ACWI",original_qty=Q)
        assert again["stage"]=="ALREADY_RESERVED_NEVER_DUPLICATE"
        no_broker(again)

@pytest.mark.parametrize("status,filled,held",[
    ("partially_filled","0.06","0.063456789"),
    ("pending_new","0",Q),
    ("new","0",Q),
    ("pending_cancel","0.06","0.063456789"),
    ("filled",Q,"0.000000001"),
])
def test_partial_open_or_filled_with_residual_does_not_advance(tmp_path,status,filled,held):
    with launch(disk(tmp_path)) as db:
        db.reserve_next(symbol="ACWI",original_qty=Q)
        db.mark_possible_post(symbol="ACWI",original_qty=Q)
        r=db.observe_synthetic_receipt(symbol="ACWI",original_qty=Q,
                receipt=fake_receipt(status=status,filled=filled),currently_held_qty=held)
        no_broker(r)
        assert r["stage"]=="NO_RETRY_BROKER_RECONCILIATION_HOLD"
        assert db.reserve_next(symbol="EEM",original_qty=Q)["stage"]=="WAIT_PRIOR_LEGACY_EXIT_RECONCILIATION"

@pytest.mark.parametrize("status",["canceled","rejected","expired","replaced","held","pending_replace"])
def test_terminal_and_ambiguous_receipt_permanently_held_not_resubmitted(tmp_path,status):
    with launch(disk(tmp_path)) as db:
        db.reserve_next(symbol="ACWI",original_qty=Q)
        db.mark_possible_post(symbol="ACWI",original_qty=Q)
        r=db.observe_synthetic_receipt(symbol="ACWI",original_qty=Q,
                receipt=fake_receipt(status=status,filled="0"),currently_held_qty=Q)
        assert r["stage"]=="NO_RETRY_BROKER_RECONCILIATION_HOLD"
        assert db.current(symbol="ACWI",original_qty=Q)["stage"]=="HOLD_TERMINAL_OR_AMBIGUOUS"
        later=db.observe_synthetic_receipt(symbol="ACWI",original_qty=Q,
                receipt=fake_receipt(),currently_held_qty=None)
        assert later["stage"]=="PERMANENT_TERMINAL_REVIEW_NO_RETRY"
        assert db.reserve_next(symbol="EEM",original_qty=Q)["stage"]=="WAIT_PRIOR_LEGACY_EXIT_RECONCILIATION"

@pytest.mark.parametrize("field,bad",[
    ("client_order_id","wrong"),("symbol","XLE"),("side","buy"),
    ("type","limit"),("qty","0.2"),("time_in_force","gtc"),
    ("filled_qty","0.123456790"),("filled_at",None),
])
def test_receipt_mismatch_fails_no_progress(tmp_path,field,bad):
    with launch(disk(tmp_path)) as db:
        db.reserve_next(symbol="ACWI",original_qty=Q)
        db.mark_possible_post(symbol="ACWI",original_qty=Q)
        r=fake_receipt()
        r[field]=bad
        with pytest.raises(j.JournalStop,match="receipt"):
            db.observe_synthetic_receipt(symbol="ACWI",original_qty=Q,
                                         receipt=r,currently_held_qty=None)
        assert db.current(symbol="ACWI",original_qty=Q)["stage"]=="POST_MAY_HAVE_BEEN_SENT"

def test_receipt_cannot_mysteriously_appear_before_attempt_boundary(tmp_path):
    with launch(disk(tmp_path)) as db:
        db.reserve_next(symbol="ACWI",original_qty=Q)
        with pytest.raises(j.JournalStop):
            db.observe_synthetic_receipt(symbol="ACWI",original_qty=Q,
                                         receipt=fake_receipt(),currently_held_qty=None)

def test_two_concurrent_connections_only_one_can_create_reservation(tmp_path):
    path=disk(tmp_path)
    def contender(_):
        with launch(path) as db:
            return db.reserve_next(symbol="ACWI",original_qty=Q)["stage"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(contender,[1,2]))
    assert sorted(results)==sorted(["NEW_PRIVATE_RESERVATION_NO_BROKER_AUTHORITY",
                                   "ALREADY_RESERVED_NEVER_DUPLICATE"])

def test_real_separate_python_process_can_reopen_existing_attempt_without_replay(tmp_path):
    path=disk(tmp_path)
    with launch(path) as db:
        db.reserve_next(symbol="ACWI",original_qty=Q)
    # Fully separate Python interpreter with only an invented key.
    script=("from pathlib import Path\n"
            "import fund100_v6_s1_private_order_attempt_journal_v1_0 as j\n"
            f"with j.PrivateJournal(path=Path({str(path)!r}),"
            f"account_binding_sha256={BINDING!r},private_hmac_key={KEY!r}) as db:\n"
            f" print(db.reserve_next(symbol='ACWI',original_qty={Q!r})['stage'])\n")
    proc=subprocess.run([sys.executable,"-c",script],
                        cwd=str(Path(j.__file__).parent),capture_output=True,text=True,check=True)
    assert proc.stdout.strip()=="ALREADY_RESERVED_NEVER_DUPLICATE"

@pytest.mark.parametrize("bad",["bad","not-a-sha",None,1,"A"*64])
def test_invalid_binding_fails_before_creating_a_journal(tmp_path,bad):
    path=disk(tmp_path)
    with pytest.raises(j.JournalStop):
        launch(path,binding=bad)
    assert not path.exists()

@pytest.mark.parametrize("bad",[b"",b"short","INVENTED_NOT_BYTES",None])
def test_short_or_nonbytes_key_rejected(tmp_path,bad):
    path=disk(tmp_path)
    with pytest.raises(j.JournalStop):
        launch(path,key=bad)
    assert not path.exists()

def test_private_parent_symlink_and_permissions_enforced(tmp_path):
    other=tmp_path/"unsafe"
    other.mkdir(mode=0o700)
    os.chmod(other,0o755)
    with pytest.raises(j.JournalStop):
        launch(other/"bad.sqlite")
    os.chmod(other,0o700)
    private=tmp_path/"private"
    private.mkdir(mode=0o700)
    path=private/"ledger.sqlite"
    with launch(path):pass
    os.chmod(path,0o644)
    with pytest.raises(j.JournalStop):
        launch(path)
    path.unlink()
    symlink=private/"symlink.sqlite"
    symlink.symlink_to(private/"no-such-file")
    with pytest.raises(j.JournalStop):
        launch(symlink)

def test_corrupt_reservation_symbol_and_status_denied(tmp_path):
    path=disk(tmp_path)
    with launch(path) as db:db.reserve_next(symbol="ACWI",original_qty=Q)
    con=sqlite3.connect(str(path))
    con.execute("UPDATE reservations SET state='UNRECOGNIZED' WHERE symbol='ACWI'")
    con.commit()
    con.close()
    with pytest.raises(j.JournalStop):
        launch(path)

def test_simulated_full_fill_can_eventually_recover_after_partial(tmp_path):
    path=disk(tmp_path)
    with launch(path) as db:
        db.reserve_next(symbol="ACWI",original_qty=Q)
        db.mark_possible_post(symbol="ACWI",original_qty=Q)
        db.observe_synthetic_receipt(symbol="ACWI",original_qty=Q,
            receipt=fake_receipt(status="partially_filled",filled="0.06"),
            currently_held_qty="0.063456789")
    with launch(path) as restarted:
        success=restarted.observe_synthetic_receipt(symbol="ACWI",original_qty=Q,
            receipt=fake_receipt(),currently_held_qty="0")
        assert success["stage"]=="SIM_FULL_FILL_AND_POSITION_FLAT"
        assert restarted.reserve_next(symbol="EEM",original_qty=Q)["stage"]=="NEW_PRIVATE_RESERVATION_NO_BROKER_AUTHORITY"

def test_no_live_broker_execution_and_readonly_original_operator_unmodified():
    source=Path(j.__file__).read_text()
    assert j.OFFLINE_RELEASED is False
    assert j.MODE=="SYNTHETIC_BROKER_EVENTS_ONLY"
    for bad in ("ALPACA_LIVE_KEY","ALPACA_LIVE_SECRET","urlopen(",
                "method=\"POST\"","requests.post(","httpx.post(",
                "os.environ","getenv(","submit_"+"authorized_order_batch("):
        assert bad not in source
    import fund100_alpaca_live_writer_candidate_v1_1 as v5
    assert v5.TRANSPORT_RELEASED is False
    assert v5.PUBLIC_EXECUTION_ENABLED is False
    assert sell.TRANSPORT_RELEASED is False
    assert sell.PUBLIC_EXECUTION_ENABLED is False
