"""Cross-copy first-attempt reservation with independent SQLite connections."""
import concurrent.futures
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from alpaca import attempts

class EntryReservations(unittest.TestCase):
    def test_independent_callers_race_and_next_regular_date(self):
        with tempfile.TemporaryDirectory() as t, patch.object(attempts,'ROOT',Path(t)):
            def try_once(i):
                return attempts.reserve('test-account','SPY','2026-11-16','client-'+str(i),1,[])
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                answers=list(pool.map(try_once,range(8)))
            self.assertEqual(answers.count(None),1)
            self.assertEqual(answers.count('DAILY_ENTRY_LIMIT'),7)
            self.assertIsNone(attempts.reserve('test-account','SPY','2026-11-17','next',1,[]))
            self.assertIsNone(attempts.reserve('another-account','SPY','2026-11-16','unrelated',1,[]))
    def test_broker_and_local_ids_union_and_unreadable_ledger(self):
        with tempfile.TemporaryDirectory() as t, patch.object(attempts,'ROOT',Path(t)):
            self.assertEqual(attempts.reserve('test','SPY','2026-11-16','new',1,['existing']), 'DAILY_ENTRY_LIMIT')
            (Path(t)/'attempts.sqlite3').write_bytes(b'corrupt')
            self.assertEqual(attempts.reserve('test','SPY','2026-11-16','new',1,[]),'ENTRY_COUNT_UNVERIFIED')
