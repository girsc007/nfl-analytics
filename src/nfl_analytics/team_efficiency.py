"""Team offensive vs. defensive EPA per play."""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from adjustText import adjust_text
from matplotlib.colors import LinearSegmentedColormap

from .logos import axis_logo, plot_team_points, team_logo
from .style import (DIVERGING_MID, SERIES_1, SERIES_2, SURFACE, TEXT_MUTED,
                    TEXT_PRIMARY, TEXT_SECONDARY, add_footnote, add_subtitle,
                    apply_style)


def team_epa(plays: pd.DataFrame) -> pd.DataFrame:
    """EPA/play and success rate for each team on offense and on defense.

    For defense, lower EPA allowed is better.
    """
    offense = plays.groupby("posteam").agg(
        off_plays=("epa", "size"),
        off_epa=("epa", "mean"),
        off_success=("success", "mean"),
        off_pass_rate=("pass", "mean"),
    )
    defense = plays.groupby("defteam").agg(
        def_plays=("epa", "size"),
        def_epa=("epa", "mean"),
        def_success=("success", "mean"),
    )
    teams = offense.join(defense, how="inner")
    teams.index.name = "team"
    # Net EPA: how much better the offense is than the defense it allows.
    teams["net_epa"] = teams["off_epa"] - teams["def_epa"]
    return teams.sort_values("net_epa", ascending=False)


def plot_team_efficiency(teams: pd.DataFrame, title: str, subtitle: str,
                         save_path: str | None = None):
    """Scatter of offensive EPA/play (x) vs. defensive EPA/play allowed (y).

    The y-axis is inverted so that up-and-right is good on both sides of the ball.
    """
    apply_style()
    fig, ax = plt.subplots(figsize=(11, 8.5))

    off_avg, def_avg = teams["off_epa"].mean(), teams["def_epa"].mean()
    ax.axvline(off_avg, color=TEXT_MUTED, linestyle="--", linewidth=1, zorder=1)
    ax.axhline(def_avg, color=TEXT_MUTED, linestyle="--", linewidth=1, zorder=1)
    ax.margins(x=0.06, y=0.1)
    ax.invert_yaxis()

    labels = plot_team_points(ax, teams["off_epa"], teams["def_epa"], teams.index)
    if labels:
        adjust_text(labels, x=teams["off_epa"].values, y=teams["def_epa"].values, ax=ax,
                    expand=(1.3, 1.5))

    corner = dict(transform=ax.transAxes, fontsize=10, color=TEXT_SECONDARY,
                  fontstyle="italic")
    ax.text(0.98, 0.98, "Good offense, good defense", ha="right", va="top", **corner)
    ax.text(0.02, 0.98, "Bad offense, good defense", ha="left", va="top", **corner)
    ax.text(0.98, 0.02, "Good offense, bad defense", ha="right", va="bottom", **corner)
    ax.text(0.02, 0.02, "Bad offense, bad defense", ha="left", va="bottom", **corner)

    ax.set_xlabel("Offensive EPA/play  →  better")
    ax.set_ylabel("Defensive EPA/play allowed  →  better (axis inverted)")
    ax.set_title(title, pad=28)
    add_subtitle(ax, subtitle)
    add_footnote(fig, "Data: nflverse via nflreadpy  ·  Dashed lines = league average")
    fig.tight_layout(rect=(0, 0.03, 1, 1))

    if save_path:
        fig.savefig(save_path, dpi=150)
    return fig, ax


def team_pass_rush_epa(plays: pd.DataFrame) -> pd.DataFrame:
    """Offensive EPA/play split into dropbacks and designed runs.

    nflverse counts QB scrambles as pass plays (`pass == 1`), so "rush" here
    means designed runs only.
    """
    grouped = plays.groupby(["posteam", "pass"])["epa"]
    split = pd.DataFrame({
        "pass_epa": grouped.mean().xs(1, level="pass"),
        "rush_epa": grouped.mean().xs(0, level="pass"),
        "pass_plays": grouped.size().xs(1, level="pass"),
        "rush_plays": grouped.size().xs(0, level="pass"),
    })
    split["pass_rate"] = split["pass_plays"] / (split["pass_plays"] + split["rush_plays"])
    split["pass_minus_rush"] = split["pass_epa"] - split["rush_epa"]
    split.index.name = "team"
    return split.sort_values("pass_epa", ascending=False)


def plot_pass_vs_rush(split: pd.DataFrame, title: str, subtitle: str,
                      save_path: str | None = None):
    """Scatter of pass EPA/play (x) vs. rush EPA/play (y) on a shared scale.

    Both axes use the same units per inch, so the wider spread of passing
    efficiency is visible. The diagonal marks pass EPA = rush EPA.
    """
    apply_style()
    fig, ax = plt.subplots(figsize=(13, 7.5))

    ax.axvline(split["pass_epa"].mean(), color=TEXT_MUTED, linestyle="--", linewidth=1, zorder=1)
    ax.axhline(split["rush_epa"].mean(), color=TEXT_MUTED, linestyle="--", linewidth=1, zorder=1)
    # Draw the logos first so the axis limits below are fit to the data.
    labels = plot_team_points(ax, split["pass_epa"], split["rush_epa"], split.index)

    ax.set_aspect("equal", adjustable="datalim")
    ax.margins(0.08)
    low = min(split["pass_epa"].min(), split["rush_epa"].min()) - 0.1
    high = max(split["pass_epa"].max(), split["rush_epa"].max()) + 0.1
    xlim, ylim = ax.get_xlim(), ax.get_ylim()
    ax.plot([low, high], [low, high], color=TEXT_SECONDARY, linewidth=1, zorder=1)
    ax.set_xlim(xlim)
    ax.set_ylim(ylim)
    # Label the diagonal a third of the way up its visible stretch, where it
    # passes through open space between the two clusters of teams.
    start, end = max(xlim[0], ylim[0]), min(xlim[1], ylim[1])
    label_at = start + (end - start) * 0.38
    ax.text(label_at, label_at, "  pass = rush", rotation=45, rotation_mode="anchor",
            ha="left", va="bottom", fontsize=9, color=TEXT_SECONDARY)

    if labels:
        adjust_text(labels, x=split["pass_epa"].values, y=split["rush_epa"].values, ax=ax,
                    expand=(1.3, 1.5))

    corner = dict(transform=ax.transAxes, fontsize=10, color=TEXT_SECONDARY,
                  fontstyle="italic")
    ax.text(0.98, 0.98, "Good passing, good rushing", ha="right", va="top", **corner)
    ax.text(0.98, 0.02, "Good passing, poor rushing", ha="right", va="bottom", **corner)

    ax.set_xlabel("Pass EPA/play (dropbacks, incl. scrambles and sacks)  →  better")
    ax.set_ylabel("Rush EPA/play (designed runs)  →  better")
    ax.set_title(title, pad=28)
    add_subtitle(ax, subtitle)
    add_footnote(fig, "Data: nflverse via nflreadpy  ·  Dashed lines = league average  ·  "
                      "Both axes on the same scale")
    fig.tight_layout(rect=(0, 0.03, 1, 1))

    if save_path:
        fig.savefig(save_path, dpi=150)
    return fig, ax


DOWNS = ["1st down", "2nd down", "3rd down"]


def pass_tendency_by_down(plays: pd.DataFrame) -> pd.DataFrame:
    """How often each team passed on each down, raw and over expected.

    `pass_rate` is the share of plays that were dropbacks. `proe` (pass rate
    over expected) subtracts nflverse's `xpass`, the expected pass probability
    given down, distance, field position, score and time, so it isolates the
    play-caller's tendency from game situation. `proe_vs_nfl` re-centers PROE
    on the league average for that down (the league itself runs slightly more
    than `xpass` predicts in these competitive situations), and `significant`
    marks teams whose 95% interval for `proe_vs_nfl` excludes zero. Includes
    an "NFL" row per down.
    """
    plays = plays[plays["down"].between(1, 3) & plays["xpass"].notna()].copy()
    plays["situation"] = plays["down"].astype(int).map(dict(enumerate(DOWNS, start=1)))
    plays["residual"] = plays["pass"] - plays["xpass"]

    frames = []
    for data in (plays, plays.assign(posteam="NFL")):
        frames.append(data.groupby(["posteam", "situation"]).agg(
            plays=("pass", "size"), pass_rate=("pass", "mean"), xpass=("xpass", "mean"),
            proe=("residual", "mean"), proe_sd=("residual", "std")))
    out = pd.concat(frames).rename_axis(["team", "situation"]).reset_index()
    league = out[out["team"] == "NFL"].set_index("situation")["proe"]
    out["proe_vs_nfl"] = out["proe"] - out["situation"].map(league)
    out["significant"] = (out["team"] != "NFL") & (
        out["proe_vs_nfl"].abs() > 1.96 * out["proe_sd"] / np.sqrt(out["plays"]))
    return out.drop(columns="proe_sd")


def _diverging_cmap() -> LinearSegmentedColormap:
    """Orange (runs more) <- gray -> blue (passes more)."""
    return LinearSegmentedColormap.from_list(
        "run_pass", ["#a3401a", SERIES_2, "#f6c3a9", DIVERGING_MID,
                     "#9ec5f4", SERIES_1, "#184f95"])


def plot_pass_tendency_by_down(tendency: pd.DataFrame, title: str, subtitle: str,
                               limit: float = 0.12, save_path: str | None = None):
    """Heatmap of pass tendency: teams as rows, downs as columns.

    Each cell shows the pass rate (large) and pass rate over expected relative
    to the league average for that down (small, ★ = 95% interval excludes the
    league average). Color uses the same measure: blue passes more than the
    average team would in the same situations, orange runs more. Rows are
    sorted by 1st down with the league average (0 by definition) on top.
    """
    apply_style()
    wide = tendency.pivot(index="team", columns="situation", values="proe_vs_nfl")
    order = ["NFL"] + list(wide.drop("NFL")[DOWNS[0]].sort_values(ascending=False).index)
    cells = tendency.set_index(["team", "situation"])

    n_rows = len(order)
    fig, ax = plt.subplots(figsize=(8.5, 0.34 * n_rows + 2.6))
    cmap, norm = _diverging_cmap(), plt.Normalize(-limit, limit)

    for row, team in enumerate(order):
        y = n_rows - 1 - row
        for col, situation in enumerate(DOWNS):
            cell = cells.loc[(team, situation)]
            color = cmap(norm(np.clip(cell["proe_vs_nfl"], -limit, limit)))
            ax.add_patch(plt.Rectangle((col + 0.02, y + 0.04), 0.96, 0.92,
                                       facecolor=color, linewidth=0))
            r, g, b, _ = color
            ink = "white" if (0.299 * r + 0.587 * g + 0.114 * b) < 0.55 else TEXT_PRIMARY
            ax.text(col + 0.36, y + 0.5, f"{cell['pass_rate']:.0%}", ha="center", va="center",
                    fontsize=9, fontweight="bold", color=ink)
            star = " ★" if cell["significant"] else ""
            ax.text(col + 0.76, y + 0.5, f"{cell['proe_vs_nfl'] * 100:+.1f}{star}", ha="center",
                    va="center", fontsize=7.5, color=ink)

    # Rule under the league-average row.
    ax.axhline(n_rows - 1, color=TEXT_SECONDARY, linewidth=1)

    ax.set_xlim(0, len(DOWNS))
    ax.set_ylim(0, n_rows)
    ax.set_xticks(np.arange(len(DOWNS)) + 0.5, DOWNS)
    ax.xaxis.tick_top()
    ax.tick_params(axis="x", length=0, labelsize=10, labelcolor=TEXT_PRIMARY, pad=4)
    ax.grid(False)
    for spine in ax.spines.values():
        spine.set_visible(False)

    logo_size = 0.24
    yticks, ylabels = [], []
    for row, team in enumerate(order):
        y = n_rows - 1 - row + 0.5
        yticks.append(y)
        ylabels.append("NFL avg" if team == "NFL" else team)
        if team != "NFL":
            axis_logo(ax, team, y, offset=4 + logo_size * 36, size=logo_size)
    ax.set_yticks(yticks, ylabels)
    ax.tick_params(axis="y", length=0, labelsize=9, labelcolor=TEXT_PRIMARY,
                   pad=logo_size * 72 + 8)

    ax.set_title(title, pad=52)
    add_subtitle(ax, subtitle, y=1.045)

    # Color legend: a slim bar under the grid.
    cax = fig.add_axes([0.3, 0.95 / fig.get_figheight(), 0.45, 0.012])
    bar = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap), cax=cax,
                       orientation="horizontal", ticks=[-limit, 0, limit])
    pts = round(limit * 100)
    bar.ax.set_xticklabels([f"Runs more than avg team\n−{pts} pts", "League average\n0",
                            f"Passes more than avg team\n+{pts} pts"],
                           fontsize=8, color=TEXT_SECONDARY)
    bar.outline.set_visible(False)
    bar.ax.tick_params(length=0)

    add_footnote(fig, "Cell: pass rate, then pass rate over expected vs. league avg, in points "
                      "(★ = 95% significant). Expected: nflverse xpass.  Data: nflverse")
    fig.subplots_adjust(left=0.2, right=0.97, top=1 - 1.25 / fig.get_figheight(),
                        bottom=1.55 / fig.get_figheight())

    if save_path:
        fig.savefig(save_path, dpi=150)
    return fig, ax
