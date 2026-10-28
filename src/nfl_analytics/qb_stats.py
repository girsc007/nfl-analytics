"""Quarterback efficiency: EPA per dropback, CPOE, success rate and more."""

import matplotlib.pyplot as plt
from matplotlib import patheffects
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
    fig, ax = plt.subplots(figsize=(12, 9.5))

    boxes = plot_logos(ax, qbs["cpoe"], qbs["epa_per_db"], qbs["team"], size=0.34)
    missing = [box is None for box in boxes]
    ax.scatter(qbs["cpoe"][missing], qbs["epa_per_db"][missing], s=70, color=ACCENT,
               edgecolor=SURFACE, linewidth=2, zorder=3)
    # Room around the extremes so corner QBs' logos and names stay inside the axes.
    ax.margins(x=0.08, y=0.10)
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
