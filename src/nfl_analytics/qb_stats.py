"""Quarterback efficiency: EPA per dropback, CPOE, success rate and more."""

import matplotlib.pyplot as plt
from matplotlib import patheffects
import numpy as np
import pandas as pd
from matplotlib.transforms import Bbox

from .logos import axis_logo, plot_logos, spread_logos, team_logo
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


def _place_labels(ax, names, anchors, obstacles, gap: float = 3,
                  pad: tuple[float, float] = (8, 2), fill: float = 0.85) -> None:
    """Put each name next to its marker without covering any marker or other name.

    `anchors` are the markers' window extents (in the same order as `names`) and
    `obstacles` any other extents to keep clear (markers, corner captions). Each
    name tries the spots around its own marker in a fixed order (below, above,
    right, left, then the diagonals), then the same ring two and three times as
    far out with a leader line, and takes the first spot that is inside the axes
    and clear of everything placed so far. A spot without a leader line must also
    be clearly closer to its own marker than to any other, so the name can't be
    misread as a neighbor's. If no spot is clear, the least-covered one wins. `pad`
    is the (x, y) clearance in pixels kept around each name. For the closeness
    test, other markers count at `fill` of their size, since logos have some
    transparent padding. Deterministic: the same data gives the same chart.
    Crowded markers pick first, since they have the fewest free spots.
    """
    fig = ax.figure
    renderer = fig.canvas.get_renderer()
    to_data = ax.transData.inverted()
    frame = ax.get_window_extent()
    stroke = [patheffects.withStroke(linewidth=2.5, foreground=SURFACE)]

    def overlap_area(a, b):
        return max(min(a[2], b[2]) - max(a[0], b[0]), 0) * max(min(a[3], b[3]) - max(a[1], b[1]), 0)

    def distance(a, b):  # gap between two boxes, 0 if they touch
        return np.hypot(max(b[0] - a[2], a[0] - b[2], 0), max(b[1] - a[3], a[1] - b[3], 0))

    def leader_segment(cx, cy, hw, hh, x, y, w, h):
        """From the marker's edge toward the label, ending at the label's near edge."""
        ux, uy = x - cx, y - cy
        scale = min(hw / abs(ux) if ux else np.inf, hh / abs(uy) if uy else np.inf)
        end_x = x - np.sign(ux) * w / 2 if abs(ux) > w / 2 else x
        end_y = y - np.sign(uy) * h / 2 if abs(uy) > h / 2 else y
        return [(cx + ux * scale, cy + uy * scale), (end_x, end_y)]

    def crosses(segment, b, samples: int = 24):
        (x0, y0), (x1, y1) = segment
        return any(b[0] <= x0 + (x1 - x0) * s <= b[2] and b[1] <= y0 + (y1 - y0) * s <= b[3]
                   for s in np.linspace(0, 1, samples))

    marker_boxes = [tuple(a.extents) for a in anchors]
    core_boxes = [tuple(a.shrunk(fill, fill).anchored("C", a).extents) for a in anchors]

    taken = [tuple(o.extents) for o in obstacles]
    label_boxes = []
    centers = [((a.x0 + a.x1) / 2, (a.y0 + a.y1) / 2) for a in anchors]
    crowding = [sum(abs(cx - ox) < 90 and abs(cy - oy) < 60 for ox, oy in centers)
                for cx, cy in centers]
    order = sorted(range(len(names)), key=lambda i: (-crowding[i], i))

    for i in order:
        text = ax.text(0, 0, names[i], fontsize=8.5, color=TEXT_PRIMARY, ha="center",
                       va="center", zorder=5, path_effects=stroke)
        bb = text.get_window_extent(renderer)
        w, h = bb.width + 2 * pad[0], bb.height + 2 * pad[1]
        a = anchors[i]
        cx, cy = centers[i]
        hw, hh = a.width / 2, a.height / 2
        dx, dy = hw + gap + w / 2, hh + gap + h / 2
        ring = [(0, -dy), (0, dy), (dx, 0), (-dx, 0),
                (dx, -dy), (-dx, -dy), (dx, dy), (-dx, dy)]
        candidates = [(ox * k, oy * k, k > 1) for k in (1, 2, 3) for ox, oy in ring]
        chosen, fallback = None, None
        for ox, oy, leader in candidates:
            x, y = cx + ox, cy + oy
            box = (x - w / 2, y - h / 2, x + w / 2, y + h / 2)
            if not (box[0] >= frame.x0 and box[2] <= frame.x1
                    and box[1] >= frame.y0 and box[3] <= frame.y1):
                continue
            clash = sum(overlap_area(box, o) for o in taken)
            if leader:
                # The line must not run through another marker or name, or it
                # would point at the wrong QB.
                segment = leader_segment(cx, cy, hw, hh, x, y, w, h)
                ok = not any(crosses(segment, b) for j, b in enumerate(core_boxes) if j != i)
                ok = ok and not any(crosses(segment, b) for b in label_boxes)
            else:
                own = distance(box, marker_boxes[i])
                nearest_other = min((distance(box, m) for j, m in enumerate(core_boxes)
                                     if j != i), default=np.inf)
                ok = own + 4 < nearest_other
            if clash == 0 and ok:
                chosen = (x, y, box, leader)
                break
            if fallback is None or clash < fallback[0]:
                fallback = (clash, (x, y, box, leader))
        if chosen is None:  # nowhere is fully clear: take the least-covered spot
            chosen = fallback[1]
        x, y, box, leader = chosen
        text.set_position(to_data.transform((x, y)))
        taken.append(box)
        label_boxes.append(box)
        if leader:
            line = to_data.transform(leader_segment(cx, cy, hw, hh, x, y, w, h))
            ax.plot(line[:, 0], line[:, 1], color=TEXT_MUTED, lw=0.5, zorder=4)


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

    corner = dict(transform=ax.transAxes, fontsize=10, color=TEXT_SECONDARY,
                  fontstyle="italic")
    captions = [
        ax.text(0.02, 0.98, "Productive despite lower accuracy", ha="left", va="top", **corner),
        ax.text(0.98, 0.02, "Accurate but less productive", ha="right", va="bottom", **corner),
    ]

    ax.set_xlabel("CPOE: completion % over expected  →  more accurate")
    ax.set_ylabel("EPA per dropback  →  more productive")
    ax.set_title(title, pad=28)
    add_subtitle(ax, subtitle)
    add_footnote(fig, "Data: nflverse via nflreadpy  ·  Dashed lines = average of qualified QBs")
    fig.tight_layout(rect=(0, 0.03, 1, 1))

    # With the layout final, pull apart logos that overlap (leader dot back to the
    # true point), then place every name around its logo.
    boxes = spread_logos(ax, boxes, color=TEXT_MUTED)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    dot = 9  # pixels: stand-in extent for a QB drawn as a dot (no logo)
    anchors = []
    for box, x, y in zip(boxes, qbs["cpoe"], qbs["epa_per_db"]):
        if box is not None:
            anchors.append(box.get_window_extent(renderer))
        else:
            px, py = ax.transData.transform((x, y))
            anchors.append(Bbox.from_extents(px - dot, py - dot, px + dot, py + dot))
    true_points = [Bbox.from_extents(px - 3, py - 3, px + 3, py + 3)
                   for px, py in ax.transData.transform(qbs[["cpoe", "epa_per_db"]].values)]
    obstacles = anchors + true_points + [c.get_window_extent(renderer) for c in captions]
    _place_labels(ax, list(qbs["name"]), anchors, obstacles)

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
