"""Funded session: after the operator's own Enable and Arm, the desk manages itself to a bounded stop.

The operator still types the live phrase at a real terminal, enables the live adapter and arms the
desk in the UI. Nothing here does any of that. From the moment the desk is armed, enabled and not
stopped, this thread runs the desk's own Check (check_new_bars) every PROTECT_CHECK_S seconds, so
there are no repeated Check clicks. One Check does all of the following:
- decides only on closed bars (Balanced pace)
- books fills of known orders
- covers any uncovered shares with the protective stop (reduce-only)
- ends the arm at its expiry with the desk's own Stop & Close. The arm ends WIND_DOWN_S before the
  regular close (the desk calendar's, early closes included) or at the operator's earlier end, so
  the reduce-only close goes out while the venue still takes it.

When the arm has ended (expiry or Stop) after this thread managed it, it does not go idle while the
desk may still hold shares or a working exit. It keeps a reconcile-only phase: every PROTECT_CHECK_S
it runs the desk's reconcile_check (book fills, work the reduce-only close and its retries, cover
uncovered shares; no bar fetch, no decision, no entry) until the broker confirms flat, for at most
RECONCILE_S. If the desk is still not confirmed flat then, it stops and shows an explicit UNRESOLVED
handoff (position, working and unsettled orders with their client ids, the close's status) for the
operator to resolve at the broker. An order whose submit was uncertain is never blindly resent.

It never enables, arms, re-arms, changes limits, clears a Stop or touches an unknown order. Every
refusal inside the desk still applies (stop, risk caps, recovery/unknown orders). A desk it never
saw armed gets no call from it. It ends with the launcher (Ctrl-C).

Stdlib only (Python 3.9).
"""
import datetime as _dt
import math
import threading

from alpaca import trading_profile as TP

IDLE = "waiting: the desk is not armed (it never arms itself; Enable and Arm are yours)"
MANAGING = "managing: Check every %ds until the arm ends or you press Stop"
RECONCILE = ("reconciling: the arm ended; every %ds the desk books fills and works the reduce-only close "
             "until the broker confirms flat (no entries; it never re-arms)")
FLAT = "ended: the arm ended and the broker confirms the desk flat"
DISARMED = "ended: disarmed without Stop, with no desk position or working order"
UNRESOLVED = ("UNRESOLVED: not confirmed flat %ds after the arm ended; nothing more is sent. Check the "
              "position and open orders in your Alpaca account (see handoff)")
ENDED = "ended with the launcher"

_DONE = ("flat", "disarmed", "unresolved")


def _utc():
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _zero(qty):
    try:
        return float(qty) == 0.0
    except (TypeError, ValueError):
        return False


class LiveSupervisor(object):
    def __init__(self, runner, every_s=None, wait=None):
        self.runner = runner
        self.every_s = int(every_s if every_s is not None else TP.PROTECT_CHECK_S)
        self.reconcile_max = max(1, int(math.ceil(float(TP.RECONCILE_S) / max(1, self.every_s))))
        self._halt = threading.Event()
        self._wait = wait or self._halt.wait
        self.thread = None
        self._activated = False
        self.view = {"profile": TP.PROFILE_ID, "every_s": self.every_s, "active": False, "state": IDLE,
                     "phase": "idle", "checks": 0, "errors": 0, "last_utc": None, "last_result": None,
                     "last_error": None, "reconcile_checks": 0, "reconcile_max": self.reconcile_max,
                     "reconcile_s": TP.RECONCILE_S, "arm_ended_utc": None, "handoff": None}
        self._publish()

    def _publish(self, **changes):
        """A new dict each time, so session_state never reads one that is being changed."""
        self.view = dict(self.view, **changes)
        try:
            self.runner.auto_manage = dict(self.view)
        except Exception:
            pass

    def _state(self):
        try:
            st = self.runner.mgr.state()
            return st if isinstance(st, dict) else None
        except Exception:
            return None

    def due(self):
        """Armed, the live adapter enabled, and not stopped. Anything unreadable counts as not due."""
        try:
            st = self.runner.mgr.state()
            if not st.get("armed") or (st.get("controls") or {}).get("stopped"):
                return False
            return getattr(self.runner.adapter_state, "enabled", False) is True
        except Exception:
            return False

    def _handoff(self, st):
        st = st or {}
        ctl, exp = st.get("controls") or {}, st.get("exposure") or {}
        work = [dict((k, o.get(k)) for k in ("kind", "side", "qty", "remaining", "status"))
                for o in (exp.get("working_orders") or []) if isinstance(o, dict)]
        return {"utc": _utc(), "position_qty": exp.get("position_qty"),
                "broker_position_qty": exp.get("broker_position_qty"), "working_orders": work,
                "unsettled_orders": self._unsettled(), "stopped": bool(ctl.get("stopped")),
                "flat_confirmed": bool(ctl.get("flat_confirmed")), "close_pending": ctl.get("close_pending"),
                "stop_reason": ctl.get("stop_reason"), "armed": bool(st.get("armed"))}

    def _unsettled(self):
        """Every desk order not yet settled, including one whose submit is uncertain (lost ACK): its
        client id is what to look up at the broker. Read only."""
        out = []
        try:
            for iid, it in list((getattr(self.runner.mgr, "intents", None) or {}).items()):
                if isinstance(it, dict) and it.get("status") in ("pending", "uncertain", "acked"):
                    out.append(dict(intent_id=iid, kind=it.get("kind"), side=it.get("side"),
                                    qty=it.get("qty"), status=it.get("status"), client_id=it.get("client_id")))
        except Exception:
            pass
        return out

    def _settle(self, st):
        """After the arm: done (flat / disarmed with nothing open), else None (keep reconciling)."""
        st = st or {}
        ctl, exp = st.get("controls") or {}, st.get("exposure") or {}
        if ctl.get("stopped") and ctl.get("flat_confirmed"):
            self._publish(active=False, phase="flat", state=FLAT, handoff=None)
            return True
        if (not ctl.get("stopped") and not st.get("armed") and _zero(exp.get("position_qty"))
                and not exp.get("working_orders")):
            self._publish(active=False, phase="disarmed", state=DISARMED, handoff=None)
            return True
        return None

    def _unresolved(self, st):
        self._publish(active=False, phase="unresolved", state=UNRESOLVED % TP.RECONCILE_S,
                      handoff=self._handoff(st))

    def _arm_ended(self):
        self._publish(phase="reconciling", reconcile_checks=0, arm_ended_utc=_utc(), handoff=None)
        st = self._state()
        if not self._settle(st):
            self._publish(active=True, state=RECONCILE % self.every_s)

    def _manage(self):
        self._activated = True
        self._publish(active=True, phase="managing", state=MANAGING % self.every_s, handoff=None,
                      reconcile_checks=0, arm_ended_utc=None)
        try:
            r = self.runner.check_new_bars()
        except Exception as exc:              # shown in session state; the next tick tries again
            self._publish(errors=self.view["errors"] + 1, last_error=exc.__class__.__name__, last_utc=_utc())
            if not self.due():
                self._arm_ended()
            return None
        r = r if isinstance(r, dict) else {}
        self._publish(checks=self.view["checks"] + 1, last_utc=r.get("utc") or _utc(),
                      last_result={"ok": r.get("ok"), "bars": r.get("bars")},
                      last_error=r.get("error"))
        if not self.due():                     # this Check ended the arm (expiry Stop & Close) or a Stop
            self._arm_ended()
        return r

    def _reconcile(self):
        if self.view["phase"] in _DONE:
            return None                        # done until the operator arms again
        if self.view["phase"] != "reconciling":
            self._arm_ended()                  # the arm ended between ticks (operator Stop)
            if self.view["phase"] in _DONE:
                return None
        if self._settle(self._state()):
            return None
        fn = getattr(self.runner, "reconcile_check", None)
        if self.view["reconcile_checks"] >= self.reconcile_max or not callable(fn):
            self._unresolved(self._state())
            return None
        self._publish(active=True, state=RECONCILE % self.every_s)
        r = None
        try:
            r = fn()
        except Exception as exc:
            self._publish(errors=self.view["errors"] + 1, last_error=exc.__class__.__name__, last_utc=_utc(),
                          reconcile_checks=self.view["reconcile_checks"] + 1)
        else:
            r = r if isinstance(r, dict) else {}
            self._publish(checks=self.view["checks"] + 1, reconcile_checks=self.view["reconcile_checks"] + 1,
                          last_utc=r.get("utc") or _utc(), last_result={"ok": r.get("ok"), "bars": 0},
                          last_error=r.get("error"))
        st = self._state()
        if not self._settle(st) and self.view["reconcile_checks"] >= self.reconcile_max:
            self._unresolved(st)
        return r

    def tick(self):
        if self.due():
            return self._manage()
        if not self._activated:
            if self.view["active"] or self.view["state"] != IDLE:
                self._publish(active=False, state=IDLE, phase="idle")
            return None
        return self._reconcile()

    def run(self):
        while not self._wait(self.every_s):
            self.tick()
        self._publish(active=False, state=ENDED)

    def start(self):
        self.thread = threading.Thread(target=self.run, name="desk-live-supervisor", daemon=True)
        self.thread.start()
        return self

    def stop(self, timeout=5.0):
        self._halt.set()
        if self.thread is not None:
            self.thread.join(timeout)
