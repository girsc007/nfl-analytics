"""Team offensive vs. defensive EPA per play."""

import matplotlib.pyplot as plt
import pandas as pd
from adjustText import adjust_text

from .style import (ACCENT, SURFACE, TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY,
                    add_footnote, add_subtitle, apply_style)


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

    ax.scatter(teams["off_epa"], teams["def_epa"], s=70, color=ACCENT,
               edgecolor=SURFACE, linewidth=2, zorder=3)

    off_avg, def_avg = teams["off_epa"].mean(), teams["def_epa"].mean()
    ax.axvline(off_avg, color=TEXT_MUTED, linestyle="--", linewidth=1, zorder=1)
    ax.axhline(def_avg, color=TEXT_MUTED, linestyle="--", linewidth=1, zorder=1)
    ax.margins(x=0.06, y=0.1)
    ax.invert_yaxis()

    labels = [ax.text(x, y, team, fontsize=9, fontweight="bold", color=TEXT_PRIMARY)
              for team, x, y in zip(teams.index, teams["off_epa"], teams["def_epa"])]
    adjust_text(labels, x=teams["off_epa"].values, y=teams["def_epa"].values, ax=ax,
                expand=(1.3, 1.5), arrowprops=dict(arrowstyle="-", color=TEXT_MUTED, lw=0.5))

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
