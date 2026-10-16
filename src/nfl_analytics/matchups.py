"""Find mismatches between pass/rush offenses and the defenses they face.

Each team gets four unit ratings (EPA/play, relative to league average):
pass offense, rush offense, pass defense allowed and rush defense allowed.
A matchup's edge adds the two sides together:

    edge = (offense rating - league avg) + (defense allowed - league avg)

Positive: the offense should beat its usual efficiency (offense advantage).
Negative: the defense should hold it below average (defense advantage).

By default ratings are opponent-adjusted: a defense that has only faced weak
offenses doesn't get full credit for the low EPA it allowed.
"""

import matplotlib.pyplot as plt
import nflreadpy as nfl
import numpy as np
import pandas as pd

from .style import (SERIES_1, SERIES_2, TEXT_PRIMARY, TEXT_SECONDARY,
                    add_footnote, add_subtitle, apply_style)

KINDS = {"pass": 1, "rush": 0}


def _ridge_ratings(subset: pd.DataFrame, shrinkage: float) -> tuple[pd.Series, pd.Series, float]:
    """Solve EPA = league + offense + defense for every team at once.

    Weighted ridge regression: `shrinkage` acts like that many league-average
    plays added to each team, pulling thin samples toward zero. Returns each
    team's offense and defense coefficient (EPA/play vs. average) and the
    intercept (league average).
    """
    teams = sorted(set(subset["posteam"]) | set(subset["defteam"]))
    index = {team: i for i, team in enumerate(teams)}
    n_teams = len(teams)
    off_idx = subset["posteam"].map(index).to_numpy()
    def_idx = subset["defteam"].map(index).to_numpy() + n_teams

    rows = np.arange(len(subset))
    X = np.zeros((len(subset), 1 + 2 * n_teams))
    X[:, 0] = 1.0
    X[rows, 1 + off_idx] = 1.0
    X[rows, 1 + def_idx] = 1.0
    w = subset["weight"].to_numpy()
    y = subset["epa"].to_numpy()

    penalty = np.full(1 + 2 * n_teams, max(shrinkage, 1e-6))
    penalty[0] = 0.0  # don't shrink the league average
    beta = np.linalg.solve((X.T * w) @ X + np.diag(penalty), (X.T * w) @ y)
    return (pd.Series(beta[1:1 + n_teams], index=teams),
            pd.Series(beta[1 + n_teams:], index=teams), beta[0])


def unit_ratings(plays: pd.DataFrame, prior_plays: pd.DataFrame | None = None,
                 prior_weight: float = 0.0, adjust: bool = True,
                 shrinkage: float = 200.0) -> pd.DataFrame:
    """EPA/play for each team's pass/rush offense and pass/rush defense.

    adjust=True accounts for opponent strength: each rating is what remains
    after crediting the opponents faced, fit jointly by ridge regression
    (see `_ridge_ratings`). adjust=False gives raw per-play averages. Raw
    averages are always kept in the `*_raw` columns. `*_sos` is strength of
    schedule: how good the opponents each unit faced were, in EPA/play
    (positive = tougher opponents, for offenses and defenses alike).

    With `prior_plays`, each prior-season play counts `prior_weight` as much as
    a current-season play.
    """
    frames = [plays.assign(weight=1.0)]
    if prior_plays is not None and prior_weight > 0:
        frames.append(prior_plays.assign(weight=prior_weight))
    data = pd.concat(frames)
    data["weighted_epa"] = data["epa"] * data["weight"]

    columns, leagues = {}, {}
    for kind, flag in KINDS.items():
        subset = data[data["pass"] == flag]
        league = subset["weighted_epa"].sum() / subset["weight"].sum()
        off_coef, def_coef, intercept = _ridge_ratings(subset, shrinkage)

        # A tough defense has a negative coefficient (allows less EPA), so flip
        # it so that positive strength of schedule always means tougher opponents.
        for side, team_col, coef, opp_col, opp_coef in [
                ("off", "posteam", off_coef, "defteam", -def_coef),
                ("def", "defteam", def_coef, "posteam", off_coef)]:
            grouped = subset.groupby(team_col)
            raw = grouped["weighted_epa"].sum() / grouped["weight"].sum()
            opp_strength = subset[opp_col].map(opp_coef) * subset["weight"]
            columns[f"{side}_{kind}"] = (intercept + coef) if adjust else raw
            columns[f"{side}_{kind}_raw"] = raw
            columns[f"{side}_{kind}_sos"] = opp_strength.groupby(subset[team_col]).sum() / grouped["weight"].sum()
            columns[f"{side}_{kind}_plays"] = grouped["weight"].sum()
        leagues[kind] = intercept if adjust else league

    table = pd.DataFrame(columns)
    for kind, league in leagues.items():
        table.attrs[f"league_{kind}"] = league
    table.index.name = "team"
    return table


def week_schedule(season: int, week: int | None = None) -> tuple[pd.DataFrame, int]:
    """Games for a week. Defaults to the first week with an unplayed game."""
    sched = nfl.load_schedules(season).to_pandas()
    sched = sched[sched["game_type"] == "REG"]
    if week is None:
        unplayed = sched[sched["home_score"].isna()]
        week = int(unplayed["week"].min()) if len(unplayed) else int(sched["week"].max())
    games = sched[sched["week"] == week]
    return games[["game_id", "week", "gameday", "away_team", "home_team",
                  "home_score", "away_score", "spread_line"]], week


def matchup_edges(games: pd.DataFrame, ratings: pd.DataFrame) -> pd.DataFrame:
    """One row per (game, offense, pass/rush) with the matchup edge."""
    rows = []
    for game in games.itertuples():
        for offense, defense in [(game.away_team, game.home_team),
                                 (game.home_team, game.away_team)]:
            for kind in KINDS:
                league = ratings.attrs[f"league_{kind}"]
                off_rel = ratings.at[offense, f"off_{kind}"] - league
                def_rel = ratings.at[defense, f"def_{kind}"] - league
                rows.append({
                    "game_id": game.game_id, "gameday": game.gameday,
                    "matchup": f"{game.away_team} @ {game.home_team}",
                    "offense": offense, "defense": defense, "kind": kind,
                    "off_vs_avg": off_rel, "def_vs_avg": def_rel,
                    "edge": off_rel + def_rel,
                })
    edges = pd.DataFrame(rows)

    # Passing ratings vary about twice as much as rushing, so also express each
    # edge in standard deviations of its own kind to compare pass and rush fairly.
    for kind in KINDS:
        spread = np.sqrt(ratings[f"off_{kind}"].var() + ratings[f"def_{kind}"].var())
        mask = edges["kind"] == kind
        edges.loc[mask, "edge_sd"] = edges.loc[mask, "edge"] / spread

    edges["advantage"] = np.where(edges["edge"] >= 0, "offense", "defense")
    return edges.sort_values("edge", key=abs, ascending=False).reset_index(drop=True)


def plot_matchup_edges(edges: pd.DataFrame, title: str, subtitle: str, top: int = 12,
                       save_path: str | None = None):
    """Diverging bars of the largest edges: right = offense, left = defense."""
    apply_style()
    shown = edges.head(top).iloc[::-1]
    fig, ax = plt.subplots(figsize=(11, max(4.5, 0.45 * len(shown) + 2.2)))

    colors = [SERIES_1 if k == "pass" else SERIES_2 for k in shown["kind"]]
    y = np.arange(len(shown))
    ax.barh(y, shown["edge"], height=0.65, color=colors, zorder=3)
    ax.axvline(0, color=TEXT_SECONDARY, linewidth=1, zorder=4)

    labels = [f"{o} {k} O  vs.  {d} {k} D" for o, d, k in
              zip(shown["offense"], shown["defense"], shown["kind"])]
    ax.set_yticks(y, labels)
    ax.tick_params(axis="y", length=0, labelsize=9.5, labelcolor=TEXT_PRIMARY)
    ax.grid(axis="y", visible=False)

    limit = shown["edge"].abs().max() * 1.25
    ax.set_xlim(-limit, limit)
    pad = limit * 0.015
    for yi, value in zip(y, shown["edge"]):
        ax.text(value + (pad if value >= 0 else -pad), yi, f"{value:+.2f}", va="center",
                ha="left" if value >= 0 else "right", fontsize=8.5, color=TEXT_SECONDARY)

    ax.text(0.99, 1.0, "Offense advantage  →", transform=ax.transAxes, ha="right",
            va="bottom", fontsize=9.5, color=TEXT_SECONDARY)
    ax.text(0.01, 1.0, "←  Defense advantage", transform=ax.transAxes, ha="left",
            va="bottom", fontsize=9.5, color=TEXT_SECONDARY)

    handles = [plt.Rectangle((0, 0), 1, 1, color=SERIES_1),
               plt.Rectangle((0, 0), 1, 1, color=SERIES_2)]
    ax.legend(handles, ["Passing matchup", "Rushing matchup"], loc="upper center",
              bbox_to_anchor=(0.5, -0.1), ncol=2, frameon=False, fontsize=9.5,
              labelcolor=TEXT_SECONDARY)

    ax.set_xlabel("Matchup edge: expected EPA/play vs. league average")
    ax.set_title(title, pad=40)
    add_subtitle(ax, subtitle, y=1.06)  # sits above the direction labels
    add_footnote(fig, "Edge = offense rating vs. avg + defense rating (EPA/play allowed) vs. avg  ·  "
                      "Data: nflverse via nflreadpy")
    fig.tight_layout(rect=(0, 0.03, 1, 1))

    if save_path:
        fig.savefig(save_path, dpi=150)
    return fig, ax
