"""Team logos as chart markers.

Logos are downloaded from ESPN's CDN (URLs from nflverse's team table) on
first use and cached in `.cache/logos/`, which is git-ignored, so the repo
doesn't redistribute them.
"""

import urllib.request
from functools import lru_cache
from pathlib import Path

import nflreadpy as nfl
import numpy as np
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
from PIL import Image

CACHE = Path(__file__).resolve().parents[2] / ".cache" / "logos"
PIXELS = 120  # stored size; plenty for a ~0.35 inch marker at 150 dpi


@lru_cache(maxsize=1)
def _logo_urls() -> dict[str, str]:
    teams = nfl.load_teams().to_pandas()
    return dict(zip(teams["team_abbr"], teams["team_logo_espn"]))


@lru_cache(maxsize=None)
def team_logo(team: str) -> np.ndarray | None:
    """RGBA image array for a team, or None if it can't be fetched."""
    path = CACHE / f"{team}.png"
    if not path.exists():
        url = _logo_urls().get(team)
        if url is None:
            return None
        try:
            CACHE.mkdir(parents=True, exist_ok=True)
            with urllib.request.urlopen(url, timeout=20) as response:
                path.write_bytes(response.read())
        except OSError:
            return None
    image = Image.open(path).convert("RGBA")
    image.thumbnail((PIXELS, PIXELS), Image.LANCZOS)
    return np.asarray(image)


def plot_logos(ax, x, y, teams, size: float = 0.42) -> list:
    """Draw each team's logo at (x, y). `size` is the logo's longest side in inches.

    Returns, per point, the logo artist, or None where no logo was available
    so callers can fall back to a dot and text label.
    """
    boxes = []
    for xi, yi, team in zip(x, y, teams):
        logo = team_logo(team)
        if logo is None:
            boxes.append(None)
            continue
        # OffsetImage zoom is in points per pixel (72 points per inch).
        zoom = size * 72 / max(logo.shape[:2])
        box = AnnotationBbox(OffsetImage(logo, zoom=zoom), (xi, yi), frameon=False,
                             pad=0, zorder=3)
        ax.add_artist(box)
        boxes.append(box)
    # AnnotationBbox doesn't update data limits; an invisible scatter does.
    ax.scatter(x, y, s=0)
    return boxes


def spread_logos(ax, boxes: list, color: str = "#8a8a8a", fill: float = 0.9,
                 gap: float = 4, iterations: int = 300) -> None:
    """Nudge overlapping logos apart, with a leader line back to each true point.

    Call after the final layout (tight_layout) so data-to-screen scale is fixed.
    Overlap is judged on each logo's bounding box scaled by `fill`, since logos
    have some transparent padding; moved logos keep `gap` points apart. Logos that
    don't overlap stay put.
    """
    drawn = [box for box in boxes if box is not None]
    if len(drawn) < 2:
        return
    # Freeze limits: the offsets below are computed against the current scale.
    ax.set_xlim(ax.get_xlim())
    ax.set_ylim(ax.get_ylim())
    to_points = 72 / ax.figure.dpi
    origin = np.array([ax.transData.transform(box.xy) for box in drawn]) * to_points
    sizes = np.array([np.array(box.offsetbox.get_data().shape[1::-1]) * box.offsetbox.get_zoom()
                      for box in drawn]) * fill
    pos = origin.copy()
    for _ in range(iterations):
        moved = False
        for i in range(len(pos)):
            for j in range(i + 1, len(pos)):
                delta = pos[j] - pos[i]
                overlap = (sizes[i] + sizes[j]) / 2 + gap - np.abs(delta)
                if (overlap <= 0).any():
                    continue
                # Separate along the axis that needs the smaller push.
                axis = int(np.argmin(overlap))
                sign = np.sign(delta[axis]) or (1 if i % 2 else -1)
                step = np.zeros(2)
                step[axis] = sign * overlap[axis] / 2
                pos[i] -= step
                pos[j] += step
                moved = True
        if not moved:
            break

    for box, start, end in zip(drawn, origin, pos):
        offset = end - start
        if np.hypot(*offset) < 1:
            continue
        box.remove()
        ax.add_artist(AnnotationBbox(
            box.offsetbox, box.xy, xybox=tuple(offset), boxcoords="offset points",
            frameon=False, pad=0, zorder=3,
            arrowprops=dict(arrowstyle="-", color=color, lw=0.7, shrinkA=0, shrinkB=0)))
        ax.scatter([box.xy[0]], [box.xy[1]], s=8, color=color, zorder=2)


def plot_team_points(ax, x, y, teams, size: float = 0.42, color: str = "#2a78d6",
                     label_color: str = "#0b0b0b") -> list:
    """Team logos as markers; any team without a logo gets a dot and a label.

    Returns the fallback text labels (for label-collision adjustment) and the
    per-point logo artists (for `spread_logos`).
    """
    boxes = plot_logos(ax, x, y, teams, size=size)
    labels = []
    for xi, yi, team, box in zip(x, y, teams, boxes):
        if box is None:
            ax.scatter([xi], [yi], s=70, color=color, edgecolor="white", linewidth=2, zorder=3)
            labels.append(ax.text(xi, yi, team, fontsize=9, fontweight="bold", color=label_color))
    return labels, boxes


def axis_logo(ax, team: str, y: float, offset: float, size: float = 0.26):
    """Draw a team logo in the y-axis label area, `offset` points left of the axis.

    Positioned in (axes fraction, data) coordinates, so it lines up with a bar
    or row at data value `y`. Returns the artist, or None if no logo exists.
    """
    logo = team_logo(team)
    if logo is None:
        return None
    zoom = size * 72 / max(logo.shape[:2])
    box = AnnotationBbox(OffsetImage(logo, zoom=zoom), (0, y),
                         xycoords=("axes fraction", "data"), xybox=(-offset, 0),
                         boxcoords="offset points", frameon=False, pad=0,
                         annotation_clip=False)
    ax.add_artist(box)
    return box
