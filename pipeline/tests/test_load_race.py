"""
Tests for load_race.py. Run from the pipeline folder with:  pytest

These tests use small, made-up races, so they need no internet or Snowflake access.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import load_race as lr  # noqa: E402


# ---------------------------------------------------------------------------
# A fake race shaped like real OpenF1 data: 2 drivers, 58 laps, 2 pit stops each
# (stints: MEDIUM laps 1-10, HARD laps 11-33, MEDIUM laps 34-58)
# ---------------------------------------------------------------------------
def make_raw(n_laps=58):
    laps, stints, pits, drivers = [], [], [], []
    for num, code in [(1, "NOR"), (44, "HAM")]:
        drivers.append(dict(driver_number=num, name_acronym=code,
                            full_name=f"Driver {code}", team_name="Team"))
        plan = [(1, 10, "MEDIUM", 3), (11, 33, "HARD", 0), (34, n_laps, "MEDIUM", 0)]
        for s, (start, end, compound, age) in enumerate(plan, 1):
            stints.append(dict(driver_number=num, stint_number=s, lap_start=start,
                               lap_end=end, compound=compound, tyre_age_at_start=age))
        for lap in range(1, n_laps + 1):
            laps.append(dict(driver_number=num, lap_number=lap,
                             lap_duration=None if lap == 1 else 86.5,
                             duration_sector_1=30.0, duration_sector_2=18.0,
                             duration_sector_3=38.5, is_pit_out_lap=lap in (11, 34)))
        pits += [dict(driver_number=num, lap_number=11, lane_duration=18.2),
                 dict(driver_number=num, lap_number=34, lane_duration=17.6)]
    return dict(session_key=11234, event_name="Test Grand Prix",
                laps=pd.DataFrame(laps), stints=pd.DataFrame(stints),
                pits=pd.DataFrame(pits), drivers=pd.DataFrame(drivers))


@pytest.fixture
def df():
    return lr.transform(make_raw(), 2026, 1)


def lap(df, driver, n):
    return df[(df.DRIVER_CODE == driver) & (df.LAP_NUMBER == n)].iloc[0]


# ---------------------------------------------------------------------------
# transform
# ---------------------------------------------------------------------------
def test_one_row_per_driver_per_lap(df):
    assert len(df) == 2 * 58
    assert not df.duplicated(["DRIVER_NUMBER", "LAP_NUMBER"]).any()


def test_columns_match_snowflake_table(df):
    for col in ["SEASON", "RACE_ROUND", "DRIVER_CODE", "LAP_TIME_SEC",
                "COMPOUND", "TYRE_LIFE", "PIT_IN", "PIT_OUT", "PIT_LANE_SEC"]:
        assert col in df.columns
        assert col in lr.CREATE_TABLE_SQL


def test_laps_get_the_right_tires(df):
    assert lap(df, "NOR", 10).COMPOUND == "MEDIUM"
    assert lap(df, "NOR", 11).COMPOUND == "HARD"
    assert lap(df, "NOR", 34).COMPOUND == "MEDIUM"


def test_tyre_life_counts_up_and_resets_after_a_stop(df):
    assert lap(df, "NOR", 1).TYRE_LIFE == 4    # fitted with 3 laps of use
    assert lap(df, "NOR", 10).TYRE_LIFE == 13
    assert lap(df, "NOR", 11).TYRE_LIFE == 1   # fresh set after the stop
    assert lap(df, "NOR", 11).FRESH_TYRE
    assert not lap(df, "NOR", 1).FRESH_TYRE


def test_pit_in_and_out_laps(df):
    pit_in = df[df.PIT_IN & (df.DRIVER_CODE == "NOR")].LAP_NUMBER.tolist()
    pit_out = df[df.PIT_OUT & (df.DRIVER_CODE == "NOR")].LAP_NUMBER.tolist()
    assert pit_in == [10, 33]
    assert pit_out == [11, 34]
    assert lap(df, "NOR", 11).PIT_LANE_SEC == 18.2


def test_pit_in_never_leaks_between_drivers(df):
    # NOR's last lap must not inherit HAM's lap-1 values, and vice versa
    assert not lap(df, "NOR", 58).PIT_IN
    assert not lap(df, "HAM", 58).PIT_IN


def test_missing_lap_time_becomes_null(df):
    assert pd.isna(lap(df, "NOR", 1).LAP_TIME_SEC)


def test_race_without_pit_data_still_transforms():
    raw = make_raw()
    raw["pits"] = pd.DataFrame()  # what fetch() returns when OpenF1 answers 404
    df = lr.transform(raw, 2023, 1)
    assert df.PIT_LANE_SEC.isna().all()
    assert lap(df, "NOR", 11).PIT_OUT  # pit laps still come from the lap data
    lr.check_quality(df)


def test_fetch_treats_404_as_no_rows(monkeypatch, tmp_path):
    class Resp:
        status_code = 404
        def raise_for_status(self):
            raise AssertionError("404 should not raise")
    monkeypatch.setattr(lr, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(lr.requests, "get", lambda *a, **k: Resp())
    monkeypatch.setattr(lr.time, "sleep", lambda s: None)
    assert lr.fetch("pit", session_key=1).empty
    assert not list(tmp_path.iterdir())  # empty answers are never cached


def test_empty_laps_means_no_data_yet():
    raw = make_raw()
    raw["laps"] = pd.DataFrame()
    with pytest.raises(lr.NoDataYet):
        lr.transform(raw, 2026, 1)


# ---------------------------------------------------------------------------
# check_quality
# ---------------------------------------------------------------------------
def test_good_data_passes(df):
    lr.check_quality(df)  # should not raise


def test_catches_duplicate_laps(df):
    with pytest.raises(ValueError, match="duplicate"):
        lr.check_quality(pd.concat([df, df.head(1)]))


def test_catches_negative_lap_times(df):
    df.loc[5, "LAP_TIME_SEC"] = -1.0
    with pytest.raises(ValueError, match="negative"):
        lr.check_quality(df)


def test_catches_implausible_race_length():
    short = lr.transform(make_raw(n_laps=12), 2026, 1)
    with pytest.raises(ValueError, match="race length"):
        lr.check_quality(short)


def test_catches_missing_tire_data(df):
    df.loc[: len(df) // 2, "COMPOUND"] = None
    with pytest.raises(ValueError, match="tire data"):
        lr.check_quality(df)


# ---------------------------------------------------------------------------
# Season schedule logic used by --auto
# ---------------------------------------------------------------------------
SCHEDULE = pd.DataFrame({
    "session_key": [3, 1, 2, 4],
    "year": [2026] * 4,
    "date_start": ["2026-04-01T12:00:00+00:00", "2026-03-01T12:00:00+00:00",
                   "2026-03-15T12:00:00+00:00", "2026-04-15T12:00:00+00:00"],
    "date_end": ["2026-04-01T14:00:00+00:00", "2026-03-01T14:00:00+00:00",
                 "2026-03-15T14:00:00+00:00", "2026-04-15T14:00:00+00:00"],
    "is_cancelled": [False, False, True, False],
})


@pytest.fixture
def races(monkeypatch):
    monkeypatch.setattr(lr, "fetch", lambda *a, **k: SCHEDULE.copy())
    return lr.season_races(2026)


def test_rounds_follow_date_order_and_skip_cancelled(races):
    # session 2 was cancelled, so sessions 1, 3, 4 become rounds 1, 2, 3
    assert races["session_key"].tolist() == [1, 3, 4]
    assert races["ROUND"].tolist() == [1, 2, 3]


def test_finished_rounds_waits_after_race_end(races):
    # 1 hour after round 2 ended: too soon to load it
    now = pd.Timestamp("2026-04-01T15:00:00+00:00")
    assert lr.finished_rounds(races, now) == [1]
    # 4 hours after: round 2 is ready
    now = pd.Timestamp("2026-04-01T18:00:00+00:00")
    assert lr.finished_rounds(races, now) == [1, 2]