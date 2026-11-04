"""Where teams run (inside, off tackle, outside) and how well it works."""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, to_rgb

from .logos import axis_logo
from .style import (DIVERGING_MID, SERIES_1, SERIES_2, TEXT_PRIMARY, TEXT_SECONDARY,
                    add_footnote, add_subtitle, apply_style)

LANES = ["Inside", "Off tackle", "Outside"]
ALL = "All runs"
# nflverse leaves run_gap empty for runs up the middle.
GAP_TO_LANE = {"guard": "Inside", "tackle": "Off tackle", "end": "Outside"}


def run_direction(plays: pd.DataFrame) -> pd.DataFrame:
    """Designed-run volume and EPA/carry by lane for each team.

    Lanes come from nflverse's `run_location`/`run_gap`, with left and right
    combined: inside = guard gaps and middle, off tackle = tackle gaps,
    outside = end. Runs with no recorded direction (aborted snaps and the like)
    are dropped. `share` is the team's share of its carries in that lane,
    `epa_vs_nfl` compares EPA/carry with the league in the same lane, and
    `significant` marks teams whose 95% interval for it excludes zero.
    Includes an "NFL" row per lane and an "All runs" lane per team.
    """
    runs = plays[(plays["pass"] == 0) & plays["run_location"].notna()].copy()
    runs["lane"] = np.where(runs["run_location"] == "middle", "Inside",
                            runs["run_gap"].map(GAP_TO_LANE))
    runs = runs[runs["lane"].notna()]

    frames = []
    for data in (runs, runs.assign(posteam="NFL")):
        for lanes in (data, data.assign(lane=ALL)):
            frames.append(lanes.groupby(["posteam", "lane"]).agg(
                carries=("epa", "size"), epa=("epa", "mean"), epa_sd=("epa", "std"),
                success=("success", "mean")))
    out = pd.concat(frames).rename_axis(["team", "lane"]).reset_index()
    totals = out[out["lane"] == ALL].set_index("team")["carries"]
    out["share"] = out["carries"] / out["team"].map(totals)
    league = out[out["team"] == "NFL"].set_index("lane")["epa"]
    out["epa_vs_nfl"] = out["epa"] - out["lane"].map(league)
    out["significant"] = (out["team"] != "NFL") & (
        out["epa_vs_nfl"].abs() > 1.96 * out["epa_sd"] / np.sqrt(out["carries"]))
    return out.drop(columns="epa_sd")


def _diverging_cmap() -> LinearSegmentedColormap:
    """Orange (worse than league) <- gray -> blue (better)."""
    return LinearSegmentedColormap.from_list(
        "worse_better", ["#a3401a", SERIES_2, "#f6c3a9", DIVERGING_MID,
                         "#9ec5f4", SERIES_1, "#184f95"])


# Inside -> outside as light -> dark gray: the lanes are ordered, and gray keeps
# blue/orange meaning better/worse than league in the heatmap beside it.
LANE_COLORS = {"Inside": "#dcdbd6", "Off tackle": "#aeada8", "Outside": "#76756f"}


def _ink(color) -> str:
    r, g, b = color[:3]
    return "white" if (0.299 * r + 0.587 * g + 0.114 * b) < 0.55 else TEXT_PRIMARY


def plot_run_direction(direction: pd.DataFrame, title: str, subtitle: str,
                       limit: float = 0.25, save_path: str | None = None):
    """Two aligned panels, teams as rows sorted by EPA/carry on all designed runs.

    Left: each team's carries split into inside / off tackle / outside.
    Right: EPA/carry overall and in each lane (★ = 95% interval excludes the
    league average for that lane), small text = carries. Color compares with
    the league in the same lane: blue better, orange worse.
    """
    apply_style()
    cells = direction.set_index(["team", "lane"])
    overall = direction[(direction["lane"] == ALL) & (direction["team"] != "NFL")]
    order = ["NFL"] + list(overall.sort_values("epa", ascending=False)["team"])
    columns = [ALL] + LANES

    n_rows = len(order)
    fig, (bar_ax, heat_ax) = plt.subplots(
        1, 2, figsize=(11, 0.34 * n_rows + 2.6), sharey=True,
        gridspec_kw=dict(width_ratios=[1.15, 1.6], wspace=0.06))
    fig.subplots_adjust(left=0.1, right=0.98, top=1 - 1.25 / fig.get_figheight(),
                        bottom=1.55 / fig.get_figheight())
    cmap, norm = _diverging_cmap(), plt.Normalize(-limit, limit)

    for row, team in enumerate(order):
        y = n_rows - 1 - row
        left = 0.0
        for lane in LANES:
            share = cells.loc[(team, lane), "share"]
            color = LANE_COLORS[lane]
            bar_ax.barh(y + 0.5, share, left=left, height=0.92, color=color, linewidth=0)
            if share >= 0.08:
                bar_ax.text(left + share / 2, y + 0.5, f"{share:.0%}", ha="center", va="center",
                            fontsize=8, color=_ink(to_rgb(color)))
            left += share

        for col, lane in enumerate(columns):
            cell = cells.loc[(team, lane)]
            color = cmap(norm(np.clip(cell["epa_vs_nfl"], -limit, limit)))
            heat_ax.add_patch(plt.Rectangle((col + 0.02, y + 0.04), 0.96, 0.92,
                                            facecolor=color, linewidth=0))
            ink = _ink(color)
            star = " ★" if cell["significant"] else ""
            heat_ax.text(col + 0.42, y + 0.5, f"{cell['epa']:+.2f}{star}", ha="center",
                         va="center", fontsize=9, fontweight="bold", color=ink)
            heat_ax.text(col + 0.86, y + 0.5, f"{cell['carries']:.0f}", ha="center",
                         va="center", fontsize=7, color=ink)

    for ax in (bar_ax, heat_ax):
        ax.axhline(n_rows - 1, color=TEXT_SECONDARY, linewidth=1)
        ax.grid(False)
        ax.xaxis.tick_top()
        ax.tick_params(axis="x", length=0, labelsize=10, labelcolor=TEXT_PRIMARY, pad=4)
        for spine in ax.spines.values():
            spine.set_visible(False)
    # Column divider between "All runs" and the lanes.
    heat_ax.axvline(1, color=TEXT_SECONDARY, linewidth=1)

    bar_ax.set_xlim(0, 1)
    heat_ax.set_xlim(0, len(columns))
    heat_ax.set_xticks(np.arange(len(columns)) + 0.5, columns)
    heat_ax.set_ylim(0, n_rows)

    # Lane names centered on the league-average segments double as the bar legend.
    starts = np.cumsum([0] + [cells.loc[("NFL", lane), "share"] for lane in LANES])
    bar_ax.set_xticks((starts[:-1] + starts[1:]) / 2, LANES)

    logo_size = 0.24
    yticks, ylabels = [], []
    for row, team in enumerate(order):
        y = n_rows - 1 - row + 0.5
        yticks.append(y)
        ylabels.append("NFL avg" if team == "NFL" else team)
        if team != "NFL":
            axis_logo(bar_ax, team, y, offset=4 + logo_size * 36, size=logo_size)
    bar_ax.set_yticks(yticks, ylabels)
    bar_ax.tick_params(axis="y", length=0, labelsize=9, labelcolor=TEXT_PRIMARY,
                       pad=logo_size * 72 + 8)
    heat_ax.tick_params(axis="y", length=0, labelleft=False)

    bar_ax.set_title(title, pad=52)
    add_subtitle(bar_ax, subtitle, y=1.045)
    for ax, text in ((bar_ax, "Share of carries"), (heat_ax, "EPA per carry  ·  carries")):
        ax.text(0, 1 + 0.3 / fig.get_figheight(), text, transform=ax.transAxes, fontsize=9,
                color=TEXT_SECONDARY, va="bottom")

    # Color legend: a slim bar under the heatmap.
    pos = heat_ax.get_position()
    cax = fig.add_axes([pos.x0 + pos.width * 0.1, 0.95 / fig.get_figheight(),
                        pos.width * 0.8, 0.012])
    bar = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap), cax=cax,
                       orientation="horizontal", ticks=[-limit, 0, limit])
    bar.ax.set_xticklabels([f"Worse than league\n−{limit:.2f}", "League avg\nin that lane",
                            f"Better than league\n+{limit:.2f}"],
                           fontsize=8, color=TEXT_SECONDARY)
    bar.outline.set_visible(False)
    bar.ax.tick_params(length=0)

    add_footnote(fig, "Designed runs (incl. QB) with a recorded direction; left + right combined. "
                      "Inside = guard gaps + middle, off tackle = tackle, outside = end.\n"
                      "★ = 95% significant vs. league in that lane.  Data: nflverse via nflreadpy")

    if save_path:
        fig.savefig(save_path, dpi=150)
    return fig, (bar_ax, heat_ax)
