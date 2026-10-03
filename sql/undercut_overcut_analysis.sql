USE DATABASE F1_PROJECT;
USE SCHEMA ANALYTICS;

SELECT DISTINCT circuitId, name 
FROM RAW.CIRCUITS 
WHERE LOWER(name) LIKE '%spa%' OR LOWER(location) LIKE '%spa%';

SELECT raceId, year, name, date 
FROM RAW.RACES 
WHERE circuitId = (SELECT circuitId FROM RAW.CIRCUITS WHERE LOWER(name) LIKE '%spa%' LIMIT 1)
ORDER BY year DESC
LIMIT 10;

SELECT raceId, year, name, date 
FROM RAW.RACES 
WHERE circuitId = (SELECT circuitId FROM RAW.CIRCUITS WHERE LOWER(name) LIKE '%spa%' LIMIT 1)
  AND year = 2023;


SELECT 
    lt.driverId,
    rr.driver_name,
    lt.lap,
    lt.position,
    ps.stop,
    ps.milliseconds AS pit_duration_ms
FROM RAW.LAP_TIMES lt
JOIN ANALYTICS.RACE_RESULTS_ENRICHED rr 
    ON lt.raceId = rr.raceId AND lt.driverId = rr.driverId
LEFT JOIN RAW.PIT_STOPS ps 
    ON lt.raceId = ps.raceId AND lt.driverId = ps.driverId AND lt.lap = ps.lap
WHERE lt.raceId = 1110
ORDER BY lt.lap, lt.position;


SELECT 
    ps.driverId,
    rr.driver_name,
    ps.lap AS pit_lap,
    ps.milliseconds AS pit_duration_ms,
    lt_before.position AS position_before_pit,
    lt_after.position AS position_after_pit
FROM RAW.PIT_STOPS ps
JOIN ANALYTICS.RACE_RESULTS_ENRICHED rr 
    ON ps.raceId = rr.raceId AND ps.driverId = rr.driverId
LEFT JOIN RAW.LAP_TIMES lt_before 
    ON ps.raceId = lt_before.raceId AND ps.driverId = lt_before.driverId AND lt_before.lap = ps.lap - 1
LEFT JOIN RAW.LAP_TIMES lt_after 
    ON ps.raceId = lt_after.raceId AND ps.driverId = lt_after.driverId AND lt_after.lap = ps.lap + 1
WHERE ps.raceId = 1110
ORDER BY ps.lap;


SELECT 
    ps.driverId,
    rr.driver_name,
    ps.lap AS pit_lap,
    lt_before.position AS position_before_pit,
    lt_after1.position AS position_1lap_after,
    lt_after3.position AS position_3laps_after
FROM RAW.PIT_STOPS ps
JOIN ANALYTICS.RACE_RESULTS_ENRICHED rr 
    ON ps.raceId = rr.raceId AND ps.driverId = rr.driverId
LEFT JOIN RAW.LAP_TIMES lt_before 
    ON ps.raceId = lt_before.raceId AND ps.driverId = lt_before.driverId AND lt_before.lap = ps.lap - 1
LEFT JOIN RAW.LAP_TIMES lt_after1 
    ON ps.raceId = lt_after1.raceId AND ps.driverId = lt_after1.driverId AND lt_after1.lap = ps.lap + 1
LEFT JOIN RAW.LAP_TIMES lt_after3 
    ON ps.raceId = lt_after3.raceId AND ps.driverId = lt_after3.driverId AND lt_after3.lap = ps.lap + 3
WHERE ps.raceId = 1110
ORDER BY ps.lap;


SELECT 
    ps.driverId,
    rr.driver_name,
    ps.lap AS pit_lap,
    lt_before.position AS position_before_pit,
    lt_after1.position AS position_1lap_after,
    lt_after5.position AS position_5laps_after,
    lt_after10.position AS position_10laps_after
FROM RAW.PIT_STOPS ps
JOIN ANALYTICS.RACE_RESULTS_ENRICHED rr 
    ON ps.raceId = rr.raceId AND ps.driverId = rr.driverId
LEFT JOIN RAW.LAP_TIMES lt_before 
    ON ps.raceId = lt_before.raceId AND ps.driverId = lt_before.driverId AND lt_before.lap = ps.lap - 1
LEFT JOIN RAW.LAP_TIMES lt_after1 
    ON ps.raceId = lt_after1.raceId AND ps.driverId = lt_after1.driverId AND lt_after1.lap = ps.lap + 1
LEFT JOIN RAW.LAP_TIMES lt_after5 
    ON ps.raceId = lt_after5.raceId AND ps.driverId = lt_after5.driverId AND lt_after5.lap = ps.lap + 5
LEFT JOIN RAW.LAP_TIMES lt_after10 
    ON ps.raceId = lt_after10.raceId AND ps.driverId = lt_after10.driverId AND lt_after10.lap = ps.lap + 10
WHERE ps.raceId = 1110
ORDER BY ps.lap;



WITH pit_summary AS (
    SELECT 
        ps.driverId,
        rr.driver_name,
        ps.lap AS pit_lap,
        lt_before.position AS position_before_pit
    FROM RAW.PIT_STOPS ps
    JOIN ANALYTICS.RACE_RESULTS_ENRICHED rr 
        ON ps.raceId = rr.raceId AND ps.driverId = rr.driverId
    LEFT JOIN RAW.LAP_TIMES lt_before 
        ON ps.raceId = lt_before.raceId AND ps.driverId = lt_before.driverId AND lt_before.lap = ps.lap - 1
    WHERE ps.raceId = 1110
)
SELECT
    a.driver_name AS driver_a,
    a.pit_lap AS driver_a_pit_lap,
    a.position_before_pit AS driver_a_position_before,
    b.driver_name AS driver_b,
    b.pit_lap AS driver_b_pit_lap,
    b.position_before_pit AS driver_b_position_before,
    lt_a_later.position AS driver_a_position_after,
    lt_b_later.position AS driver_b_position_after,
    CASE 
        WHEN lt_a_later.position < lt_b_later.position THEN 'Undercut WORKED (A jumped ahead)'
        WHEN lt_a_later.position > lt_b_later.position THEN 'Undercut FAILED (B stayed ahead)'
        ELSE 'No change'
    END AS verdict
FROM pit_summary a
JOIN pit_summary b 
    ON a.driverId != b.driverId
    AND ABS(a.position_before_pit - b.position_before_pit) <= 2
    AND a.pit_lap < b.pit_lap
    AND a.position_before_pit > b.position_before_pit  -- A was BEHIND B before pitting (so a jump ahead is a real undercut)
LEFT JOIN RAW.LAP_TIMES lt_a_later 
    ON lt_a_later.raceId = 1110 AND lt_a_later.driverId = a.driverId AND lt_a_later.lap = a.pit_lap + 10
LEFT JOIN RAW.LAP_TIMES lt_b_later 
    ON lt_b_later.raceId = 1110 AND lt_b_later.driverId = b.driverId AND lt_b_later.lap = a.pit_lap + 10
WHERE lt_a_later.position IS NOT NULL AND lt_b_later.position IS NOT NULL
ORDER BY verdict, a.pit_lap;



WITH spa_races AS (
    SELECT raceId, year
    FROM RAW.RACES 
    WHERE circuitId = (SELECT circuitId FROM RAW.CIRCUITS WHERE LOWER(name) LIKE '%spa%' LIMIT 1)
      AND year >= 2011
),
pit_summary AS (
    SELECT 
        ps.raceId,
        sr.year,
        ps.driverId,
        rr.driver_name,
        ps.lap AS pit_lap,
        lt_before.position AS position_before_pit
    FROM RAW.PIT_STOPS ps
    JOIN spa_races sr ON ps.raceId = sr.raceId
    JOIN ANALYTICS.RACE_RESULTS_ENRICHED rr 
        ON ps.raceId = rr.raceId AND ps.driverId = rr.driverId
    LEFT JOIN RAW.LAP_TIMES lt_before 
        ON ps.raceId = lt_before.raceId AND ps.driverId = lt_before.driverId AND lt_before.lap = ps.lap - 1
)
SELECT
    a.year,
    COUNT(*) AS total_undercut_attempts,
    SUM(CASE WHEN lt_a_later.position < lt_b_later.position THEN 1 ELSE 0 END) AS undercut_worked,
    SUM(CASE WHEN lt_a_later.position >= lt_b_later.position THEN 1 ELSE 0 END) AS undercut_failed,
    ROUND(100.0 * SUM(CASE WHEN lt_a_later.position < lt_b_later.position THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_undercut_worked
FROM pit_summary a
JOIN pit_summary b 
    ON a.raceId = b.raceId
    AND a.driverId != b.driverId
    AND ABS(a.position_before_pit - b.position_before_pit) <= 2
    AND a.pit_lap < b.pit_lap
    AND a.position_before_pit > b.position_before_pit
LEFT JOIN RAW.LAP_TIMES lt_a_later 
    ON lt_a_later.raceId = a.raceId AND lt_a_later.driverId = a.driverId AND lt_a_later.lap = a.pit_lap + 10
LEFT JOIN RAW.LAP_TIMES lt_b_later 
    ON lt_b_later.raceId = b.raceId AND lt_b_later.driverId = b.driverId AND lt_b_later.lap = a.pit_lap + 10
WHERE lt_a_later.position IS NOT NULL AND lt_b_later.position IS NOT NULL
GROUP BY a.year
ORDER BY a.year;


SELECT circuitId, name, location, country
FROM RAW.CIRCUITS
WHERE LOWER(name) LIKE '%silverstone%'
   OR LOWER(name) LIKE '%suzuka%'
   OR LOWER(name) LIKE '%monaco%'
   OR LOWER(name) LIKE '%red bull ring%'
   OR LOWER(name) LIKE '%a1-ring%'  -- older name for the same Austria circuit
ORDER BY name;

WITH target_circuits AS (
    SELECT circuitId, name AS circuit_name
    FROM RAW.CIRCUITS
    WHERE circuitId IN (6, 70, 9, 22)
),
target_races AS (
    SELECT r.raceId, r.year, tc.circuit_name
    FROM RAW.RACES r
    JOIN target_circuits tc ON r.circuitId = tc.circuitId
    WHERE r.year >= 2011
),
pit_summary AS (
    SELECT 
        ps.raceId,
        tr.circuit_name,
        ps.driverId,
        ps.lap AS pit_lap,
        lt_before.position AS position_before_pit
    FROM RAW.PIT_STOPS ps
    JOIN target_races tr ON ps.raceId = tr.raceId
    LEFT JOIN RAW.LAP_TIMES lt_before 
        ON ps.raceId = lt_before.raceId AND ps.driverId = lt_before.driverId AND lt_before.lap = ps.lap - 1
)
SELECT
    a.circuit_name,
    COUNT(*) AS total_undercut_attempts,
    SUM(CASE WHEN lt_a_later.position < lt_b_later.position THEN 1 ELSE 0 END) AS undercut_worked,
    ROUND(100.0 * SUM(CASE WHEN lt_a_later.position < lt_b_later.position THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_undercut_worked
FROM pit_summary a
JOIN pit_summary b 
    ON a.raceId = b.raceId
    AND a.driverId != b.driverId
    AND ABS(a.position_before_pit - b.position_before_pit) <= 2
    AND a.pit_lap < b.pit_lap
    AND a.position_before_pit > b.position_before_pit
LEFT JOIN RAW.LAP_TIMES lt_a_later 
    ON lt_a_later.raceId = a.raceId AND lt_a_later.driverId = a.driverId AND lt_a_later.lap = a.pit_lap + 10
LEFT JOIN RAW.LAP_TIMES lt_b_later 
    ON lt_b_later.raceId = b.raceId AND lt_b_later.driverId = b.driverId AND lt_b_later.lap = a.pit_lap + 10
WHERE lt_a_later.position IS NOT NULL AND lt_b_later.position IS NOT NULL
GROUP BY a.circuit_name
ORDER BY pct_undercut_worked DESC;


WITH target_races AS (
    SELECT r.raceId, r.year, c.name AS circuit_name, c.circuitId
    FROM RAW.RACES r
    JOIN RAW.CIRCUITS c ON r.circuitId = c.circuitId
    WHERE r.year >= 2011
),
pit_summary AS (
    SELECT 
        ps.raceId,
        tr.circuit_name,
        ps.driverId,
        ps.lap AS pit_lap,
        lt_before.position AS position_before_pit
    FROM RAW.PIT_STOPS ps
    JOIN target_races tr ON ps.raceId = tr.raceId
    LEFT JOIN RAW.LAP_TIMES lt_before 
        ON ps.raceId = lt_before.raceId AND ps.driverId = lt_before.driverId AND lt_before.lap = ps.lap - 1
)
SELECT
    a.circuit_name,
    COUNT(*) AS total_undercut_attempts,
    SUM(CASE WHEN lt_a_later.position < lt_b_later.position THEN 1 ELSE 0 END) AS undercut_worked,
    ROUND(100.0 * SUM(CASE WHEN lt_a_later.position < lt_b_later.position THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_undercut_worked
FROM pit_summary a
JOIN pit_summary b 
    ON a.raceId = b.raceId
    AND a.driverId != b.driverId
    AND ABS(a.position_before_pit - b.position_before_pit) <= 2
    AND a.pit_lap < b.pit_lap
    AND a.position_before_pit > b.position_before_pit
LEFT JOIN RAW.LAP_TIMES lt_a_later 
    ON lt_a_later.raceId = a.raceId AND lt_a_later.driverId = a.driverId AND lt_a_later.lap = a.pit_lap + 10
LEFT JOIN RAW.LAP_TIMES lt_b_later 
    ON lt_b_later.raceId = b.raceId AND lt_b_later.driverId = b.driverId AND lt_b_later.lap = a.pit_lap + 10
WHERE lt_a_later.position IS NOT NULL AND lt_b_later.position IS NOT NULL
GROUP BY a.circuit_name
HAVING COUNT(*) >= 100  -- drop circuits with too few races/attempts to be reliable
ORDER BY pct_undercut_worked DESC;



CREATE OR REPLACE TABLE ANALYTICS.CIRCUIT_LENGTHS (
    circuit_name STRING,
    lap_length_km FLOAT
);

INSERT INTO ANALYTICS.CIRCUIT_LENGTHS (circuit_name, lap_length_km) VALUES
('Korean International Circuit', 5.615),
('Shanghai International Circuit', 5.451),
('Suzuka Circuit', 5.807),
('Autódromo Internacional do Algarve', 4.653),
('Autodromo Internazionale del Mugello', 5.245),
('Autodromo Nazionale di Monza', 5.793),
('Circuit de Spa-Francorchamps', 7.004),
('Baku City Circuit', 6.003),
('Hockenheimring', 4.574),
('Marina Bay Street Circuit', 4.940),
('Sepang International Circuit', 5.543),
('Circuit de Barcelona-Catalunya', 4.655),
('Albert Park Grand Prix Circuit', 5.278),
('Circuit of the Americas', 5.513),
('Valencia Street Circuit', 5.419),
('Losail International Circuit', 5.380),
('Istanbul Park', 5.338),
('Bahrain International Circuit', 5.412),
('Las Vegas Strip Street Circuit', 6.201),
('Autódromo José Carlos Pace', 4.309),
('Autodromo Enzo e Dino Ferrari', 4.909),
('Silverstone Circuit', 5.891),
('Hungaroring', 4.381),
('Red Bull Ring', 4.318),
('Nürburgring', 5.148),
('Circuit Gilles Villeneuve', 4.361),
('Yas Marina Circuit', 5.281),
('Circuit de Monaco', 3.337),
('Circuit Park Zandvoort', 4.259),
('Buddh International Circuit', 5.125),
('Sochi Autodrom', 5.848),
('Autódromo Hermanos Rodríguez', 4.304);


WITH target_races AS (
    SELECT r.raceId, r.year, c.name AS circuit_name, c.circuitId
    FROM RAW.RACES r
    JOIN RAW.CIRCUITS c ON r.circuitId = c.circuitId
    WHERE r.year >= 2011
),
pit_summary AS (
    SELECT 
        ps.raceId,
        tr.circuit_name,
        ps.driverId,
        ps.lap AS pit_lap,
        lt_before.position AS position_before_pit
    FROM RAW.PIT_STOPS ps
    JOIN target_races tr ON ps.raceId = tr.raceId
    LEFT JOIN RAW.LAP_TIMES lt_before 
        ON ps.raceId = lt_before.raceId AND ps.driverId = lt_before.driverId AND lt_before.lap = ps.lap - 1
),
undercut_results AS (
    SELECT
        a.circuit_name,
        COUNT(*) AS total_undercut_attempts,
        ROUND(100.0 * SUM(CASE WHEN lt_a_later.position < lt_b_later.position THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_undercut_worked
    FROM pit_summary a
    JOIN pit_summary b 
        ON a.raceId = b.raceId
        AND a.driverId != b.driverId
        AND ABS(a.position_before_pit - b.position_before_pit) <= 2
        AND a.pit_lap < b.pit_lap
        AND a.position_before_pit > b.position_before_pit
    LEFT JOIN RAW.LAP_TIMES lt_a_later 
        ON lt_a_later.raceId = a.raceId AND lt_a_later.driverId = a.driverId AND lt_a_later.lap = a.pit_lap + 10
    LEFT JOIN RAW.LAP_TIMES lt_b_later 
        ON lt_b_later.raceId = b.raceId AND lt_b_later.driverId = b.driverId AND lt_b_later.lap = a.pit_lap + 10
    WHERE lt_a_later.position IS NOT NULL AND lt_b_later.position IS NOT NULL
    GROUP BY a.circuit_name
    HAVING COUNT(*) >= 100
)
SELECT
    CORR(cl.lap_length_km, ur.pct_undercut_worked) AS correlation_coefficient,
    COUNT(*) AS num_circuits
FROM undercut_results ur
JOIN ANALYTICS.CIRCUIT_LENGTHS cl ON ur.circuit_name = cl.circuit_name;




WITH target_races AS (
    SELECT r.raceId, r.year, c.name AS circuit_name, c.circuitId
    FROM RAW.RACES r
    JOIN RAW.CIRCUITS c ON r.circuitId = c.circuitId
    WHERE r.year >= 2011
),
pit_summary AS (
    SELECT 
        ps.raceId,
        tr.circuit_name,
        ps.driverId,
        ps.lap AS pit_lap,
        lt_before.position AS position_before_pit
    FROM RAW.PIT_STOPS ps
    JOIN target_races tr ON ps.raceId = tr.raceId
    LEFT JOIN RAW.LAP_TIMES lt_before 
        ON ps.raceId = lt_before.raceId AND ps.driverId = lt_before.driverId AND lt_before.lap = ps.lap - 1
),
undercut_results AS (
    SELECT
        a.circuit_name,
        COUNT(*) AS total_undercut_attempts,
        ROUND(100.0 * SUM(CASE WHEN lt_a_later.position < lt_b_later.position THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_undercut_worked
    FROM pit_summary a
    JOIN pit_summary b 
        ON a.raceId = b.raceId
        AND a.driverId != b.driverId
        AND ABS(a.position_before_pit - b.position_before_pit) <= 2
        AND a.pit_lap < b.pit_lap
        AND a.position_before_pit > b.position_before_pit
    LEFT JOIN RAW.LAP_TIMES lt_a_later 
        ON lt_a_later.raceId = a.raceId AND lt_a_later.driverId = a.driverId AND lt_a_later.lap = a.pit_lap + 10
    LEFT JOIN RAW.LAP_TIMES lt_b_later 
        ON lt_b_later.raceId = b.raceId AND lt_b_later.driverId = b.driverId AND lt_b_later.lap = a.pit_lap + 10
    WHERE lt_a_later.position IS NOT NULL AND lt_b_later.position IS NOT NULL
    GROUP BY a.circuit_name
    HAVING COUNT(*) >= 100
)
SELECT
    ur.circuit_name,
    cl.lap_length_km,
    ur.total_undercut_attempts,
    ur.pct_undercut_worked
FROM undercut_results ur
JOIN ANALYTICS.CIRCUIT_LENGTHS cl ON ur.circuit_name = cl.circuit_name
ORDER BY cl.lap_length_km DESC;