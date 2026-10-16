"""Team offensive vs. defensive EPA per play."""

import matplotlib.pyplot as plt
import pandas as pd
from adjustText import adjust_text

from .logos import plot_team_points
from .style import (TEXT_MUTED, TEXT_SECONDARY, add_footnote, add_subtitle,
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
