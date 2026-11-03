"""
Tests for the tire model and strategy simulator (notebooks/degradation.py, strategy.py).

They use simulated races with KNOWN answers, so they need no data files or internet.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "notebooks"))
from degradation import (eligible_teams, fit_degradation,  # noqa: E402
                         fit_team_degradation, partial_pool, simulate_races)
from strategy import _stint_time, best_plans, pit_loss_by_event, simulate  # noqa: E402

TRUE = {"fuel": -0.065, "SOFT": 0.11, "MEDIUM": 0.065, "HARD": 0.035}


@pytest.fixture(scope="module")
def sim():
    return simulate_races(TRUE, n_races=8, seed=1,
                          team_wear={"Team A": 0.6, "Team E": 1.4})


# ---------------------------------------------------------------------------
# Degradation model
# ---------------------------------------------------------------------------
def test_recovers_known_fuel_and_wear(sim):
    est = fit_degradation(sim[~sim["TEAM"].isin(["Team A", "Team E"])])
    assert est["fuel"] == pytest.approx(TRUE["fuel"], abs=0.003)
    for c in ["SOFT", "MEDIUM", "HARD"]:
        assert est[f"deg_{c}"] == pytest.approx(TRUE[c], abs=0.005)


def test_without_fuel_correction_wear_is_underestimated(sim):
    naive = fit_degradation(sim, fuel_correction=False)
    assert naive["deg_HARD"] < TRUE["HARD"] / 2


def test_team_rates_recover_known_differences(sim):
    eligible = eligible_teams(sim, min_laps=100)
    est = fit_team_degradation(sim, eligible)
    assert est["MEDIUM|Team A"] == pytest.approx(0.6 * TRUE["MEDIUM"], abs=0.006)
    assert est["MEDIUM|Team E"] == pytest.approx(1.4 * TRUE["MEDIUM"], abs=0.006)
    assert est["MEDIUM|Team A"] < est["MEDIUM|Team C"] < est["MEDIUM|Team E"]


def test_partial_pool_shrinks_noisy_teams_more():
    raw = pd.Series({"precise": 0.08, "noisy": 0.08, "x": 0.04, "y": 0.05})
    se = pd.Series({"precise": 0.002, "noisy": 0.02, "x": 0.005, "y": 0.005})
    p = partial_pool(raw, se, field=0.05)
    assert p.loc["precise", "weight"] > p.loc["noisy", "weight"]
    assert p.loc["noisy", "pooled"] < p.loc["precise", "pooled"]   # pulled toward 0.05


def test_partial_pool_with_no_real_differences_returns_the_field():
    raw = pd.Series({"a": 0.050, "b": 0.051, "c": 0.049})
    p = partial_pool(raw, pd.Series(0.02, index=raw.index), field=0.05)
    assert (p["weight"] == 0).all()
    assert np.allclose(p["pooled"], 0.05)


# ---------------------------------------------------------------------------
# Strategy simulator
# ---------------------------------------------------------------------------
PARAMS = dict(fuel=-0.06, offset_SOFT=-0.6, offset_HARD=0.4,
              wear_SOFT=0.10, wear_MEDIUM=0.05, wear_HARD=0.03)
CAPS = {"SOFT": 25, "MEDIUM": 35, "HARD": 45}


def test_stint_formula_matches_lap_by_lap_sum():
    base, fuel, off, wear, start, n = 90, -0.065, -0.6, 0.11, 20, 25
    loop = sum(base * (1 + (fuel * lap + off + wear * (lap - start + 1)) / 100)
               for lap in range(start, start + n))
    assert _stint_time(base, fuel, off, wear, start, n) == pytest.approx(loop)


def test_every_strategy_is_legal():
    sims = simulate(PARAMS, 57, 90, 22, CAPS)
    for plan in sims["plan"]:
        assert len(set(plan.split(" → "))) >= 2   # at least two different compounds
    for plan, pits in zip(sims["plan"], sims["pit_laps"]):
        bounds = [0, *pits, 57]
        for compound, start, end in zip(plan.split(" → "), bounds, bounds[1:]):
            assert 5 <= end - start <= CAPS[compound]   # every stint within its limits
    assert (sims["vs_best"] >= 0).all()


def test_heavy_wear_favors_two_stops_and_light_wear_one_stop():
    light = best_plans(simulate(PARAMS, 57, 90, 22, CAPS))
    heavy = best_plans(simulate({**PARAMS, "wear_SOFT": 0.4, "wear_MEDIUM": 0.3,
                                 "wear_HARD": 0.2}, 57, 90, 22, CAPS))
    assert light.iloc[0]["stops"] == 1
    assert heavy.iloc[0]["stops"] == 2


def test_mirror_image_plans_are_grouped():
    plans = best_plans(simulate(PARAMS, 57, 90, 22, CAPS))
    assert plans["plan"].is_unique
    assert "MEDIUM + SOFT" in set(plans["plan"])


def test_pit_loss_is_measured_from_in_and_out_laps():
    raw = simulate_races(TRUE, n_races=4, seed=3).assign(SEASON=2026, EVENT_NAME="Test GP")
    raw = raw.sort_values(["RACE_ROUND", "DRIVER_NUMBER", "LAP_NUMBER"]).reset_index(drop=True)
    raw["LAP_TIME_SEC"] = raw["PACE_RATIO"] * 90
    raw["PIT_OUT"] = (raw["TYRE_LIFE"] == 1) & (raw["LAP_NUMBER"] > 1)
    raw["PIT_IN"] = raw.groupby(["RACE_ROUND", "DRIVER_NUMBER"])["PIT_OUT"].shift(
        -1, fill_value=False).astype(bool)
    raw.loc[raw["PIT_IN"], "LAP_TIME_SEC"] += 8
    raw.loc[raw["PIT_OUT"], "LAP_TIME_SEC"] += 14     # 22 s lost per stop
    assert pit_loss_by_event(raw)["Test GP"] == pytest.approx(22, abs=1.0)
