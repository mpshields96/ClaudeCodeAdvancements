"""Decision lab (desk/alpaca/CONTRACT.md section 7): shadow forecasts, later-bar scores, verify.

SHADOW ONLY: never routes orders, never auto-promotes, never changes size or limits.
SHADOW names are refused as the active strategy by session.load_strategy.
"""
from strategies import challenger as _challenger

SHADOW = {"challenger": _challenger.decide}

from .record import Lab, LabRecorder, view  # noqa: E402

__all__ = ["SHADOW", "Lab", "LabRecorder", "view"]
