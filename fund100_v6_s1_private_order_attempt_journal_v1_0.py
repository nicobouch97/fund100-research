"""V6-S1 private on-disk atomic PRE-POST journal; OFFLINE and NON-EXECUTABLE.

Stores HMAC commitments and categorical order states, no raw shares or
account ID. SQLite durability is only for a retained local filesystem.
No connection to LIVE broker or GitHub, and no proof of off-host ledger
continuity. Never use an ephemeral GitHub Actions DB for actual orders.
"""
from __future__ import annotations

from contextlib import contextmanager
from hashlib import sha256
import hmac
import os
from pathlib import Path
import secrets
import sqlite3
import stat

import fund100_v6_s1_frac_live_sell_writer_candidate_v1_0 as sell

SCHEMA="FUND100_V6_S1_PRIVATE_SQLITE_PRE_POST_ATTEMPT_LEDGER_OFFLINE_V1"
MODE="SYNTHETIC_BROKER_EVENTS_ONLY"
STATES=frozenset({"RESERVED_NO_RETRY","POST_MAY_HAVE_BEEN_SENT",
    "HOLD_BROKER_RECONCILIATION","HOLD_TERMINAL_OR_AMBIGUOUS",
    "SIM_FILLED_AND_FLAT_RECONCILED"})
OFFLINE_RELEASED=False

class JournalStop(RuntimeError):pass

def _require_private_path(p:Path)->None:
    if not p.is_absolute():
        raise JournalStop("Ledger path must be absolute, local and private")
    parent=p.parent
    if not parent.is_dir() or parent.is_symlink():
        raise JournalStop("Ledger directory must exist and not be a symlink")
    st=parent.stat()
    if (st.st_uid!=os.getuid() or stat.S_IMODE(st.st_mode)&0o077):
        raise JournalStop("Ledger directory must be owned and 0700 private")
    if p.is_symlink():
        raise JournalStop("Ledger cannot be a symlink")
    if p.exists():
        fs=p.stat()
        if (not stat.S_ISREG(fs.st_mode) or fs.st_uid!=os.getuid()
            or stat.S_IMODE(fs.st_mode)!=0o600):
            raise JournalStop("Existing ledger must be owned regular file mode 0600")

def _init_file(p:Path)->None:
    _require_private_path(p)
    if not p.exists():
        try:
            fd=os.open(str(p),os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        except FileExistsError:
            pass  # another transaction owner must still have 0600; check below
        except OSError as exc:
            raise JournalStop("Cannot atomically create private ledger") from None
        else:
            os.close(fd)
    _require_private_path(p)

def _digest(key:bytes,binding:str,symbol:str,qty:str)->str:
    normalized=fill_qty(qty)
    data="|".join((sell.MIGRATION_KEY,binding,symbol,normalized)).encode("utf-8")
    return hmac.new(key,data,sha256).hexdigest()

def fill_qty(value:str)->str:
    return format(sell._qty(value),"f")

class PrivateJournal:
    """One locally persistent SQLite database bound to exactly one pilot.

    Public methods accept synthetic broker events ONLY, return zero
    executable orders, and do not accept an actual LIVE source mode.
    """
    def __init__(self,*,path:Path,account_binding_sha256:str,
                 private_hmac_key:bytes,mode:str=MODE):
        if mode!=MODE:
            raise JournalStop("Original LIVE broker source not released for journal")
        if type(private_hmac_key) is not bytes or len(private_hmac_key)<32:
            raise JournalStop("Private HMAC key must be memory-only >=32 bytes")
        if (type(account_binding_sha256) is not str
            or len(account_binding_sha256)!=64
            or any(c not in "0123456789abcdef" for c in account_binding_sha256)):
            raise JournalStop("Account binding must be original lowercase SHA256 commitment")
        if not isinstance(path,Path):
            raise JournalStop("No private persistent-path instance")
        _init_file(path)
        self.path=path
        self.binding=account_binding_sha256
        self._key=private_hmac_key
        try:
            self.db=sqlite3.connect(str(path),timeout=1.0,isolation_level=None)
            self.db.execute("PRAGMA busy_timeout=1000")
            self.db.execute("PRAGMA synchronous=FULL")
            self.db.execute("PRAGMA journal_mode=DELETE")
            self.db.execute("PRAGMA foreign_keys=ON")
            with self._transaction():
                self.db.execute("""CREATE TABLE IF NOT EXISTS metadata(
                    only_row INTEGER PRIMARY KEY CHECK(only_row=1),
                    schema TEXT NOT NULL, migration TEXT NOT NULL,
                    account_binding TEXT NOT NULL, private_genesis TEXT NOT NULL
                )""")
                self.db.execute("""CREATE TABLE IF NOT EXISTS reservations(
                    symbol TEXT NOT NULL UNIQUE, client_order_id TEXT NOT NULL UNIQUE,
                    qty_commitment TEXT NOT NULL,
                    state TEXT NOT NULL, version INTEGER NOT NULL
                )""")
                row=self.db.execute("SELECT schema,migration,account_binding,private_genesis FROM metadata WHERE only_row=1").fetchone()
                if row is None:
                    self.db.execute("INSERT INTO metadata VALUES(1,?,?,?,?)",
                                    (SCHEMA,sell.MIGRATION_KEY,self.binding,secrets.token_hex(16)))
                elif (row[0]!=SCHEMA or row[1]!=sell.MIGRATION_KEY
                      or not hmac.compare_digest(row[2],self.binding)
                      or len(row[3])!=32):
                    raise JournalStop("Existing store binds another account or migration")
                # Corrupted historical order IDs/states must never silently unlock.
                self._verify_rows()
        except (sqlite3.Error,OSError):
            if hasattr(self,"db"):self.db.close()
            raise JournalStop("Private SQLite journal failed closed") from None

    @contextmanager
    def _transaction(self):
        try:
            self.db.execute("BEGIN IMMEDIATE")
            yield
            self.db.execute("COMMIT")
        except BaseException:
            if self.db.in_transaction:self.db.execute("ROLLBACK")
            raise

    def _verify_rows(self):
        rows=self.db.execute("SELECT symbol,client_order_id,qty_commitment,state,version FROM reservations").fetchall()
        if len(rows)>3:
            raise JournalStop("Unknown extra reserved orders")
        for symbol,cid,commitment,state,revision in rows:
            if (symbol not in sell.LEGACY_TO_EXIT or cid!=sell._id(symbol)
                or type(commitment) is not str or len(commitment)!=64
                or any(c not in "0123456789abcdef" for c in commitment)
                or state not in STATES or type(revision) is not int or revision<1):
                raise JournalStop("Corrupt or foreign private reservation metadata")

    def _verified(self,symbol:str,qty:str):
        if symbol not in sell.LEGACY_TO_EXIT:
            raise JournalStop("Only ACWI,EEM,XLV are original exits; XLE remains")
        sell.inspect_sell_shape(symbol=symbol,original_qty=qty)
        expected=_digest(self._key,self.binding,symbol,qty)
        row=self.db.execute(
            "SELECT client_order_id,qty_commitment,state,version FROM reservations WHERE symbol=?",
            (symbol,)).fetchone()
        if row and (row[0]!=sell._id(symbol)
                    or not hmac.compare_digest(row[1],expected)):
            raise JournalStop("Different quantity/key/account or changed existing client ID")
        return row,expected

    @staticmethod
    def _nonexec(stage,symbol,revision=0):
        return {"schema":SCHEMA,"source_mode":MODE,
            "stage":stage,"symbol":symbol,"revision":revision,
            "broker_state_authenticated":False,
            "externally_anchored_persistent_volume":False,
            "survives_new_ephemeral_actions_runner":False,
            "broker_404_is_safe_to_retry":False,
            "order_may_be_resubmitted":False,
            "live_order_authorized":False,
            "broker_get_requests":0,"broker_order_posts":0,
            "private_quantity":None,"account_identifier":None,
            "order_payload":None}

    def reserve_next(self,*,symbol:str,original_qty:str)->dict:
        with self._transaction():
            row,commitment=self._verified(symbol,original_qty)
            if row:
                return self._nonexec("ALREADY_RESERVED_NEVER_DUPLICATE",symbol,row[3])
            order=list(sell.LEGACY_TO_EXIT)
            prior=order[:order.index(symbol)]
            for earlier in prior:
                old=self.db.execute("SELECT state FROM reservations WHERE symbol=?",(earlier,)).fetchone()
                if not old or old[0]!="SIM_FILLED_AND_FLAT_RECONCILED":
                    return self._nonexec("WAIT_PRIOR_LEGACY_EXIT_RECONCILIATION",symbol)
            self.db.execute(
                "INSERT INTO reservations(symbol,client_order_id,qty_commitment,state,version) VALUES(?,?,?,?,1)",
                (symbol,sell._id(symbol),commitment,"RESERVED_NO_RETRY"))
            return self._nonexec("NEW_PRIVATE_RESERVATION_NO_BROKER_AUTHORITY",symbol,1)

    def mark_possible_post(self,*,symbol:str,original_qty:str)->dict:
        """Commit BEFORE any future separately reviewed POST boundary.

        The current caller has NO POST capability and cannot use the
        transition as a trading permit. Crash afterward => no retry.
        """
        with self._transaction():
            row,_=self._verified(symbol,original_qty)
            if row is None:
                raise JournalStop("No durable reservation before possible order")
            if row[2]!="RESERVED_NO_RETRY":
                return self._nonexec("EXISTING_UNCERTAIN_ATTEMPT_NO_RESUBMIT",symbol,row[3])
            changed=self.db.execute(
                "UPDATE reservations SET state=?,version=version+1 WHERE symbol=? AND state=? AND version=?",
                ("POST_MAY_HAVE_BEEN_SENT",symbol,"RESERVED_NO_RETRY",row[3]))
            if changed.rowcount!=1:
                raise JournalStop("Attempt state compare-and-swap conflict")
            return self._nonexec("POST_BOUNDARY_JOURNALED_NO_REAL_POST",symbol,row[3]+1)

    def observe_synthetic_receipt(self,*,symbol:str,original_qty:str,
                                  receipt:dict|None,currently_held_qty:str|None)->dict:
        """Offline broker-shaped event; NEVER actual private account proof."""
        with self._transaction():
            row,_=self._verified(symbol,original_qty)
            if row is None or row[2]=="RESERVED_NO_RETRY":
                raise JournalStop("Cannot reconcile order before committed possible-POST boundary")
            if row[2]=="SIM_FILLED_AND_FLAT_RECONCILED":
                return self._nonexec("ALREADY_SIM_RECONCILED_NO_NEW_ORDER",symbol,row[3])
            if row[2]=="HOLD_TERMINAL_OR_AMBIGUOUS":
                return self._nonexec("PERMANENT_TERMINAL_REVIEW_NO_RETRY",symbol,row[3])
            try:
                result=sell.reconcile(symbol=symbol,original_qty=original_qty,
                                      receipt=receipt,currently_held_qty=currently_held_qty)
            except sell.V6SellStop:
                raise JournalStop("Original broker order receipt identity or status invalid") from None
            status=result["stage"]
            # This journal only accepts synthetic broker events. Explicit
            # zero in the fake position snapshot is required; None remains
            # UNKNOWN. Even this simulated completion is never a LIVE proof.
            if (status=="REVIEW_FILLED_RECEIPT_AND_ZERO_QTY_INPUT_NOT_INDEPENDENTLY_VERIFIED"
                and result["explicit_zero_holdings_input_present"] is True
                and result["broker_zero_holdings_source_independently_verified"] is False
                and result["live_order_authorized"] is False
                and MODE=="SYNTHETIC_BROKER_EVENTS_ONLY"):
                new_state="SIM_FILLED_AND_FLAT_RECONCILED"
            elif status.startswith("HOLD_TERMINAL_") or status.startswith("HOLD_AMBIGUOUS_"):
                new_state="HOLD_TERMINAL_OR_AMBIGUOUS"
            else:
                new_state="HOLD_BROKER_RECONCILIATION"
            changed=self.db.execute(
                "UPDATE reservations SET state=?,version=version+1 WHERE symbol=? AND version=?",
                (new_state,symbol,row[3]))
            if changed.rowcount!=1:
                raise JournalStop("Source receipt state compare-and-swap conflict")
            return self._nonexec(
                "SIM_FULL_FILL_AND_POSITION_FLAT" if new_state=="SIM_FILLED_AND_FLAT_RECONCILED"
                else "NO_RETRY_BROKER_RECONCILIATION_HOLD",
                symbol,row[3]+1)

    def current(self,*,symbol:str,original_qty:str)->dict:
        row,_=self._verified(symbol,original_qty)
        return self._nonexec(row[2] if row else "NOT_RESERVED",symbol,row[3] if row else 0)

    def close(self)->None:
        self.db.close()

    def __enter__(self):return self
    def __exit__(self,*args):self.close()
