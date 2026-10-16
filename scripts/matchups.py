"""Highlight the biggest pass/rush mismatches for a week of games.

Rates every team's pass offense, rush offense, pass defense and rush defense
(EPA/play, garbage time removed) using only games before the target week, then
scores each offense-vs-defense matchup. Ratings are adjusted for opponent
strength and shrunk toward average when samples are small (ridge regression).
Prints the biggest edges, saves CSVs of the ratings and every matchup, and
charts the largest ones.

Usage:
    python scripts/matchups.py                        # next unplayed week
    python scripts/matchups.py --season 2026 --week 8
    python scripts/matchups.py --prior-weight 0.25    # blend in last season
    python scripts/matchups.py --no-adjust            # raw averages, no opponent adjustment
    python scripts/matchups.py --season 2025 --week 12 --top 15
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import nflreadpy as nfl  # noqa: E402

from nfl_analytics import load_pbp, offensive_plays  # noqa: E402
from nfl_analytics.matchups import (matchup_edges, plot_matchup_edges,  # noqa: E402
                                    unit_ratings, week_schedule)


def print_schedule_movers(ratings: pd.DataFrame, shrinkage: float, n: int = 6) -> None:
    """Units whose rating moved most because of the opponents they faced.

    The adjustment does two things: it shrinks small samples toward average,
    and it accounts for opponent strength. To isolate the opponent part,
    compare against the raw rating shrunk on its own (approximately what the
    ridge would give if every team had faced an average schedule).
    """
    rows = []
    for col in ["off_pass", "off_rush", "def_pass", "def_rush"]:
        side, kind = col.split("_")
        league = ratings.attrs[f"league_{kind}"]
        plays = ratings[f"{col}_plays"]
        raw = ratings[f"{col}_raw"] - league
        shrunk = raw * plays / (plays + shrinkage)
        adjusted = ratings[col] - league
        # Flip defenses so a positive effect always means "better than it looked".
        effect = (adjusted - shrunk) * (1 if side == "off" else -1)
        rows.append(pd.DataFrame({
            "unit": f"{kind} {'offense' if side == 'off' else 'defense'}",
            "raw_vs_avg": raw, "shrunk_only": shrunk, "adjusted_vs_avg": adjusted,
            "schedule_effect": effect, "opp_toughness": ratings[f"{col}_sos"],
        }))
    movers = pd.concat(rows).rename_axis("team").reset_index()
    movers = movers.reindex(movers["schedule_effect"].abs()
                            .sort_values(ascending=False).index).head(n)
    movers["reading"] = np.where(movers["schedule_effect"] > 0,
                                 "better than raw (tough schedule)",
                                 "worse than raw (easy schedule)")
    print("Biggest opponent-strength adjustments:")
    print(movers.round(3).to_string(index=False), "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--season", type=int, default=nfl.get_current_season())
    parser.add_argument("--week", type=int, default=None,
                        help="week to preview (default: first week with an unplayed game)")
    parser.add_argument("--prior-weight", type=float, default=0.0,
                        help="weight of each previous-season play vs. a current one (0-1)")
    parser.add_argument("--no-adjust", action="store_true",
                        help="use raw EPA/play averages instead of opponent-adjusted ratings")
    parser.add_argument("--shrinkage", type=float, default=200.0,
                        help="ridge penalty, in league-average plays added to each team (default 200)")
    parser.add_argument("--top", type=int, default=12, help="number of matchups to chart")
    args = parser.parse_args()

    games, week = week_schedule(args.season, args.week)
    if games.empty:
        sys.exit(f"No regular-season games found for {args.season} week {args.week}.")

    plays = offensive_plays(load_pbp(args.season))
    plays = plays[plays["week"] < week]
    prior = None
    if args.prior_weight > 0 or plays.empty:
        prior = offensive_plays(load_pbp(args.season - 1))
        if plays.empty:
            print(f"No {args.season} games before week {week}; rating teams on {args.season - 1}.")
            args.prior_weight = 1.0

    ratings = unit_ratings(plays, prior, args.prior_weight, adjust=not args.no_adjust,
                           shrinkage=args.shrinkage)
    edges = matchup_edges(games, ratings)
    weeks_used = int(plays["week"].max()) if not plays.empty else 0

    basis = f"{args.season} weeks 1–{weeks_used}" if weeks_used else f"{args.season - 1} season"
    if args.prior_weight > 0 and weeks_used:
        basis += f" + {args.season - 1} at {args.prior_weight:g}× weight"
    method = "raw-average" if args.no_adjust else "opponent-adjusted"

    output, figures = ROOT / "output", ROOT / "figures"
    output.mkdir(exist_ok=True)
    figures.mkdir(exist_ok=True)
    tag = f"{args.season}_wk{week:02d}"
    edges.round(3).to_csv(output / f"matchups_{tag}.csv", index=False)
    ratings.round(3).to_csv(output / f"unit_ratings_{tag}.csv")
    plot_matchup_edges(
        edges, top=args.top,
        title=f"{args.season} week {week}: biggest pass and rush mismatches",
        subtitle=f"{method.capitalize()} ratings from {basis}  ·  win prob. 10–90%",
        save_path=figures / f"matchups_{tag}.png",
    )

    pd.set_option("display.width", 200)
    cols = ["matchup", "offense", "defense", "kind", "off_vs_avg", "def_vs_avg", "edge", "edge_sd"]
    print(f"\n{args.season} week {week}  ·  {len(games)} games  ·  {method} ratings from {basis}\n")
    if not args.no_adjust:
        print_schedule_movers(ratings, args.shrinkage)
    for side in ["offense", "defense"]:
        top = edges[edges["advantage"] == side].head(5)
        print(f"Biggest {side} advantages:")
        print(top[cols].round(3).to_string(index=False), "\n")

    # Largest edge in each game, measured in SDs so pass and rush compare fairly.
    by_game = edges.loc[edges.groupby("game_id")["edge_sd"].apply(lambda s: s.abs().idxmax())]
    by_game = by_game.sort_values("edge_sd", key=abs, ascending=False)
    print("Most lopsided unit matchup in each game:")
    print(by_game[["gameday"] + cols].round(3).to_string(index=False))

    if args.no_adjust and weeks_used and weeks_used < 8:
        print(f"\nNote: only {weeks_used} weeks of data. In a 2025 backtest, raw early-season edges "
              "overstated real results about 3x; the default adjusted ratings correct for this.")
    print(f"\nSaved {output / f'matchups_{tag}.csv'} and {figures / f'matchups_{tag}.png'}")


if __name__ == "__main__":
    main()
