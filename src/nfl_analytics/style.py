"""Shared matplotlib styling so every chart looks like part of one set."""

import matplotlib.pyplot as plt

SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
TEXT_MUTED = "#8a8984"
GRID = "#e4e3df"
ACCENT = "#2a78d6"  # blue: the single series color
ACCENT_DARK = "#1c5cab"


def apply_style() -> None:
    plt.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "axes.edgecolor": GRID,
        "axes.labelcolor": TEXT_SECONDARY,
        "axes.titlecolor": TEXT_PRIMARY,
        "axes.titlesize": 15,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.labelsize": 11,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "xtick.color": TEXT_MUTED,
        "ytick.color": TEXT_MUTED,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "text.color": TEXT_PRIMARY,
        "font.family": "DejaVu Sans",
    })


def add_subtitle(ax, text: str, y: float = 1.015) -> None:
    """Place a muted subtitle line just under the axes title."""
    ax.text(0, y, text, transform=ax.transAxes, fontsize=10,
            color=TEXT_SECONDARY, va="bottom")


def add_footnote(fig, text: str) -> None:
    fig.text(0.01, 0.01, text, fontsize=8, color=TEXT_MUTED, ha="left", va="bottom")

# Two-series categorical pair (validated for color-vision deficiency).
SERIES_1 = "#2a78d6"  # blue
SERIES_2 = "#eb6834"  # orange
DIVERGING_MID = "#f0efec"  # neutral gray midpoint for diverging scales
