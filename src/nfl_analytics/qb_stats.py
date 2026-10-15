"""Quarterback efficiency: EPA per dropback, CPOE, success rate and more."""

import matplotlib.pyplot as plt
import pandas as pd
from adjustText import adjust_text

from .style import (ACCENT, SURFACE, TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY,
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

    ax.scatter(qbs["cpoe"], qbs["epa_per_db"], s=70, color=ACCENT,
               edgecolor=SURFACE, linewidth=2, zorder=3)
    ax.axvline(qbs["cpoe"].mean(), color=TEXT_MUTED, linestyle="--", linewidth=1, zorder=1)
    ax.axhline(qbs["epa_per_db"].mean(), color=TEXT_MUTED, linestyle="--", linewidth=1, zorder=1)

    labels = [ax.text(x, y, name, fontsize=9, color=TEXT_PRIMARY)
              for name, x, y in zip(qbs["name"], qbs["cpoe"], qbs["epa_per_db"])]
    adjust_text(labels, x=qbs["cpoe"].values, y=qbs["epa_per_db"].values, ax=ax,
                expand=(1.3, 1.5), arrowprops=dict(arrowstyle="-", color=TEXT_MUTED, lw=0.5))

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

    labels = [f"{n} ({t})" for n, t in zip(ranked["name"], ranked["team"])]
    ax.barh(labels, ranked["epa_per_db"], height=0.7, color=ACCENT, zorder=3)
    ax.axvline(0, color=TEXT_SECONDARY, linewidth=1, zorder=4)

    pad = 0.005
    for i, value in enumerate(ranked["epa_per_db"]):
        ax.text(value + (pad if value >= 0 else -pad), i, f"{value:+.2f}",
                va="center", ha="left" if value >= 0 else "right",
                fontsize=8, color=TEXT_SECONDARY)

    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", length=0, labelsize=9, labelcolor=TEXT_PRIMARY)
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
