"""
load_race.py - Load F1 race lap-by-lap data from the OpenF1 API into Snowflake.

Usage (from PyCharm's terminal):
    python load_race.py 2026 1             # load round 1 of the 2026 season
    python load_race.py 2026 1 --replace   # delete that race's rows and reload it
    python load_race.py --auto             # load every finished 2026 race not yet in Snowflake
    python load_race.py --auto --year 2025 # same, for another season

The pipeline has three stages, the classic ETL pattern:
    1. EXTRACT   - download the race's laps, tire stints, pit stops and drivers from OpenF1
    2. TRANSFORM - combine them into one flat table with one row per driver per lap
    3. LOAD      - write it into F1_PROJECT.RAW.FF1_LAPS in Snowflake
Quality checks run between TRANSFORM and LOAD, so bad data never reaches Snowflake.

Why OpenF1: F1's own live-timing server (which the FastF1 library depends on) now
blocks many networks, including cloud servers like GitHub Actions. OpenF1 is a free,
open API with historical data from 2023 onward and no login required.
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

import pandas as pd
import requests
import snowflake.connector
from dotenv import load_dotenv
from snowflake.connector.pandas_tools import write_pandas

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
TABLE = "FF1_LAPS"
API = "https://api.openf1.org/v1"
CACHE_DIR = Path(__file__).parent / "openf1_cache"  # raw API responses are saved here
HOURS_AFTER_RACE = 3  # wait this long after a race ends before loading it

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s %(message)s")
log = logging.getLogger("load_race")

# The table's structure. "IF NOT EXISTS" makes this safe to run every time.
CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    SEASON          INT,
    RACE_ROUND      INT,
    SESSION_KEY     INT,       -- OpenF1's unique ID for this race session
    EVENT_NAME      STRING,
    DRIVER_NUMBER   INT,
    DRIVER_CODE     STRING,    -- three-letter code, e.g. VER
    DRIVER_NAME     STRING,    -- full name, used to match the Kaggle DRIVERS table
    TEAM            STRING,
    LAP_NUMBER      INT,
    LAP_TIME_SEC    FLOAT,     -- NULL when timing is missing (often lap 1)
    SECTOR_1_SEC    FLOAT,
    SECTOR_2_SEC    FLOAT,
    SECTOR_3_SEC    FLOAT,
    STINT           INT,       -- 1 = first set of tires, 2 = after first stop, ...
    COMPOUND        STRING,    -- SOFT / MEDIUM / HARD / INTERMEDIATE / WET
    TYRE_LIFE       INT,       -- laps on this set of tires, counting this lap
    FRESH_TYRE      BOOLEAN,   -- was the set new when fitted?
    PIT_IN          BOOLEAN,   -- driver entered the pits at the end of this lap
    PIT_OUT         BOOLEAN,   -- driver left the pits at the start of this lap
    PIT_LANE_SEC    FLOAT      -- time spent in the pit lane, on the pit-out lap
)
"""


class NoDataYet(Exception):
    """OpenF1 has no lap data for this race yet. Not a failure; try again later."""


# ---------------------------------------------------------------------------
# 1. EXTRACT
# ---------------------------------------------------------------------------
def fetch(endpoint: str, use_cache: bool = True, **params) -> pd.DataFrame:
    """Call one OpenF1 endpoint, reusing a saved copy if we already downloaded it."""
    CACHE_DIR.mkdir(exist_ok=True)
    key = endpoint + "_" + "_".join(f"{k}-{v}" for k, v in sorted(params.items()))
    cache_file = CACHE_DIR / f"{key}.json"

    if use_cache and cache_file.exists():
        return pd.DataFrame(json.loads(cache_file.read_text()))

    resp = requests.get(f"{API}/{endpoint}", params=params, timeout=30)
    resp.raise_for_status()  # turn HTTP errors (404, 500...) into Python errors
    data = resp.json()
    if use_cache and data:  # never cache an empty answer; the data may arrive later
        cache_file.write_text(json.dumps(data))
    time.sleep(0.5)  # stay well under OpenF1's free rate limit
    return pd.DataFrame(data)


def season_races(year: int) -> pd.DataFrame:
    """Return the season's races in date order with a ROUND column (1, 2, 3...).

    Cancelled races are skipped, so round numbers match the official calendar.
    The schedule is always fetched fresh, since it can change during a season.
    """
    races = fetch("sessions", use_cache=False, year=year, session_name="Race")
    if races.empty:
        raise ValueError(f"No races found for {year}.")
    if "is_cancelled" in races:
        races = races[races["is_cancelled"] != True]  # noqa: E712
    races = races.sort_values("date_start").reset_index(drop=True)
    races["ROUND"] = races.index + 1
    return races


def finished_rounds(races: pd.DataFrame, now: pd.Timestamp) -> list[int]:
    """Rounds whose race ended at least HOURS_AFTER_RACE hours before `now`."""
    ended = pd.to_datetime(races["date_end"], utc=True)
    done = ended <= now - pd.to_timedelta(HOURS_AFTER_RACE, unit="h")
    return races.loc[done, "ROUND"].tolist()


def extract(race: pd.Series) -> dict:
    key = int(race["session_key"])
    meeting = fetch("meetings", meeting_key=int(race["meeting_key"]))
    event_name = meeting["meeting_name"].iloc[0] if not meeting.empty else race["location"]
    log.info("Loading %s %s (round %s, session %s)...",
             race["year"], event_name, race["ROUND"], key)

    return {
        "session_key": key,
        "event_name": event_name,
        "laps": fetch("laps", session_key=key),
        "stints": fetch("stints", session_key=key),
        "pits": fetch("pit", session_key=key),
        "drivers": fetch("drivers", session_key=key),
    }


# ---------------------------------------------------------------------------
# 2. TRANSFORM
# ---------------------------------------------------------------------------
def transform(raw: dict, year: int, rnd: int) -> pd.DataFrame:
    """Combine laps, stints, pit stops and drivers into one table matching FF1_LAPS."""
    laps = raw["laps"]
    if laps.empty:
        raise NoDataYet("No lap data yet. Has this race happened?")

    laps = laps.sort_values(["driver_number", "lap_number"]).reset_index(drop=True)

    # Attach driver details (code, name, team) by car number.
    drivers = raw["drivers"][["driver_number", "name_acronym", "full_name", "team_name"]]
    df = laps.merge(drivers.drop_duplicates("driver_number"), on="driver_number", how="left")

    # Attach tire info. Each stint covers a range of laps (lap_start to lap_end),
    # so match every lap to the stint whose range contains it.
    stints = raw["stints"]
    df = df.merge(stints[["driver_number", "stint_number", "lap_start", "lap_end",
                          "compound", "tyre_age_at_start"]],
                  on="driver_number", how="left")
    in_stint = (df["lap_number"] >= df["lap_start"]) & (df["lap_number"] <= df["lap_end"])
    df = df[in_stint | df["stint_number"].isna()]
    df = df.drop_duplicates(["driver_number", "lap_number"])  # keep one row per lap

    # Tire age on this lap = age when fitted + laps driven on it so far.
    df["tyre_life"] = df["tyre_age_at_start"] + (df["lap_number"] - df["lap_start"]) + 1

    # Pit stops: OpenF1 marks the lap the car leaves the pits (pit-out lap).
    # The pit-in lap is the lap just before it, for the same driver.
    df["pit_out"] = df["is_pit_out_lap"].fillna(False).astype(bool) & (df["lap_number"] > 1)
    df["pit_in"] = df.groupby("driver_number")["pit_out"].shift(-1, fill_value=False)

    pits = raw["pits"]
    if not pits.empty:
        df = df.merge(pits[["driver_number", "lap_number", "lane_duration"]],
                      on=["driver_number", "lap_number"], how="left")
    else:
        df["lane_duration"] = None

    out = pd.DataFrame({
        "SEASON": year,
        "RACE_ROUND": rnd,
        "SESSION_KEY": raw["session_key"],
        "EVENT_NAME": raw["event_name"],
        "DRIVER_NUMBER": df["driver_number"].astype("Int64"),
        "DRIVER_CODE": df["name_acronym"],
        "DRIVER_NAME": df["full_name"],
        "TEAM": df["team_name"],
        "LAP_NUMBER": df["lap_number"].astype("Int64"),
        "LAP_TIME_SEC": pd.to_numeric(df["lap_duration"], errors="coerce"),
        "SECTOR_1_SEC": pd.to_numeric(df["duration_sector_1"], errors="coerce"),
        "SECTOR_2_SEC": pd.to_numeric(df["duration_sector_2"], errors="coerce"),
        "SECTOR_3_SEC": pd.to_numeric(df["duration_sector_3"], errors="coerce"),
        "STINT": df["stint_number"].astype("Int64"),
        "COMPOUND": df["compound"],
        "TYRE_LIFE": df["tyre_life"].astype("Int64"),
        "FRESH_TYRE": (df["tyre_age_at_start"] == 0).astype("boolean"),
        "PIT_IN": df["pit_in"].astype(bool),
        "PIT_OUT": df["pit_out"].astype(bool),
        "PIT_LANE_SEC": pd.to_numeric(df["lane_duration"], errors="coerce"),
    }).reset_index(drop=True)

    log.info("Transformed %d laps for %d drivers.", len(out), out["DRIVER_NUMBER"].nunique())
    return out


# ---------------------------------------------------------------------------
# Quality checks: stop the load if something looks wrong
# ---------------------------------------------------------------------------
def check_quality(df: pd.DataFrame) -> None:
    problems = []

    if df.duplicated(subset=["DRIVER_NUMBER", "LAP_NUMBER"]).any():
        problems.append("duplicate driver/lap rows")

    if (df["LAP_TIME_SEC"].dropna() <= 0).any():
        problems.append("zero or negative lap times")

    max_laps = df["LAP_NUMBER"].max()
    if not 20 <= max_laps <= 90:  # every modern Grand Prix falls in this range
        problems.append(f"implausible race length ({max_laps} laps)")

    no_tyre = df["COMPOUND"].isna().mean()
    if no_tyre > 0.10:
        problems.append(f"{no_tyre:.0%} of laps have no tire data")

    missing_names = df.loc[df["DRIVER_CODE"].isna(), "DRIVER_NUMBER"].unique()
    if len(missing_names):
        log.warning("No driver details for car numbers: %s", list(missing_names))

    if problems:
        raise ValueError("Quality checks failed: " + "; ".join(problems))
    log.info("Quality checks passed.")


# ---------------------------------------------------------------------------
# 3. LOAD
# ---------------------------------------------------------------------------
def get_connection():
    """Connect to Snowflake. Credentials come from .env locally, or from
    GitHub Secrets (as environment variables) when running in GitHub Actions."""
    load_dotenv()
    conn = snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PAT"],  # programmatic access token
        warehouse="F1_WH",
        database="F1_PROJECT",
        schema="RAW",
    )
    conn.cursor().execute(CREATE_TABLE_SQL)
    return conn


def loaded_rounds(conn, year: int) -> set[int]:
    """Which rounds of this season are already in Snowflake."""
    cur = conn.cursor()
    cur.execute(f"SELECT DISTINCT RACE_ROUND FROM {TABLE} WHERE SEASON = %s", (year,))
    return {row[0] for row in cur.fetchall()}


def load(conn, df: pd.DataFrame, year: int, rnd: int, replace: bool) -> None:
    cur = conn.cursor()

    # Idempotency: refuse to load the same race twice unless asked to.
    # The %s placeholders let the connector insert values safely.
    cur.execute(
        f"SELECT COUNT(*) FROM {TABLE} WHERE SEASON = %s AND RACE_ROUND = %s",
        (year, rnd),
    )
    existing = cur.fetchone()[0]
    if existing and not replace:
        log.info("Already loaded (%d rows). Use --replace to reload. Nothing to do.", existing)
        return
    if existing:
        cur.execute(f"DELETE FROM {TABLE} WHERE SEASON = %s AND RACE_ROUND = %s", (year, rnd))
        log.info("Deleted %d old rows.", existing)

    success, _, nrows, _ = write_pandas(conn, df, TABLE, quote_identifiers=False)
    if not success:
        raise RuntimeError("Snowflake reported a failed load.")
    log.info("Loaded %d rows into %s.", nrows, TABLE)


def run_one(conn, race: pd.Series, replace: bool = False) -> None:
    """Extract, transform, check and load a single race."""
    year, rnd = int(race["year"]), int(race["ROUND"])
    df = transform(extract(race), year, rnd)
    check_quality(df)
    load(conn, df, year, rnd, replace)


# ---------------------------------------------------------------------------
# Run modes
# ---------------------------------------------------------------------------
def run_manual(year: int, rnd: int, replace: bool) -> int:
    races = season_races(year)
    if not 1 <= rnd <= len(races):
        raise ValueError(f"{year} has {len(races)} races; round {rnd} doesn't exist.")
    conn = get_connection()
    try:
        run_one(conn, races.iloc[rnd - 1], replace)
    finally:
        conn.close()  # always close the connection, even after an error
    return 0


def run_auto(year: int) -> int:
    """Load every finished race of the season that isn't in Snowflake yet."""
    races = season_races(year)
    done = finished_rounds(races, pd.Timestamp.now(tz="UTC"))

    conn = get_connection()
    try:
        todo = [r for r in done if r not in loaded_rounds(conn, year)]
        log.info("%s: %d races finished, %d to load: %s", year, len(done), len(todo), todo)

        failures = 0
        for rnd in todo:
            try:
                run_one(conn, races.iloc[rnd - 1])
            except NoDataYet as exc:
                log.warning("Round %s skipped: %s Will retry next run.", rnd, exc)
            except Exception as exc:  # keep going so one bad race doesn't block the rest
                log.error("Round %s failed: %s", rnd, exc)
                failures += 1
    finally:
        conn.close()
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Load F1 races into Snowflake.")
    parser.add_argument("year", type=int, nargs="?", help="season, 2023 or later")
    parser.add_argument("round", type=int, nargs="?", help="round number, e.g. 1")
    parser.add_argument("--replace", action="store_true", help="reload a race already loaded")
    parser.add_argument("--auto", action="store_true",
                        help="load every finished race not yet in Snowflake")
    parser.add_argument("--year", dest="auto_year", type=int,
                        help="season for --auto (default: current year)")
    args = parser.parse_args()

    try:
        if args.auto:
            return run_auto(args.auto_year or pd.Timestamp.now(tz="UTC").year)
        if args.year is None or args.round is None:
            parser.error("give a year and round, or use --auto")
        return run_manual(args.year, args.round, args.replace)
    except Exception as exc:
        log.error("Pipeline failed: %s", exc)
        return 1  # a non-zero exit code tells GitHub Actions the run failed


if __name__ == "__main__":
    sys.exit(main())
