-- ============================================
-- WAREHOUSE, DATABASE, AND SCHEMA SETUP
-- ============================================

-- Compute resource
CREATE WAREHOUSE IF NOT EXISTS F1_WH
  WITH WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE;

-- Database for the whole project
CREATE DATABASE IF NOT EXISTS F1_PROJECT;

USE DATABASE F1_PROJECT;

-- RAW: unprocessed data landing zone, mirrors source CSVs exactly
-- ANALYTICS: cleaned, joined, human-readable tables for analysis
CREATE SCHEMA IF NOT EXISTS RAW;
CREATE SCHEMA IF NOT EXISTS ANALYTICS;

USE WAREHOUSE F1_WH;
USE SCHEMA RAW;

-- File format for Kaggle's F1 dataset CSVs
-- (source uses \N to represent null values)
CREATE OR REPLACE FILE FORMAT F1_CSV_FORMAT
  TYPE = 'CSV'
  FIELD_DELIMITER = ','
  SKIP_HEADER = 1
  NULL_IF = ('\\N', 'NULL', '')
  EMPTY_FIELD_AS_NULL = TRUE
  FIELD_OPTIONALLY_ENCLOSED_BY = '"';

-- IF NOT EXISTS is intentional: CREATE OR REPLACE would silently wipe
-- any files already uploaded to this stage on every re-run
CREATE STAGE IF NOT EXISTS F1_STAGE
  FILE_FORMAT = F1_CSV_FORMAT;