"""Persisted enable/disabled state for the Alpaca paper adapter.

<state_dir>/alpaca_paper.json. It starts DISABLED. Only an explicit operator
enable (with confirm) turns it on. Stop, an integrity fault or a load error turns
it off, and it stays off across restarts until the operator enables it again.
A missing, unreadable or malformed file reads as disabled (fail safe).
"""
import json
import os
import tempfile
import time

from alpaca import STATE_FILE


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class AdapterState(object):
    FILE = STATE_FILE        # the live subclass (alpaca/live.py LiveAdapterState) uses its own file

    def __init__(self, state_dir):
        self.path = os.path.join(os.path.abspath(state_dir), self.FILE)
        self.data = self._load()

    def _load(self):
        base = {"enabled": False, "disabled_reason": "never enabled", "changed_utc": None, "history": []}
        try:
            with open(self.path) as fh:
                d = json.load(fh)
        except (OSError, ValueError):
            if os.path.exists(self.path):
                base["disabled_reason"] = "state file unreadable; treated as disabled"
            return base
        if not isinstance(d, dict) or d.get("enabled") not in (True, False):
            base["disabled_reason"] = "state file malformed; treated as disabled"
            return base
        d.setdefault("history", [])
        return d

    def _save(self):
        d = os.path.dirname(self.path)
        os.makedirs(d, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".alpaca_state.", dir=d)
        with os.fdopen(fd, "w") as fh:
            json.dump(self.data, fh, indent=2, sort_keys=True)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, self.path)

    @property
    def enabled(self):
        return self.data.get("enabled") is True

    def enable(self, by="operator"):
        self.data.update(enabled=True, disabled_reason=None, changed_utc=_now())
        self.data["history"].append({"utc": self.data["changed_utc"], "enabled": True, "by": by})
        self._save()

    def disable(self, reason, by="desk"):
        self.data.update(enabled=False, disabled_reason=str(reason), changed_utc=_now())
        self.data["history"].append({"utc": self.data["changed_utc"], "enabled": False, "by": by,
                                     "reason": str(reason)})
        self.data["history"] = self.data["history"][-200:]
        self._save()

    def view(self):
        return {"enabled": self.enabled, "disabled_reason": self.data.get("disabled_reason"),
                "changed_utc": self.data.get("changed_utc"), "path_name": self.FILE}
