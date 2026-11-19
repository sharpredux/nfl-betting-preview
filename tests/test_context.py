from datetime import date
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from context import great_circle_miles, rest_days, select_games, slate_window, team_id, timestamp


def event(game_id, stamp, *, season=2026, kind=2, week=11, status="STATUS_SCHEDULED",
          teams=("WSH", "JAC"), confirmed=True):
    return {
        "id": game_id,
        "date": stamp,
        "season": {"year": season, "type": kind},
        "week": {"number": week},
        "status": {"type": {"name": status}},
        "competitions": [{
            "timeValid": confirmed,
            "competitors": [
                {"homeAway": side, "team": {"abbreviation": team}}
                for side, team in zip(("home", "away"), teams)
            ],
        }],
    }


class ContextTests(unittest.TestCase):
    def test_manila_date_is_half_open(self):
        games = [
            event("early", "2026-11-22T15:59:59Z"),
            event("start", "2026-11-22T16:00:00Z"),
            event("end", "2026-11-23T16:00:00Z"),
        ]
        selected = select_games(games, 2026, day=date(2026, 11, 23))
        self.assertEqual([game["id"] for game in selected], ["start"])
        window = slate_window("2026-11-23")
        self.assertEqual(window["start_utc"], "2026-11-22T16:00:00+00:00")
        self.assertEqual(window["nfl_dates_et"], ["2026-11-22", "2026-11-23"])

    def test_daylight_saving_and_eastern_calendar_rest(self):
        for day, expected_hours in [("2026-03-08", 23), ("2026-11-01", 25)]:
            window = slate_window(day, "America/New_York")
            duration = timestamp(window["end_utc_exclusive"]) - timestamp(window["start_utc"])
            self.assertEqual(duration.total_seconds() / 3600, expected_hours)
        self.assertEqual(rest_days(timestamp("2026-10-29T23:15:00Z"),
                                   timestamp("2026-11-03T01:15:00Z")), 4)
        with self.assertRaises(ValueError):
            timestamp("2026-11-03T01:15:00")

    def test_official_week_and_postseason_round(self):
        games = [
            event("thursday", "2026-11-20T01:15Z"),
            event("monday", "2026-11-24T01:15Z"),
            event("another-week", "2026-11-23T01:15Z", week=12),
            event("other-season", "2025-11-20T01:15Z", season=2025),
            event("wild-card", "2027-01-16T18:00Z", kind=3, week=1),
            event("wild-card-tbd", "2027-01-17T00:00Z", kind=3, week=1,
                  teams=("TBD", "TBD"), confirmed=False),
            event("divisional", "2027-01-23T18:00Z", kind=3, week=2),
        ]
        week = select_games(games, 2026, week=11)
        self.assertEqual([row["id"] for row in week], ["thursday", "monday"])
        playoffs = select_games(games, 2026, playoff_round=1)
        self.assertEqual([row["id"] for row in playoffs], ["wild-card", "wild-card-tbd"])
        self.assertIsNone(playoffs[1]["kickoff_local"])
        self.assertIsNone(playoffs[1]["home"])

    def test_named_matchup_picks_next_scheduled_meeting(self):
        games = [
            event("finished", "2026-11-20T01:00Z", status="STATUS_FINAL"),
            event("postponed", "2026-11-21T01:00Z", status="STATUS_POSTPONED"),
            event("different-teams", "2026-11-22T01:00Z", teams=("NE", "JAX")),
            event("next", "2026-11-23T01:00Z"),
            event("later", "2026-11-25T01:00Z"),
        ]
        selected = select_games(games, 2026, matchup=("WAS", "JAX"),
                                now=timestamp("2026-11-20T23:00Z"))
        self.assertEqual([row["id"] for row in selected], ["next"])
        historical = select_games(games, 2026, matchup=("WAS", "JAX"),
                                  day=date(2026, 11, 20))
        self.assertEqual([row["id"] for row in historical], ["finished"])

    def test_aliases_and_mileage(self):
        self.assertEqual([team_id(team) for team in ("az", "jac", "la", "LAC", "WSH", "SD", "OAK")],
                         ["ARI", "JAX", "LAR", "LAC", "WAS", "LAC", "LV"])
        with self.assertRaises(ValueError):
            team_id("NY")
        self.assertEqual(great_circle_miles((40.8, -74), (40.8, -74)), 0)
        self.assertAlmostEqual(great_circle_miles((0, 179), (0, -179)), 138.2, places=0)
        with self.assertRaises(ValueError):
            great_circle_miles((91, 0), (0, 0))


if __name__ == "__main__":
    unittest.main()
