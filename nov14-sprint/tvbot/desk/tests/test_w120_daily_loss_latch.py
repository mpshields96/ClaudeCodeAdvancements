"""W120 private coverage: the DAILY_LOSS_STOP latch (orders/manager.py _check_entry_risk and
entry_block_reason). Offline: in-process FakeBroker, fixture bars, TEST VALUES limits from
test_orders_manager (daily_loss 30). The day's realized loss is seeded white-box into by_day,
because no fixture produces a 30-dollar realized loss. Sizing is operator-only.

Set W120_DESK to run these tests against another desk tree (used to prove they pass on installed bytes).
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
DESK = os.environ.get("W120_DESK") or os.path.dirname(HERE)
sys.path.insert(0, os.path.join(DESK, "tests"))
sys.path.insert(0, DESK)

import test_orders_manager as T  # noqa: E402


class DailyLossLatch(T.DeskCase):
    def seed_loss(self, realized):
        self.m.by_day[self.m._day_key(None)] = {"realized": float(realized), "fees": 0.0}

    def test_loss_at_limit_latches_and_sends_nothing(self):
        self.start()
        self.seed_loss(-30.0)                                   # loss 30 >= daily_loss 30
        iid = self.buy("after_loss", 1)
        self.assertEqual((self.status(iid), self.reason(iid)), ("rejected", "DAILY_LOSS_STOP"))
        ds = self.m.controls["day_stop"]
        self.assertEqual((ds["reason"], ds["day"]), ("DAILY_LOSS", self.m._day_key(None)))
        audit = [r for r in self.read_audit() if r.get("action") == "day_stop"]
        self.assertTrue(audit, "day_stop audit record missing")
        self.assertEqual(self.b.list_orders()["total"], 0)

    def test_latch_holds_after_loss_recovers_and_after_restart(self):
        self.start()
        self.seed_loss(-30.0)
        self.assertEqual(self.reason(self.buy("a", 1)), "DAILY_LOSS_STOP")
        self.seed_loss(0.0)                                      # the day's P&L recovers
        self.assertEqual(self.reason(self.buy("b", 1)), "DAILY_LOSS_STOP")
        day = self.m._day_key(None)
        self.restart()                                           # in-memory by_day is gone, the latch is on disk
        self.bar()                                               # next fixture bar sets the sim clock
        self.assertEqual(self.m._day_key(None), day)             # still the same session day
        self.assertEqual(self.m.controls["day_stop"]["day"], day)
        self.m.arm("S1", expires_utc=T.FAR)
        self.assertEqual(self.reason(self.buy("c", 1)), "DAILY_LOSS_STOP")
        self.assertEqual(self.b.list_orders()["total"], 0)

    def test_below_limit_uses_worst_case_not_latch(self):
        self.start()
        self.seed_loss(-29.6)                                    # 29.6 + 0.50 new risk = 30.1 > 30
        iid = self.buy("wc", 1)
        self.assertEqual((self.status(iid), self.reason(iid)), ("rejected", "RISK_DAILY_LOSS_WORST_CASE"))
        self.seed_loss(-29.0)                                    # 29.0 + 0.50 = 29.5 <= 30
        ok = self.buy("ok", 1)
        self.assertEqual(self.status(ok), "acked")
        self.assertEqual(self.b.list_orders()["total"], 1)


if __name__ == "__main__":
    unittest.main()
