USE DATABASE F1_PROJECT;
USE SCHEMA ANALYTICS;

SELECT
    rr.year,
    CASE WHEN rr.constructor_name = 'Ferrari' THEN 'Ferrari' ELSE 'All Other Teams' END AS team_group,
    COUNT(*) AS num_stops,
    AVG(ps.milliseconds / 1000) AS avg_pit_stop_seconds
FROM ANALYTICS.PIT_STOPS_ENRICHED ps
JOIN ANALYTICS.RACE_RESULTS_ENRICHED rr
    ON ps.raceId = rr.raceId AND ps.driverId = rr.driverId
WHERE ps.milliseconds IS NOT NULL
    AND ps.milliseconds < 60000
    AND rr.year >= 2020
GROUP BY rr.year, team_group
ORDER BY rr.year, team_group;


SELECT
    rr.constructor_name,
    COUNT(*) AS num_stops,
    AVG(ps.milliseconds / 1000) AS avg_pit_stop_seconds,
    MIN(ps.milliseconds / 1000) AS fastest_stop_seconds
FROM ANALYTICS.PIT_STOPS_ENRICHED ps
JOIN ANALYTICS.RACE_RESULTS_ENRICHED rr
    ON ps.raceId = rr.raceId AND ps.driverId = rr.driverId
WHERE ps.milliseconds IS NOT NULL
    AND ps.milliseconds < 60000
    AND rr.year >= 2020
GROUP BY rr.constructor_name
HAVING COUNT(*) >= 30
ORDER BY avg_pit_stop_seconds ASC;