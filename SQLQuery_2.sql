-------------------------------------------------- PRE‑RUN queries (config healthy + clean slate)
USE aerostream;
GO

-- 1) Config tables must be populated
SELECT 'channels' AS tbl, COUNT(*) AS cnt FROM channels WHERE is_active = 1;
SELECT 'run_states' AS tbl, COUNT(*) AS cnt FROM run_states;
SELECT 'run_types' AS tbl, COUNT(*) AS cnt FROM run_types;
SELECT 'qc_rules' AS tbl, COUNT(*) AS cnt FROM qc_rules;

-- Optional: confirm key QC rule codes exist
SELECT rule_code, rule_name, threshold_warn, threshold_fail
FROM qc_rules
ORDER BY rule_id;

-- 2) If you reset, these should be 0 before starting a new test
SELECT 'test_sessions' AS tbl, COUNT(*) AS cnt FROM test_sessions;
SELECT 'runs' AS tbl, COUNT(*) AS cnt FROM runs;
SELECT 'samples' AS tbl, COUNT(*) AS cnt FROM samples;
SELECT 'run_statistics' AS tbl, COUNT(*) AS cnt FROM run_statistics;
SELECT 'qc_summaries' AS tbl, COUNT(*) AS cnt FROM qc_summaries;
SELECT 'qc_results' AS tbl, COUNT(*) AS cnt FROM qc_results;
SELECT 'samples_1sec' AS tbl, COUNT(*) AS cnt FROM samples_1sec;


-------------------------------------------------- DURING‑RUN queries (while producer+consumer are running)
-- Step 1: identify the active run
USE aerostream;
GO

-- Latest run (most recent run_id)
SELECT TOP 1 r.run_id, r.run_name, r.session_id, rs.state_name AS state, r.ts_start, r.ts_end, r.sample_count
FROM runs r
LEFT JOIN run_states rs ON rs.state_id = r.state_id
ORDER BY r.run_id DESC;

-- Step 2: set @run_id and watch ingestion
DECLARE @run_id INT = (SELECT TOP 1 run_id FROM runs ORDER BY run_id DESC);

-- Run lifecycle
SELECT r.run_id, r.run_name, rs.state_name AS state, r.ts_start, r.ts_end, r.sample_count
FROM runs r
LEFT JOIN run_states rs ON rs.state_id = r.state_id
WHERE r.run_id = @run_id;

-- This should increase while streaming
SELECT COUNT(*) AS sample_rows_so_far
FROM samples
WHERE run_id = @run_id;

-- Channels appearing (should climb toward 72)
SELECT COUNT(DISTINCT channel_id) AS distinct_channels_so_far
FROM samples
WHERE run_id = @run_id;

-- Quick progress by channel (top 10 counts)
SELECT TOP 10 channel_id, COUNT(*) AS cnt
FROM samples
WHERE run_id = @run_id
GROUP BY channel_id
ORDER BY cnt DESC;


-------------------------------------------------- POST‑RUN queries (after streaming stops + you run process_run.py)
-- Step 1: run_id to inspect
DECLARE @run_id INT = (SELECT TOP 1 run_id FROM runs ORDER BY run_id DESC);

-- Step 2: confirm the run closed + sample_count is correct
-- Run should be completed/validated/rejected, ts_end not null
SELECT r.run_id, r.run_name, rs.state_name AS state, r.ts_start, r.ts_end, r.sample_count
FROM runs r
LEFT JOIN run_states rs ON rs.state_id = r.state_id
WHERE r.run_id = @run_id;

-- sample_count should match actual samples rows
SELECT 
  (SELECT sample_count FROM runs WHERE run_id = @run_id) AS run_sample_count,
  (SELECT COUNT(*) FROM samples WHERE run_id = @run_id) AS actual_sample_rows;

-- Step 3: confirm raw data looks sane
-- Duration should match expected (e.g., ~5 seconds)
SELECT 
  MIN(ts) AS min_ts,
  MAX(ts) AS max_ts,
  DATEDIFF(SECOND, MIN(ts), MAX(ts)) AS duration_seconds
FROM samples
WHERE run_id = @run_id;

-- Should be 72 for full simulator
SELECT COUNT(DISTINCT channel_id) AS distinct_channels
FROM samples
WHERE run_id = @run_id;

-- Key signal sanity: lift/drag/velocity
SELECT channel_id,
       MIN(value) AS min_val,
       AVG(value) AS avg_val,
       MAX(value) AS max_val,
       STDEV(value) AS std_val
FROM samples
WHERE run_id = @run_id AND channel_id IN (1,2,59)
GROUP BY channel_id
ORDER BY channel_id;

-- Step 4: confirm aggregates exist (for fast charting)
SELECT COUNT(*) AS rows_1sec
FROM samples_1sec
WHERE run_id = @run_id;

-- Step 5: confirm processing outputs exist
-- Metrics (one row)
SELECT *
FROM run_statistics
WHERE run_id = @run_id;

-- QC summary (one row)
SELECT *
FROM qc_summaries
WHERE run_id = @run_id;

-- QC details (many rows)
SELECT status, COUNT(*) AS cnt
FROM qc_results
WHERE run_id = @run_id
GROUP BY status
ORDER BY status;

-- Which rules failed/warned (join sanity)
SELECT r.rule_code, r.rule_name, qr.status, COUNT(*) AS cnt
FROM qc_results qr
JOIN qc_rules r ON r.rule_id = qr.rule_id
WHERE qr.run_id = @run_id AND qr.status IN ('fail','warn')
GROUP BY r.rule_code, r.rule_name, qr.status
ORDER BY qr.status DESC, cnt DESC;

