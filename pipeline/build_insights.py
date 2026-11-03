"""
build_insights.py - Refresh the model results the dashboard shows.

Runs after export_app_data.py (weekly in GitHub Actions, or by hand):
    python build_insights.py                  # next race from the OpenF1 schedule
    python build_insights.py --event "Mexico City Grand Prix"   # pick the race by hand

Reads  app/data/laps.parquet and app/data/clean_laps.parquet
Writes app/data/team_wear.parquet          team-specific tire wear (notebook 03)
       app/data/strategy_next_race.parquet best plan per team (notebook 04)
       app/data/strategy_curves.parquet    race time vs pit lap, for the dashboard chart
       app/data/next_race.parquet          the circuit facts behind the strategy

The notebooks explain and explore each method; this script runs the same code
on a schedule so the dashboard stays current.
"""

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

# The model code lives with the notebooks that explain it
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "notebooks"))
from degradation import (bootstrap, eligible_teams, fit_degradation,  # noqa: E402
                         fit_team_degradation, partial_pool)
from strategy import (circuit_profile, max_stint_laps, pit_loss_by_event,  # noqa: E402
                      recommend_all, upcoming_races)

DATA = REPO / "app" / "data"
SKIP = 5            # opening laps dropped (notebook 02)
K = 0.9             # % -> seconds on a 90 s reference lap
COMPOUNDS = ["MEDIUM", "HARD"]
BOOTSTRAPS = 200

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s %(message)s")
log = logging.getLogger("build_insights")


def build_team_wear(season_laps: pd.DataFrame, season: int) -> pd.DataFrame:
    """Team-specific medium/hard wear with partial pooling (see notebook 03)."""
    field = fit_degradation(season_laps, skip_opening_laps=SKIP)
    field_boot = bootstrap(season_laps, n=BOOTSTRAPS, skip_opening_laps=SKIP)
    eligible = eligible_teams(season_laps, COMPOUNDS, min_laps=150, skip_opening_laps=SKIP)
    team_est = fit_team_degradation(season_laps, eligible, skip_opening_laps=SKIP)
    team_boot = bootstrap(season_laps, n=BOOTSTRAPS, fit_fn=fit_team_degradation,
                          eligible=eligible, skip_opening_laps=SKIP)

    parts = []
    for c in COMPOUNDS:
        cols = [f"{c}|{t}" for t in eligible[c]]
        if len(cols) < 2:
            continue
        # Uncertainty of each team's difference from the field, within each resample
        diff_se = team_boot[cols].sub(field_boot[f"deg_{c}"], axis=0).std()
        p = partial_pool(team_est[cols], diff_se, field[f"deg_{c}"])
        p.index = [i.split("|")[1] for i in p.index]
        parts.append(p.assign(compound=c, field_wear=field[f"deg_{c}"] * K))
    out = pd.concat(parts).rename_axis("team").reset_index()
    out[["raw", "raw_se", "pooled", "low", "high"]] *= K   # store in seconds
    out["season"] = season
    out["races"] = season_laps[["RACE_ROUND"]].drop_duplicates().shape[0]
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh dashboard model results.")
    parser.add_argument("--event", help="race to plan for (default: next on the schedule)")
    args = parser.parse_args()

    raw = pd.read_parquet(DATA / "laps.parquet")
    clean = pd.read_parquet(DATA / "clean_laps.parquet")
    season = int(clean["SEASON"].max())
    season_laps = clean[clean["SEASON"] == season]

    team_wear = build_team_wear(season_laps, season)
    team_wear.to_parquet(DATA / "team_wear.parquet", index=False)
    log.info("Wrote team wear for %d teams.", team_wear["team"].nunique())

    # Strategy for the next race. If this part fails (say, the schedule can't be
    # reached), keep last week's strategy files rather than failing the whole run.
    try:
        if args.event:
            event, date = args.event, None
        else:
            upcoming = upcoming_races(season)
            if upcoming.empty:
                log.info("No races left this season; strategy files unchanged.")
                return 0
            event, date = upcoming["meeting_name"].iloc[0], upcoming["date_start"].iloc[0]

        field = fit_degradation(season_laps, skip_opening_laps=SKIP)
        field_before = fit_degradation(clean[clean["SEASON"] < season], skip_opening_laps=SKIP)
        all_wear = fit_degradation(clean, skip_opening_laps=SKIP)
        circuit = circuit_profile(event, raw, clean, pit_loss_by_event(raw), all_wear, skip=SKIP)
        caps = max_stint_laps(raw, season).to_dict()

        recs, curves = recommend_all(team_wear, field, field_before, circuit, caps)
        recs.assign(event=event, season=season).to_parquet(
            DATA / "strategy_next_race.parquet", index=False)
        curves.to_parquet(DATA / "strategy_curves.parquet", index=False)
        pd.DataFrame([{**circuit, "date": date, "season": season,
                       **{f"max_stint_{c}": v for c, v in caps.items()}}]).to_parquet(
            DATA / "next_race.parquet", index=False)
        log.info("Wrote strategy for the %s (%d past races here).", event, circuit["past_races"])
    except Exception as exc:
        log.warning("Strategy step skipped: %s", exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
