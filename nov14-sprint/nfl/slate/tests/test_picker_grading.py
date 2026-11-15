"""Regression checks for the archived-score and period-specific grading paths."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import picker


def candidate(key, market, side, line, **extra):
    return dict(id=key, event_id="provider-id", label=key, game="PIT at CIN",
                selected=False, price=-110, hit_likelihood=0.5, market=market,
                side=side, line=line, **extra)


def results(rows, score=None, player_stats=None):
    game = {"event_id": "provider-id", "espn_event_id": "espn-id"}
    record = {"slate": {"games": [game], "candidates": rows}}
    finals = {"espn-id": score} if score else {}
    return picker.grade_candidates(record, finals, {}, player_stats)


class GradeTest(unittest.TestCase):
    def test_first_half_needs_a_first_half_score(self):
        row = candidate("half", "total", "over", 21.5, period="first_half")
        score = {"home": 24, "away": 21}
        self.assertIsNone(results([row], score)[0]["profit_per_unit"])
        score["first_half"] = {"home": 10, "away": 7}
        self.assertEqual(results([row], score)[0]["result"], "loss")

    def test_home_handicap_and_team_points(self):
        rows = [candidate("hcap", "spread", "home", -2.5),
                candidate("pp", "team_total", "under", 21, subject="Cincinnati Bengals")]
        scored = results(rows, {"home": 21, "away": 20})
        self.assertEqual([r["result"] for r in scored], ["loss", "push"])

    def test_zero_yards_and_void_are_distinct(self):
        row = candidate("warren", "prop", "over", 22.5)
        self.assertIn("ungraded", results([row])[0]["result"])
        stats = {"warren": {"disposition": "played", "value": 0}}
        self.assertEqual(results([row], player_stats=stats)[0]["profit_per_unit"], -1)
        stats = {"warren": {"disposition": "void"}}
        self.assertEqual(results([row], player_stats=stats)[0]["profit_per_unit"], 0)

    def test_repeated_matchup_from_another_week_cannot_settle_sunday(self):
        history = Path(picker.LANE) / "data" / "raw" / "games.csv"
        _, finals = picker.load_finals(None, history)
        self.assertFalse(finals)


if __name__ == "__main__":
    unittest.main()
