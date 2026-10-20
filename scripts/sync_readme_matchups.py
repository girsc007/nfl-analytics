"""Point the README at the latest weekly matchup chart and drop the superseded one.

Run after scripts/matchups.py. Scans figures/ for matchups_<season>_wk<week>.png,
keeps only the most recent (season, week), deletes the rest (and their output/ CSVs),
and rewrites the README image line to match.

Usage:
    python scripts/sync_readme_matchups.py
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAG_RE = re.compile(r"matchups_(\d+)_wk(\d+)\.png$")
README_RE = re.compile(
    r"!\[\d+ week \d+ matchups\]\(figures/matchups_\d+_wk\d+\.png\)"
)


def main() -> None:
    figures, output = ROOT / "figures", ROOT / "output"
    charts = {}
    for path in figures.glob("matchups_*.png"):
        match = TAG_RE.search(path.name)
        if match:
            charts[(int(match.group(1)), int(match.group(2)))] = path

    if not charts:
        sys.exit("No figures/matchups_*.png found; run scripts/matchups.py first.")

    latest = max(charts)
    season, week = latest
    tag = f"{season}_wk{week:02d}"
    print(f"Latest matchup chart: {tag}")

    for (s, w), path in charts.items():
        if (s, w) == latest:
            continue
        path.unlink()
        for stale in (output / f"matchups_{s}_wk{w:02d}.csv",
                      output / f"unit_ratings_{s}_wk{w:02d}.csv"):
            stale.unlink(missing_ok=True)
        print(f"Removed superseded {s}_wk{w:02d} outputs")

    readme = ROOT / "README.md"
    text = readme.read_text()
    new_line = f"![{season} week {week} matchups](figures/matchups_{tag}.png)"
    updated, count = README_RE.subn(new_line, text)
    if count == 0:
        sys.exit("Could not find the matchups image line in README.md to update.")
    readme.write_text(updated)
    print(f"README updated to reference {tag}")


if __name__ == "__main__":
    main()
