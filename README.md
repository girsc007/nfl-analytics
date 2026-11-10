# NFL Analytics

Exploring NFL team and quarterback efficiency with play-by-play data from
[nflverse](https://github.com/nflverse), using Python, pandas and matplotlib.

## Team efficiency (2026 season, through week 9)

![2026 team efficiency](figures/team_efficiency_2026.png)

Each dot is a team: **offensive EPA per play** (x) vs. **defensive EPA per play allowed** (y,
inverted so up is good). Teams in the top-right are good on both sides of the ball.

- **SF**, **CHI** and **JAX** had the best combination of offense and defense.
- **MIN** and **TB** had the best defenses, despite struggling offenses.
- **DAL** had a top-four offense undone by the league's fifth-worst defense; **MIA** allowed the most EPA/play.

## Passing vs. rushing (2026 season, through week 9)

![2026 pass vs. rush EPA](figures/team_pass_vs_rush_2026.png)

Offensive EPA/play split into dropbacks (x) and designed runs (y), with both axes on the same scale.

- **Passing is more efficient:** the league averaged **+0.076** EPA per dropback vs. **−0.093** per designed run.
  Only **IND, PIT, ATL and TB** ran more efficiently than they passed.
- **Passing separates teams:** pass EPA varies more between teams than rush EPA
  (std. dev. 0.15 vs. 0.11). **CIN** and **SF** had the best passing offenses, ahead of **GB**, **JAX** and **CHI**.
- **Run-heavy ≠ run-efficient:** pass rate has only a weak correlation with pass efficiency so far (r = 0.31).
  PIT ran better than it passed yet had the 4th-highest pass rate.
- **Good offenses aren't reliably good at both yet** (r = 0.05 between pass and rush EPA, far weaker than a full
  season typically shows). **KC, SF, BUF and DAL** stand out as above average at both.

## Run direction (2026 season, through week 9)

![2026 run direction](figures/run_direction_2026.png)

Designed runs split by lane, using nflverse's run location and gap with left and right combined:
**inside** (guard gaps and middle), **off tackle** and **outside** (around the end). The left panel shows
how each team divides its carries; the right panel shows EPA per carry in each lane, colored against the
league average for that lane. Most teams have only 20–40 off-tackle or outside carries so far, so these
cells are noisy; the ★ marks the few differences that are statistically clear.

- **Outside runs work best, but are used least:** the league averaged **+0.01** EPA per carry outside vs.
  **−0.03** off tackle and **−0.11** inside, yet only 22% of designed runs went outside (55% inside).
- **Running outside more isn't a shortcut:** teams with a higher outside share were slightly *worse* overall
  (r = −0.26). **LAC** (38% outside) and **SEA** (37%) ran outside the most and had the two worst run games.
- **PIT** (+0.17 per carry) and **KC** (+0.15) had the best run games, PIT through the middle (+0.35 inside)
  and KC around the edge (+0.43 outside on 35 carries). **CIN** (71%), **BUF**, **LA** and **NO** (69% each)
  were the most inside-heavy.

## Pass/run tendencies by down (2026 season, through week 9)

![2026 pass tendency by down](figures/pass_tendency_by_down_2026.png)

Each cell shows how often a team **passed** on that down, followed by its **pass rate over expected**
relative to the league average. Pass rate over expected subtracts nflverse's `xpass`, which accounts for
distance, field position, score and time, so it reflects play-calling rather than game script. It's then
re-centered so the league average is 0 on every down. The color uses the same measure: blue passes more
than a typical team would in the same situations, orange runs more.

- **The most run-leaning 1st-down offenses** were LAC (38% pass, −12.1 points vs. league average),
  TB (−9.9) and BUF (−9.3). The most pass-leaning were CIN (+15.0), CAR (+10.1), LV (+7.8) and SF (+5.9).
- **Tendencies change by down.** A team's 1st-down tendency barely predicts its 2nd-down tendency (r = 0.31).
- **LV, TB and NYG** were the most run-heavy on 2nd down (−9 to −11 points). **MIA** was the most
  run-heavy on 3rd down by far (−11.7), while **MIN** and **KC** (+7.8 each) were the most pass-heavy.
- **Why re-center?** `xpass` is fit on all plays, including garbage time. In the competitive situations
  analyzed here, the whole league runs slightly more than it predicts (about 1 point on 1st down and 3 on
  3rd), so comparing to the league average is fairer than comparing to zero.

## Weekly matchup mismatches

![2026 week 10 matchups](figures/matchups_2026_wk10.png)

`scripts/matchups.py` rates every team's **pass offense, rush offense, pass defense and rush defense**
(EPA/play, using only games before the target week), then scores each offense-vs-defense matchup:

> **edge** = (offense rating − league avg) + (defense rating − league avg)

A positive edge favors the offense; a negative edge favors the defense. `edge_sd` puts it in standard
deviations, so pass and rush mismatches compare fairly.

**Opponent adjustment.** Ratings come from a ridge regression fit on every play, separately for passing
and rushing: *EPA = league average + offense rating + defense rating*. Solving for all teams at once
credits each unit only for what it did beyond what its opponents usually allow or produce. The ridge
penalty (`--shrinkage`, default 200) works like adding 200 league-average plays to each team, which
pulls small early-season samples toward average. The script also prints the units whose ratings moved
most because of their schedule, and saves every rating, raw and adjusted, to `output/unit_ratings_*.csv`.

```bash
python scripts/matchups.py                          # next week with unplayed games
python scripts/matchups.py --season 2026 --week 8
python scripts/matchups.py --no-adjust              # raw per-play averages
python scripts/matchups.py --prior-weight 0.25      # blend in last season's plays
```

**Does it work?** Backtested on 2025, rating teams on prior weeks only and comparing each edge to
the game's actual EPA/play:

| Ratings | Pass r (wk 3–8) | Pass r (wk 9–18) | Rush r (wk 9–18) | Early pass error |
|---|---:|---:|---:|---:|
| Raw averages | 0.205 | 0.368 | 0.165 | 0.148 |
| Shrinkage only | 0.186 | 0.376 | 0.161 | 0.116 |
| **Opponent-adjusted + shrinkage (default)** | 0.193 | 0.373 | 0.174 | **0.115** |

Most of the gain comes from **shrinkage**. Raw early-season edges overstated real results by about 3×,
and shrinking them cut prediction error by about 22%. Opponent adjustment adds a small improvement on
top, mainly for rushing, though one season is not enough to be confident about a gain that size.
Passing mismatches remain far more predictive than rushing ones.

## Quarterbacks (2026 season, through week 9)

![2026 QB accuracy vs. production](figures/qb_epa_vs_cpoe_2026.png)

| # | QB | Team | Dropbacks | EPA/db | CPOE | Success % |
|---|---|---|---:|---:|---:|---:|
| 1 | C.Williams | CHI | 190 | +0.327 | +5.5 | 52.1 |
| 2 | J.Burrow | CIN | 270 | +0.322 | +10.3 | 56.3 |
| 3 | B.Purdy | SF | 207 | +0.314 | +4.5 | 54.6 |
| 4 | T.Lawrence | JAX | 201 | +0.290 | +2.0 | 50.2 |
| 5 | J.Allen | BUF | 238 | +0.269 | +2.8 | 46.6 |
| 6 | J.Love | GB | 269 | +0.250 | +1.4 | 43.9 |
| 7 | C.Stroud | HOU | 264 | +0.213 | +2.4 | 50.0 |
| 8 | D.Prescott | DAL | 279 | +0.213 | +1.4 | 48.4 |
| 9 | D.Maye | NE | 249 | +0.206 | +5.6 | 51.4 |
| 10 | K.Cousins | LV | 244 | +0.179 | +0.8 | 49.2 |

Minimum 135 dropbacks (15 per week played). Full table: [`output/qb_stats_2026.csv`](output/qb_stats_2026.csv).
Ranked bar chart: [`figures/qb_epa_ranking_2026.png`](figures/qb_epa_ranking_2026.png).

## Using the data (Power BI, Excel, etc.)

Every table is also written to `output/latest/<name>.csv` under a name that never changes, so a dashboard
can point at the raw GitHub URL and pick up each week's update on refresh. Each file starts with `season`,
`week` and `data_through_week` columns, and `team` is a regular column. For the season tables, `week` is
the latest completed week; for `matchups` and `unit_ratings` it is the previewed week, and
`data_through_week` is the last week the ratings use.

| Table | URL |
|---|---|
| team_epa | https://raw.githubusercontent.com/girsc007/nfl-analytics/main/output/latest/team_epa.csv |
| team_pass_rush_epa | https://raw.githubusercontent.com/girsc007/nfl-analytics/main/output/latest/team_pass_rush_epa.csv |
| run_direction | https://raw.githubusercontent.com/girsc007/nfl-analytics/main/output/latest/run_direction.csv |
| pass_tendency_by_down | https://raw.githubusercontent.com/girsc007/nfl-analytics/main/output/latest/pass_tendency_by_down.csv |
| qb_stats | https://raw.githubusercontent.com/girsc007/nfl-analytics/main/output/latest/qb_stats.csv |
| matchups | https://raw.githubusercontent.com/girsc007/nfl-analytics/main/output/latest/matchups.csv |
| unit_ratings | https://raw.githubusercontent.com/girsc007/nfl-analytics/main/output/latest/unit_ratings.csv |

In Power BI: **Get Data → Web**, paste a URL, choose **Anonymous**. `run_direction` and
`pass_tendency_by_down` are long tables (one row per team and lane or down) and include league-average rows with
`team` = `NFL`; filter them out before aggregating. The dated files in `output/` (for example `team_epa_2026.csv`) are the
same data without the extra columns.

## Methodology

- **Data:** nflverse play-by-play, loaded with [`nflreadpy`](https://github.com/nflverse/nflreadpy).
- **Plays:** regular-season pass and run plays with an EPA value.
- **Garbage time removed:** only plays where the offense's win probability was 10–90%.
- **EPA (expected points added):** how much a play changed the offense's expected points.
- **QB stats** use dropbacks (passes, sacks, scrambles) and `qb_epa`, which doesn't penalize
  the QB for a receiver's fumble after the catch.
- **CPOE:** completion percentage over expected, based on throw difficulty.
- **Composite:** average of EPA/dropback and CPOE z-scores among qualified QBs.

## Project structure

```
src/nfl_analytics/
  data.py             load and filter play-by-play
  team_efficiency.py  team EPA, pass vs. rush split, and charts
  qb_stats.py         QB stats table and charts
  matchups.py         pass/rush unit ratings and matchup edges
  export.py           fixed-name copies of every table in output/latest/
  logos.py            team logos as chart markers (downloaded once, cached)
  style.py            shared chart styling
scripts/make_charts.py  regenerate every season chart and table
scripts/matchups.py     weekly matchup mismatches
notebooks/
  01_team_efficiency.ipynb
  02_qb_stats.ipynb
figures/   saved charts
output/    CSV tables (output/latest/: fixed names for dashboards)
```

## Getting started

```bash
git clone https://github.com/girsc007/nfl-analytics.git
cd nfl-analytics
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python scripts/make_charts.py                  # 2026 season to date
python scripts/make_charts.py --season 2025    # final 2025 regular season
python scripts/make_charts.py --all-plays      # keep garbage time
jupyter notebook notebooks/
```

## Ideas for next analyses

- Pass vs. rush EPA by down and field position (does running pay off near the goal line?)
- Year-over-year stability of EPA vs. CPOE for QBs
- QB performance on 3rd down and in the red zone
- 4th-down decision-making vs. win-probability recommendations
- Does net EPA/play predict win totals better than point differential?

Data courtesy of the nflverse project (CC-BY 4.0). Team logos are downloaded from ESPN's CDN when charts
are generated and cached in `.cache/logos/` (not committed). They're trademarks of their respective teams.
