-- Migration: Add demo_run_requests table (public demo request queue)
-- Safe to run multiple times.

IF OBJECT_ID('dbo.demo_run_requests', 'U') IS NULL
BEGIN
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
        run_id INT NULL,
        
        -- Metadata
        ip_address NVARCHAR(45) NULL,
        user_agent NVARCHAR(500) NULL,
        created_at DATETIME2 DEFAULT GETDATE(),
        reviewed_at DATETIME2 NULL
    );

    CREATE INDEX IX_demo_run_requests_status ON demo_run_requests(status, created_at DESC);
    CREATE INDEX IX_demo_run_requests_created ON demo_run_requests(created_at DESC);
    CREATE INDEX IX_demo_run_requests_run_id ON demo_run_requests(run_id);
END
GO

