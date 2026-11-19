# NFL Betting Preview

An Agent Skill for sourced NFL matchup predictions and research on the full-game spread, total, and moneyline. A named matchup defaults to its next scheduled meeting. Ask explicitly for a local date slate, numbered NFL week, or named playoff round. Display times and date windows default to Asia/Manila.

## Install

Clone the public repository into your Codex skills directory.

```sh
mkdir -p ~/.codex/skills
git clone https://github.com/sharpredux/nfl-betting-preview.git ~/.codex/skills/nfl-betting-preview
```

You can also ask Codex to use `$skill-installer` with this repository and its root path. Use your host agent's personal skills directory if it differs. Codex can select this skill automatically for NFL matchup or betting requests, or you can invoke `$nfl-betting-preview` explicitly.

Try “Preview Colts at Texans” or “Use $nfl-betting-preview to review 2026 NFL Week 11.”

## Research and profiles

The skill includes researched profiles for all 32 teams. It checks only the participating teams' profiles and reuses matching-season snapshots fresher than 15 minutes. It checks live availability, conditions, and prices separately. It can use a verified local refresh when publication is unavailable and share updates on GitHub with authorization. [Profile workflow](references/team-profiles.md)

The skill needs live web research for current recommendations. Source gaps and incomplete quotes affect the markets that depend on them. The bundled Python 3.9+ helpers use the standard library and the system IANA time-zone database. Git is required for shared publication.

- [Preview workflow](SKILL.md)
- [Research guide](references/research.md)
- [Market comparison and tiers](references/edges.md)
- [Time windows, schedule selection, rest and distance](scripts/context.py)
- [Profile checks and scoped publication](scripts/team_profiles.py)
- [Codex metadata](agents/openai.yaml)

Run the helper tests with `python3 -m unittest discover -s tests`.

## License

[MIT](LICENSE)
