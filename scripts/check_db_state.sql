/*
AeroStream - DB Inspection Queries (SQL Server)
================================================

How to run (docker + sqlcmd):
  docker exec aerostream-sqlserver /opt/mssql-tools18/bin/sqlcmd \
    -S localhost -U sa -P 'AeroStream_Secure_123!' -C -d aerostream \
    -i /scripts/check_db_state.sql

Tips:
  - Set @RUN_ID to drill into a specific run.
  - During streaming, focus on samples ingesting and run state/sample_count.
*/

SET NOCOUNT ON;

DECLARE @RUN_ID INT = NULL;  -- <-- set to a specific run_id (e.g., 11) when you want deep-dive queries

PRINT '============================================================';
PRINT 'AeroStream DB Inspection';
PRINT '============================================================';

/* -------------------------------------------------------------------------
   0) TABLES OVERVIEW (row counts)
------------------------------------------------------------------------- */
PRINT '';
PRINT '--- Row counts (quick health) ---';

SELECT 'teams' AS table_name, COUNT(*) AS row_count FROM teams
UNION ALL SELECT 'users', COUNT(*) FROM users
UNION ALL SELECT 'test_cells', COUNT(*) FROM test_cells
UNION ALL SELECT 'models', COUNT(*) FROM models
UNION ALL SELECT 'run_types', COUNT(*) FROM run_types
UNION ALL SELECT 'run_states', COUNT(*) FROM run_states
UNION ALL SELECT 'channels', COUNT(*) FROM channels
UNION ALL SELECT 'calibrations', COUNT(*) FROM calibrations
UNION ALL SELECT 'test_sessions', COUNT(*) FROM test_sessions
UNION ALL SELECT 'runs', COUNT(*) FROM runs
UNION ALL SELECT 'samples', COUNT(*) FROM samples
UNION ALL SELECT 'samples_processed', COUNT(*) FROM samples_processed
UNION ALL SELECT 'samples_1sec', COUNT(*) FROM samples_1sec
UNION ALL SELECT 'run_statistics', COUNT(*) FROM run_statistics
UNION ALL SELECT 'run_deltas', COUNT(*) FROM run_deltas
UNION ALL SELECT 'qc_rules', COUNT(*) FROM qc_rules
UNION ALL SELECT 'qc_results', COUNT(*) FROM qc_results
UNION ALL SELECT 'qc_summaries', COUNT(*) FROM qc_summaries
UNION ALL SELECT 'audit_log', COUNT(*) FROM audit_log
UNION ALL SELECT 'run_comments', COUNT(*) FROM run_comments
UNION ALL SELECT 'demo_run_requests', COUNT(*) FROM demo_run_requests
ORDER BY table_name;

/* -------------------------------------------------------------------------
   1) CONFIG / REFERENCE TABLES (should always have rows after init.sql)
------------------------------------------------------------------------- */
PRINT '';
PRINT '--- Config/reference tables (sanity) ---';

SELECT TOP 50 team_id, team_name, created_at FROM teams ORDER BY team_id;
SELECT TOP 50 user_id, username, role, team_id, created_at FROM users ORDER BY user_id;
SELECT TOP 50 cell_id, cell_code, cell_name, location, tunnel_type, max_speed_ms FROM test_cells ORDER BY cell_id;
SELECT TOP 50 model_id, model_code, model_name, scale_factor, season_year, version FROM models ORDER BY model_id;
SELECT TOP 50 run_type_id, type_code, type_name, default_duration_sec, requires_baseline FROM run_types ORDER BY run_type_id;
SELECT TOP 50 state_id, state_name, state_order, color_hex FROM run_states ORDER BY state_id;
SELECT TOP 50 channel_id, name AS channel_name, display_name, category, unit, sample_rate_hz FROM channels ORDER BY channel_id;
SELECT TOP 50 rule_id, rule_code, rule_name, category, severity, is_active FROM qc_rules ORDER BY rule_id;

/* -------------------------------------------------------------------------
   2) SESSIONS + RUNS (high-level “what’s in the DB?”)
------------------------------------------------------------------------- */
PRINT '';
PRINT '--- Latest sessions ---';

SELECT TOP 20
  s.session_id,
  s.session_name,
  s.session_code,
  s.session_date,
  s.cell_id,
  s.model_id,
  s.state,
  s.objective,
  s.created_at
FROM test_sessions s
ORDER BY s.session_id DESC;

PRINT '';
PRINT '--- Latest runs (with state + QC) ---';

SELECT TOP 25
  r.run_id,
  r.run_number,
  r.run_name,
  r.session_id,
  rs.state_name AS state,
  rt.type_name AS run_type,
  r.ts_start,
  r.ts_end,
  r.sample_count,
  q.overall_status AS qc_status
FROM runs r
LEFT JOIN run_states rs ON rs.state_id = r.state_id
LEFT JOIN run_types rt ON rt.run_type_id = r.run_type_id
LEFT JOIN qc_summaries q ON q.run_id = r.run_id
ORDER BY r.run_id DESC;

/* -------------------------------------------------------------------------
   3) DEMO REQUEST QUEUE (public website requests)
------------------------------------------------------------------------- */
PRINT '';
PRINT '--- Demo run requests (queue) ---';

SELECT TOP 50
  request_id,
  status,
  run_id,
  requester_email,
  requested_variant,
  requested_duration_sec,
  requested_speed_ms,
  requested_aoa_deg,
  requested_yaw_deg,
  created_at,
  reviewed_at,
  reviewer_notes
FROM demo_run_requests
ORDER BY request_id DESC;

/* -------------------------------------------------------------------------
   4) DURING-RUN / INGESTION CHECKS (useful while streaming is happening)
------------------------------------------------------------------------- */
PRINT '';
PRINT '--- Ingestion checks (pick the newest run_id and set @RUN_ID) ---';

-- Find a likely "current" run if @RUN_ID is NULL
IF @RUN_ID IS NULL
BEGIN
  SELECT TOP 1 @RUN_ID = r.run_id
  FROM runs r
  ORDER BY r.run_id DESC;
END

PRINT '';
PRINT 'Using @RUN_ID = ' + CAST(@RUN_ID AS NVARCHAR(20));

PRINT '';
PRINT '--- Run header ---';

SELECT
  r.run_id,
  r.run_name,
  r.session_id,
  rs.state_name AS state,
  r.ts_start,
  r.ts_end,
  r.sample_count,
  r.tunnel_speed_setpoint,
  r.tunnel_aoa_setpoint,
  r.tunnel_yaw_setpoint
FROM runs r
LEFT JOIN run_states rs ON rs.state_id = r.state_id
WHERE r.run_id = @RUN_ID;

PRINT '';
PRINT '--- Raw samples: row count + time range ---';

SELECT
  s.run_id,
  COUNT(*) AS sample_rows,
  MIN(s.ts) AS min_ts,
  MAX(s.ts) AS max_ts,
  DATEDIFF(SECOND, MIN(s.ts), MAX(s.ts)) AS duration_seconds
FROM samples s
WHERE s.run_id = @RUN_ID
GROUP BY s.run_id;

PRINT '';
PRINT '--- Per-channel sample counts (top 20) ---';

SELECT TOP 20
  c.name AS channel_name,
  c.display_name,
  c.sample_rate_hz,
  COUNT(*) AS rows_per_channel
FROM samples s
JOIN channels c ON c.channel_id = s.channel_id
WHERE s.run_id = @RUN_ID
GROUP BY c.name, c.display_name, c.sample_rate_hz
ORDER BY rows_per_channel DESC;

PRINT '';
PRINT '--- Latest raw samples (for quick sanity) ---';

SELECT TOP 50
  s.run_id,
  c.name AS channel_name,
  s.ts,
  s.value,
  s.quality_flag
FROM samples s
JOIN channels c ON c.channel_id = s.channel_id
WHERE s.run_id = @RUN_ID
ORDER BY s.ts DESC, s.channel_id;

/* -------------------------------------------------------------------------
   5) POST-RUN / DERIVED OUTPUTS (after scripts/process_run.py)
------------------------------------------------------------------------- */
PRINT '';
PRINT '--- Run statistics (derived) ---';

SELECT
  run_id,
  total_samples,
  valid_samples,
  spike_count,
  cl_mean,
  cd_mean,
  efficiency,
  aero_balance_pct,
  computed_at
FROM run_statistics
WHERE run_id = @RUN_ID;

PRINT '';
PRINT '--- QC summary (derived) ---';

SELECT
  run_id,
  overall_status,
  total_checks,
  passed_checks,
  warning_checks,
  failed_checks,
  skipped_checks,
  computed_at
FROM qc_summaries
WHERE run_id = @RUN_ID;

PRINT '';
PRINT '--- QC failures/warnings (top 50) ---';

SELECT TOP 50
  qr.status,
  r.rule_code,
  r.rule_name,
  qr.channel_id,
  c.name AS channel_name,
  qr.measured_value,
  qr.threshold_used,
  qr.details,
  qr.checked_at
FROM qc_results qr
JOIN qc_rules r ON r.rule_id = qr.rule_id
LEFT JOIN channels c ON c.channel_id = qr.channel_id
WHERE qr.run_id = @RUN_ID
  AND qr.status IN ('fail','warn')
ORDER BY
  CASE qr.status WHEN 'fail' THEN 1 ELSE 2 END,
  qr.checked_at DESC;

PRINT '';
PRINT '--- 1-second aggregates (samples_1sec) (top 50) ---';

SELECT TOP 50
  a.run_id,
  c.name AS channel_name,
  a.bucket,
  a.avg_value,
  a.min_value,
  a.max_value,
  a.sample_count
FROM samples_1sec a
JOIN channels c ON c.channel_id = a.channel_id
WHERE a.run_id = @RUN_ID
ORDER BY a.bucket DESC, c.name;

/* -------------------------------------------------------------------------
   6) OPTIONAL: COMPARE / DELTAS
------------------------------------------------------------------------- */
PRINT '';
PRINT '--- Run deltas (if you computed compare mode) ---';

SELECT TOP 50
  delta_id,
  run_id,
  baseline_run_id,
  delta_cl,
  delta_cd,
  delta_efficiency,
  pct_change_cl,
  pct_change_cd,
  pct_change_efficiency,
  is_significant,
  computed_at
FROM run_deltas
WHERE run_id = @RUN_ID OR baseline_run_id = @RUN_ID
ORDER BY computed_at DESC;


