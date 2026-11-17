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


def _label_qb_points(ax, qbs: pd.DataFrame, x: str, y: str, boxes: list,
                     captions: list) -> None:
    """Spread overlapping logos and place every QB's name around its marker.

    Call after the final layout (tight_layout), since both steps work in pixels.
    `boxes` are the logo artists from `plot_logos` (None for a QB drawn as a dot),
    `captions` any corner texts the names must avoid.
    """
    fig = ax.figure
    # Pull apart logos that overlap (leader dot back to the true point).
    boxes = spread_logos(ax, boxes, color=TEXT_MUTED)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    dot = 9  # pixels: stand-in extent for a QB drawn as a dot (no logo)
    anchors = []
    for box, xi, yi in zip(boxes, qbs[x], qbs[y]):
        if box is not None:
            anchors.append(box.get_window_extent(renderer))
        else:
            px, py = ax.transData.transform((xi, yi))
            anchors.append(Bbox.from_extents(px - dot, py - dot, px + dot, py + dot))
    true_points = [Bbox.from_extents(px - 3, py - 3, px + 3, py + 3)
                   for px, py in ax.transData.transform(qbs[[x, y]].values)]
    obstacles = anchors + true_points + [c.get_window_extent(renderer) for c in captions]
    _place_labels(ax, list(qbs["name"]), anchors, obstacles)


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

    _label_qb_points(ax, qbs, "cpoe", "epa_per_db", boxes, captions)

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


# 3rd-down distance buckets for expected conversion: (label, low, high) yards to go.
_DISTANCE_BUCKETS = [(1, 1), (2, 2), (3, 3), (4, 5), (6, 7), (8, 10), (11, 15), (16, 99)]


def third_down_conversion(plays: pd.DataFrame, qbs: pd.DataFrame) -> pd.DataFrame:
    """3rd-down conversion rate over expected for the QBs in `qbs` (from `qb_stats`).

    A conversion is a dropback where the QB's own pass or scramble gained the
    first down (touchdowns included); first downs by defensive penalty don't
    count. Expected conversion is the league rate on all 3rd-down dropbacks at
    the same distance, so a QB isn't punished for facing long 3rd downs.
    `se` is the binomial standard error of the over-expected rate.
    """
    third = plays[(plays["qb_dropback"] == 1) & (plays["down"] == 3) & plays["id"].notna()].copy()
    third["converted"] = ((third["first_down_pass"] == 1) | (third["first_down_rush"] == 1)).astype(float)
    edges = [low - 0.5 for low, _ in _DISTANCE_BUCKETS] + [np.inf]
    third["bucket"] = pd.cut(third["ydstogo"], edges, labels=False)
    third["expected"] = third.groupby("bucket")["converted"].transform("mean")

    third = third[third["id"].isin(qbs.index)]
    out = third.groupby("id").agg(
        third_down_dropbacks=("converted", "size"),
        conversion_rate=("converted", "mean"),
        expected_rate=("expected", "mean"),
        avg_ydstogo=("ydstogo", "mean"),
        variance=("expected", lambda e: (e * (1 - e)).sum()),
    )
    out["conversion_over_expected"] = out["conversion_rate"] - out["expected_rate"]
    out["se"] = np.sqrt(out.pop("variance")) / out["third_down_dropbacks"]
    out = qbs[["name", "team"]].join(out, how="inner")
    out.index.name = "player_id"
    return out.sort_values("conversion_over_expected", ascending=False)


def red_zone_split(plays: pd.DataFrame, qbs: pd.DataFrame) -> pd.DataFrame:
    """EPA per dropback inside the red zone vs. outside it, for the QBs in `qbs`.

    Each split is also given relative to the league average of all dropbacks in
    that zone (`*_vs_avg`), since red-zone EPA runs at a different level. The
    red-zone edge is how much more the QB beats average inside the 20 than
    outside it.
    """
    dropbacks = plays[(plays["qb_dropback"] == 1) & plays["id"].notna()].copy()
    dropbacks["zone"] = np.where(dropbacks["yardline_100"] <= 20, "rz", "field")
    league = dropbacks.groupby("zone")["qb_epa"].mean()

    mine = dropbacks[dropbacks["id"].isin(qbs.index)]
    agg = mine.groupby(["id", "zone"]).agg(dropbacks=("qb_epa", "size"),
                                           epa_per_db=("qb_epa", "mean"),
                                           tds=("pass_touchdown", "sum"),
                                           ints=("interception", "sum")).unstack("zone")
    out = pd.DataFrame({
        "rz_dropbacks": agg[("dropbacks", "rz")],
        "rz_epa_per_db": agg[("epa_per_db", "rz")],
        "rz_td_rate": agg[("tds", "rz")] / agg[("dropbacks", "rz")],
        "rz_ints": agg[("ints", "rz")],
        "field_dropbacks": agg[("dropbacks", "field")],
        "field_epa_per_db": agg[("epa_per_db", "field")],
    })
    out["rz_vs_avg"] = out["rz_epa_per_db"] - league["rz"]
    out["field_vs_avg"] = out["field_epa_per_db"] - league["field"]
    out["rz_edge"] = out["rz_vs_avg"] - out["field_vs_avg"]
    out = qbs[["name", "team"]].join(out, how="inner").dropna(subset=["rz_epa_per_db"])
    out.index.name = "player_id"
    return out.sort_values("rz_edge", ascending=False)


def plot_third_down_conversion(third: pd.DataFrame, title: str, subtitle: str,
                               save_path: str | None = None):
    """Horizontal bars of 3rd-down conversion rate over expected, with ±1 SE whiskers."""
    apply_style()
    ranked = third.sort_values("conversion_over_expected")
    value = ranked["conversion_over_expected"] * 100
    se = ranked["se"] * 100
    fig, ax = plt.subplots(figsize=(9.5, max(5, 0.32 * len(ranked) + 1.8)))

    labels = [n if team_logo(t) is not None else f"{n} ({t})"
              for n, t in zip(ranked["name"], ranked["team"])]
    y = np.arange(len(ranked))
    ax.barh(y, value, height=0.7, color=ACCENT, zorder=3)
    ax.errorbar(value, y, xerr=se, fmt="none", ecolor=TEXT_MUTED, elinewidth=1, capsize=0,
                zorder=4)
    ax.set_yticks(y, labels)
    logo_size = 0.24
    for i, team in enumerate(ranked["team"]):
        axis_logo(ax, team, i, offset=4 + logo_size * 36, size=logo_size)
    ax.axvline(0, color=TEXT_SECONDARY, linewidth=1, zorder=5)

    # Value and raw rate past the end of the whisker, so the text never sits on it.
    pad = 0.6
    for i, (v, s, rate, n) in enumerate(zip(value, se, ranked["conversion_rate"],
                                            ranked["third_down_dropbacks"])):
        end = v + s + pad if v >= 0 else v - s - pad
        ax.text(end, i, f"{v:+.1f}  ({rate:.0%} of {n})", va="center",
                ha="left" if v >= 0 else "right", fontsize=7.5, color=TEXT_SECONDARY)

    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", length=0, labelsize=9, labelcolor=TEXT_PRIMARY,
                   pad=logo_size * 72 + 8)
    ax.set_ylim(-0.6, len(ranked) - 0.4)
    reach = (value.abs() + se).max()
    ax.set_xlim(-reach * 1.55, reach * 1.55)
    ax.set_xlabel("3rd-down conversion rate over expected (percentage points)")
    ax.set_title(title, pad=28)
    add_subtitle(ax, subtitle)
    add_footnote(fig, "Data: nflverse via nflreadpy  ·  Expected = league rate at the same "
                      "distance  ·  Whiskers = ±1 standard error  ·  In parentheses: "
                      "raw rate of 3rd-down dropbacks")
    fig.tight_layout(rect=(0, 0.025, 1, 1))

    if save_path:
        fig.savefig(save_path, dpi=150)
    return fig, ax


def plot_red_zone_vs_field(split: pd.DataFrame, title: str, subtitle: str,
                           save_path: str | None = None):
    """Scatter of EPA/dropback vs. league average outside (x) and inside (y) the red zone.

    The diagonal marks equal performance; QBs above it are relatively better
    in the red zone than between the 20s.
    """
    apply_style()
    fig, ax = plt.subplots(figsize=(12, 9.5))

    x, y = split["field_vs_avg"], split["rz_vs_avg"]
    boxes = plot_logos(ax, x, y, split["team"], size=0.34)
    missing = [box is None for box in boxes]
    ax.scatter(x[missing], y[missing], s=70, color=ACCENT, edgecolor=SURFACE, linewidth=2,
               zorder=3)
    ax.margins(x=0.10, y=0.10)
    ax.axvline(0, color=TEXT_MUTED, linestyle="--", linewidth=1, zorder=1)
    ax.axhline(0, color=TEXT_MUTED, linestyle="--", linewidth=1, zorder=1)
    # Freeze limits from the data before drawing the diagonal across them.
    xlim, ylim = ax.get_xlim(), ax.get_ylim()
    lo, hi = min(xlim[0], ylim[0]), max(xlim[1], ylim[1])
    ax.plot([lo, hi], [lo, hi], color=TEXT_SECONDARY, linewidth=1, zorder=1)
    ax.set_xlim(xlim)
    ax.set_ylim(ylim)

    corner = dict(transform=ax.transAxes, fontsize=10, color=TEXT_SECONDARY,
                  fontstyle="italic")
    captions = [
        ax.text(0.02, 0.98, "Better in the red zone than between the 20s", ha="left",
                va="top", **corner),
        ax.text(0.98, 0.02, "Moves the ball, stalls in the red zone", ha="right",
                va="bottom", **corner),
    ]

    ax.set_xlabel("EPA per dropback outside the red zone, vs. league average")
    ax.set_ylabel("EPA per dropback inside the 20, vs. league average")
    ax.set_title(title, pad=28)
    add_subtitle(ax, subtitle)
    add_footnote(fig, "Data: nflverse via nflreadpy  ·  Dashed lines = league average  ·  "
                      f"Diagonal = equal in both zones  ·  Red-zone dropbacks per QB: "
                      f"{int(split['rz_dropbacks'].min())}–{int(split['rz_dropbacks'].max())}")
    fig.tight_layout(rect=(0, 0.03, 1, 1))

    _label_qb_points(ax, split, "field_vs_avg", "rz_vs_avg", boxes, captions)

    if save_path:
        fig.savefig(save_path, dpi=150)
    return fig, ax
