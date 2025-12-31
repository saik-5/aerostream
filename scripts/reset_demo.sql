-- =============================================================================
-- AeroStream Demo Reset Script (keep config, wipe run/test data)
-- =============================================================================
-- Purpose:
--   Reset only the *mutable* demo/test data so you can re-generate a clean set
--   of runs and reprocess them repeatedly during development/interviews.
--
-- Keeps (config/reference):
--   channels, run_states, run_types, qc_rules, models, test_cells, teams, users
--   calibrations (optional - see below)
--
-- Wipes (mutable/test + derived):
--   sessions, runs, samples, aggregates, stats, QC results, comments, audit
--   demo_run_requests (public website request queue)
-- =============================================================================

USE aerostream;
GO

-- -----------------------------------------------------------------------------
-- Derived / recomputable tables (safe to delete and regenerate)
-- -----------------------------------------------------------------------------
TRUNCATE TABLE qc_results;
TRUNCATE TABLE qc_summaries;
TRUNCATE TABLE run_statistics;
TRUNCATE TABLE run_deltas;
TRUNCATE TABLE samples_1sec;
TRUNCATE TABLE samples_processed;
GO

-- -----------------------------------------------------------------------------
-- Raw/test data tables (append-per-run in real life; safe to wipe for demos)
-- -----------------------------------------------------------------------------
TRUNCATE TABLE samples;
TRUNCATE TABLE runs;
TRUNCATE TABLE test_sessions;
GO

-- -----------------------------------------------------------------------------
-- Optional demo cleanup (safe to wipe for demos)
-- -----------------------------------------------------------------------------
TRUNCATE TABLE run_comments;
TRUNCATE TABLE audit_log;
TRUNCATE TABLE demo_run_requests;
GO

-- -----------------------------------------------------------------------------
-- NOTE: calibrations is a "config-like history" table.
-- In a real system you usually KEEP calibration history. For demos you may wipe it.
-- Uncomment the next line if you want to wipe calibrations too.
-- -----------------------------------------------------------------------------
-- TRUNCATE TABLE calibrations;
-- GO

PRINT '✅ Demo reset complete (config tables preserved)';
GO


