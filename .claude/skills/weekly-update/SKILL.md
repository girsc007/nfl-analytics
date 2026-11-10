---
name: weekly-update
description: Runbook for the week-to-week season update - regenerate the season charts, CSVs and notebooks with the latest completed week, refresh every number the README quotes, check the weekly matchup preview, and commit. Use when the user asks to update the graphs/charts/README "with week N", "with the new data", "for this week", or similar.
---

# Weekly season update

Follow these steps in order. Each step says what "done" looks like; don't move on until it is.
The update covers the **season charts** (`make_charts.py`). The **matchup preview** is normally
published by CI every Tuesday (step 7); only regenerate it when the user asks or CI missed a week.

Throughout, `N` is the latest completed week and `SEASON` is the current season (default 2026).

## 1. Sync with GitHub first

```bash
git status --short          # must be clean; if not, ask the user what to do with local changes
git pull --ff-only origin main
```

The `Weekly matchup update` GitHub Action (`.github/workflows/weekly-matchups.yml`, Tuesdays 13:00 UTC)
pushes matchup charts and a README line to `main`. Pulling first avoids a conflict when you commit.

## 2. Get a working Python

The sandbox may not have the dependencies. Use the first option that works and reuse it for every
command below as `$PY`:

```bash
python -c "import nflreadpy" 2>/dev/null && PY=python
# otherwise: a venv outside the repo (system pip is "externally managed")
python3 -m venv ~/.venvs/nfl-analytics
~/.venvs/nfl-analytics/bin/pip install -q -r requirements.txt nbconvert ipykernel
PY=~/.venvs/nfl-analytics/bin/python     # jupyter is ~/.venvs/nfl-analytics/bin/jupyter
```

Don't install with `--break-system-packages`, and don't create a venv inside the repo.

## 3. Regenerate the season charts and tables

```bash
$PY scripts/make_charts.py --season SEASON
```

It prints `Data runs through week N (G games in week N)`. **Check that the data is complete before going on:**

- If N isn't the week the user expects, nflverse hasn't published it yet. Stop and tell the user. Don't
  update anything for a partial week.
- Compare G with the number of games scheduled that week (bye weeks mean fewer than 16):

  ```bash
  $PY -c "import nflreadpy as nfl; s=nfl.load_schedules(SEASON).to_pandas(); w=s[(s.game_type=='REG')&(s.week==N)]; print(len(w), 'scheduled,', w.result.notna().sum(), 'final')"
  ```

  A missing game (usually Monday night, or a Tuesday makeup game) means nflverse is still processing it.
  Tell the user and ask whether to wait or go ahead.

Outputs: 6 PNGs in `figures/*_SEASON.png`, 5 CSVs in `output/*_SEASON.csv`, and the same 5 tables under
fixed names in `output/latest/` (with `season`/`week`/`data_through_week` columns, for Power BI). Check that
`week` in `output/latest/team_epa.csv` is N.

## 4. Look at every chart

Open each PNG with Read: `team_efficiency`, `team_pass_vs_rush`, `run_direction`, `pass_tendency_by_down`,
`qb_epa_vs_cpoe`, `qb_epa_ranking`. For each one, check:

- The subtitle says `through week N`. The QB charts also say `min. 15×N dropbacks`.
- No clipped title, subtitle, footnote or axis label, and no logo or point cut off at the plot edge.
- Logos don't cover each other or the quadrant labels. The team efficiency chart nudges overlapping logos
  apart and draws a small leader dot back to the true position, so those dots are expected.
- QB scatter: names are readable and sit next to the right logo. Label placement is random, so if the
  labels collide badly, re-run step 3 once. If they still collide, report it rather than looping.
- Pass-tendency and run-direction tables: 32 teams plus the NFL avg row, and the color bar is intact.
  On run direction, the share labels fit inside their bar segments and the lane headers line up.

Fix real layout bugs in `src/nfl_analytics/` only if the user asks. Otherwise list them in the report (step 9).

## 5. Re-execute the notebooks

```bash
cd notebooks
JUPYTER="$(dirname "$PY")/jupyter"
$JUPYTER nbconvert --to notebook --execute --inplace 01_team_efficiency.ipynb
$JUPYTER nbconvert --to notebook --execute --inplace 02_qb_stats.ipynb
cd ..
```

Both must finish without an error cell. GitHub renders the saved outputs.

## 6. Refresh the README numbers

```bash
$PY scripts/readme_stats.py --season SEASON
```

This prints every figure the README quotes, in README order, recomputed from the new CSVs. Never carry a
number over from the old README. Update:

1. **Section headers:** all five `(SEASON season, through week N-1)` become `through week N`.
2. **Team efficiency bullets:**
   - The top 3 by net EPA.
   - The best defenses that come with a below-average offense (high `off_rank`).
   - The notable top-offense/bad-defense team (for example DAL, a top-4 offense with a bottom defense).
     Quote ranks exactly ("second-worst", not "worst").
3. **Passing vs. rushing bullets:**
   - The league EPA per dropback and per designed run, to 3 decimals with a real minus sign `−`.
   - The teams that ran better than they passed, the std. devs, and the best passing teams.
   - Both r values, and the pass-rate rank of the run-better-than-pass team quoted in the text.
   - The teams above average at both, ranked by pass + rush EPA (name the top 4).
4. **Run direction bullets:**
   - The league EPA per carry and share of carries for each lane.
   - The outside-share vs. run-EPA r and the teams with the highest outside share.
   - The best run games, each with its best lane (quote the carries when the sample is small), and the
     most inside-heavy teams.
5. **Tendencies bullets:**
   - The most run-leaning and most pass-leaning teams on 1st down (including the leader's pass %).
   - The 1st-vs-2nd-down r.
   - The 2nd- and 3rd-down extremes.
   - Check that the "Why re-center?" bullet still matches (about 1 point on 1st down, 3 on 3rd).
6. **QB table:** paste the 10 printed rows. Change `Minimum X dropbacks` to `15 × N`.

Rules:

- **Wording:** when the leaders change, rewrite the sentence instead of forcing new teams into the old
  wording. For example, "far better than anyone else" is wrong if the gap is now 0.01.
- **Claims:** recheck every qualitative claim ("by far", "only", "stand out") against the printed numbers.
- **Scope:** leave the matchup section, the backtest table and the methodology text alone.

Check the result with `git diff README.md`. Every changed number should appear in the `readme_stats.py`
output.

## 7. Weekly matchup preview

Check `figures/matchups_SEASON_wk*.png`. After a Tuesday CI run it should be week N+1.

- If CI already pushed week N+1 (you pulled it in step 1), there's nothing to do.
- If it's stale and the user asked for matchups, or confirms they want them, run:

  ```bash
  $PY scripts/matchups.py --season SEASON              # next week with unplayed games
  $PY scripts/sync_readme_matchups.py                  # repoints README, deletes last week's files
  ```

  Then Read the new `figures/matchups_*.png` and check it the same way as step 4.

## 8. Review and commit

```bash
git status --short
git diff --stat
```

Expected changes: 6 season PNGs, 5 season CSVs, 5 `output/latest/` CSVs, 2 notebooks and `README.md`, plus
matchup files (including `output/latest/matchups.csv` and `unit_ratings.csv`) if step 7 ran. Anything else needs an explanation.

Commit only if the user asked for one; otherwise ask. Use this message format, with all the files in
one commit:

```
Update season charts, tables, notebooks and README through week N
```

Push with `git push origin main` only when the user asks (or has asked for "commit and push").

## 9. Report back

Keep it short:

- **Data:** through week N, G of G games.
- **What changed:** which files were regenerated and the headline movement in the README, such as new
  top teams, QBs entering or leaving the top 10, and claims that flipped.
- **Problems:** any chart issues from step 4 that are still there.
- **Matchups:** their status (current from CI, regenerated, or stale).
- **Git:** committed/pushed or not.
