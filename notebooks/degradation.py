"""Shared helpers for the tire degradation notebooks."""
import numpy as np
import pandas as pd

DRY = ["SOFT", "MEDIUM", "HARD"]


# ---------------------------------------------------------------------------
# Shared model machinery
# ---------------------------------------------------------------------------
def _prepare(laps: pd.DataFrame, skip_opening_laps: int) -> pd.DataFrame:
    """Dry-tire laps only, minus the opening laps (start-of-race traffic)."""
    d = laps[laps["COMPOUND"].isin(DRY) & (laps["LAP_NUMBER"] > 1 + skip_opening_laps)].copy()
    d["PACE_PCT"] = (d["PACE_RATIO"] - 1) * 100
    return d


def _solve(d: pd.DataFrame, X: pd.DataFrame) -> pd.Series:
    """Least squares after removing each driver-race's average ("demeaning").

    Subtracting each driver-race's average from every column cancels out
    everything constant within one driver's race: car speed, circuit, conditions.
    """
    groups = [d["SEASON"], d["RACE_ROUND"], d["DRIVER_NUMBER"]]
    y = d["PACE_PCT"] - d.groupby(groups)["PACE_PCT"].transform("mean")
    Xd = X - X.groupby(groups).transform("mean")
    coef, *_ = np.linalg.lstsq(Xd.to_numpy(float), y.to_numpy(float), rcond=None)
    out = pd.Series(coef, index=X.columns)
    out["laps_used"] = len(d)
    return out


# ---------------------------------------------------------------------------
# Field-wide model (notebooks 01 and 02)
# ---------------------------------------------------------------------------
def fit_degradation(laps: pd.DataFrame, fuel_correction: bool = True,
                    skip_opening_laps: int = 0) -> pd.Series:
    """Estimate fuel effect and per-compound degradation, in % of race-median lap time.

    Model, for every clean lap:
        pace% = driver-race baseline
              + fuel  * lap_number                    (car gets lighter, faster)
              + deg_c * tyre_life      (per compound)  (tires wear, slower)
              + offset_c               (per compound)  (softs start faster)

    skip_opening_laps drops laps 2..(1 + n), where start-of-race traffic slows cars
    for reasons unrelated to tires (see notebook 02).
    """
    d = _prepare(laps, skip_opening_laps)
    X = pd.DataFrame(index=d.index)
    if fuel_correction:
        X["fuel"] = d["LAP_NUMBER"]
    for c in DRY:
        X[f"deg_{c}"] = d["TYRE_LIFE"] * (d["COMPOUND"] == c)
    X["offset_SOFT"] = (d["COMPOUND"] == "SOFT").astype(float)   # vs MEDIUM
    X["offset_HARD"] = (d["COMPOUND"] == "HARD").astype(float)   # vs MEDIUM
    return _solve(d, X)


# ---------------------------------------------------------------------------
# Team-specific model (notebook 03)
# ---------------------------------------------------------------------------
def eligible_teams(laps: pd.DataFrame, compounds=("MEDIUM", "HARD"),
                   min_laps: int = 150, skip_opening_laps: int = 5) -> dict:
    """Teams with at least `min_laps` usable laps on each compound.

    Decided once on the full data, so every bootstrap resample estimates the same terms.
    """
    d = _prepare(laps, skip_opening_laps)
    counts = d.groupby(["COMPOUND", "TEAM"]).size()
    return {c: sorted(counts.loc[c][counts.loc[c] >= min_laps].index)
            if c in counts.index.get_level_values(0) else [] for c in compounds}


def fit_team_degradation(laps: pd.DataFrame, eligible: dict,
                         skip_opening_laps: int = 5) -> pd.Series:
    """Like fit_degradation, but each eligible team gets its own wear rate on the
    compounds in `eligible`. Fuel, compound offsets, and soft wear stay shared.

    Output names look like "MEDIUM|McLaren". Teams below the lap threshold for a
    compound share one "MEDIUM|other teams" rate.
    """
    d = _prepare(laps, skip_opening_laps)
    X = pd.DataFrame(index=d.index)
    X["fuel"] = d["LAP_NUMBER"]
    for c in DRY:
        on_c = d["COMPOUND"] == c
        if c not in eligible:
            X[f"deg_{c}"] = d["TYRE_LIFE"] * on_c
            continue
        for team in eligible[c]:
            X[f"{c}|{team}"] = d["TYRE_LIFE"] * (on_c & (d["TEAM"] == team))
        others = on_c & ~d["TEAM"].isin(eligible[c])
        if others.any():
            X[f"{c}|other teams"] = d["TYRE_LIFE"] * others
    X["offset_SOFT"] = (d["COMPOUND"] == "SOFT").astype(float)
    X["offset_HARD"] = (d["COMPOUND"] == "HARD").astype(float)
    return _solve(d, X)


def partial_pool(raw: pd.Series, se: pd.Series, field: float) -> pd.DataFrame:
    """Shrink each team's estimate toward the field average, more so when uncertain.

    weight = spread_between_teams² / (spread_between_teams² + team_uncertainty²)

    A team with precise data (small uncertainty) keeps most of its own estimate;
    a team with noisy data is pulled toward the field. If teams barely differ
    beyond noise, everyone is pulled close to the field. This is "empirical Bayes".

    `se` should be the uncertainty of each team's DIFFERENCE from the field
    (measured within each bootstrap resample), not of its overall level: circuit-to-
    circuit variation moves every team together and isn't evidence about teams.
    """
    between = max(0.0, raw.var(ddof=1) - (se ** 2).mean())   # real spread, noise removed
    weight = between / (between + se ** 2) if between > 0 else se * 0
    pooled = field + weight * (raw - field)
    pooled_se = np.sqrt(weight) * se
    return pd.DataFrame({"raw": raw, "raw_se": se, "weight": weight,
                         "pooled": pooled, "low": pooled - 1.96 * pooled_se,
                         "high": pooled + 1.96 * pooled_se})


# ---------------------------------------------------------------------------
# Uncertainty
# ---------------------------------------------------------------------------
def bootstrap(laps: pd.DataFrame, n: int = 200, seed: int = 0,
              fit_fn=fit_degradation, **fit_kwargs) -> pd.DataFrame:
    """Refit a model on `n` resampled sets of races (drawn with replacement).

    Resampling whole races, not individual laps, matters: laps from the same race
    share conditions, so treating them as independent would make ranges too narrow.
    Returns one row of estimates per resample.
    """
    rng = np.random.default_rng(seed)
    by_race = {k: g for k, g in laps.groupby(["SEASON", "RACE_ROUND"])}
    keys = list(by_race)
    rows = []
    for _ in range(n):
        picks = rng.integers(0, len(keys), len(keys))
        # Give each drawn race its own ID, so a race drawn twice counts as two races
        sample = pd.concat([by_race[keys[k]].assign(SEASON=0, RACE_ROUND=i)
                            for i, k in enumerate(picks)])
        rows.append(fit_fn(sample, **fit_kwargs))
    return pd.DataFrame(rows)


def summarize(estimate: pd.Series, boot: pd.DataFrame, ref_lap: float = 90) -> pd.DataFrame:
    """Estimate with a 95% range, converted from % to seconds on a `ref_lap` lap."""
    cols = [c for c in ["fuel", "deg_SOFT", "deg_MEDIUM", "deg_HARD",
                        "offset_SOFT", "offset_HARD"] if c in estimate]
    k = ref_lap / 100
    return pd.DataFrame({
        "estimate": estimate[cols] * k,
        "low (2.5%)": boot[cols].quantile(0.025) * k,
        "high (97.5%)": boot[cols].quantile(0.975) * k,
    })


# ---------------------------------------------------------------------------
# Simulated data, for checking the methods recover known answers
# ---------------------------------------------------------------------------
def simulate_races(true: dict, n_races: int = 20, seed: int = 0,
                   team_wear: dict | None = None, circuit_spread: float = 0.0) -> pd.DataFrame:
    """Make fake clean laps with KNOWN fuel and degradation effects (in % per lap).

    Drivers are paired into 10 teams ("Team A".."Team J"). `team_wear` optionally
    multiplies a team's MEDIUM and HARD wear, e.g. {"Team A": 0.6} = 40% gentler.
    `circuit_spread` makes wear vary by circuit for everyone (0.5 = each race's wear
    is randomly 50% to 150% of normal), like real tracks that are harder on tires.
    """
    rng = np.random.default_rng(seed)
    offsets = {"SOFT": -0.6, "MEDIUM": 0.0, "HARD": 0.4}
    team_wear = team_wear or {}
    rows = []
    for race in range(n_races):
        circuit = rng.uniform(1 - circuit_spread, 1 + circuit_spread)
        for drv in range(20):
            team = f"Team {chr(65 + drv // 2)}"
            n = 58
            s1 = rng.integers(12, 26)
            s2 = rng.integers(s1 + 12, min(s1 + 28, n - 5))
            plan = [(1, s1, rng.choice(["SOFT", "MEDIUM"])), (s1 + 1, s2, "HARD"),
                    (s2 + 1, n, rng.choice(DRY))]
            if drv % 3 == 0:  # some one-stop races
                plan = [(1, s1 + 8, "MEDIUM"), (s1 + 9, n, "HARD")]
            base = rng.normal(0, 0.5)
            for stint, (a, b, c) in enumerate(plan, 1):
                wear = circuit * true[c] * (team_wear.get(team, 1.0) if c != "SOFT" else 1.0)
                for lap in range(a, b + 1):
                    life = lap - a + 1
                    pct = (base + true["fuel"] * lap + wear * life + offsets[c]
                           + rng.normal(0, 0.25))
                    rows.append(dict(SEASON=0, RACE_ROUND=race, DRIVER_NUMBER=drv,
                                     TEAM=team, LAP_NUMBER=lap, STINT=stint,
                                     COMPOUND=c, TYRE_LIFE=life, PACE_RATIO=1 + pct / 100))
    return pd.DataFrame(rows)
