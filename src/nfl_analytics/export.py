"""Fixed-name copies of the output tables, for BI tools such as Power BI.

The regular outputs are named by season (and week, for matchups), so their URLs
change over time. These copies live at ``output/latest/<name>.csv`` and are
overwritten on every run, so a dashboard pointed at the raw GitHub URL keeps
working and picks up the new week on refresh. Each copy starts with ``season``,
``week`` and ``data_through_week`` columns, and any index (usually ``team``)
is written as a regular column.
"""

from pathlib import Path

import pandas as pd


def write_latest(df: pd.DataFrame, name: str, output_dir: Path, *, season: int, week: int,
                 data_through_week: int, decimals: int = 3) -> Path:
    """Write ``df`` to ``output_dir/latest/<name>.csv`` with season/week columns in front.

    ``week`` is the week the table describes: the latest completed week for
    season-to-date tables, or the previewed week for matchups. ``data_through_week``
    is the last week of play-by-play the numbers use.
    """
    table = df.round(decimals)
    if table.index.name is not None:
        table = table.reset_index()
    table.insert(0, "season", season)
    table.insert(1, "week", week)
    table.insert(2, "data_through_week", data_through_week)

    latest = Path(output_dir) / "latest"
    latest.mkdir(parents=True, exist_ok=True)
    path = latest / f"{name}.csv"
    table.to_csv(path, index=False)
    return path
