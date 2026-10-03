# Finding: Ferrari's 2020s Pit Stop Performance

## Question
Public narrative frequently criticizes Ferrari for slow, error-prone pit stops.
Does this hold up against actual timing data from 2020-2025?

## Method
Compared average pit stop duration (in seconds) across all constructors from the
2020 season onward, using `ANALYTICS.PIT_STOPS_ENRICHED` joined against
`ANALYTICS.RACE_RESULTS_ENRICHED`. Stops over 60 seconds were excluded as
non-standard (penalties, mechanical issues, not representative tire changes).
Only constructors with 30+ recorded stops in the window were included.

## Result
Ferrari ranked among the **fastest** teams in the field during this period,
with an average stop of roughly 24.3 seconds — tied closely with Mercedes and
just behind Red Bull (the fastest team, ~24.1s). The slowest teams in the same
window were Haas (~26.1s) and Sauber (~25.7s).

## Conclusion
**The data does not support the narrative that Ferrari has been a consistently
slow pit crew in the 2020s.** On raw average stop duration, Ferrari performs
at or near the top of the field. Public criticism of Ferrari's pit stops is
more likely driven by a small number of highly visible, high-stakes errors
(e.g., incorrect tire fitted, red-light release incidents) rather than
systematic slowness — a distinction averages alone can't fully resolve, but
one worth noting as a limitation.

## Limitations
- This measures *average* duration only — it does not capture error rate
  (wrong tires, unsafe releases, procedural mistakes), which may be the real
  driver of the public narrative.
- Does not control for race-specific pressure/strategy complexity.