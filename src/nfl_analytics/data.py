"""Loading and filtering nflverse play-by-play data."""

import nflreadpy as nfl
import pandas as pd


def load_pbp(seasons: int | list[int]) -> pd.DataFrame:
    """Load play-by-play data for one or more seasons as a pandas DataFrame.

    nflreadpy caches downloads, so repeat calls are fast.
    """
    return nfl.load_pbp(seasons).to_pandas()


def offensive_plays(
    pbp: pd.DataFrame,
    regular_season_only: bool = True,
    wp_range: tuple[float, float] | None = (0.10, 0.90),
) -> pd.DataFrame:
    """Return real pass and run plays that have an EPA value.

    wp_range drops "garbage time" (plays where the offense's win probability is
    outside the range), since teams play differently when the game is decided.
    Pass None to keep every play.
    """
    plays = pbp[((pbp["pass"] == 1) | (pbp["rush"] == 1)) & pbp["epa"].notna()]
    if regular_season_only:
        plays = plays[plays["season_type"] == "REG"]
    if wp_range is not None:
        low, high = wp_range
        plays = plays[plays["wp"].between(low, high)]
    return plays
