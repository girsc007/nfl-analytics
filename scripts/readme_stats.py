"""Print every number the README findings quote, recomputed from the output/ CSVs.

Run after scripts/make_charts.py, then update the README bullets and QB table to
match. Sections are printed in README order. Nothing is written to disk.

Usage:
    python scripts/readme_stats.py                 # 2026
    python scripts/readme_stats.py --season 2025
"""

import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def team_efficiency(teams: pd.DataFrame) -> None:
    print("## Team efficiency")
    cols = ["team", "off_epa", "def_epa", "net_epa"]
    print("Best net EPA/play (best combination of offense and defense):")
    print(teams.sort_values("net_epa", ascending=False).head(5)[cols].to_string(index=False))
    ranked = teams.assign(off_rank=teams["off_epa"].rank(ascending=False, method="min"),
                          def_rank=teams["def_epa"].rank(method="min"))
    rank_cols = ["team", "off_epa", "off_rank", "def_epa", "def_rank"]
    print("\nBest defenses (lowest EPA/play allowed):")
    print(ranked.sort_values("def_epa").head(5)[rank_cols].to_string(index=False))
    print("\nWorst defenses:")
    print(ranked.sort_values("def_epa", ascending=False).head(4)[rank_cols].to_string(index=False))


def pass_vs_rush(split: pd.DataFrame) -> None:
    print("\n## Passing vs. rushing")
    league_pass = (split["pass_epa"] * split["pass_plays"]).sum() / split["pass_plays"].sum()
    league_rush = (split["rush_epa"] * split["rush_plays"]).sum() / split["rush_plays"].sum()
    print(f"League EPA per dropback {league_pass:+.3f}, per designed run {league_rush:+.3f}")
    print("Ran more efficiently than they passed:",
          ", ".join(split.loc[split["rush_epa"] > split["pass_epa"], "team"]))
    print(f"Std. dev. between teams: pass {split['pass_epa'].std():.2f}, "
          f"rush {split['rush_epa'].std():.2f}")
    print("Best passing offenses:")
    print(split.sort_values("pass_epa", ascending=False).head(5)
          [["team", "pass_epa", "rush_epa"]].to_string(index=False))
    print(f"r(pass rate, pass EPA) = {split['pass_rate'].corr(split['pass_epa']):.2f}")
    pass_rate_rank = split["pass_rate"].rank(ascending=False, method="min")
    for team in split.loc[split["rush_epa"] > split["pass_epa"], "team"]:
        print(f"  {team} pass-rate rank: {int(pass_rate_rank[split['team'] == team].iloc[0])}")
    print(f"r(pass EPA, rush EPA) = {split['pass_epa'].corr(split['rush_epa']):.2f}")
    both = split[(split["pass_epa"] > league_pass) & (split["rush_epa"] > league_rush)]
    print("Above average at both (sorted by pass + rush EPA):")
    print(both.assign(total=both["pass_epa"] + both["rush_epa"]).sort_values("total", ascending=False)
          [["team", "pass_epa", "rush_epa"]].to_string(index=False))


def run_direction(direction: pd.DataFrame) -> None:
    print("\n## Run direction")
    league = direction[direction["team"] == "NFL"].set_index("lane")
    print("League by lane:", ", ".join(f"{lane} {row.epa:+.3f} EPA/carry, {row.share:.0%} of carries"
                                       for lane, row in league.iterrows()))
    teams = direction[direction["team"] != "NFL"]
    share = teams.pivot(index="team", columns="lane", values="share")
    epa = teams.pivot(index="team", columns="lane", values="epa")
    carries = teams.pivot(index="team", columns="lane", values="carries")
    for lane in ["Inside", "Outside"]:
        top = share[lane].sort_values(ascending=False).head(4)
        print(f"Highest {lane.lower()} share:", ", ".join(f"{t} {v:.0%}" for t, v in top.items()))
    print(f"r(outside share, EPA on all runs) = {share['Outside'].corr(epa['All runs']):.2f}")
    print("Best and worst run games (EPA/carry, all runs):")
    ranked = epa["All runs"].sort_values(ascending=False)
    for label, part in (("  best ", ranked.head(4)), ("  worst", ranked.tail(3))):
        print(label, ", ".join(f"{t} {v:+.2f}" for t, v in part.items()))
    print("Best lane for each of the top 4 (EPA/carry, carries):")
    for team in ranked.head(4).index:
        lane = epa.loc[team].drop("All runs").idxmax()
        print(f"  {team}: {lane} {epa.loc[team, lane]:+.2f} on {carries.loc[team, lane]:.0f}")
    print("Significant (★) cells:")
    print(teams[teams["significant"]][["team", "lane", "epa", "carries"]].to_string(index=False))


def tendency_by_down(tendency: pd.DataFrame) -> None:
    print("\n## Pass/run tendencies by down (points vs. league average)")
    teams = tendency[tendency["team"] != "NFL"]
    proe = teams.pivot(index="team", columns="situation", values="proe_vs_nfl") * 100
    pass_rate = teams.pivot(index="team", columns="situation", values="pass_rate") * 100
    for down in proe.columns:
        order = proe[down].sort_values()
        run = ", ".join(f"{t} {v:+.1f} ({pass_rate.loc[t, down]:.0f}% pass)"
                        for t, v in order.head(4).items())
        passing = ", ".join(f"{t} {v:+.1f} ({pass_rate.loc[t, down]:.0f}% pass)"
                            for t, v in order[::-1].head(4).items())
        print(f"{down}\n  most run-leaning:  {run}\n  most pass-leaning: {passing}")
    print(f"r(1st-down, 2nd-down tendency) = {proe['1st down'].corr(proe['2nd down']):.2f}")
    league = teams.groupby("situation").apply(
        lambda g: ((g["pass_rate"] - g["xpass"]) * g["plays"]).sum() / g["plays"].sum() * 100,
        include_groups=False)
    print("League pass rate minus xpass, in points (the 'Why re-center?' bullet):",
          ", ".join(f"{down} {v:+.1f}" for down, v in league.items()))


def quarterbacks(qbs: pd.DataFrame) -> None:
    print("\n## Quarterbacks (README table, already filtered to qualifying QBs)")
    print("| # | QB | Team | Dropbacks | EPA/db | CPOE | Success % |")
    print("|---|---|---|---:|---:|---:|---:|")
    top = qbs.sort_values("epa_per_db", ascending=False).head(10)
    for i, row in enumerate(top.itertuples(), 1):
        print(f"| {i} | {row.name} | {row.team} | {row.dropbacks} | {row.epa_per_db:+.3f} "
              f"| {row.cpoe:+.1f} | {row.success_rate * 100:.1f} |")
    print(f"Qualified QBs: {len(qbs)} (fewest dropbacks: {qbs['dropbacks'].min()})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--season", type=int, default=2026)
    args = parser.parse_args()

    output = ROOT / "output"
    team_efficiency(pd.read_csv(output / f"team_epa_{args.season}.csv"))
    pass_vs_rush(pd.read_csv(output / f"team_pass_rush_epa_{args.season}.csv"))
    run_direction(pd.read_csv(output / f"run_direction_{args.season}.csv"))
    tendency_by_down(pd.read_csv(output / f"pass_tendency_by_down_{args.season}.csv"))
    quarterbacks(pd.read_csv(output / f"qb_stats_{args.season}.csv"))


if __name__ == "__main__":
    main()
