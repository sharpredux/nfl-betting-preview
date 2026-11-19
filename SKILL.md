---
name: nfl-betting-preview
description: Analyze NFL matchup predictions and betting questions with sourced spreads, totals, moneylines, availability, weather, travel, and team form. Use for an NFL game, pick, odds question, or explicitly requested local-date slate, numbered NFL week, or playoff round.
---

# NFL Betting Preview

## Resolve the request

Default to the named or contextually clear game. Without a date, find the next scheduled meeting on the [official NFL schedule](https://www.nfl.com/schedules/). Confirm each team's identity, season, round or week, venue, kickoff, and status. If a division rematch or another occurrence could be what the user meant, identify the selected meeting with its date.

Cover several games only when explicitly requested. For a date slate, use the half-open midnight-to-midnight window in the user's time zone, defaulting to Asia/Manila for both the window and displayed times. An explicitly numbered NFL week or named playoff round uses the league's schedule labels, including games that fall on other local dates. Flag TBD, postponed, suspended, live, and completed games. Give pregame calls only for confirmed upcoming games. For historical analysis, set an evidence cutoff before kickoff and keep the team profile workflow read-only.

## Research and compare

Read [the research guide](references/research.md) for schedule, rest, travel, availability, weather, scoring, and source selection. Read [the team profile guide](references/team-profiles.md), then check only the participating teams. Reuse a matching-season profile verified less than 15 minutes ago. Research profiles due for refresh alongside the game. A local refresh can support the preview when sharing is unavailable. Publish shared profile changes only with authorization.

- **Rest and travel.** Count Eastern Time calendar days from each team's last played kickoff. Flag byes, short weeks, international venues and travel. Estimate venue-to-venue mileage for both teams and label the estimate.
- **Availability and venue.** Check the applicable practice and game-status reports and published inactives. Check venue roof status and the exposed-venue kickoff wind and gusts. For an uncertainty that could reverse a market, show plausible scenarios, hold the affected market, and refresh the quote after the update.
- **Scoring and matchup.** Compare season and last-four scoring for and against, plus EPA per play and success rate where verified. Account for opponent quality, game state, personnel and sample size. Explain personnel or unit matchups that affect the market, such as pass protection against pressure.
- **Price and evidence.** Compare full-game spread, total, and moneyline using [the market guide](references/edges.md). Use the user's lines or requested sportsbook first. Record sportsbook, line, price, source, and observation time. Treat missing juice as an incomplete quote. Reassess spreads moving through or onto 3 or 7. Use each market's evidence and price to decide whether it can proceed independently.

## Present the preview

Lead with a compact game card with kickoff and status, rest and estimated travel by team, material availability, weather and roof, scoring context, and the three full-game market quotes. Follow with a short three-market assessment and the best supported angle or **Pass**. Use **Pass / Lean / Moderate / Strong** and present Leans as watchlist items. For detailed requests, say whether the report can proceed or is provisional and identify what would unblock each held market. A supported market can proceed while another is held. Include the strongest counterargument and the news or price movement that could change the call. Cite the direct sources and include timestamps for time-sensitive facts.

For an explicit slate, keep each game card compact, cover the whole requested scope, and rank only qualifying pregame angles. Include passes where warranted. Where a game is already underway or complete, provide its requested status or historical context without issuing a pregame call.
