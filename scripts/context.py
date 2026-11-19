#!/usr/bin/env python3
"""Calculate NFL slate selection, Eastern calendar rest, and venue-to-venue mileage.

No network, file writes, third-party packages, or betting predictions.
"""

import argparse
from datetime import date, datetime, time, timedelta, timezone
import json
import math
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


ET = ZoneInfo("America/New_York")
TEAM_IDS = frozenset("""
ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LAC LAR LV MIA
MIN NE NO NYG NYJ PHI PIT SEA SF TB TEN WAS
""".split())
TEAM_ALIASES = {
    "ARZ": "ARI", "AZ": "ARI", "BLT": "BAL", "CLV": "CLE", "GBP": "GB", "HST": "HOU",
    "JAC": "JAX", "KAN": "KC", "KCC": "KC", "LA": "LAR", "NEP": "NE",
    "NOR": "NO", "NOS": "NO", "NWE": "NE", "OAK": "LV", "LVR": "LV",
    "SD": "LAC", "SDG": "LAC", "SFO": "SF", "STL": "LAR", "TAM": "TB",
    "TBB": "TB", "WSH": "WAS", "WFT": "WAS",
}
PLAYOFF_ROUNDS = {
    "wild card": 1, "wildcard": 1, "wild card round": 1, "wildcard round": 1,
    "divisional": 2, "divisional round": 2,
    "conference championship": 3, "conference championships": 3, "super bowl": 5,
}


def team_id(value):
    code = value.strip().upper()
    code = TEAM_ALIASES.get(code, code)
    if code not in TEAM_IDS:
        raise ValueError(f"Unrecognized NFL team ID: {value}")
    return code


def timestamp(value):
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.utcoffset() is None:
        raise ValueError("Kickoff timestamps require an explicit UTC offset")
    return stamp


def rest_days(previous, current):
    if previous >= current:
        raise ValueError("Previous kickoff must be earlier than the current kickoff")
    return (current.astimezone(ET).date() - previous.astimezone(ET).date()).days


def select_games(events, season, *, day=None, zone="Asia/Manila", week=None,
                 playoff_round=None, matchup=None, now=None):
    """Filter ESPN scoreboard events by NFL labels or a local kickoff date."""
    local_zone = ZoneInfo(zone)
    now = now or datetime.now(timezone.utc)
    if matchup is not None and len(set(matchup)) != 2:
        raise ValueError("A matchup requires two distinct teams")
    rows = {}
    for event in events:
        event_season = event["season"]
        kind = event_season["type"]
        if event_season["year"] != season or kind not in (2, 3):
            continue
        number = event["week"]["number"]
        if week is not None and (kind, number) != (2, week):
            continue
        if playoff_round is not None and (kind, number) != (3, playoff_round):
            continue
        kickoff = timestamp(event["date"])
        status = event["status"]["type"]["name"]
        venue_game = event["competitions"][0]
        if venue_game.get("timeValid") is False:
            kickoff_local = None
        else:
            kickoff_local = kickoff.astimezone(local_zone)
        if day is not None and (kickoff_local is None or kickoff_local.date() != day):
            continue
        teams = {"home": None, "away": None}
        for club in venue_game["competitors"]:
            code = club.get("team", {}).get("abbreviation")
            if code and code.upper() not in {"TBD", "TBA"}:
                teams[club["homeAway"]] = team_id(code)
        if matchup is not None and set(teams.values()) != set(matchup):
            continue
        # A nearest-meeting query can include scheduled games with a provisional time.
        if matchup is not None and day is None and (status != "STATUS_SCHEDULED" or kickoff <= now):
            continue
        rows[event["id"]] = {
            "id": event["id"], "date_feed_utc": kickoff.astimezone(timezone.utc).isoformat(),
            "kickoff_local": kickoff_local.isoformat() if kickoff_local else None,
            "status": status, "season_type": kind, "week": number, **teams,
            "venue": venue_game.get("venue", {}).get("fullName"),
        }
    ordered = sorted(rows.values(), key=lambda row: (row["date_feed_utc"], row["id"]))
    return ordered[:1] if matchup is not None and day is None else ordered


def slate_window(day, timezone_name="Asia/Manila"):
    local_zone = ZoneInfo(timezone_name)
    selected_date = date.fromisoformat(day) if day else datetime.now(local_zone).date()
    local_start = datetime.combine(selected_date, time.min, tzinfo=local_zone)
    local_end = datetime.combine(
        selected_date + timedelta(days=1), time.min, tzinfo=local_zone
    )
    start_utc = local_start.astimezone(timezone.utc)
    end_utc = local_end.astimezone(timezone.utc)
    first_et_date = start_utc.astimezone(ET).date()
    last_et_date = (end_utc - timedelta(microseconds=1)).astimezone(ET).date()
    et_dates = []
    current_date = first_et_date
    while current_date <= last_et_date:
        et_dates.append(current_date.isoformat())
        current_date += timedelta(days=1)
    return {
        "local_date": selected_date.isoformat(),
        "timezone": timezone_name,
        "start_local": local_start.isoformat(),
        "end_local_exclusive": local_end.isoformat(),
        "start_utc": start_utc.isoformat(),
        "end_utc_exclusive": end_utc.isoformat(),
        "nfl_dates_et": et_dates,
    }


def great_circle_miles(origin, destination):
    for latitude, longitude in (origin, destination):
        if not (
            math.isfinite(latitude)
            and math.isfinite(longitude)
            and -90 <= latitude <= 90
            and -180 <= longitude <= 180
        ):
            raise ValueError("latitude must be in [-90, 90] and longitude in [-180, 180]")
    lat1, lon1 = map(math.radians, origin)
    lat2, lon2 = map(math.radians, destination)
    haversine = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    angle = 2 * math.asin(math.sqrt(min(1.0, max(0.0, haversine))))
    # IUGG mean Earth radius in km, converted to statute miles.
    return 6371.0088 / 1.609344 * angle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    window_parser = subparsers.add_parser("window", help="Get an inclusive/exclusive slate window")
    window_parser.add_argument("--date", help="YYYY-MM-DD; default: today in --timezone")
    window_parser.add_argument("--timezone", default="Asia/Manila", help="IANA timezone name")
    miles_parser = subparsers.add_parser("miles", help="Calculate approximate venue-to-venue miles")
    miles_parser.add_argument("--origin", type=float, nargs=2, required=True, metavar=("LAT", "LON"))
    miles_parser.add_argument("--destination", type=float, nargs=2, required=True, metavar=("LAT", "LON"))
    rest_parser = subparsers.add_parser("rest", help="Count Eastern calendar days between kickoffs")
    rest_parser.add_argument("previous")
    rest_parser.add_argument("current")
    select_parser = subparsers.add_parser("select", help="Filter downloaded ESPN scoreboard JSON")
    select_parser.add_argument("scoreboards", nargs="+", type=argparse.FileType(encoding="utf-8"))
    select_parser.add_argument("--season", required=True, help="Four-digit NFL season")
    select_parser.add_argument("--timezone", default="Asia/Manila")
    select_parser.add_argument("--date", type=date.fromisoformat)
    select_parser.add_argument("--matchup", nargs=2, type=team_id)
    select_parser.add_argument("--as-of", type=timestamp, help="Override current time for replaying an upcoming selection")
    round_or_week = select_parser.add_mutually_exclusive_group()
    round_or_week.add_argument("--week", type=int, choices=range(1, 19), metavar="1–18")
    round_or_week.add_argument("--round", type=lambda s: s.lower().strip().replace("-", " "),
                               choices=PLAYOFF_ROUNDS)
    args = parser.parse_args()
    if args.command == "select":
        if len(args.season) != 4 or not args.season.isascii() or not args.season.isdecimal():
            parser.error("--season must be a four-digit NFL season")
        if not any((args.date, args.week, args.round, args.matchup)):
            parser.error("select requires a date, week, playoff round, or matchup")
        if (args.week or args.round) and (args.date or args.matchup):
            parser.error("An official week or round uses its own schedule scope")
    try:
        if args.command == "window":
            result = slate_window(args.date, args.timezone)
        elif args.command == "rest":
            result = {"eastern_calendar_days": rest_days(timestamp(args.previous), timestamp(args.current))}
        elif args.command == "select":
            events = [event for feed in args.scoreboards for event in json.load(feed)["events"]]
            result = select_games(
                events, int(args.season), day=args.date, zone=args.timezone, week=args.week,
                playoff_round=PLAYOFF_ROUNDS.get(args.round), matchup=args.matchup, now=args.as_of,
            )
        else:
            result = {
                "origin_lat_lon": args.origin,
                "destination_lat_lon": args.destination,
                "approximate_miles": round(great_circle_miles(args.origin, args.destination), 1),
                "method": "great-circle; mean Earth radius; not actual itinerary",
            }
    except (KeyError, TypeError, ValueError, OverflowError, ZoneInfoNotFoundError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
