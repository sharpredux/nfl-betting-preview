# Shared team profiles

Use `teams/<ID>/TEAM.md` with the four-digit NFL season. Canonical IDs include `GB`, `KC`, `LAR`, `LV`, `NE`, `NO`, `SF`, `TB`, and `WAS`. The helper maps provider aliases such as `JAC` to `JAX`, nflverse `LA` to `LAR`, and ESPN `WSH` to `WAS`. Resolve ambiguous city names before calling it.

## Check participating teams

```sh
python3 scripts/team_profiles.py check --season 2026 IND HOU
```

Pass only the teams in the requested game or explicitly requested slate, deduplicated. Read each returned profile. The freshness window is zero to less than 15 minutes by the file's UTC timestamp, with the same NFL season. Exactly 15 minutes, future timestamps and invalid profiles require a refresh.

- **shared_fresh** means a verified shared snapshot is available. Continue the independent schedule, market, venue, and availability checks.
- **refresh_required** means research the team. The returned older text is a starting point. Open its underlying sources and confirm or update claims before relying on them.
- **local_only** means a recent local snapshot met the freshness window. Use the verified evidence and mention that the profile stayed local when relevant to a refresh.
- For a **historical** preview, run `check --historical --before 2026-11-20T01:15:00Z --season 2026 IND HOU` with the actual pregame cutoff. This reads eligible matching-season bundled and public evidence without writing. Verify each returned claim against material available before that cutoff. The current files may be newer than the game, in which case obtain contemporaneous evidence directly. For a future game whose season data has yet to exist, use verified dated background as applicable and keep the shared current-season profiles intact.

If the helper is unavailable, check the corresponding shipped files and GitHub copies. Follow the same freshness and historical rules, and report any unavailable evidence that affects the preview.

## Research and apply

Use the league's team directory, official standings or playoff picture, recent gamebooks, play-by-play, snap or box-score usage, and credible team reporting. Check the current head coach and relevant usage at QB, backfield or receiver, and relevant defensive personnel. Record play tendencies on both sides and baseline and recent form with dated samples. Confirm standings or playoff status as of the cutoff. Label unknowns, small samples and source delays. Use direct source links. Keep live odds, picks, and player availability in the matchup preview.

For each completed refresh, save a temporary `<ID>.md` draft using the headers below. Keep an earlier timestamp when fresh research could not verify a refresh.

```markdown
---
team: IND
season: 2026
---
# Indianapolis Colts

## Coaching and personnel
Confirmed coach and observed usage, with sample dates.

## Offensive and defensive tendencies
Verified season and recent efficiency context.

## Recent form
Completed games and dated scoring sample.

## Standings and playoff context
Verified standings or playoff status at the cutoff.

## Sources
- Direct links to the inspected evidence.
```

```sh
python3 scripts/team_profiles.py apply --season 2026 --draft-dir /path/to/drafts IND
```

`apply` stamps the verified profile and checks the shared branch again. With user authorization to publish, add `--publish`. The helper fetches the latest shared branch, uses fresh updates already published by collaborators, commits only submitted teams still due, and retries once if the branch advances during the push. It uses a private Git index and leaves the caller's branch, index, and working files intact. Read the returned profile, which may be a collaborator's newer snapshot. If the publish fails or is unavailable, use the local result and disclose that it stayed local.

Use a Git clone with `sharpredux/nfl-betting-preview` as its origin, a configured Git author, and push access to `main` for publication. The helper looks for the skill root or `~/nfl-betting-preview`. Set `NFL_BETTING_PREVIEW_REPO_ROOT` to an alternate checkout. Public reads do not require credentials. Local refreshes are cached per team and season under `${XDG_CACHE_HOME:-~/.cache}/nfl-betting-preview/` without touching the checkout.
