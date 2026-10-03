# F1 Pit Strategy Analysis (2011–2025)

A data pipeline and analysis project exploring pit stop performance and undercut strategy
in Formula 1, built on Snowflake and visualized in Tableau. Created as a portfolio project
to apply SQL, data modeling, and statistical analysis to a real-world dataset.

**[→ View the live Tableau dashboard](https://public.tableau.com/app/profile/brian.earle1210/viz/F1PitStrategyAnalysis2011-2025/F1PitStrategyAnalysis2011-2025)**

## Overview

Using the Kaggle "Formula 1 World Championship (1950–2024)" dataset, this project builds
a two-layer Snowflake data warehouse and answers three questions:

1. Is Ferrari's pit crew actually as slow as the public narrative suggests?
2. Which circuits favor the "undercut" pit strategy most — and least?
3. Is undercut success actually explained by track length, or is that just a convenient story?

Each finding is backed by SQL queries against the full dataset and, for the third,
a statistical significance test rather than a visual guess.

## Data source

[Formula 1 World Championship (1950–2024)](https://www.kaggle.com/datasets/rohanrao/formula-1-world-championship-1950-2020)
on Kaggle (Ergast API archive). Note: pit stop and lap-by-lap timing data only exists from
the **2011 season onward** — earlier seasons weren't tracked at that granularity — so all
pit stop and undercut analysis here is scoped to 2011–2025.

## Architecture

Snowflake warehouse with two schemas:

- **RAW** — 14 tables loaded directly from the Kaggle CSVs via internal stage + `COPY INTO`
  (drivers, constructors, circuits, races, results, pit stops, lap times, standings, etc.)
- **ANALYTICS** — derived tables built with `CREATE TABLE AS SELECT`, joining and enriching
  the raw tables for analysis:
  - `PIT_STOPS_ENRICHED` — pit stops joined with driver, race, and constructor context
  - `RACE_RESULTS_ENRICHED` — race results joined with driver, constructor, and status context
  - `CIRCUIT_LENGTHS` — manually sourced reference table of lap length (km) per circuit
sql/
├── 01_setup_warehouse.sql — warehouse, database, schema, stage setup
├── 02_create_raw_tables.sql — RAW schema table definitions
├── 03_load_data.sql — COPY INTO statements loading all 14 raw tables
├── 04_analytics_schema.sql — ANALYTICS schema: enriched tables
├── ferrari_queries.sql — Finding 1 queries
└── undercut_overcut_analysis.sql — Findings 2 & 3 queries


## Findings

### 1. [Ferrari's Pit Stop Speed vs. the Field](findings/01_ferrari_pit_stops.md)
Contrary to the public narrative, Ferrari ranks near the top of the field for pit stop
speed since 2020 — averaging ~24.3s, just behind Red Bull's ~24.1s, and well ahead of
the slowest teams (Haas, Sauber, ~25.7–26s).

### 2. [Undercut Success Rate by Circuit](findings/02_undercut_by_circuit.md)
Undercut success varies enormously by track — from ~9.9% to ~39.6% across 30 circuits
with sufficient sample size (n≥100 attempts). Tracks like the Korean International
Circuit, Shanghai, and Suzuka favor the undercut most; Mexico City favors it least.

### 3. [Does Track Length Explain Undercut Success?](findings/03_lap_length_correlation.md)
Testing lap length as a measurable driver of undercut success rather than relying on
subjective "overtaking difficulty": a Pearson correlation of **r = 0.42** (p = 0.022,
statistically significant at the 95% level) shows a real but moderate relationship —
track length explains roughly 17% of the variance in undercut success (r² ≈ 0.17),
meaning it's a contributing factor, not the whole story.

## Dashboard

The [Tableau Public dashboard](https://public.tableau.com/app/profile/brian.earle1210/viz/F1PitStrategyAnalysis2011-2025/F1PitStrategyAnalysis2011-2025)
visualizes all three findings:
- Ferrari pit stop speed vs. the field (2020–2025), highlighted against the average
- Undercut success rate by circuit, color-graded by success rate
- Lap length vs. undercut success, with trend line and correlation coefficient

## Tools used

- **Snowflake** — data warehousing, SQL transformation
- **SQL** — joins, CTEs, aggregate functions, correlation analysis (`CORR()`)
- **Python (scipy)** — statistical significance testing (p-value calculation)
- **Tableau Public** — dashboard and data visualization
- **Git/GitHub** — version control

## Data files

The `data/` folder contains the exported CSV extracts used to build the Tableau
dashboard, generated from the ANALYTICS queries above.
