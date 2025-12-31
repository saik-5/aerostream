-- =============================================================================
-- AeroStream Production Database Schema
-- =============================================================================
-- Comprehensive Motorsport Wind Tunnel Data Platform
-- Version: 2.0 (Production-Grade)
-- =============================================================================

USE master;
GO

-- Drop and recreate database
IF EXISTS (SELECT name FROM sys.databases WHERE name = N'aerostream')
BEGIN
    ALTER DATABASE aerostream SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE aerostream;
END
GO

CREATE DATABASE aerostream;
GO

USE aerostream;
GO

-- =============================================================================
-- SECTION 1: REFERENCE DATA (Lookup Tables)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1.1 TEAMS: Engineering teams
-- -----------------------------------------------------------------------------
CREATE TABLE teams (
    team_id INT IDENTITY(1,1) PRIMARY KEY,
    team_name NVARCHAR(100) NOT NULL UNIQUE,
    team_code NVARCHAR(10) NOT NULL UNIQUE,  -- e.g., 'AERO', 'PERF', 'VEHD'
    description NVARCHAR(500) NULL,
    is_active BIT DEFAULT 1,
    created_at DATETIME2 DEFAULT GETDATE()
);

INSERT INTO teams (team_name, team_code, description) VALUES
('Aerodynamics', 'AERO', 'Aerodynamic development and CFD correlation'),
('Vehicle Dynamics', 'VEHD', 'Suspension and handling optimization'),
('Performance Engineering', 'PERF', 'Lap time and race strategy'),
('Research & Development', 'R&D', 'Advanced concepts and innovation');

PRINT 'Created table: teams';
GO

-- -----------------------------------------------------------------------------
-- 1.2 USERS: System users
-- -----------------------------------------------------------------------------
CREATE TABLE users (
    user_id INT IDENTITY(1,1) PRIMARY KEY,
    username NVARCHAR(50) NOT NULL UNIQUE,
    email NVARCHAR(255) NOT NULL UNIQUE,
    full_name NVARCHAR(200) NOT NULL,
    team_id INT NULL,
    role NVARCHAR(50) NOT NULL DEFAULT 'engineer',  -- admin, lead, engineer, analyst, viewer
    is_active BIT DEFAULT 1,
    last_login DATETIME2 NULL,
    created_at DATETIME2 DEFAULT GETDATE()
);

INSERT INTO users (username, email, full_name, team_id, role) VALUES
('admin', 'admin@aerostream.local', 'System Administrator', NULL, 'admin'),
('aero_lead', 'aero.lead@aerostream.local', 'Aerodynamics Lead Engineer', 1, 'lead'),
('test_engineer', 'test.eng@aerostream.local', 'Wind Tunnel Test Engineer', 1, 'engineer');

PRINT 'Created table: users';
GO

-- -----------------------------------------------------------------------------
-- 1.3 TEST_CELLS: Wind tunnel facilities
-- -----------------------------------------------------------------------------
CREATE TABLE test_cells (
    cell_id INT IDENTITY(1,1) PRIMARY KEY,
    cell_name NVARCHAR(100) NOT NULL UNIQUE,
    cell_code NVARCHAR(20) NOT NULL UNIQUE,  -- e.g., 'WT-01', 'WT-02'
    location NVARCHAR(200) NULL,
    tunnel_type NVARCHAR(50) NOT NULL,  -- 'closed_return', 'open_jet', 'rolling_road'
    max_speed_ms FLOAT NULL,            -- Maximum tunnel speed
    test_section_width_m FLOAT NULL,
    test_section_height_m FLOAT NULL,
    has_rolling_road BIT DEFAULT 0,
    has_moving_ground BIT DEFAULT 0,
    has_boundary_layer_control BIT DEFAULT 0,
    turbulence_intensity_pct FLOAT NULL,
    last_calibration_date DATE NULL,
    is_active BIT DEFAULT 1,
    notes NVARCHAR(MAX) NULL,
    created_at DATETIME2 DEFAULT GETDATE()
);

INSERT INTO test_cells (cell_name, cell_code, location, tunnel_type, max_speed_ms, 
                        test_section_width_m, test_section_height_m, has_rolling_road,
                        turbulence_intensity_pct) VALUES
('Primary Wind Tunnel', 'WT-01', 'Hinwil, Switzerland', 'closed_return', 70.0, 
 4.5, 2.5, 1, 0.15),
('Development Tunnel', 'WT-02', 'Hinwil, Switzerland', 'closed_return', 60.0,
 3.0, 2.0, 1, 0.20);

PRINT 'Created table: test_cells';
GO

-- -----------------------------------------------------------------------------
-- 1.4 MODELS: Car model configurations
-- -----------------------------------------------------------------------------
CREATE TABLE models (
    model_id INT IDENTITY(1,1) PRIMARY KEY,
    model_name NVARCHAR(100) NOT NULL,
    model_code NVARCHAR(50) NOT NULL UNIQUE,  -- e.g., 'C44-R01', 'C44-R02'
    scale_factor FLOAT NOT NULL DEFAULT 0.60,  -- 60% scale typical
    wheelbase_mm FLOAT NULL,
    track_front_mm FLOAT NULL,
    track_rear_mm FLOAT NULL,
    reference_area_m2 FLOAT NULL,
    weight_kg FLOAT NULL,
    car_number NVARCHAR(10) NULL,  -- Race car number if applicable
    season_year INT NULL,
    version NVARCHAR(50) NULL,     -- 'Baseline', 'Spec-B', 'Monaco-Spec'
    parent_model_id INT NULL,      -- For variant tracking
    description NVARCHAR(500) NULL,
    is_active BIT DEFAULT 1,
    created_at DATETIME2 DEFAULT GETDATE(),
    created_by INT NULL
);

INSERT INTO models (model_name, model_code, scale_factor, wheelbase_mm, 
                   reference_area_m2, season_year, version) VALUES
('2024 Car Baseline', 'C44-BASE', 0.60, 2160, 0.54, 2024, 'Baseline'),
('2024 Car Variant A', 'C44-VA', 0.60, 2160, 0.54, 2024, 'High Downforce'),
('2024 Car Variant B', 'C44-VB', 0.60, 2160, 0.54, 2024, 'Low Drag');

PRINT 'Created table: models';
GO

-- -----------------------------------------------------------------------------
-- 1.5 RUN_TYPES: Categories of test runs
-- -----------------------------------------------------------------------------
CREATE TABLE run_types (
    run_type_id INT IDENTITY(1,1) PRIMARY KEY,
    type_name NVARCHAR(100) NOT NULL UNIQUE,
    type_code NVARCHAR(20) NOT NULL UNIQUE,
    description NVARCHAR(500) NULL,
    default_duration_sec INT NULL,
    requires_baseline BIT DEFAULT 0,
    created_at DATETIME2 DEFAULT GETDATE()
);

INSERT INTO run_types (type_name, type_code, description, default_duration_sec, requires_baseline) VALUES
('Baseline Aero Map', 'BASE', 'Standard aero map at reference conditions', 30, 0),
('Ride Height Sweep', 'RH-SWP', 'Front and rear ride height variation', 20, 1),
('Yaw Sweep', 'YAW-SWP', 'Yaw angle variation for cornering simulation', 25, 1),
('Speed Sweep', 'SPD-SWP', 'Tunnel speed variation', 20, 1),
('Component Test', 'COMP', 'Individual component evaluation', 15, 1),
('Repeatability Check', 'RPT', 'Back-to-back repeatability assessment', 10, 0),
('Calibration Run', 'CAL', 'Sensor and balance calibration', 60, 0);

PRINT 'Created table: run_types';
GO

-- -----------------------------------------------------------------------------
-- 1.6 RUN_STATES: Workflow states for runs
-- -----------------------------------------------------------------------------
CREATE TABLE run_states (
    state_id INT IDENTITY(1,1) PRIMARY KEY,
    state_name NVARCHAR(50) NOT NULL UNIQUE,
    state_order INT NOT NULL,
    description NVARCHAR(200) NULL,
    color_hex NVARCHAR(7) NULL  -- For UI display
);

INSERT INTO run_states (state_name, state_order, description, color_hex) VALUES
('draft', 1, 'Run created but not started', '#808080'),
('running', 2, 'Data acquisition in progress', '#FFA500'),
('completed', 3, 'Data acquisition finished', '#0000FF'),
('processing', 4, 'Post-processing in progress', '#800080'),
('validated', 5, 'QC passed, data approved', '#008000'),
('rejected', 6, 'QC failed, data rejected', '#FF0000'),
('archived', 7, 'Moved to cold storage', '#A0A0A0');

PRINT 'Created table: run_states';
GO

-- =============================================================================
-- SECTION 2: SENSOR & CALIBRATION
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 2.1 CHANNELS: Sensor channel definitions
-- -----------------------------------------------------------------------------
CREATE TABLE channels (
    channel_id INT PRIMARY KEY,
    name NVARCHAR(100) NOT NULL UNIQUE,
    display_name NVARCHAR(200) NULL,
    unit NVARCHAR(50) NOT NULL,
    sample_rate_hz FLOAT NOT NULL,
    category NVARCHAR(50) NOT NULL,
    subcategory NVARCHAR(50) NULL,
    sensor_type NVARCHAR(50) NULL,       -- 'strain_gauge', 'pressure_transducer', etc.
    physical_location NVARCHAR(100) NULL, -- 'front_wing_le', 'rear_wing_upper'
    range_min FLOAT NULL,
    range_max FLOAT NULL,
    precision_digits INT DEFAULT 3,
    is_derived BIT DEFAULT 0,            -- Calculated from other channels
    derived_formula NVARCHAR(500) NULL,
    description NVARCHAR(500) NULL,
    is_active BIT DEFAULT 1,
    created_at DATETIME2 DEFAULT GETDATE()
);

CREATE INDEX IX_channels_category ON channels(category);
CREATE INDEX IX_channels_sample_rate ON channels(sample_rate_hz);

PRINT 'Created table: channels';
GO

-- -----------------------------------------------------------------------------
-- 2.2 CALIBRATIONS: Sensor calibration records
-- -----------------------------------------------------------------------------
CREATE TABLE calibrations (
    calibration_id INT IDENTITY(1,1) PRIMARY KEY,
    channel_id INT NOT NULL,
    cell_id INT NULL,
    calibration_date DATE NOT NULL,
    valid_until DATE NULL,
    calibration_type NVARCHAR(50) NOT NULL,  -- 'factory', 'in-situ', 'reference'
    slope FLOAT NOT NULL DEFAULT 1.0,        -- y = slope * x + offset
    offset FLOAT NOT NULL DEFAULT 0.0,
    r_squared FLOAT NULL,                    -- Calibration fit quality
    uncertainty_pct FLOAT NULL,
    temperature_c FLOAT NULL,
    notes NVARCHAR(500) NULL,
    calibrated_by INT NULL,
    certificate_ref NVARCHAR(100) NULL,
    created_at DATETIME2 DEFAULT GETDATE()
);

CREATE INDEX IX_calibrations_channel ON calibrations(channel_id);
CREATE INDEX IX_calibrations_date ON calibrations(calibration_date DESC);

PRINT 'Created table: calibrations';
GO

-- =============================================================================
-- SECTION 3: TEST RUNS
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 3.1 TEST_SESSIONS: Grouping of runs in a test day
-- -----------------------------------------------------------------------------
CREATE TABLE test_sessions (
    session_id INT IDENTITY(1,1) PRIMARY KEY,
    session_name NVARCHAR(200) NOT NULL,
    session_code NVARCHAR(50) NOT NULL UNIQUE,  -- e.g., 'WT-2024-1215-01'
    cell_id INT NOT NULL,
    model_id INT NOT NULL,
    team_id INT NULL,
    session_date DATE NOT NULL,
    objective NVARCHAR(MAX) NULL,
    ambient_temp_c FLOAT NULL,
    ambient_pressure_pa FLOAT NULL,
    ambient_humidity_pct FLOAT NULL,
    session_lead_id INT NULL,
    state NVARCHAR(50) DEFAULT 'active',  -- active, completed, cancelled
    notes NVARCHAR(MAX) NULL,
    created_at DATETIME2 DEFAULT GETDATE(),
    created_by INT NULL
);

CREATE INDEX IX_sessions_date ON test_sessions(session_date DESC);
CREATE INDEX IX_sessions_model ON test_sessions(model_id);
CREATE INDEX IX_sessions_cell ON test_sessions(cell_id);

PRINT 'Created table: test_sessions';
GO

-- -----------------------------------------------------------------------------
-- 3.2 RUNS: Individual test runs (enhanced)
-- -----------------------------------------------------------------------------
CREATE TABLE runs (
    run_id INT IDENTITY(1,1) PRIMARY KEY,
    run_number INT NOT NULL,                 -- Sequential within session
    run_name NVARCHAR(255) NOT NULL,
    session_id INT NULL,
    run_type_id INT NULL,
    state_id INT NOT NULL DEFAULT 1,         -- FK to run_states
    
    -- Timing
    ts_scheduled DATETIME2(3) NULL,
    ts_start DATETIME2(3) NULL,
    ts_end DATETIME2(3) NULL,
    duration_actual_sec FLOAT NULL,
    
    -- Tunnel conditions (setpoints)
    tunnel_speed_setpoint FLOAT NULL,
    tunnel_aoa_setpoint FLOAT NULL,
    tunnel_yaw_setpoint FLOAT NULL,
    
    -- Tunnel conditions (actual/measured)
    tunnel_speed_actual FLOAT NULL,
    tunnel_aoa_actual FLOAT NULL,
    tunnel_yaw_actual FLOAT NULL,
    tunnel_temp_actual FLOAT NULL,
    tunnel_pressure_actual FLOAT NULL,
    tunnel_humidity_actual FLOAT NULL,
    air_density_actual FLOAT NULL,
    reynolds_number FLOAT NULL,
    
    -- Model configuration
    ride_height_f FLOAT NULL,
    ride_height_r FLOAT NULL,
    rake_angle_deg FLOAT NULL,
    steering_angle_deg FLOAT NULL,
    roll_angle_deg FLOAT NULL,
    
    -- Component settings
    front_wing_flap_deg FLOAT NULL,
    rear_wing_flap_deg FLOAT NULL,
    drs_open BIT DEFAULT 0,
    beam_wing_config NVARCHAR(50) NULL,
    diffuser_gurney_mm FLOAT NULL,
    
    -- Data quality
    data_quality_score FLOAT NULL,           -- 0-100
    sample_count INT NULL,
    missing_samples_pct FLOAT NULL,
    
    -- Comparison reference
    baseline_run_id INT NULL,                -- Reference run for delta calcs
    
    -- Metadata
    priority INT DEFAULT 5,                  -- 1=critical, 5=normal, 10=low
    tags NVARCHAR(500) NULL,                 -- Comma-separated tags
    notes NVARCHAR(MAX) NULL,
    
    -- Audit
    created_at DATETIME2 DEFAULT GETDATE(),
    created_by INT NULL,
    modified_at DATETIME2 NULL,
    modified_by INT NULL,
    validated_at DATETIME2 NULL,
    validated_by INT NULL
);

CREATE INDEX IX_runs_session ON runs(session_id);
CREATE INDEX IX_runs_state ON runs(state_id);
CREATE INDEX IX_runs_ts_start ON runs(ts_start DESC);
CREATE INDEX IX_runs_run_type ON runs(run_type_id);
CREATE INDEX IX_runs_baseline ON runs(baseline_run_id);

PRINT 'Created table: runs';
GO

-- =============================================================================
-- SECTION 4: TIME-SERIES DATA
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 4.1 SAMPLES: Raw sensor data (high-volume)
-- -----------------------------------------------------------------------------
CREATE TABLE samples (
    run_id INT NOT NULL,
    channel_id INT NOT NULL,
    ts DATETIME2(3) NOT NULL,
    value FLOAT NOT NULL,
    quality_flag TINYINT DEFAULT 0      -- 0=good, 1=interpolated, 2=suspect, 3=bad
);

-- Clustered index for time-range queries
CREATE CLUSTERED INDEX IX_samples_ts_run_channel 
    ON samples(ts, run_id, channel_id);

-- Non-clustered for per-run channel queries
CREATE NONCLUSTERED INDEX IX_samples_run_channel_ts 
    ON samples(run_id, channel_id, ts)
    INCLUDE (value, quality_flag);

-- Columnstore index for analytics (fast aggregations)
CREATE NONCLUSTERED COLUMNSTORE INDEX IX_samples_columnstore
    ON samples (run_id, channel_id, ts, value, quality_flag);

-- Enable compression
ALTER TABLE samples REBUILD WITH (DATA_COMPRESSION = PAGE);

PRINT 'Created table: samples (with columnstore)';
GO

-- -----------------------------------------------------------------------------
-- 4.2 SAMPLES_PROCESSED: Resampled/filtered data
-- -----------------------------------------------------------------------------
CREATE TABLE samples_processed (
    run_id INT NOT NULL,
    channel_id INT NOT NULL,
    ts DATETIME2(3) NOT NULL,
    value_raw FLOAT NOT NULL,
    value_filtered FLOAT NULL,          -- After low-pass filter
    value_despiked FLOAT NULL,          -- After spike removal
    is_spike BIT DEFAULT 0,
    is_outlier BIT DEFAULT 0
);

CREATE CLUSTERED INDEX IX_samples_proc_run_channel_ts 
    ON samples_processed(run_id, channel_id, ts);

ALTER TABLE samples_processed REBUILD WITH (DATA_COMPRESSION = PAGE);

PRINT 'Created table: samples_processed';
GO

-- -----------------------------------------------------------------------------
-- 4.3 SAMPLES_1SEC: Pre-aggregated 1-second buckets (like TimescaleDB continuous aggregates)
-- -----------------------------------------------------------------------------
CREATE TABLE samples_1sec (
    run_id INT NOT NULL,
    channel_id INT NOT NULL,
    bucket DATETIME2(0) NOT NULL,       -- 1-second time buckets
    avg_value FLOAT NOT NULL,
    min_value FLOAT NOT NULL,
    max_value FLOAT NOT NULL,
    std_value FLOAT NULL,               -- Standard deviation
    sample_count INT NOT NULL,
    CONSTRAINT PK_samples_1sec PRIMARY KEY (run_id, channel_id, bucket)
);

CREATE INDEX IX_samples_1sec_bucket ON samples_1sec(bucket);

ALTER TABLE samples_1sec REBUILD WITH (DATA_COMPRESSION = PAGE);

PRINT 'Created table: samples_1sec';
GO

-- -----------------------------------------------------------------------------
-- 4.4 Stored Procedure: Refresh samples_1sec aggregates for a run
-- -----------------------------------------------------------------------------
CREATE PROCEDURE sp_refresh_samples_1sec 
    @run_id INT
AS
BEGIN
    SET NOCOUNT ON;
    
    -- Delete existing aggregates for this run
    DELETE FROM samples_1sec WHERE run_id = @run_id;
    
    -- Insert new aggregates (1-second buckets)
    INSERT INTO samples_1sec (run_id, channel_id, bucket, avg_value, min_value, max_value, std_value, sample_count)
    SELECT 
        run_id,
        channel_id,
        DATEADD(SECOND, DATEDIFF(SECOND, '2000-01-01', ts), '2000-01-01') AS bucket,
        AVG(value) AS avg_value,
        MIN(value) AS min_value,
        MAX(value) AS max_value,
        STDEV(value) AS std_value,
        COUNT(*) AS sample_count
    FROM samples
    WHERE run_id = @run_id
    GROUP BY run_id, channel_id, DATEADD(SECOND, DATEDIFF(SECOND, '2000-01-01', ts), '2000-01-01');
    
    RETURN @@ROWCOUNT;
END
GO

PRINT 'Created stored procedure: sp_refresh_samples_1sec';
GO

-- -----------------------------------------------------------------------------
-- 4.5 Stored Procedure: Get downsampled time-series data
-- -----------------------------------------------------------------------------
CREATE PROCEDURE sp_get_downsampled_data
    @run_id INT,
    @channel_id INT = NULL,
    @bucket_seconds INT = 1,
    @start_time DATETIME2(3) = NULL,
    @end_time DATETIME2(3) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    
    -- Use pre-aggregated data if 1-second buckets exist and match
    IF @bucket_seconds = 1 AND EXISTS (SELECT 1 FROM samples_1sec WHERE run_id = @run_id)
    BEGIN
        SELECT 
            run_id,
            channel_id,
            bucket AS ts,
            avg_value AS value,
            min_value,
            max_value,
            sample_count
        FROM samples_1sec
        WHERE run_id = @run_id
          AND (@channel_id IS NULL OR channel_id = @channel_id)
          AND (@start_time IS NULL OR bucket >= @start_time)
          AND (@end_time IS NULL OR bucket <= @end_time)
        ORDER BY channel_id, bucket;
    END
    ELSE
    BEGIN
        -- Dynamic aggregation for other bucket sizes
        SELECT 
            run_id,
            channel_id,
            DATEADD(SECOND, 
                (DATEDIFF(SECOND, '2000-01-01', ts) / @bucket_seconds) * @bucket_seconds, 
                '2000-01-01') AS ts,
            AVG(value) AS value,
            MIN(value) AS min_value,
            MAX(value) AS max_value,
            COUNT(*) AS sample_count
        FROM samples
        WHERE run_id = @run_id
          AND (@channel_id IS NULL OR channel_id = @channel_id)
          AND (@start_time IS NULL OR ts >= @start_time)
          AND (@end_time IS NULL OR ts <= @end_time)
        GROUP BY 
            run_id,
            channel_id,
            DATEADD(SECOND, 
                (DATEDIFF(SECOND, '2000-01-01', ts) / @bucket_seconds) * @bucket_seconds, 
                '2000-01-01')
        ORDER BY channel_id, ts;
    END
END
GO

PRINT 'Created stored procedure: sp_get_downsampled_data';
GO

-- =============================================================================
-- SECTION 5: COMPUTED RESULTS
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 5.1 RUN_STATISTICS: Per-run aggregated metrics
-- -----------------------------------------------------------------------------
CREATE TABLE run_statistics (
    stat_id INT IDENTITY(1,1) PRIMARY KEY,
    run_id INT NOT NULL UNIQUE,
    
    -- Sample counts
    total_samples INT NULL,
    valid_samples INT NULL,
    spike_count INT NULL,
    missing_count INT NULL,
    
    -- Force balance statistics
    lift_mean FLOAT NULL,
    lift_std FLOAT NULL,
    lift_min FLOAT NULL,
    lift_max FLOAT NULL,
    
    drag_mean FLOAT NULL,
    drag_std FLOAT NULL,
    drag_min FLOAT NULL,
    drag_max FLOAT NULL,
    
    side_force_mean FLOAT NULL,
    side_force_std FLOAT NULL,
    
    -- Moments
    pitch_moment_mean FLOAT NULL,
    roll_moment_mean FLOAT NULL,
    yaw_moment_mean FLOAT NULL,
    
    -- Aerodynamic coefficients
    cl_mean FLOAT NULL,
    cl_std FLOAT NULL,
    cd_mean FLOAT NULL,
    cd_std FLOAT NULL,
    cy_mean FLOAT NULL,
    
    -- Derived metrics
    efficiency FLOAT NULL,              -- L/D ratio
    aero_balance_pct FLOAT NULL,        -- Front percentage
    downforce_front FLOAT NULL,
    downforce_rear FLOAT NULL,
    
    -- Pressure integration
    fw_cp_avg FLOAT NULL,
    rw_cp_avg FLOAT NULL,
    floor_cp_avg FLOAT NULL,
    
    -- Stability metrics
    stability_index FLOAT NULL,         -- Measure of data steadiness
    
    computed_at DATETIME2 DEFAULT GETDATE()
);

CREATE INDEX IX_run_statistics_run ON run_statistics(run_id);

PRINT 'Created table: run_statistics';
GO

-- -----------------------------------------------------------------------------
-- 5.2 RUN_DELTAS: Comparison between runs
-- -----------------------------------------------------------------------------
CREATE TABLE run_deltas (
    delta_id INT IDENTITY(1,1) PRIMARY KEY,
    run_id INT NOT NULL,
    baseline_run_id INT NOT NULL,
    
    -- Delta values (run - baseline)
    delta_cl FLOAT NULL,
    delta_cd FLOAT NULL,
    delta_efficiency FLOAT NULL,
    delta_balance FLOAT NULL,
    delta_downforce FLOAT NULL,
    delta_drag FLOAT NULL,
    
    -- Percentage changes
    pct_change_cl FLOAT NULL,
    pct_change_cd FLOAT NULL,
    pct_change_efficiency FLOAT NULL,
    
    -- Statistical significance
    is_significant BIT DEFAULT 0,
    confidence_level FLOAT NULL,
    
    notes NVARCHAR(500) NULL,
    computed_at DATETIME2 DEFAULT GETDATE()
);

CREATE INDEX IX_run_deltas_run ON run_deltas(run_id);
CREATE INDEX IX_run_deltas_baseline ON run_deltas(baseline_run_id);

PRINT 'Created table: run_deltas';
GO

-- =============================================================================
-- SECTION 6: QUALITY CONTROL
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 6.1 QC_RULES: Define QC check rules
-- -----------------------------------------------------------------------------
CREATE TABLE qc_rules (
    rule_id INT IDENTITY(1,1) PRIMARY KEY,
    rule_name NVARCHAR(100) NOT NULL UNIQUE,
    rule_code NVARCHAR(50) NOT NULL UNIQUE,
    category NVARCHAR(50) NOT NULL,      -- 'completeness', 'accuracy', 'stability'
    description NVARCHAR(500) NULL,
    check_type NVARCHAR(50) NOT NULL,    -- 'threshold', 'range', 'trend', 'comparison'
    severity NVARCHAR(20) NOT NULL,      -- 'critical', 'major', 'minor', 'info'
    threshold_warn FLOAT NULL,
    threshold_fail FLOAT NULL,
    applies_to_channels NVARCHAR(500) NULL,  -- Channel categories
    is_active BIT DEFAULT 1,
    created_at DATETIME2 DEFAULT GETDATE()
);

INSERT INTO qc_rules (rule_name, rule_code, category, check_type, severity, threshold_warn, threshold_fail, description) VALUES
('Missing Data Check', 'MISS-DATA', 'completeness', 'threshold', 'critical', 1.0, 5.0, 'Percentage of missing samples'),
('Spike Detection', 'SPIKE-DET', 'accuracy', 'threshold', 'major', 0.5, 2.0, 'Percentage of detected spikes'),
('Sensor Range Check', 'RANGE-CHK', 'accuracy', 'range', 'critical', NULL, NULL, 'Values outside sensor range'),
('Stability Check', 'STAB-CHK', 'stability', 'threshold', 'minor', 5.0, 10.0, 'Standard deviation too high'),
('Repeatability Check', 'RPT-CHK', 'accuracy', 'comparison', 'major', 1.0, 3.0, 'Deviation from repeat run'),
('Balance Check', 'BAL-CHK', 'accuracy', 'threshold', 'minor', 2.0, 5.0, 'Force balance closure error'),
('Temperature Drift', 'TEMP-DFT', 'stability', 'trend', 'minor', 0.5, 1.0, 'Temperature change during run'),
('Tunnel Speed Stability', 'SPD-STAB', 'stability', 'threshold', 'major', 0.5, 1.0, 'Speed variation during run'),
('Timestamp Gaps', 'TS-GAP', 'completeness', 'threshold', 'major', 1.0, 5.0, 'Number of timestamp gaps > 2x expected dt'),
('Flatline Detection', 'FLAT-DET', 'accuracy', 'threshold', 'major', 1.0, NULL, 'Seconds of constant signal (sensor stuck)');

PRINT 'Created table: qc_rules';
GO

-- -----------------------------------------------------------------------------
-- 6.2 QC_RESULTS: Individual QC check results
-- -----------------------------------------------------------------------------
CREATE TABLE qc_results (
    result_id INT IDENTITY(1,1) PRIMARY KEY,
    run_id INT NOT NULL,
    rule_id INT NOT NULL,
    channel_id INT NULL,                 -- NULL if run-level check
    
    status NVARCHAR(20) NOT NULL,        -- 'pass', 'warn', 'fail', 'skip'
    measured_value FLOAT NULL,
    threshold_used FLOAT NULL,
    
    details NVARCHAR(500) NULL,
    timestamp_start DATETIME2(3) NULL,   -- If time-specific issue
    timestamp_end DATETIME2(3) NULL,
    
    checked_at DATETIME2 DEFAULT GETDATE()
);

CREATE INDEX IX_qc_results_run ON qc_results(run_id);
CREATE INDEX IX_qc_results_status ON qc_results(status);

PRINT 'Created table: qc_results';
GO

-- -----------------------------------------------------------------------------
-- 6.3 QC_SUMMARIES: Overall QC status per run
-- -----------------------------------------------------------------------------
CREATE TABLE qc_summaries (
    summary_id INT IDENTITY(1,1) PRIMARY KEY,
    run_id INT NOT NULL UNIQUE,
    
    overall_status NVARCHAR(20) NOT NULL,  -- 'pass', 'warn', 'fail'
    total_checks INT NOT NULL,
    passed_checks INT NOT NULL,
    warning_checks INT NOT NULL,
    failed_checks INT NOT NULL,
    skipped_checks INT NOT NULL,
    
    critical_issues NVARCHAR(MAX) NULL,    -- JSON array of critical failures
    recommendations NVARCHAR(MAX) NULL,
    
    approved_by INT NULL,
    approved_at DATETIME2 NULL,
    approval_notes NVARCHAR(500) NULL,
    
    computed_at DATETIME2 DEFAULT GETDATE()
);

PRINT 'Created table: qc_summaries';
GO

-- =============================================================================
-- SECTION 7: AUDIT & HISTORY
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 7.1 AUDIT_LOG: Track all changes
-- -----------------------------------------------------------------------------
CREATE TABLE audit_log (
    log_id BIGINT IDENTITY(1,1) PRIMARY KEY,
    table_name NVARCHAR(100) NOT NULL,
    record_id INT NOT NULL,
    action NVARCHAR(20) NOT NULL,        -- 'INSERT', 'UPDATE', 'DELETE'
    changed_fields NVARCHAR(MAX) NULL,   -- JSON of changed fields
    old_values NVARCHAR(MAX) NULL,       -- JSON of old values
    new_values NVARCHAR(MAX) NULL,       -- JSON of new values
    user_id INT NULL,
    ip_address NVARCHAR(45) NULL,
    user_agent NVARCHAR(500) NULL,
    timestamp DATETIME2 DEFAULT GETDATE()
);

CREATE INDEX IX_audit_log_table ON audit_log(table_name, record_id);
CREATE INDEX IX_audit_log_time ON audit_log(timestamp DESC);
CREATE INDEX IX_audit_log_user ON audit_log(user_id);

PRINT 'Created table: audit_log';
GO

-- -----------------------------------------------------------------------------
-- 7.2 RUN_COMMENTS: Discussion on runs
-- -----------------------------------------------------------------------------
CREATE TABLE run_comments (
    comment_id INT IDENTITY(1,1) PRIMARY KEY,
    run_id INT NOT NULL,
    parent_comment_id INT NULL,          -- For threaded comments
    user_id INT NOT NULL,
    comment_text NVARCHAR(MAX) NOT NULL,
    is_pinned BIT DEFAULT 0,
    created_at DATETIME2 DEFAULT GETDATE(),
    modified_at DATETIME2 NULL
);

CREATE INDEX IX_run_comments_run ON run_comments(run_id);

PRINT 'Created table: run_comments';
GO

-- =============================================================================
-- SECTION 8: DEMO REQUEST QUEUE (Public website requests, admin approval)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 8.1 DEMO_RUN_REQUESTS: Public "request a demo run" queue
-- -----------------------------------------------------------------------------
CREATE TABLE demo_run_requests (
    request_id INT IDENTITY(1,1) PRIMARY KEY,
    
    -- Requester info (no-login flow)
    requester_name NVARCHAR(200) NULL,
    requester_email NVARCHAR(255) NULL,
    
    -- Requested parameters (bounded by API validation)
    requested_variant NVARCHAR(50) NOT NULL DEFAULT 'baseline', -- baseline/variant_a/variant_b
    requested_duration_sec FLOAT NOT NULL DEFAULT 5.0,
    requested_speed_ms FLOAT NOT NULL DEFAULT 50.0,
    requested_aoa_deg FLOAT NOT NULL DEFAULT 0.0,
    requested_yaw_deg FLOAT NOT NULL DEFAULT 0.0,
    requested_notes NVARCHAR(1000) NULL,
    
    -- Workflow
    status NVARCHAR(20) NOT NULL DEFAULT 'pending', -- pending/approved/rejected/running/completed/failed
    reviewer_notes NVARCHAR(1000) NULL,
    run_id INT NULL, -- filled when a run is executed for this request
    
    -- Audit-ish metadata
    ip_address NVARCHAR(45) NULL,
    user_agent NVARCHAR(500) NULL,
    created_at DATETIME2 DEFAULT GETDATE(),
    reviewed_at DATETIME2 NULL
);

CREATE INDEX IX_demo_run_requests_status ON demo_run_requests(status, created_at DESC);
CREATE INDEX IX_demo_run_requests_created ON demo_run_requests(created_at DESC);
CREATE INDEX IX_demo_run_requests_run_id ON demo_run_requests(run_id);

PRINT 'Created table: demo_run_requests';
GO

-- =============================================================================
-- SECTION 8: INSERT CHANNEL DEFINITIONS (72 channels)
-- =============================================================================

-- 1. Main Force Balance (6 channels @ 1000 Hz)
INSERT INTO channels (channel_id, name, display_name, unit, sample_rate_hz, category, subcategory, sensor_type, range_min, range_max, description) VALUES
(1, 'balance_lift', 'Total Lift (Fz)', 'N', 1000, 'Force Balance', 'Forces', 'strain_gauge', -10000, 10000, 'Total vertical force (negative = downforce)'),
(2, 'balance_drag', 'Total Drag (Fx)', 'N', 1000, 'Force Balance', 'Forces', 'strain_gauge', 0, 5000, 'Total drag force'),
(3, 'balance_side', 'Side Force (Fy)', 'N', 1000, 'Force Balance', 'Forces', 'strain_gauge', -2000, 2000, 'Lateral side force'),
(4, 'balance_pitch', 'Pitch Moment (My)', 'Nm', 1000, 'Force Balance', 'Moments', 'strain_gauge', -5000, 5000, 'Pitching moment'),
(5, 'balance_roll', 'Roll Moment (Mx)', 'Nm', 1000, 'Force Balance', 'Moments', 'strain_gauge', -1000, 1000, 'Rolling moment'),
(6, 'balance_yaw', 'Yaw Moment (Mz)', 'Nm', 1000, 'Force Balance', 'Moments', 'strain_gauge', -1000, 1000, 'Yawing moment');

-- 2. Component Load Cells (8 channels @ 500 Hz)
INSERT INTO channels (channel_id, name, display_name, unit, sample_rate_hz, category, subcategory, sensor_type, range_min, range_max, description) VALUES
(7, 'fw_lift', 'Front Wing Lift', 'N', 500, 'Component Loads', 'Front Wing', 'load_cell', -5000, 0, 'Front wing downforce'),
(8, 'fw_drag', 'Front Wing Drag', 'N', 500, 'Component Loads', 'Front Wing', 'load_cell', 0, 1000, 'Front wing drag'),
(9, 'rw_lift', 'Rear Wing Lift', 'N', 500, 'Component Loads', 'Rear Wing', 'load_cell', -5000, 0, 'Rear wing downforce'),
(10, 'rw_drag', 'Rear Wing Drag', 'N', 500, 'Component Loads', 'Rear Wing', 'load_cell', 0, 2000, 'Rear wing drag'),
(11, 'wheel_fl', 'Wheel Load FL', 'N', 500, 'Component Loads', 'Wheels', 'load_cell', 0, 3000, 'Front-left contact patch load'),
(12, 'wheel_fr', 'Wheel Load FR', 'N', 500, 'Component Loads', 'Wheels', 'load_cell', 0, 3000, 'Front-right contact patch load'),
(13, 'wheel_rl', 'Wheel Load RL', 'N', 500, 'Component Loads', 'Wheels', 'load_cell', 0, 3000, 'Rear-left contact patch load'),
(14, 'wheel_rr', 'Wheel Load RR', 'N', 500, 'Component Loads', 'Wheels', 'load_cell', 0, 3000, 'Rear-right contact patch load');

-- 3. Front Wing Pressure Taps (12 channels @ 500 Hz)
INSERT INTO channels (channel_id, name, display_name, unit, sample_rate_hz, category, subcategory, sensor_type, physical_location, range_min, range_max) VALUES
(15, 'fw_le_1', 'FW Leading Edge 1', 'Pa', 500, 'Pressure', 'Front Wing', 'pressure_transducer', 'front_wing_leading_edge', 95000, 105000),
(16, 'fw_le_2', 'FW Leading Edge 2', 'Pa', 500, 'Pressure', 'Front Wing', 'pressure_transducer', 'front_wing_leading_edge', 95000, 105000),
(17, 'fw_le_3', 'FW Leading Edge 3', 'Pa', 500, 'Pressure', 'Front Wing', 'pressure_transducer', 'front_wing_leading_edge', 95000, 105000),
(18, 'fw_le_4', 'FW Leading Edge 4', 'Pa', 500, 'Pressure', 'Front Wing', 'pressure_transducer', 'front_wing_leading_edge', 95000, 105000),
(19, 'fw_mid_1', 'FW Mid-Chord 1', 'Pa', 500, 'Pressure', 'Front Wing', 'pressure_transducer', 'front_wing_mid', 95000, 105000),
(20, 'fw_mid_2', 'FW Mid-Chord 2', 'Pa', 500, 'Pressure', 'Front Wing', 'pressure_transducer', 'front_wing_mid', 95000, 105000),
(21, 'fw_mid_3', 'FW Mid-Chord 3', 'Pa', 500, 'Pressure', 'Front Wing', 'pressure_transducer', 'front_wing_mid', 95000, 105000),
(22, 'fw_mid_4', 'FW Mid-Chord 4', 'Pa', 500, 'Pressure', 'Front Wing', 'pressure_transducer', 'front_wing_mid', 95000, 105000),
(23, 'fw_te_1', 'FW Trailing Edge 1', 'Pa', 500, 'Pressure', 'Front Wing', 'pressure_transducer', 'front_wing_trailing', 95000, 105000),
(24, 'fw_te_2', 'FW Trailing Edge 2', 'Pa', 500, 'Pressure', 'Front Wing', 'pressure_transducer', 'front_wing_trailing', 95000, 105000),
(25, 'fw_te_3', 'FW Trailing Edge 3', 'Pa', 500, 'Pressure', 'Front Wing', 'pressure_transducer', 'front_wing_trailing', 95000, 105000),
(26, 'fw_te_4', 'FW Trailing Edge 4', 'Pa', 500, 'Pressure', 'Front Wing', 'pressure_transducer', 'front_wing_trailing', 95000, 105000);

-- 4. Rear Wing Pressure Taps (12 channels @ 500 Hz)
INSERT INTO channels (channel_id, name, display_name, unit, sample_rate_hz, category, subcategory, sensor_type, physical_location, range_min, range_max) VALUES
(27, 'rw_upper_1', 'RW Upper Surface 1', 'Pa', 500, 'Pressure', 'Rear Wing', 'pressure_transducer', 'rear_wing_upper', 95000, 105000),
(28, 'rw_upper_2', 'RW Upper Surface 2', 'Pa', 500, 'Pressure', 'Rear Wing', 'pressure_transducer', 'rear_wing_upper', 95000, 105000),
(29, 'rw_upper_3', 'RW Upper Surface 3', 'Pa', 500, 'Pressure', 'Rear Wing', 'pressure_transducer', 'rear_wing_upper', 95000, 105000),
(30, 'rw_upper_4', 'RW Upper Surface 4', 'Pa', 500, 'Pressure', 'Rear Wing', 'pressure_transducer', 'rear_wing_upper', 95000, 105000),
(31, 'rw_lower_1', 'RW Lower Surface 1', 'Pa', 500, 'Pressure', 'Rear Wing', 'pressure_transducer', 'rear_wing_lower', 95000, 105000),
(32, 'rw_lower_2', 'RW Lower Surface 2', 'Pa', 500, 'Pressure', 'Rear Wing', 'pressure_transducer', 'rear_wing_lower', 95000, 105000),
(33, 'rw_lower_3', 'RW Lower Surface 3', 'Pa', 500, 'Pressure', 'Rear Wing', 'pressure_transducer', 'rear_wing_lower', 95000, 105000),
(34, 'rw_lower_4', 'RW Lower Surface 4', 'Pa', 500, 'Pressure', 'Rear Wing', 'pressure_transducer', 'rear_wing_lower', 95000, 105000),
(35, 'rw_drs_1', 'RW DRS Flap 1', 'Pa', 500, 'Pressure', 'Rear Wing', 'pressure_transducer', 'rear_wing_drs', 95000, 105000),
(36, 'rw_drs_2', 'RW DRS Flap 2', 'Pa', 500, 'Pressure', 'Rear Wing', 'pressure_transducer', 'rear_wing_drs', 95000, 105000),
(37, 'rw_drs_3', 'RW DRS Flap 3', 'Pa', 500, 'Pressure', 'Rear Wing', 'pressure_transducer', 'rear_wing_drs', 95000, 105000),
(38, 'rw_drs_4', 'RW DRS Flap 4', 'Pa', 500, 'Pressure', 'Rear Wing', 'pressure_transducer', 'rear_wing_drs', 95000, 105000);

-- 5. Floor & Diffuser Pressure (12 channels @ 500 Hz)
INSERT INTO channels (channel_id, name, display_name, unit, sample_rate_hz, category, subcategory, sensor_type, physical_location, range_min, range_max) VALUES
(39, 'floor_fwd_1', 'Floor Forward 1', 'Pa', 500, 'Pressure', 'Floor', 'pressure_transducer', 'floor_forward', 95000, 105000),
(40, 'floor_fwd_2', 'Floor Forward 2', 'Pa', 500, 'Pressure', 'Floor', 'pressure_transducer', 'floor_forward', 95000, 105000),
(41, 'floor_fwd_3', 'Floor Forward 3', 'Pa', 500, 'Pressure', 'Floor', 'pressure_transducer', 'floor_forward', 95000, 105000),
(42, 'floor_fwd_4', 'Floor Forward 4', 'Pa', 500, 'Pressure', 'Floor', 'pressure_transducer', 'floor_forward', 95000, 105000),
(43, 'floor_mid_1', 'Floor Mid (Venturi) 1', 'Pa', 500, 'Pressure', 'Floor', 'pressure_transducer', 'floor_mid', 95000, 105000),
(44, 'floor_mid_2', 'Floor Mid (Venturi) 2', 'Pa', 500, 'Pressure', 'Floor', 'pressure_transducer', 'floor_mid', 95000, 105000),
(45, 'floor_mid_3', 'Floor Mid (Venturi) 3', 'Pa', 500, 'Pressure', 'Floor', 'pressure_transducer', 'floor_mid', 95000, 105000),
(46, 'floor_mid_4', 'Floor Mid (Venturi) 4', 'Pa', 500, 'Pressure', 'Floor', 'pressure_transducer', 'floor_mid', 95000, 105000),
(47, 'diffuser_1', 'Diffuser Exit 1', 'Pa', 500, 'Pressure', 'Diffuser', 'pressure_transducer', 'diffuser', 95000, 105000),
(48, 'diffuser_2', 'Diffuser Exit 2', 'Pa', 500, 'Pressure', 'Diffuser', 'pressure_transducer', 'diffuser', 95000, 105000),
(49, 'diffuser_3', 'Diffuser Exit 3', 'Pa', 500, 'Pressure', 'Diffuser', 'pressure_transducer', 'diffuser', 95000, 105000),
(50, 'diffuser_4', 'Diffuser Exit 4', 'Pa', 500, 'Pressure', 'Diffuser', 'pressure_transducer', 'diffuser', 95000, 105000);

-- 6. Sidepod & Bargeboard Pressure (8 channels @ 500 Hz)
INSERT INTO channels (channel_id, name, display_name, unit, sample_rate_hz, category, subcategory, sensor_type, physical_location, range_min, range_max) VALUES
(51, 'sidepod_1', 'Sidepod 1', 'Pa', 500, 'Pressure', 'Sidepod', 'pressure_transducer', 'sidepod', 95000, 105000),
(52, 'sidepod_2', 'Sidepod 2', 'Pa', 500, 'Pressure', 'Sidepod', 'pressure_transducer', 'sidepod', 95000, 105000),
(53, 'sidepod_3', 'Sidepod 3', 'Pa', 500, 'Pressure', 'Sidepod', 'pressure_transducer', 'sidepod', 95000, 105000),
(54, 'sidepod_4', 'Sidepod 4', 'Pa', 500, 'Pressure', 'Sidepod', 'pressure_transducer', 'sidepod', 95000, 105000),
(55, 'barge_1', 'Bargeboard 1', 'Pa', 500, 'Pressure', 'Bargeboard', 'pressure_transducer', 'bargeboard', 95000, 105000),
(56, 'barge_2', 'Bargeboard 2', 'Pa', 500, 'Pressure', 'Bargeboard', 'pressure_transducer', 'bargeboard', 95000, 105000),
(57, 'barge_3', 'Bargeboard 3', 'Pa', 500, 'Pressure', 'Bargeboard', 'pressure_transducer', 'bargeboard', 95000, 105000),
(58, 'barge_4', 'Bargeboard 4', 'Pa', 500, 'Pressure', 'Bargeboard', 'pressure_transducer', 'bargeboard', 95000, 105000);

-- 7. Velocity & Flow Sensors (6 channels @ 1000 Hz)
INSERT INTO channels (channel_id, name, display_name, unit, sample_rate_hz, category, subcategory, sensor_type, range_min, range_max, description) VALUES
(59, 'velocity_x', 'Tunnel Velocity (X)', 'm/s', 1000, 'Velocity', 'Freestream', 'pitot_static', 0, 80, 'Freestream tunnel velocity'),
(60, 'velocity_y', 'Crosswind (Y)', 'm/s', 1000, 'Velocity', 'Components', 'hot_wire', -10, 10, 'Lateral velocity component'),
(61, 'velocity_z', 'Vertical (Z)', 'm/s', 1000, 'Velocity', 'Components', 'hot_wire', -5, 5, 'Vertical velocity component'),
(62, 'turbulence', 'Turbulence Intensity', '%', 1000, 'Velocity', 'Quality', 'hot_wire', 0, 5, 'Flow turbulence intensity'),
(63, 'q_dynamic', 'Dynamic Pressure', 'Pa', 1000, 'Velocity', 'Pressure', 'pitot_static', 0, 5000, 'Dynamic pressure (0.5*rho*V^2)'),
(64, 'p_static', 'Static Pressure', 'Pa', 1000, 'Velocity', 'Pressure', 'pitot_static', 95000, 105000, 'Reference static pressure');

-- 8. Tunnel Environment (4 channels @ 100 Hz)
INSERT INTO channels (channel_id, name, display_name, unit, sample_rate_hz, category, subcategory, sensor_type, range_min, range_max, description) VALUES
(65, 'temp_tunnel', 'Tunnel Temperature', 'C', 100, 'Environment', 'Temperature', 'thermocouple', 10, 40, 'Test section air temperature'),
(66, 'humidity', 'Relative Humidity', '%', 100, 'Environment', 'Humidity', 'hygrometer', 20, 80, 'Test section humidity'),
(67, 'p_baro', 'Barometric Pressure', 'Pa', 100, 'Environment', 'Pressure', 'barometer', 95000, 105000, 'Ambient barometric pressure'),
(68, 'rho_air', 'Air Density', 'kg/m3', 100, 'Environment', 'Derived', 'calculated', 1.0, 1.4, 'Calculated air density');

-- 9. Model Position & Attitude (4 channels @ 100 Hz)
INSERT INTO channels (channel_id, name, display_name, unit, sample_rate_hz, category, subcategory, sensor_type, range_min, range_max, description) VALUES
(69, 'ride_height_f', 'Front Ride Height', 'mm', 100, 'Position', 'Ride Height', 'laser', 20, 60, 'Front axle ride height'),
(70, 'ride_height_r', 'Rear Ride Height', 'mm', 100, 'Position', 'Ride Height', 'laser', 30, 80, 'Rear axle ride height'),
(71, 'pitch_angle', 'Model Pitch', 'deg', 100, 'Position', 'Attitude', 'inclinometer', -3, 3, 'Model pitch attitude'),
(72, 'roll_angle', 'Model Roll', 'deg', 100, 'Position', 'Attitude', 'inclinometer', -1, 1, 'Model roll attitude');

PRINT 'Inserted 72 channel definitions';
GO

-- =============================================================================
-- VERIFICATION
-- =============================================================================
PRINT '';
PRINT '=== AEROSTREAM DATABASE INITIALIZED ===';
PRINT '';

SELECT 'Table Summary:' AS info;
SELECT 
    t.name AS table_name,
    p.rows AS row_count
FROM sys.tables t
JOIN sys.partitions p ON t.object_id = p.object_id
WHERE p.index_id IN (0, 1)
ORDER BY t.name;

PRINT '';
PRINT 'Production schema v2.0 deployed successfully!';
PRINT 'Tables: 18 total (7 reference, 4 run management, 3 time-series, 4 results/QC)';
GO
