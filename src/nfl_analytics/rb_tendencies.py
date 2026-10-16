"""Does the running back on the field tip off a pass or a run?

For each team's top two backs (by snaps), compare plays where only RB1 was on
the field with plays where only RB2 was. Raw pass rates are confounded by
situation (backups often play 3rd downs and the 2-minute drill), so the key
measure is pass rate over expected (PROE): actual pass rate minus nflverse's
`xpass`, the expected pass probability given down, distance, field position,
score and time.
"""

import matplotlib.pyplot as plt
import nflreadpy as nfl
import numpy as np
import pandas as pd

from .logos import axis_logo, team_logo
from .style import (SERIES_1, SERIES_2, SURFACE, TEXT_MUTED, TEXT_PRIMARY,
                    TEXT_SECONDARY, add_footnote, add_subtitle, apply_style)


def load_participation(seasons: int | list[int]) -> pd.DataFrame:
    """Per-play lists of the offensive players on the field."""
    cols = ["nflverse_game_id", "play_id", "offense_players", "offense_positions",
            "offense_names"]
    return nfl.load_participation(seasons).select(cols).to_pandas()


def rb_on_field(plays: pd.DataFrame, participation: pd.DataFrame) -> pd.DataFrame:
    """One row per (play, running back on the field). Fullbacks are excluded."""
    merged = plays[["game_id", "play_id", "posteam"]].merge(
        participation, left_on=["game_id", "play_id"],
        right_on=["nflverse_game_id", "play_id"])
    merged = merged.dropna(subset=["offense_players"])

    for col in ["offense_players", "offense_positions", "offense_names"]:
        merged[col] = merged[col].str.split(";")
    # Skip the rare rows where the three lists disagree in length.
    lengths = merged[["offense_players", "offense_positions", "offense_names"]].map(len)
    merged = merged[lengths.nunique(axis=1) == 1]

    players = merged.explode(["offense_players", "offense_positions", "offense_names"])
    rbs = players[players["offense_positions"] == "RB"]
    return rbs.rename(columns={"posteam": "team", "offense_players": "rb_id",
                               "offense_names": "rb_name"})[
        ["game_id", "play_id", "team", "rb_id", "rb_name"]]


def _short_name(full_name: str) -> str:
    """'Kenneth Walker III' -> 'K. Walker III'."""
    first, _, rest = full_name.partition(" ")
    return f"{first[0]}. {rest}" if rest else full_name


def rb_pass_tendencies(plays: pd.DataFrame, participation: pd.DataFrame,
                       min_plays: int = 150) -> pd.DataFrame:
    """Pass rate, expected pass rate and PROE with each team's RB1 vs. RB2 alone.

    Teams qualify as two-back committees when both backs were the only RB on the
    field for at least `min_plays` plays. Returns one row per qualifying team,
    sorted by how much more the offense passes with RB2 than with RB1.
    """
    plays = plays[plays["xpass"].notna()]
    rbs = rb_on_field(plays, participation)

    snaps = rbs.groupby(["team", "rb_id"]).agg(snaps=("play_id", "size"),
                                               name=("rb_name", "first"))
    snaps = snaps.sort_values("snaps", ascending=False)
    top2 = snaps.groupby("team").head(2).reset_index()
    top2["rank"] = top2.groupby("team")["snaps"].rank(method="first", ascending=False)

    on_field = rbs.merge(top2[["team", "rb_id", "rank"]], on=["team", "rb_id"])
    flags = (on_field.pivot_table(index=["game_id", "play_id"], columns="rank",
                                  values="rb_id", aggfunc="size")
             .reindex(columns=[1.0, 2.0]).notna())
    flags.columns = ["rb1_on", "rb2_on"]

    keyed = plays.set_index(["game_id", "play_id"]).join(flags, how="inner")
    keyed["residual"] = keyed["pass"] - keyed["xpass"]
    keyed["lineup"] = np.select(
        [keyed["rb1_on"] & ~keyed["rb2_on"], keyed["rb2_on"] & ~keyed["rb1_on"],
         keyed["rb1_on"] & keyed["rb2_on"]],
        ["rb1", "rb2", "both"], default="other")

    stats = (keyed[keyed["lineup"].isin(["rb1", "rb2"])]
             .groupby(["posteam", "lineup"])
             .agg(plays=("pass", "size"), pass_rate=("pass", "mean"),
                  xpass=("xpass", "mean"), proe=("residual", "mean"),
                  proe_sd=("residual", "std"))
             .unstack("lineup"))
    stats.columns = [f"{lineup}_{stat}" for stat, lineup in stats.columns]
    stats.index.name = "team"

    names = top2.pivot(index="team", columns="rank", values="name")
    stats["rb1_name"] = names[1.0].map(_short_name)
    stats["rb2_name"] = names[2.0].map(_short_name)
    stats["both_plays"] = keyed[keyed["lineup"] == "both"].groupby("posteam").size()
    stats["both_plays"] = stats["both_plays"].fillna(0).astype(int)

    stats = stats[(stats["rb1_plays"] >= min_plays) & (stats["rb2_plays"] >= min_plays)].copy()

    # Gap in PROE (RB2 minus RB1) with a 95% interval from the residual spread.
    stats["proe_gap"] = stats["rb2_proe"] - stats["rb1_proe"]
    se = np.sqrt(stats["rb1_proe_sd"] ** 2 / stats["rb1_plays"]
                 + stats["rb2_proe_sd"] ** 2 / stats["rb2_plays"])
    stats["gap_low"] = stats["proe_gap"] - 1.96 * se
    stats["gap_high"] = stats["proe_gap"] + 1.96 * se
    stats["significant"] = (stats["gap_low"] > 0) | (stats["gap_high"] < 0)

    order = ["rb1_name", "rb2_name", "rb1_plays", "rb2_plays", "both_plays",
             "rb1_pass_rate", "rb2_pass_rate", "rb1_xpass", "rb2_xpass",
             "rb1_proe", "rb2_proe", "proe_gap", "gap_low", "gap_high", "significant"]
    return stats[order].sort_values("proe_gap", ascending=False)


def plot_rb_tendencies(stats: pd.DataFrame, title: str, subtitle: str,
                       save_path: str | None = None):
    """Dumbbell chart of PROE with RB1 alone (blue) vs. RB2 alone (orange)."""
    apply_style()
    ranked = stats.sort_values("proe_gap")
    fig, ax = plt.subplots(figsize=(11, max(5, 0.42 * len(ranked) + 2)))
    y = np.arange(len(ranked))
    rb1, rb2 = ranked["rb1_proe"] * 100, ranked["rb2_proe"] * 100

    ax.hlines(y, np.minimum(rb1, rb2), np.maximum(rb1, rb2), color=TEXT_MUTED,
              linewidth=2, zorder=2)
    ax.scatter(rb1, y, s=80, color=SERIES_1, edgecolor=SURFACE, linewidth=2,
               zorder=3, label="Lead back (RB1) on field alone")
    ax.scatter(rb2, y, s=80, color=SERIES_2, edgecolor=SURFACE, linewidth=2,
               zorder=3, label="Second back (RB2) on field alone")
    ax.axvline(0, color=TEXT_SECONDARY, linewidth=1, zorder=1)

    # Direct-label each back next to its dot, on the outer side of the pair.
    for yi, (_, row) in zip(y, ranked.iterrows()):
        for name, value, other in [(row["rb1_name"], row["rb1_proe"], row["rb2_proe"]),
                                   (row["rb2_name"], row["rb2_proe"], row["rb1_proe"])]:
            right = value >= other
            ax.text(value * 100 + (0.9 if right else -0.9), yi, name, va="center",
                    ha="left" if right else "right", fontsize=8.5, color=TEXT_SECONDARY)

    # Each row: gap value, then the team logo beside the axis. Teams without a
    # logo keep their abbreviation in the label.
    logo_size = 0.3
    gap_labels = []
    for yi, team, g, sig in zip(y, ranked.index, ranked["proe_gap"], ranked["significant"]):
        gap = f"{g * 100:+.1f}{' *' if sig else '  '}"
        gap_labels.append(gap if team_logo(team) is not None else f"{team}   {gap}")
        axis_logo(ax, team, yi, offset=4 + logo_size * 36, size=logo_size)
    ax.set_yticks(y, gap_labels)
    ax.tick_params(axis="y", length=0, labelsize=9.5, labelcolor=TEXT_PRIMARY,
                   pad=logo_size * 72 + 8)
    ax.grid(axis="y", visible=False)
    ax.set_ylim(-0.7, len(ranked) - 0.3)
    ax.margins(x=0.22)

    ax.set_xlabel("Pass rate over expected (percentage points)   ←  runs more  ·  passes more  →")
    ax.set_title(title, pad=28)
    add_subtitle(ax, subtitle)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.09), ncol=2, frameon=False,
              fontsize=9.5, labelcolor=TEXT_SECONDARY)
    add_footnote(fig, "Number beside each logo is the RB2 − RB1 gap in points; * = 95% interval excludes zero.  "
                      "Expected pass rate: nflverse xpass.  Data: nflverse via nflreadpy")
    fig.tight_layout(rect=(0, 0.03, 1, 1))

    if save_path:
        fig.savefig(save_path, dpi=150)
    return fig, ax
