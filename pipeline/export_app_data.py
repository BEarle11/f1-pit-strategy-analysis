"""
export_app_data.py - Copy the data the Streamlit app needs from Snowflake into files.

Usage (from the pipeline folder, with .venv active):
    python export_app_data.py

Why files instead of letting the app query Snowflake directly:
  - Visitors never start the Snowflake warehouse, so the app costs nothing to run.
  - The app needs no Snowflake credentials, so no secrets live in the app.
  - The app keeps working even if Snowflake is ever shut down.
The files are small (a few MB) and are saved to app/data/ in the repo.
"""

import logging
from pathlib import Path

from load_race import get_connection

log = logging.getLogger("export_app_data")
OUT_DIR = Path(__file__).resolve().parent.parent / "app" / "data"

QUERIES = {
    # Every lap, including pit and safety-car laps, for race replays.
    "laps": """
        SELECT SEASON, RACE_ROUND, EVENT_NAME, DRIVER_NUMBER, DRIVER_CODE,
               DRIVER_NAME, TEAM, LAP_NUMBER, LAP_TIME_SEC, STINT, COMPOUND,
               TYRE_LIFE, FRESH_TYRE, PIT_IN, PIT_OUT, PIT_LANE_SEC
        FROM F1_PROJECT.RAW.FF1_LAPS
        ORDER BY SEASON, RACE_ROUND, DRIVER_NUMBER, LAP_NUMBER
    """,
    # Cleaned laps for degradation analysis.
    "clean_laps": """
        SELECT * FROM F1_PROJECT.ANALYTICS.CLEAN_LAPS
        ORDER BY SEASON, RACE_ROUND, DRIVER_NUMBER, LAP_NUMBER
    """,
}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    try:
        for name, sql in QUERIES.items():
            df = conn.cursor().execute(sql).fetch_pandas_all()
            path = OUT_DIR / f"{name}.parquet"
            df.to_parquet(path, index=False)
            log.info("Wrote %s rows to %s", f"{len(df):,}", path)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
