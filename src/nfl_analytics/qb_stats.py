"""Quarterback efficiency: EPA per dropback, CPOE, success rate and more."""

import matplotlib.pyplot as plt
from matplotlib import patheffects
import numpy as np
import pandas as pd
from adjustText import adjust_text

from .logos import axis_logo, plot_logos, team_logo
from .style import (ACCENT, SERIES_1, SERIES_2, SURFACE, TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY,
                    add_footnote, add_subtitle, apply_style)


def qb_stats(plays: pd.DataFrame, min_dropbacks: int = 200) -> pd.DataFrame:
    """Per-QB stats on dropbacks (passes, sacks and scrambles).

    Uses nflverse's `id`/`name` columns, which credit scrambles and sacks to the
    QB, and `qb_epa`, which doesn't charge the QB for a receiver's fumble.
    """
    dropbacks = plays[(plays["qb_dropback"] == 1) & plays["id"].notna()]

    qbs = dropbacks.groupby("id").agg(
        name=("name", lambda s: s.mode().iat[0]),
        team=("posteam", lambda s: s.mode().iat[0]),
        dropbacks=("qb_epa", "size"),
        epa_per_db=("qb_epa", "mean"),
        total_epa=("qb_epa", "sum"),
        success_rate=("success", "mean"),
        cpoe=("cpoe", "mean"),
        pass_tds=("pass_touchdown", "sum"),
        ints=("interception", "sum"),
        sacks=("sack", "sum"),
    )
    qbs = qbs[qbs["dropbacks"] >= min_dropbacks].copy()
    qbs["sack_rate"] = qbs["sacks"] / qbs["dropbacks"]

    # Composite: average of EPA/dropback and CPOE z-scores among qualified QBs.
    z = lambda col: (qbs[col] - qbs[col].mean()) / qbs[col].std()
    qbs["composite"] = (z("epa_per_db") + z("cpoe")) / 2

    qbs = qbs.sort_values("epa_per_db", ascending=False)
    qbs.index.name = "player_id"
    return qbs


def plot_epa_vs_cpoe(qbs: pd.DataFrame, title: str, subtitle: str,
                     save_path: str | None = None):
    """Scatter of CPOE (accuracy, x) vs. EPA per dropback (production, y)."""
    apply_style()
    fig, ax = plt.subplots(figsize=(11, 8.5))

    boxes = plot_logos(ax, qbs["cpoe"], qbs["epa_per_db"], qbs["team"], size=0.34)
    missing = [box is None for box in boxes]
    ax.scatter(qbs["cpoe"][missing], qbs["epa_per_db"][missing], s=70, color=ACCENT,
               edgecolor=SURFACE, linewidth=2, zorder=3)
    ax.axvline(qbs["cpoe"].mean(), color=TEXT_MUTED, linestyle="--", linewidth=1, zorder=1)
    ax.axhline(qbs["epa_per_db"].mean(), color=TEXT_MUTED, linestyle="--", linewidth=1, zorder=1)

    # Start each name just below its logo, then let adjust_text resolve the
    # remaining collisions, treating the logos as obstacles.
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    to_data = ax.transData.inverted()
    below = 0.34 / 2 * fig.dpi + 2  # half a logo plus a small gap, in pixels
    labels = []
    for name, x, y in zip(qbs["name"], qbs["cpoe"], qbs["epa_per_db"]):
        px, py = ax.transData.transform((x, y))
        lx, ly = to_data.transform((px, py - below))
        labels.append(ax.text(lx, ly, name, fontsize=8.5, color=TEXT_PRIMARY,
                              ha="center", va="top", zorder=5,
                              path_effects=[patheffects.withStroke(linewidth=2.5,
                                                                   foreground=SURFACE)]))
    fig.canvas.draw()
    obstacles = [box.get_window_extent() for box in boxes if box is not None]
    adjust_text(labels, x=qbs["cpoe"].values, y=qbs["epa_per_db"].values, ax=ax,
                objects=obstacles, expand=(1.1, 1.2), only_move={"text": "xy"}, arrowprops=dict(arrowstyle="-", color=TEXT_MUTED, lw=0.5))

    corner = dict(transform=ax.transAxes, fontsize=10, color=TEXT_SECONDARY,
                  fontstyle="italic")
    ax.text(0.02, 0.98, "Productive despite lower accuracy", ha="left", va="top", **corner)
    ax.text(0.98, 0.02, "Accurate but less productive", ha="right", va="bottom", **corner)

    ax.set_xlabel("CPOE: completion % over expected  →  more accurate")
    ax.set_ylabel("EPA per dropback  →  more productive")
    ax.set_title(title, pad=28)
    add_subtitle(ax, subtitle)
    add_footnote(fig, "Data: nflverse via nflreadpy  ·  Dashed lines = average of qualified QBs")
    fig.tight_layout(rect=(0, 0.03, 1, 1))

    if save_path:
        fig.savefig(save_path, dpi=150)
    return fig, ax


def plot_epa_ranking(qbs: pd.DataFrame, title: str, subtitle: str,
                     save_path: str | None = None):
    """Horizontal bars of EPA per dropback, best at the top."""
    apply_style()
    ranked = qbs.sort_values("epa_per_db")
    fig, ax = plt.subplots(figsize=(9, max(5, 0.32 * len(ranked) + 1.5)))

    # The logo shows the team; fall back to "(TEAM)" in the label if it's missing.
    labels = [n if team_logo(t) is not None else f"{n} ({t})"
              for n, t in zip(ranked["name"], ranked["team"])]
    ax.barh(range(len(ranked)), ranked["epa_per_db"], height=0.7, color=ACCENT, zorder=3)
    ax.set_yticks(range(len(ranked)), labels)
    logo_size = 0.24
    for i, team in enumerate(ranked["team"]):
        axis_logo(ax, team, i, offset=4 + logo_size * 36, size=logo_size)
    ax.axvline(0, color=TEXT_SECONDARY, linewidth=1, zorder=4)

    pad = 0.005
    for i, value in enumerate(ranked["epa_per_db"]):
        ax.text(value + (pad if value >= 0 else -pad), i, f"{value:+.2f}",
                va="center", ha="left" if value >= 0 else "right",
                fontsize=8, color=TEXT_SECONDARY)

    ax.grid(axis="y", visible=False)
    # Push the names left to make room for the logos beside the axis.
    ax.tick_params(axis="y", length=0, labelsize=9, labelcolor=TEXT_PRIMARY,
                   pad=logo_size * 72 + 8)
    ax.set_ylim(-0.6, len(ranked) - 0.4)
    ax.margins(x=0.12)
    ax.set_xlabel("EPA per dropback")
    ax.set_title(title, pad=28)
    add_subtitle(ax, subtitle)
    add_footnote(fig, "Data: nflverse via nflreadpy")
    fig.tight_layout(rect=(0, 0.02, 1, 1))

    if save_path:
        fig.savefig(save_path, dpi=150)
    return fig, ax


def qb_pressure_splits(plays: pd.DataFrame, participation: pd.DataFrame,
                       min_dropbacks: int = 200) -> pd.DataFrame:
    """EPA per dropback from a clean pocket vs. under pressure, per QB.

    `participation` needs `was_pressure` (from `load_participation(season,
    ["was_pressure"])`). Sacks always count as pressured dropbacks, so
    pressured EPA reflects both escaping pressure and avoiding sacks.
    """
    dropbacks = plays[(plays["qb_dropback"] == 1) & plays["id"].notna()].merge(
        participation[["nflverse_game_id", "play_id", "was_pressure"]],
        left_on=["game_id", "play_id"], right_on=["nflverse_game_id", "play_id"])
    dropbacks = dropbacks[dropbacks["was_pressure"].notna()]
    dropbacks["was_pressure"] = dropbacks["was_pressure"].astype(bool)

    by_qb = dropbacks.groupby("id")
    splits = pd.DataFrame({
        "name": by_qb["name"].agg(lambda s: s.mode().iat[0]),
        "team": by_qb["posteam"].agg(lambda s: s.mode().iat[0]),
        "dropbacks": by_qb.size(),
        "pressure_rate": by_qb["was_pressure"].mean(),
    })
    for label, flag in [("clean", False), ("pressured", True)]:
        subset = dropbacks[dropbacks["was_pressure"] == flag].groupby("id")
        splits[f"{label}_dropbacks"] = subset.size()
        splits[f"{label}_epa"] = subset["qb_epa"].mean()
        splits[f"{label}_sack_rate"] = subset["sack"].mean()
    splits["drop_off"] = splits["pressured_epa"] - splits["clean_epa"]

    splits = splits[splits["dropbacks"] >= min_dropbacks]
    splits.index.name = "player_id"
    return splits.sort_values("pressured_epa", ascending=False)


def plot_pressure_dumbbell(splits: pd.DataFrame, title: str, subtitle: str,
                           save_path: str | None = None):
    """Dumbbell of EPA/dropback: clean pocket (blue) vs. under pressure (orange).

    Rows are sorted by EPA under pressure, best at the top, with each QB's
    pressure rate in a column on the right.
    """
    apply_style()
    ranked = splits.sort_values("pressured_epa")
    n = len(ranked)
    fig, ax = plt.subplots(figsize=(10, 0.36 * n + 2.4))
    y = np.arange(n)

    ax.hlines(y, ranked["pressured_epa"], ranked["clean_epa"], color=TEXT_MUTED,
              linewidth=2, zorder=2)
    ax.scatter(ranked["clean_epa"], y, s=70, color=SERIES_1, edgecolor=SURFACE,
               linewidth=2, zorder=3, label="Clean pocket")
    ax.scatter(ranked["pressured_epa"], y, s=70, color=SERIES_2, edgecolor=SURFACE,
               linewidth=2, zorder=3, label="Under pressure")
    ax.axvline(0, color=TEXT_SECONDARY, linewidth=1, zorder=1)

    # Direct-label the two series once, above the top row.
    top = n - 1
    for col, text, color in [("clean_epa", "Clean pocket", SERIES_1),
                             ("pressured_epa", "Under pressure", SERIES_2)]:
        ax.annotate(text, (ranked[col].iat[-1], top), xytext=(0, 11),
                    textcoords="offset points", ha="center", va="bottom",
                    fontsize=8.5, color=TEXT_SECONDARY)

    # Logo beside the axis, name to its left; "(TEAM)" only if the logo is missing.
    logo_size = 0.24
    labels = [nm if team_logo(t) is not None else f"{nm} ({t})"
              for nm, t in zip(ranked["name"], ranked["team"])]
    for yi, team in zip(y, ranked["team"]):
        axis_logo(ax, team, yi, offset=4 + logo_size * 36, size=logo_size)
    ax.set_yticks(y, labels)
    ax.tick_params(axis="y", length=0, labelsize=9, labelcolor=TEXT_PRIMARY,
                   pad=logo_size * 72 + 8)
    ax.grid(axis="y", visible=False)
    ax.set_ylim(-0.7, n - 0.1)

    # Pressure-rate column just right of the plot.
    blended = ax.get_yaxis_transform()
    ax.text(1.02, n - 0.2, "Pressured", transform=blended, ha="left", va="bottom",
            fontsize=8.5, color=TEXT_SECONDARY)
    for yi, rate in zip(y, ranked["pressure_rate"]):
        ax.text(1.02, yi, f"{rate:.0%}", transform=blended, ha="left", va="center",
                fontsize=8.5, color=TEXT_SECONDARY)

    ax.set_xlabel("EPA per dropback")
    ax.set_title(title, pad=28)
    add_subtitle(ax, subtitle)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.07), ncol=2, frameon=False,
              fontsize=9.5, labelcolor=TEXT_SECONDARY)
    add_footnote(fig, "Pressure from nflverse participation data; sacks count as pressured.  "
                      "Sorted by EPA under pressure.  Data: nflverse via nflreadpy")
    fig.tight_layout(rect=(0, 0.03, 0.93, 1))

    if save_path:
        fig.savefig(save_path, dpi=150)
    return fig, ax
