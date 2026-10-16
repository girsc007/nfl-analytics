"""Build every chart and table for a season.

Usage:
    python scripts/make_charts.py                 # 2025 regular season
    python scripts/make_charts.py --season 2026   # current season to date
    python scripts/make_charts.py --min-dropbacks 100 --all-plays
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nfl_analytics import (load_participation, load_pbp, offensive_plays,  # noqa: E402
                           pass_tendency_by_down, plot_epa_ranking, plot_epa_vs_cpoe,
                           plot_pass_tendency_by_down, plot_pass_vs_rush,
                           plot_rb_tendencies, plot_team_efficiency, qb_stats,
                           rb_pass_tendencies, team_epa, team_pass_rush_epa)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--season", type=int, default=2025)
    parser.add_argument("--min-dropbacks", type=int, default=None,
                        help="QB qualifying threshold (default: 15 per week played)")
    parser.add_argument("--all-plays", action="store_true",
                        help="keep garbage time (default filters to 10-90%% win probability)")
    args = parser.parse_args()

    figures, output = ROOT / "figures", ROOT / "output"
    figures.mkdir(exist_ok=True)
    output.mkdir(exist_ok=True)

    print(f"Loading {args.season} play-by-play...")
    pbp = load_pbp(args.season)
    plays = offensive_plays(pbp, wp_range=None if args.all_plays else (0.10, 0.90))
    weeks = int(plays["week"].max())
    scope = "all plays" if args.all_plays else "win prob. 10–90%"
    through = "regular season" if weeks >= 18 else f"through week {weeks}"

    teams = team_epa(plays)
    teams.round(3).to_csv(output / f"team_epa_{args.season}.csv")
    plot_team_efficiency(
        teams,
        title=f"{args.season} NFL team efficiency",
        subtitle=f"EPA per play on offense vs. defense  ·  {through}  ·  {scope}",
        save_path=figures / f"team_efficiency_{args.season}.png",
    )

    split = team_pass_rush_epa(plays)
    split.round(3).to_csv(output / f"team_pass_rush_epa_{args.season}.csv")
    plot_pass_vs_rush(
        split,
        title=f"{args.season} offense: passing vs. rushing efficiency",
        subtitle=f"EPA per play by play type  ·  {through}  ·  {scope}",
        save_path=figures / f"team_pass_vs_rush_{args.season}.png",
    )

    tendency = pass_tendency_by_down(plays)
    tendency.round(3).to_csv(output / f"pass_tendency_by_down_{args.season}.csv", index=False)
    plot_pass_tendency_by_down(
        tendency,
        title=f"{args.season}: who passes or runs more than expected, by down?",
        subtitle=f"Pass rate and pass rate over expected  ·  {through}  ·  {scope}",
        save_path=figures / f"pass_tendency_by_down_{args.season}.png",
    )

    rb_min = max(40, 8 * weeks)
    rbs = rb_pass_tendencies(plays, load_participation(args.season), min_plays=rb_min)
    rbs.round(3).to_csv(output / f"rb_pass_tendencies_{args.season}.csv")
    plot_rb_tendencies(
        rbs,
        title=f"{args.season}: does the running back tip off a pass?",
        subtitle=f"Pass rate over expected with each team's top two backs on the field alone  ·  "
                 f"{through}  ·  min. {rb_min} plays each",
        save_path=figures / f"rb_pass_tendencies_{args.season}.png",
    )

    min_db = args.min_dropbacks or 15 * weeks
    qbs = qb_stats(plays, min_dropbacks=min_db)
    qbs.round(3).to_csv(output / f"qb_stats_{args.season}.csv")
    qb_subtitle = f"{through}  ·  {scope}  ·  min. {min_db} dropbacks"
    plot_epa_vs_cpoe(
        qbs,
        title=f"{args.season} QB accuracy vs. production",
        subtitle=qb_subtitle,
        save_path=figures / f"qb_epa_vs_cpoe_{args.season}.png",
    )
    plot_epa_ranking(
        qbs,
        title=f"{args.season} QB EPA per dropback",
        subtitle=qb_subtitle,
        save_path=figures / f"qb_epa_ranking_{args.season}.png",
    )

    print("\nTop 5 teams by net EPA/play:")
    print(teams[["off_epa", "def_epa", "net_epa"]].head().round(3).to_string())
    print("\nTop 5 QBs by EPA/dropback:")
    print(qbs[["name", "team", "dropbacks", "epa_per_db", "cpoe"]].head().round(3).to_string())
    print(f"\nCharts saved to {figures}, tables to {output}")


if __name__ == "__main__":
    main()
