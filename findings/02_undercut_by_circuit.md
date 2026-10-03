# Finding: Undercut Success Rate by Circuit

## Question
Does pitting first (attempting an "undercut") reliably gain track position,
and does this vary meaningfully by circuit?

## Method
For every pair of drivers running within 2 track positions of each other,
where one pitted at least 1 lap before the other, compared their relative
track position 10 laps after the first driver's stop. Built using
`RAW.PIT_STOPS` and `RAW.LAP_TIMES`, joined across each driver's position
immediately before their stop and again 10 laps later. Pit stop data in this
dataset is only available from 2011 onward (earlier seasons are not tracked
in the source). Circuits with fewer than 100 qualifying attempts across
2011-2025 were excluded to avoid small-sample noise.

A 10-lap recovery window was chosen after testing showed 1-3 laps was too
short to observe the undercut effect play out (tire degradation and pace
advantages compound gradually, not instantly).

## Result
Across 30 circuits with sufficient data, undercut success ranged from **9.9%
(Autódromo Hermanos Rodríguez, Mexico City) to 39.6% (Korean International
Circuit)**. Notable results:

| Circuit | Undercut Success Rate |
|---|---|
| Korean International Circuit | 39.6% |
| Shanghai International Circuit | 36.5% |
| Suzuka Circuit | 36.3% |
| Silverstone Circuit | 26.2% |
| Red Bull Ring | 24.4% |
| Circuit de Monaco | 21.9% |
| Autódromo Hermanos Rodríguez | 9.9% |

## Conclusion
Undercut success varies substantially by circuit — nearly a 4x difference
between the best and worst performing tracks. Circuits known for long
straights and hard-braking overtaking zones (Shanghai, Suzuka) cluster near
the top; tight, technical circuits with limited passing opportunity (Monaco)
cluster near the bottom. Mexico City is a notable outlier at the very bottom,
possibly related to its high-altitude characteristics affecting car
performance, though this warrants further investigation given its smaller
sample size relative to other top-tier circuits.

## Limitations
- The 10-lap window is a simplification — actual lap time varies significantly
  by circuit (e.g., ~75s at Monaco vs. ~105s at Spa), so "10 laps" represents
  different real-world time spans at different tracks.
- Korean International Circuit's result is based on a comparatively smaller
  sample (235 attempts) than other top-ranked circuits (900+ for Suzuka/Shanghai).
- Does not account for weather, safety car periods, or race-specific strategy
  context that could override the general pattern.