#!/usr/bin/env python3
"""Read, refresh, and share the team profiles used by the NFL preview skill."""

import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
from tempfile import TemporaryDirectory
from urllib.request import Request, urlopen
from uuid import uuid4

from context import team_id, timestamp


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "sharpredux/nfl-betting-preview"
BRANCH = "refs/heads/main"
FRESH_FOR = timedelta(minutes=15)
MAX_BYTES = 12_000
HEADINGS = (
    "## Coaching and personnel",
    "## Offensive and defensive tendencies",
    "## Recent form",
    "## Standings and playoff context",
    "## Sources",
)
FRONTMATTER = re.compile(
    r"\A---\nteam: ([A-Z]{2,3})\nseason: (\d{4})\n"
    r"(?:last_refreshed_at: ([^\n]+)\n)?---\n"
)


def utc_now():
    return datetime.now(timezone.utc)


def profile_path(team):
    return f"teams/{team}/TEAM.md"


def parse_profile(body, team, *, draft=False):
    if len(body.encode("utf-8")) > MAX_BYTES:
        raise ValueError(f"{team} profile is too long")
    match = FRONTMATTER.match(body)
    if not match or match[1] != team or (match[3] is None) != draft:
        raise ValueError(f"{team} profile has invalid frontmatter")
    sections = list(re.finditer(r"^## .+$", body[match.end():], re.MULTILINE))
    if tuple(section[0] for section in sections) != HEADINGS:
        raise ValueError(f"{team} profile is missing the required sections")
    content = body[match.end():]
    if any(not content[section.end():following.start()].strip()
           for section, following in zip(sections, sections[1:])):
        raise ValueError(f"{team} profile has an empty section")
    if not re.search(r"https://[^\s)]+", content[sections[-1].end():]):
        raise ValueError(f"{team} profile requires direct source links")
    timestamp = None if draft else datetime.strptime(
        match[3], "%Y-%m-%dT%H:%M:%SZ"
    ).replace(tzinfo=timezone.utc)
    return match[2], timestamp


def is_fresh(body, team, season, now):
    if body is None:
        return False
    profile_season, refreshed = parse_profile(body, team)
    return profile_season == season and timedelta(0) <= now - refreshed < FRESH_FOR


def accepted_drafts(directory, teams, season, now):
    drafts = {}
    for team in teams:
        body = (directory / f"{team}.md").read_text(encoding="utf-8")
        if parse_profile(body, team, draft=True)[0] != season:
            raise ValueError(f"{team} draft has the wrong season")
        timestamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        line = f"season: {season}\n"
        drafts[team] = body.replace(line, f"{line}last_refreshed_at: {timestamp}\n", 1)
        parse_profile(drafts[team], team)
    return drafts


def git(repo, *args, input_text=None, index=None):
    env = {key: value for key, value in os.environ.items()
           if key not in {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE",
                          "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY"}}
    env["GIT_TERMINAL_PROMPT"] = "0"
    if index is not None:
        env["GIT_INDEX_FILE"] = str(index)
    data = input_text.encode("utf-8") if input_text is not None else None
    return subprocess.run(
        ["git", "-C", str(repo), *args], input=data, env=env,
        capture_output=True, check=True, timeout=25,
    ).stdout.decode("utf-8", errors="replace")


def checkout(override):
    candidates = [override] if override else [ROOT, Path.home() / "nfl-betting-preview"]
    valid_urls = {
        f"https://github.com/{REPOSITORY}", f"git@github.com:{REPOSITORY}",
        f"ssh://git@github.com/{REPOSITORY}",
    }
    for candidate in candidates:
        repo = candidate.resolve()
        try:
            if Path(git(repo, "rev-parse", "--show-toplevel").strip()).resolve() != repo:
                continue
            urls = []
            for option in ((), ("--push",)):
                urls.extend(git(repo, "remote", "get-url", "--all", *option, "origin").splitlines())
            if urls and all(url.rstrip("/").removesuffix(".git") in valid_urls for url in urls):
                return repo
        except (OSError, subprocess.SubprocessError):
            continue
    return None


@contextmanager
def fetched_head(repo):
    ref = f"refs/nfl-betting-preview/{uuid4().hex}"
    try:
        git(repo, "fetch", "--no-tags", "--no-write-fetch-head", "--refmap=", "origin", f"{BRANCH}:{ref}")
        yield git(repo, "rev-parse", ref).strip()
    finally:
        try:
            git(repo, "update-ref", "-d", ref)
        except (OSError, subprocess.SubprocessError):
            pass


def validated(body, team):
    parse_profile(body, team)
    return body


def repo_profiles(repo, head, teams, notes):
    profiles = {}
    for team in teams:
        try:
            profiles[team] = validated(git(repo, "show", f"{head}:{profile_path(team)}"), team)
        except (ValueError, OSError, subprocess.SubprocessError):
            notes.append(f"{team} shared profile is missing or invalid.")
    return profiles


def public_profiles(teams, notes):
    from concurrent.futures import ThreadPoolExecutor

    def fetch(team):
        url = (f"https://raw.githubusercontent.com/{REPOSITORY}/main/{profile_path(team)}"
               f"?check={uuid4().hex}")
        try:
            request = Request(url, headers={"Cache-Control": "no-cache"})
            with urlopen(request, timeout=10) as response:
                return team, validated(response.read(MAX_BYTES + 1).decode("utf-8"), team)
        except (OSError, ValueError):
            return team, None

    profiles = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        for team, body in pool.map(fetch, teams):
            if body is None:
                notes.append(f"{team} shared profile is missing, invalid, or unavailable.")
            else:
                profiles[team] = body
    return profiles


def refresh_commit(repo, head, profiles):
    # Use a private index so unrelated edits and staged files cannot enter the commit.
    with TemporaryDirectory(prefix="nfl-profile-index-") as directory:
        index = Path(directory) / "index"
        git(repo, "read-tree", head, index=index)
        for team, body in profiles.items():
            blob = git(repo, "hash-object", "-w", "--stdin", input_text=body).strip()
            git(repo, "update-index", "--add", "--cacheinfo",
                f"100644,{blob},{profile_path(team)}", index=index)
        tree = git(repo, "write-tree", index=index).strip()
        teams = ", ".join(profiles)
        return git(repo, "commit-tree", tree, "-p", head, "-m", f"Refresh NFL team context: {teams}").strip()


def push_refreshed(repo, teams, season, drafts, notes):
    for attempt in range(2):
        with fetched_head(repo) as head:
            profiles = repo_profiles(repo, head, teams, notes)
            # Another collaborator may have refreshed a team since check ran.
            pending = {team: drafts[team] for team in teams if team in drafts
                       and not is_fresh(profiles.get(team), team, season, utc_now())}
            if not pending:
                return head, profiles, set()
            commit = refresh_commit(repo, head, pending)
            try:
                git(repo, "push", "origin", f"{commit}:{BRANCH}")
            except subprocess.CalledProcessError:
                if attempt == 0:
                    with fetched_head(repo) as latest:
                        if latest != head:
                            continue
                raise
            return commit, profiles | pending, set(pending)


def read_local(root, team):
    try:
        return validated((root / profile_path(team)).read_text(encoding="utf-8"), team)
    except (OSError, ValueError):
        return None


@contextmanager
def profile_cache(*, create=False):
    path = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    path = path.expanduser().resolve() / "nfl-betting-preview" / "profiles.sqlite3"
    if create:
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path)
    elif path.is_file():
        connection = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    else:
        yield None
        return
    try:
        with connection:
            if create:
                connection.execute("""CREATE TABLE IF NOT EXISTS profiles (
                    team TEXT, season TEXT, refreshed TEXT, body TEXT,
                    PRIMARY KEY (team, season)
                )""")
            yield connection
    finally:
        connection.close()


def cached_profiles(teams, season):
    with profile_cache() as cache:
        if cache is None:
            return {}
        bodies = {}
        for team in teams:
            row = cache.execute(
                "SELECT body FROM profiles WHERE team = ? AND season = ?", (team, season)
            ).fetchone()
            if row is not None:
                bodies[team] = validated(row[0], team)
        return bodies


def save_profiles(profiles):
    with profile_cache(create=True) as cache:
        for team, body in profiles.items():
            season, refreshed = parse_profile(body, team)
            cache.execute("""
                INSERT INTO profiles VALUES (?, ?, ?, ?)
                ON CONFLICT (team, season) DO UPDATE SET
                    refreshed = excluded.refreshed, body = excluded.body
                WHERE excluded.refreshed >= profiles.refreshed
            """, (team, season, refreshed.isoformat(), body))


def matching_profile(bodies, team, season, before):
    eligible = []
    for body in bodies:
        if body is not None:
            profile_season, refreshed = parse_profile(body, team)
            if profile_season == season and refreshed < before:
                eligible.append((refreshed, body))
    return max(eligible)[1] if eligible else None


def read_historical(teams, season, before):
    notes = []
    shared = public_profiles(teams, notes)
    result = {}
    for team in teams:
        candidates = (shared.get(team), read_local(ROOT, team))
        result[team] = {
            "state": "historical_read_only",
            "profile": matching_profile(candidates, team, season, before),
        }
    notes.append("Verify each claim against pre-kickoff sources. Research missing historical evidence separately.")
    return {"teams": result, "shared_commit": None, "notes": notes}


def run(args):
    teams = tuple(dict.fromkeys(args.teams))
    if args.historical:
        return read_historical(teams, args.season, args.before)
    notes = []
    override = os.environ.get("NFL_BETTING_PREVIEW_REPO_ROOT")
    repo = checkout(Path(override).expanduser() if override else None)
    drafts = accepted_drafts(args.draft_dir, teams, args.season, utc_now()) if args.command == "apply" else {}
    shared, published = {}, set()
    shared_commit = None
    if repo:
        try:
            if args.publish:
                shared_commit, shared, published = push_refreshed(repo, teams, args.season, drafts, notes)
            else:
                with fetched_head(repo) as head:
                    shared_commit = head
                    shared = repo_profiles(repo, head, teams, notes)
        except (OSError, subprocess.SubprocessError) as error:
            notes.append(f"GitHub profile check or publication failed ({type(error).__name__}).")
    elif args.publish:
        notes.append("Publication requires a writable clone with the project's origin and GitHub collaborator credentials.")
    if shared_commit is None:
        shared = public_profiles(teams, notes)
    try:
        cached = cached_profiles(teams, args.season)
    except (OSError, ValueError, sqlite3.Error):
        cached = {}
        notes.append("The local profile cache could not be read.")

    result = {}
    local_updates = {}
    now = utc_now()
    for team in teams:
        bundled = read_local(ROOT, team)
        local = matching_profile((cached.get(team), bundled), team, args.season,
                                 now + timedelta(microseconds=1))
        body = shared.get(team)
        if team in published:
            state = "published"
        elif is_fresh(body, team, args.season, now):
            state = "shared_fresh"
        elif team in drafts:
            state, body = "local_only", drafts[team]
            local_updates[team] = body
        elif is_fresh(local, team, args.season, now):
            state, body = "local_only", local
        else:
            state = "refresh_required"
            body = matching_profile((body, local), team, args.season,
                                    now + timedelta(microseconds=1))
        result[team] = {"state": state, "profile": body}
    if local_updates:
        try:
            save_profiles(local_updates)
        except (OSError, sqlite3.Error):
            notes.append("The verified local refresh is available in this result. The local cache write failed.")
    if any(item["state"] == "local_only" for item in result.values()):
        notes.append("Local-only profiles were not published to GitHub.")
    return {"teams": result, "shared_commit": shared_commit, "notes": list(dict.fromkeys(notes))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(required=True, dest="command")
    for command in ("check", "apply"):
        sub = subparsers.add_parser(command)
        sub.add_argument("--season", required=True, help="NFL season, such as 2026")
        sub.add_argument("teams", nargs="+", help="Canonical NFL IDs or supported provider aliases")
        sub.set_defaults(historical=False, publish=False)
        if command == "check":
            sub.add_argument("--historical", action="store_true")
            sub.add_argument("--before", type=timestamp, help="Historical kickoff with explicit UTC offset")
        else:
            sub.add_argument("--draft-dir", required=True, type=Path)
            sub.add_argument("--publish", action="store_true", help="Publish only with authorization")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9]{4}", args.season):
        parser.error("--season must have YYYY format")
    if args.command == "check" and bool(args.before) != args.historical:
        parser.error("--historical and --before must be used together")
    try:
        args.teams = [team_id(team) for team in args.teams]
        print(json.dumps(run(args), ensure_ascii=False, indent=2))
    except (ValueError, OSError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
