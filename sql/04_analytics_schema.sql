-- ============================================
-- ANALYTICS SCHEMA: enriched, human-readable tables
-- Joins RAW tables into analysis-ready views
-- ============================================

USE DATABASE F1_PROJECT;
USE SCHEMA ANALYTICS;

-- Every pit stop with driver name, race name, and constructor name attached
CREATE OR REPLACE TABLE ANALYTICS.PIT_STOPS_ENRICHED AS
SELECT
    ps.raceId,
    r.year,
    r.name AS race_name,
    r.round,
    d.driverId,
    d.forename || ' ' || d.surname AS driver_name,
    c.name AS constructor_name,
    ps.stop,
    ps.lap,
    ps.duration,
    ps.milliseconds
FROM RAW.PIT_STOPS ps
JOIN RAW.DRIVERS d ON ps.driverId = d.driverId
JOIN RAW.RACES r ON ps.raceId = r.raceId
JOIN RAW.RESULTS res ON ps.raceId = res.raceId AND ps.driverId = res.driverId
JOIN RAW.CONSTRUCTORS c ON res.constructorId = c.constructorId;

-- Every race result with driver name, constructor name, and finish status attached
CREATE OR REPLACE TABLE ANALYTICS.RACE_RESULTS_ENRICHED AS
SELECT
    res.raceId,
    r.year,
    r.name AS race_name,
    r.round,
    d.driverId,
    d.forename || ' ' || d.surname AS driver_name,
    c.name AS constructor_name,
    res.grid AS starting_position,
    res.positionOrder AS finishing_position,
    res.points,
    res.laps,
    s.status
FROM RAW.RESULTS res
JOIN RAW.DRIVERS d ON res.driverId = d.driverId
JOIN RAW.RACES r ON res.raceId = r.raceId
JOIN RAW.CONSTRUCTORS c ON res.constructorId = c.constructorId
JOIN RAW.STATUS s ON res.statusId = s.statusId;

-- Sanity checks
SELECT * FROM ANALYTICS.PIT_STOPS_ENRICHED LIMIT 10;
SELECT * FROM ANALYTICS.RACE_RESULTS_ENRICHED LIMIT 10;