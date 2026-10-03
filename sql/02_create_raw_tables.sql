-- ============================================
-- RAW TABLE DEFINITIONS
-- Source: Kaggle "Formula 1 World Championship (1950-2024)"
-- https://www.kaggle.com/datasets/rohanrao/formula-1-world-championship-1950-2020
-- ============================================

USE DATABASE F1_PROJECT;
USE SCHEMA RAW;

CREATE OR REPLACE TABLE DRIVERS (
  driverId INT, driverRef STRING, number STRING, code STRING,
  forename STRING, surname STRING, dob DATE, nationality STRING, url STRING
);

CREATE OR REPLACE TABLE CONSTRUCTORS (
  constructorId INT, constructorRef STRING, name STRING, nationality STRING, url STRING
);

CREATE OR REPLACE TABLE CIRCUITS (
  circuitId INT, circuitRef STRING, name STRING, location STRING, country STRING,
  lat FLOAT, lng FLOAT, alt INT, url STRING
);

CREATE OR REPLACE TABLE SEASONS (
  year INT, url STRING
);

CREATE OR REPLACE TABLE RACES (
  raceId INT, year INT, round INT, circuitId INT, name STRING,
  date DATE, time STRING, url STRING,
  fp1_date STRING, fp1_time STRING, fp2_date STRING, fp2_time STRING,
  fp3_date STRING, fp3_time STRING, quali_date STRING, quali_time STRING,
  sprint_date STRING, sprint_time STRING
);

CREATE OR REPLACE TABLE RESULTS (
  resultId INT, raceId INT, driverId INT, constructorId INT, number STRING,
  grid INT, position STRING, positionText STRING, positionOrder INT,
  points FLOAT, laps INT, time STRING, milliseconds INT, fastestLap INT,
  rank STRING, fastestLapTime STRING, fastestLapSpeed STRING, statusId INT
);

CREATE OR REPLACE TABLE SPRINT_RESULTS (
  resultId INT, raceId INT, driverId INT, constructorId INT, number STRING,
  grid INT, position STRING, positionText STRING, positionOrder INT,
  points FLOAT, laps INT, time STRING, milliseconds INT,
  fastestLap INT, fastestLapTime STRING, statusId INT
);

CREATE OR REPLACE TABLE QUALIFYING (
  qualifyId INT, raceId INT, driverId INT, constructorId INT, number INT,
  position INT, q1 STRING, q2 STRING, q3 STRING
);

CREATE OR REPLACE TABLE PIT_STOPS (
  raceId INT, driverId INT, stop INT, lap INT, time STRING,
  duration STRING, milliseconds INT
);

CREATE OR REPLACE TABLE LAP_TIMES (
  raceId INT, driverId INT, lap INT, position INT, time STRING, milliseconds INT
);

CREATE OR REPLACE TABLE DRIVER_STANDINGS (
  driverStandingsId INT, raceId INT, driverId INT, points FLOAT,
  position INT, positionText STRING, wins INT
);

CREATE OR REPLACE TABLE CONSTRUCTOR_STANDINGS (
  constructorStandingsId INT, raceId INT, constructorId INT, points FLOAT,
  position INT, positionText STRING, wins INT
);

CREATE OR REPLACE TABLE CONSTRUCTOR_RESULTS (
  constructorResultsId INT, raceId INT, constructorId INT, points FLOAT, status STRING
);

CREATE OR REPLACE TABLE STATUS (
  statusId INT, status STRING
);