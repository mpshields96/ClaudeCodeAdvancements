import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from next_man_up import environment_change, screen_team_block, team_environment


def candidate(player, status, market=None):
    return {"player": player, "availability": {"status": status},
            "market": {"stats": market or {}}}


def screen(*players):
    return screen_team_block({"team": "Home", "environment": {"label": "U"},
                              "absences": [{"player": "Starter", "status": "out"}],
                              "candidates": list(players)})


class AvailabilityTest(unittest.TestCase):
    def test_unavailable_player_is_evidence_only(self):
        stale_line = {"rush_attempts": {"line_median": 19.5}}
        for designation in ("Out", "ruled out", "inactive"):
            with self.subTest(designation=designation):
                result = screen(candidate("Second back", designation, stale_line))
                self.assertEqual(result["screen_status"], "unknown_next_man")
                self.assertEqual(result["replacement_context"]["next_men"], [])
                self.assertEqual(result["candidates"], [])
                self.assertEqual(result["unavailable_candidates"][0]["market"]["stats"], stale_line)

    def test_conditional_third_back_and_no_market(self):
        result = screen(candidate("Second back", "out"), candidate("Third back", "Questionable"))
        role = result["replacement_context"]
        self.assertEqual([r["player"] for r in role["next_men"]], ["Third back"])
        self.assertTrue(role["next_men"][0]["conditional"])
        self.assertEqual(role["priced_status"], "no_market")
        self.assertEqual(role["confidence"], "low")
        self.assertIn("Third back is questionable", role["qualifier"])

    def test_complete_dated_quotes_must_straddle_news(self):
        before = {"implied_points": 24, "label": "K", "books": ["DK"],
                  "source": "example feed", "captured_utc": "2026-11-15T07:00:00Z"}
        after = dict(before, implied_points=25, captured_utc="2026-11-15T08:00:00Z")
        for current, news in [({"label": "U"}, "2026-11-15T07:30:00Z"),
                              (after, "2026-11-15T08:05:00Z"),
                              (after, "2026-11-15T08:00:00Z"),
                              (after, "unknown")]:
            with self.subTest(current=current, news=news):
                self.assertEqual(environment_change(current, before, news)["vs_pre_news"], "unknown")
        result = environment_change(after, before, "2026-11-15T01:30:00-06:00")
        self.assertEqual(result["vs_pre_news"], 1)
        self.assertIn("noncausal", result["note"])

    def test_missing_book_update_keeps_capture(self):
        game = {"bookmakers": [{"key": "draftkings", "markets": [
            {"key": "spreads", "outcomes": [{"name": "Home", "point": -3.5}]},
            {"key": "totals", "outcomes": [{"name": "Over", "point": 46.5}]}]}]}
        quote = team_environment(game, "Home", "2026-11-15T07:00:00Z")
        self.assertEqual(quote["captured_utc"], "2026-11-15T07:00:00Z")
        self.assertIsNone(quote["book_last_update_max_utc"])


if __name__ == "__main__":
    unittest.main()
