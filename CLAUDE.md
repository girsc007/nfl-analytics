# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

NFL team and QB analytics in Python on nflverse play-by-play data (loaded with `nflreadpy`). Output is
static PNG charts, CSV tables, executed notebooks and a README that presents the findings. Published at
https://github.com/girsc007/nfl-analytics.

## Commands

```bash
pip install -r requirements.txt

python scripts/make_charts.py                 # all season charts + CSVs (default season 2025)
python scripts/make_charts.py --season 2026   # current season to date
python scripts/make_charts.py --all-plays     # disable the garbage-time filter
python scripts/matchups.py                    # weekly mismatch preview (next unplayed week)
python scripts/matchups.py --season 2026 --week 8 --no-adjust --shrinkage 200 --prior-weight 0.25

# Re-execute notebooks in place after changing code they call (GitHub renders the saved output)
cd notebooks && jupyter nbconvert --to notebook --execute --inplace 01_team_efficiency.ipynb
```

There is no test suite or linter. Verify changes by running the script and opening the generated PNG.
If `python` isn't on PATH in the sandbox, try `bash -l -c "..."`.

## Architecture

- `src/nfl_analytics/` is the library. Scripts and notebooks don't install it; they add `src` to
  `sys.path` (`sys.path.insert(0, ...)`). New public functions must be exported from `__init__.py`.
- Every analysis pairs a **compute function returning a DataFrame** with a **`plot_*` function** that
  takes that DataFrame plus `title`, `subtitle` and optional `save_path`. `scripts/make_charts.py` calls
  each pair, writes `output/<name>_<season>.csv` and `figures/<name>_<season>.png`.
- `data.offensive_plays()` is the shared filter applied before nearly everything: pass or run plays with
  EPA, regular season, and offense win probability 10–90% (garbage time removed).
- nflverse conventions the code relies on: `pass == 1` includes scrambles and sacks, so "rush" means
  designed runs; QB stats use `qb_dropback`, the `id`/`name` columns (credit scrambles/sacks to the QB)
  and `qb_epa`; tendencies use `xpass` (expected pass probability) to get pass rate over expected.
- Participation data (`rb_tendencies.load_participation(season, columns)`) joins to play-by-play on
  `game_id`/`play_id` ↔ `nflverse_game_id`/`play_id`. It provides on-field players and `was_pressure`.
- `matchups.py`: unit ratings (pass/rush × offense/defense) come from a weighted **ridge regression**
  (EPA = league + offense + defense), which both adjusts for opponents and shrinks small samples. The
  default shrinkage of 200 was chosen by backtesting 2025; ratings use only games before the target week.

## Chart conventions

- Call `style.apply_style()` first; use the color/text constants in `style.py` (`SERIES_1` blue = pass /
  first series, `SERIES_2` orange = rush / second series, `DIVERGING_MID` gray midpoint). Text uses the
  text tokens, never series colors.
- Team identity is shown with logos via `logos.py`: `plot_team_points` / `plot_logos` for scatter
  markers, `axis_logo` beside y-axis rows. Logos download from ESPN once into the git-ignored
  `.cache/logos/`; every caller must fall back to text when `team_logo()` returns `None`.
- Logos are `AnnotationBbox` artists and don't update data limits. Draw them (they add an invisible
  scatter) **before** reading or setting axis limits.
- Always render and look at the PNG after a chart change: label collisions, clipped subtitles/footnotes
  and logos covering labels are the usual problems.

## Workflow notes

- When README findings quote numbers, recompute them from the CSV after regenerating; don't carry old
  numbers forward.
- Commit regenerated `figures/`, `output/` and re-executed notebooks together with the code change.
  The QB scatter's label placement is randomized, so its PNG changes on every run.
- Git identity is set repo-locally (`tategirsch`) because the sandbox can't see the Windows global
  gitconfig.
