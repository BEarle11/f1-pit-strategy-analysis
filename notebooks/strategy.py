"""Race strategy simulator: compare one-stop and two-stop plans for a team at a circuit.

Lap time model (same as the degradation notebooks), in seconds:
    lap = base * (1 + (fuel * lap_number + offset_c + wear_c * tire_age) / 100)

Everything is in % of the circuit's typical lap ("base"), converted to seconds at the end.
"""
from itertools import product

import numpy as np
import pandas as pd
import requests

from degradation import DRY, fit_degradation

DEFAULT_PIT_LOSS = 22.0   # seconds, used when a circuit has too few measured stops
DEFAULT_LAPS = 57
DEFAULT_BASE = 90.0


# ---------------------------------------------------------------------------
# Circuit facts measured from our own data
# ---------------------------------------------------------------------------
def pit_loss_by_event(raw: pd.DataFrame, min_stops: int = 5) -> pd.Series:
    """Seconds lost to one pit stop at each event.

    For every stop: (pit-in lap + pit-out lap) - 2 x that driver's typical lap
    in that race. That captures the whole cost: slowing for the pit lane, the stop
    itself, and rejoining. The median per event resists outliers (slow stops,
    stops under safety car).
    """
    d = raw.sort_values(["SEASON", "RACE_ROUND", "DRIVER_NUMBER", "LAP_NUMBER"]).copy()
    key = ["SEASON", "RACE_ROUND", "DRIVER_NUMBER"]
    race_median = d.groupby(["SEASON", "RACE_ROUND"])["LAP_TIME_SEC"].transform("median")
    green = (~d["PIT_IN"]) & (~d["PIT_OUT"]) & (d["LAP_TIME_SEC"] <= 1.07 * race_median)
    d["TYPICAL"] = d["LAP_TIME_SEC"].where(green).groupby([d[k] for k in key]).transform("median")
    d["NEXT_TIME"] = d.groupby(key)["LAP_TIME_SEC"].shift(-1)
    d["NEXT_OUT"] = d.groupby(key)["PIT_OUT"].shift(-1, fill_value=False)

    stops = d[d["PIT_IN"] & d["NEXT_OUT"]].copy()
    stops["LOSS"] = stops["LAP_TIME_SEC"] + stops["NEXT_TIME"] - 2 * stops["TYPICAL"]
    stops = stops[stops["LOSS"].between(5, 60)]          # drop broken or safety-car stops
    per_event = stops.groupby("EVENT_NAME")["LOSS"].agg(["median", "size"])
    return per_event.loc[per_event["size"] >= min_stops, "median"]


def max_stint_laps(raw: pd.DataFrame, season: int, quantile: float = 0.95) -> pd.Series:
    """Longest realistic stint per compound: the 95th percentile of real stint lengths.

    Our wear model is a straight line and can't see a tire "falling off a cliff",
    so this caps stints at lengths teams actually run.
    """
    d = raw[(raw["SEASON"] == season) & raw["COMPOUND"].isin(DRY)]
    stints = d.groupby(["RACE_ROUND", "DRIVER_NUMBER", "STINT", "COMPOUND"]).size()
    caps = stints.groupby(level="COMPOUND").quantile(quantile).round().astype(int)
    return caps.rename(index=str)


def circuit_profile(event: str, raw: pd.DataFrame, clean: pd.DataFrame,
                    pit_losses: pd.Series, all_wear: pd.Series, skip: int = 5) -> dict:
    """Laps, typical lap time, pit loss, and how hard the circuit is on tires.

    Wear factor: this circuit's medium/hard wear vs the all-circuit average, from
    every past race here. Like the team rates, it's pulled toward 1.0 (average)
    when there are few races: weight = races / (races + 2).
    """
    past_raw = raw[raw["EVENT_NAME"] == event]
    past_clean = clean[clean["EVENT_NAME"] == event]
    n_races = past_clean[["SEASON", "RACE_ROUND"]].drop_duplicates().shape[0]

    if past_raw.empty:
        laps, base = DEFAULT_LAPS, DEFAULT_BASE
    else:
        latest = past_raw[past_raw["SEASON"] == past_raw["SEASON"].max()]
        laps = int(latest["LAP_NUMBER"].max())
        base = float(latest["LAP_TIME_SEC"].median())

    raw_factor = np.nan
    if n_races > 0:
        est = fit_degradation(past_clean, skip_opening_laps=skip)
        ratios = [est[f"deg_{c}"] / all_wear[f"deg_{c}"] for c in ["MEDIUM", "HARD"]
                  if est[f"deg_{c}"] > 0 and est["laps_used"] > 200]
        if ratios:
            raw_factor = float(np.clip(np.mean(ratios), 0.3, 3.0))
    weight = n_races / (n_races + 2) if not np.isnan(raw_factor) else 0.0
    factor = 1 + weight * ((raw_factor if weight else 1.0) - 1)

    return {"event": event, "laps": laps, "base_lap": base, "past_races": n_races,
            "pit_loss": float(pit_losses.get(event, DEFAULT_PIT_LOSS)),
            "pit_loss_measured": event in pit_losses.index,
            "wear_factor_raw": raw_factor, "wear_factor": factor}


# ---------------------------------------------------------------------------
# The simulator
# ---------------------------------------------------------------------------
def _stint_time(base, fuel, offset, wear, start, length):
    """Total seconds for a stint on fresh tires covering laps start..start+length-1.

    Closed form of the lap model summed over the stint (no loop needed):
    sum of lap numbers = length*(2*start+length-1)/2, sum of tire ages = length*(length+1)/2
    """
    sum_laps = length * (2 * start + length - 1) / 2
    sum_age = length * (length + 1) / 2
    return base * length + base / 100 * (fuel * sum_laps + offset * length + wear * sum_age)


def simulate(params: dict, laps: int, base: float, pit_loss: float, max_stint: dict,
             min_stint: int = 5) -> pd.DataFrame:
    """Total race time for every legal one-stop and two-stop strategy.

    params: fuel, offset_SOFT/MEDIUM/HARD, wear_SOFT/MEDIUM/HARD (all in % per lap).
    Rules: at least two different dry compounds; every stint between min_stint
    laps and the compound's max_stint.
    """
    rows = []
    off = {"SOFT": params["offset_SOFT"], "MEDIUM": 0.0, "HARD": params["offset_HARD"]}

    def stint(c, start, length):
        return _stint_time(base, params["fuel"], off[c], params[f"wear_{c}"], start, length)

    def ok(c, length):
        return min_stint <= length <= max_stint.get(c, laps)

    for c1, c2 in product(DRY, DRY):
        if c1 == c2:
            continue
        for p in range(1, laps):
            n1, n2 = p, laps - p
            if ok(c1, n1) and ok(c2, n2):
                rows.append((1, f"{c1} → {c2}", (p,),
                             stint(c1, 1, n1) + stint(c2, p + 1, n2) + pit_loss))

    for c1, c2, c3 in product(DRY, DRY, DRY):
        if len({c1, c2, c3}) < 2:
            continue
        for p1 in range(min_stint, laps):
            if not ok(c1, p1):
                continue
            t1 = stint(c1, 1, p1)
            for p2 in range(p1 + min_stint, laps - min_stint + 1):
                n2, n3 = p2 - p1, laps - p2
                if ok(c2, n2) and ok(c3, n3):
                    rows.append((2, f"{c1} → {c2} → {c3}", (p1, p2),
                                 t1 + stint(c2, p1 + 1, n2) + stint(c3, p2 + 1, n3)
                                 + 2 * pit_loss))

    out = pd.DataFrame(rows, columns=["stops", "plan", "pit_laps", "race_time"])
    out["vs_best"] = out["race_time"] - out["race_time"].min()
    return out


def best_plans(sims: pd.DataFrame, window_s: float = 1.0) -> pd.DataFrame:
    """Best version of each plan, plus its pit window.

    In this model the ORDER of stints doesn't change the total (fuel affects every
    compound equally), so mirror-image plans tie. They're grouped as one plan,
    e.g. "MEDIUM + HARD", showing the best order.

    Pit window (one-stops): every pit lap that costs less than `window_s` seconds
    versus that plan's best lap. A wide window means the timing barely matters.
    """
    sims = sims.copy()
    sims["group"] = sims["plan"].map(lambda p: " + ".join(sorted(p.split(" → "))))
    rows = []
    for group, g in sims.groupby("group"):
        best = g.loc[g["race_time"].idxmin()]
        row = {"plan": group, "stops": best["stops"], "best order": best["plan"],
               "pit_laps": best["pit_laps"], "vs_best": best["vs_best"], "window": ""}
        if best["stops"] == 1:
            same = g[g["plan"] == best["plan"]]
            near = same[same["race_time"] <= best["race_time"] + window_s]["pit_laps"].str[0]
            row["window"] = f"laps {near.min()}–{near.max()}"
        rows.append(row)
    return pd.DataFrame(rows).sort_values("vs_best").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Upcoming races (OpenF1)
# ---------------------------------------------------------------------------
def upcoming_races(year: int) -> pd.DataFrame:
    """Races later this season, with their event names, from the OpenF1 API."""
    api = "https://api.openf1.org/v1"
    races = pd.DataFrame(requests.get(f"{api}/sessions", timeout=30,
                                      params={"year": year, "session_name": "Race"}).json())
    meetings = pd.DataFrame(requests.get(f"{api}/meetings", timeout=30,
                                         params={"year": year}).json())
    races = races.merge(meetings[["meeting_key", "meeting_name"]], on="meeting_key")
    if "is_cancelled" in races:
        races = races[races["is_cancelled"] != True]  # noqa: E712
    races["date_start"] = pd.to_datetime(races["date_start"], utc=True)
    races = races[races["date_start"] > pd.Timestamp.now(tz="UTC")].sort_values("date_start")
    return races[["meeting_name", "circuit_short_name", "date_start"]].reset_index(drop=True)
