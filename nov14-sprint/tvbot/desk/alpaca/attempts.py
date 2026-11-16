"""A live account's daily new-entry reservations, shared across installed kit copies on this Mac.

The transaction is durable before an order can be submitted. A rejection or uncertain network
result does not release a reservation. The account identifier is hashed; no credentials are stored.
"""
import hashlib
import os
from pathlib import Path
import sqlite3

ROOT = Path.home() / "Library" / "Application Support" / "SPY Desk" / "live-risk"

def reserve(account, symbol, day, client_id, maximum, seen):
    if not isinstance(account,str) or not account.strip() or not isinstance(client_id,str) or not client_id:
        return "ENTRY_COUNT_UNVERIFIED"
    database = ROOT / "attempts.sqlite3"
    con = None
    try:
        ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
        if ROOT.is_symlink() or database.is_symlink():
            return "ENTRY_COUNT_UNVERIFIED"
        scope = hashlib.sha256(("live-v1|"+account+"|"+symbol).encode()).hexdigest()
        con = sqlite3.connect(str(database),timeout=3,isolation_level=None)
        os.chmod(str(database),0o600)
        con.execute("PRAGMA synchronous=FULL")
        con.execute("CREATE TABLE IF NOT EXISTS attempts (scope TEXT NOT NULL, day TEXT NOT NULL, client TEXT NOT NULL, PRIMARY KEY(scope,day,client))")
        con.execute("BEGIN IMMEDIATE")
        ids={r[0] for r in con.execute("SELECT client FROM attempts WHERE scope=? AND day=?",(scope,day))} | set(seen)
        if client_id in ids or len(ids)>=maximum:
            con.rollback()
            return "DAILY_ENTRY_LIMIT"
        con.execute("INSERT INTO attempts VALUES(?,?,?)",(scope,day,client_id))
        con.commit()
        return None
    except (OSError,ValueError,TypeError,sqlite3.Error):
        return "ENTRY_COUNT_UNVERIFIED"
    finally:
        if con is not None:con.close()
