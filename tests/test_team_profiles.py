from argparse import Namespace
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from context import TEAM_IDS
import team_profiles as profiles

NOW = datetime(2026, 11, 19, 6, 0, tzinfo=timezone.utc)


def profile(team, updated=None, *, season="2026", marker="Verified context."):
    stamp = f"last_refreshed_at: {updated:%Y-%m-%dT%H:%M:%SZ}\n" if updated else ""
    sections = "\n".join(f"{heading}\n\n{marker}\n" for heading in profiles.HEADINGS[:-1])
    return f"---\nteam: {team}\nseason: {season}\n{stamp}---\n# {team}\n\n{sections}\n## Sources\n\n- https://www.nfl.com/teams/\n"


def write_profiles(root, bodies):
    for team, body in bodies.items():
        path = root / profiles.profile_path(team)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")


class ProfileTests(unittest.TestCase):
    def test_all_bundled_profiles_validate(self):
        paths = sorted((profiles.ROOT / "teams").glob("*/TEAM.md"))
        self.assertEqual({path.parent.name for path in paths}, TEAM_IDS)
        for path in paths:
            with self.subTest(team=path.parent.name):
                body = path.read_text(encoding="utf-8")
                season, updated = profiles.parse_profile(body, path.parent.name)
                self.assertRegex(season, r"^[0-9]{4}$")
                self.assertLessEqual(updated, profiles.utc_now())
                form = body.split("## Recent form\n", 1)[1].split("## Standings", 1)[0]
                self.assertEqual(sum(line.startswith("- [") for line in form.splitlines()), 4)

    def test_freshness_exclusive_cutoff_and_matching_season(self):
        for minutes, seconds, expected in [(14, 59, True), (15, 0, False), (0, 0, True), (0, -1, False)]:
            body = profile("IND", NOW - timedelta(minutes=minutes, seconds=seconds))
            self.assertEqual(profiles.is_fresh(body, "IND", "2026", NOW), expected)
        self.assertFalse(profiles.is_fresh(profile("IND", NOW, season="2025"), "IND", "2026", NOW))

    def test_historical_filters_exact_cutoff_newer_and_wrong_season(self):
        eligible = profile("IND", NOW - timedelta(seconds=1))
        with TemporaryDirectory() as directory:
            local = Path(directory)
            write_profiles(local, {"IND": eligible, "HOU": profile("HOU", NOW, season="2025")})
            shared = {"IND": profile("IND", NOW), "HOU": profile("HOU", NOW + timedelta(seconds=1))}
            with patch.object(profiles, "ROOT", local), patch.object(profiles, "public_profiles", return_value=shared):
                with patch.object(profiles, "git", side_effect=AssertionError("Historical check must be read-only")):
                    args = Namespace(teams=["IND", "HOU"], historical=True, season="2026", before=NOW)
                    report = profiles.run(args)
        self.assertEqual(report["teams"]["IND"]["profile"], eligible)
        self.assertIsNone(report["teams"]["HOU"]["profile"])

    def test_local_fallback_persists_when_publish_fails(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            drafts = root / "drafts"
            drafts.mkdir()
            (drafts / "IND.md").write_text(profile("IND"), encoding="utf-8")
            args = Namespace(command="apply", teams=["IND", "IND"], historical=False, season="2026",
                             draft_dir=drafts, publish=True)
            denied = subprocess.CalledProcessError(1, ["git", "push"])
            with patch.dict(os.environ, {"XDG_CACHE_HOME": str(root / "cache")}), \
                 patch.object(profiles, "checkout", return_value=root), \
                 patch.object(profiles, "utc_now", return_value=NOW), \
                 patch.object(profiles, "push_refreshed", side_effect=denied), \
                 patch.object(profiles, "public_profiles", return_value={}) as public:
                report = profiles.run(args)
                self.assertEqual(report["teams"]["IND"]["state"], "local_only")
                self.assertIn("not published", " ".join(report["notes"]))
                self.assertEqual(set(report["teams"]), {"IND"})
                self.assertEqual(public.call_args.args[0], ("IND",))
                args.command = "check"
                args.publish = False
                with patch.object(profiles, "checkout", return_value=None):
                    cached = profiles.run(args)
                self.assertEqual(cached["teams"], report["teams"])

    def test_publish_retries_against_real_remote_after_concurrent_refresh(self):
        git = profiles.git
        with TemporaryDirectory() as directory:
            root = Path(directory)
            remote, a, b = [root / name for name in ("remote.git", "a", "b")]
            git(root, "init", "--bare", "-b", "main", str(remote))
            git(root, "clone", str(remote), str(a))
            git(a, "config", "user.email", "profile-test@example.invalid")
            git(a, "config", "user.name", "Profile Test")
            (a / "README.md").write_text("Baseline\n", encoding="utf-8")
            old = NOW - timedelta(days=1)
            write_profiles(a, {team: profile(team, old) for team in ("IND", "HOU", "KC")})
            git(a, "add", ".")
            git(a, "commit", "-m", "Seed profiles")
            git(a, "push", "origin", "main")
            git(root, "clone", str(remote), str(b))
            git(b, "config", "user.email", "profile-test@example.invalid")
            git(b, "config", "user.name", "Profile Test")
            (a / "README.md").write_text("Staged user edit\n", encoding="utf-8")
            git(a, "add", "README.md")
            write_profiles(a, {"IND": profile("IND", old, marker="Unstaged user edit.")})
            (a / "unrelated.txt").write_text("Untracked user edit\n", encoding="utf-8")
            status_before = git(a, "status", "--porcelain")
            staged_before = git(a, "diff", "--cached")
            unstaged_before = git(a, "diff")
            head_before = git(a, "rev-parse", "HEAD")
            local_ind = profile("IND", NOW, marker="Our refresh.")
            local_hou = profile("HOU", NOW, marker="Our Houston refresh.")
            concurrent_ind = profile("IND", NOW, marker="Collaborator refresh.")
            attempts = []

            def race(repo, *args, **kwargs):
                if repo == a and args[0] == "push":
                    attempts.append(args)
                    if len(attempts) == 1:
                        write_profiles(b, {"IND": concurrent_ind})
                        git(b, "add", profiles.profile_path("IND"))
                        git(b, "commit", "-m", "Collaborator refresh")
                        git(b, "push", "origin", "main")
                return git(repo, *args, **kwargs)

            with patch.object(profiles, "git", side_effect=race), patch.object(profiles, "utc_now", return_value=NOW):
                head, shared, published = profiles.push_refreshed(
                    a, ("IND", "HOU"), "2026", {"IND": local_ind, "HOU": local_hou}, []
                )
            self.assertEqual(len(attempts), 2)
            self.assertEqual(published, {"HOU"})
            self.assertEqual(shared, {"IND": concurrent_ind, "HOU": local_hou})
            self.assertEqual(git(remote, "rev-parse", "main").strip(), head)
            self.assertEqual(git(remote, "diff-tree", "--no-commit-id", "--name-only", "-r", head).splitlines(),
                             ["teams/HOU/TEAM.md"])
            self.assertEqual(git(a, "rev-parse", "HEAD"), head_before)
            self.assertEqual(git(a, "status", "--porcelain"), status_before)
            self.assertEqual(git(a, "diff", "--cached"), staged_before)
            self.assertEqual(git(a, "diff"), unstaged_before)


if __name__ == "__main__":
    unittest.main()
