"""
Database Operations Module
==========================
Production-grade database operations for AeroStream.
Supports enhanced schema v2.0 with sessions, states, and audit.
"""

import pyodbc
from typing import List, Dict, Any, Optional
from datetime import datetime

from src.db.connection import get_db_connection, execute_query, execute_non_query


# =============================================================================
# DEMO RUN REQUEST QUEUE (Public requests, admin approval)
# =============================================================================

def create_demo_run_request(
    requester_name: str | None,
    requester_email: str | None,
    requested_variant: str,
    requested_duration_sec: float,
    requested_speed_ms: float,
    requested_aoa_deg: float,
    requested_yaw_deg: float,
    requested_notes: str | None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> int:
    """Create a demo run request and return request_id."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO demo_run_requests (
                requester_name, requester_email,
                requested_variant, requested_duration_sec,
                requested_speed_ms, requested_aoa_deg, requested_yaw_deg,
                requested_notes, ip_address, user_agent
            )
            OUTPUT INSERTED.request_id
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                requester_name,
                requester_email,
                requested_variant,
                requested_duration_sec,
                requested_speed_ms,
                requested_aoa_deg,
                requested_yaw_deg,
                requested_notes,
                ip_address,
                user_agent,
            ),
        )
        request_id = cursor.fetchone()[0]
        conn.commit()
        return int(request_id)


def get_demo_run_request(request_id: int) -> Optional[Dict[str, Any]]:
    """Get demo run request by request_id."""
    rows = execute_query("SELECT * FROM demo_run_requests WHERE request_id = ?", (request_id,))
    return rows[0] if rows else None


def list_demo_run_requests(
    status: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """List demo run requests with optional status filter."""
    sql = "SELECT TOP (?) * FROM demo_run_requests WHERE 1=1"
    params: list[Any] = [limit]
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY created_at DESC"
    return execute_query(sql, tuple(params))


def update_demo_run_request_status(
    request_id: int,
    status: str,
    reviewer_notes: str | None = None,
) -> int:
    """Update request status (admin action)."""
    return execute_non_query(
        """
        UPDATE demo_run_requests
        SET status = ?,
            reviewer_notes = ?,
            reviewed_at = CASE WHEN ? IN ('approved','rejected','completed','failed') THEN GETDATE() ELSE reviewed_at END
        WHERE request_id = ?
        """,
        (status, reviewer_notes, status, request_id),
    )


def attach_run_to_demo_request(request_id: int, run_id: int) -> int:
    """Attach an executed run_id to a request."""
    return execute_non_query(
        "UPDATE demo_run_requests SET run_id = ? WHERE request_id = ?",
        (run_id, request_id),
    )


# =============================================================================
# TEST SESSION OPERATIONS
# =============================================================================

def create_test_session(
    session_name: str,
    cell_id: int = 1,
    model_id: int = 1,
    team_id: int = 1,
    session_date: Optional[datetime] = None,
    objective: str = "",
    session_lead_id: int = 1,
    created_by: int = 1
) -> int:
    """
    Create a new test session (groups runs by test day).
    
    Returns:
        session_id of the created session
    """
    if session_date is None:
        session_date = datetime.now()
    
    # Generate unique session code
    session_code = f"WT-{session_date.strftime('%Y%m%d')}-{datetime.now().strftime('%H%M%S')}"
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO test_sessions (
                session_name, session_code, cell_id, model_id, team_id,
                session_date, objective, session_lead_id, created_by
            )
            OUTPUT INSERTED.session_id
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_name, session_code, cell_id, model_id, team_id,
            session_date.date(), objective, session_lead_id, created_by
        ))
        session_id = cursor.fetchone()[0]
        conn.commit()
        return session_id


def get_session(session_id: int) -> Optional[Dict[str, Any]]:
    """Get session by ID."""
    results = execute_query("""
        SELECT s.*, c.cell_name, m.model_name, t.team_name
        FROM test_sessions s
        LEFT JOIN test_cells c ON s.cell_id = c.cell_id
        LEFT JOIN models m ON s.model_id = m.model_id
        LEFT JOIN teams t ON s.team_id = t.team_id
        WHERE s.session_id = ?
    """, (session_id,))
    return results[0] if results else None


# =============================================================================
# RUN OPERATIONS (Enhanced)
# =============================================================================

def get_next_run_number(session_id: int) -> int:
    """Get the next sequential run number for a session."""
    result = execute_query("""
        SELECT ISNULL(MAX(run_number), 0) + 1 as next_num
        FROM runs WHERE session_id = ?
    """, (session_id,))
    return result[0]['next_num']


def create_run(
    run_name: str,
    session_id: Optional[int] = None,
    run_type_id: int = 1,
    
    # Tunnel setpoints
    tunnel_speed_setpoint: float = 50.0,
    tunnel_aoa_setpoint: float = 0.0,
    tunnel_yaw_setpoint: float = 0.0,
    
    # Model configuration  
    ride_height_f: float = 30.0,
    ride_height_r: float = 50.0,
    front_wing_flap_deg: float = 0.0,
    rear_wing_flap_deg: float = 0.0,
    drs_open: bool = False,
    
    # Reference run for comparison
    baseline_run_id: Optional[int] = None,
    
    # Metadata
    priority: int = 5,
    tags: str = "",
    notes: str = "",
    created_by: int = 1
) -> int:
    """
    Create a new run record.
    
    Returns:
        run_id of the created run
    """
    run_number = get_next_run_number(session_id) if session_id else 1
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO runs (
                run_number, run_name, session_id, run_type_id, state_id,
                tunnel_speed_setpoint, tunnel_aoa_setpoint, tunnel_yaw_setpoint,
                ride_height_f, ride_height_r,
                front_wing_flap_deg, rear_wing_flap_deg, drs_open,
                baseline_run_id, priority, tags, notes, created_by
            )
            OUTPUT INSERTED.run_id
            VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_number, run_name, session_id, run_type_id,
            tunnel_speed_setpoint, tunnel_aoa_setpoint, tunnel_yaw_setpoint,
            ride_height_f, ride_height_r,
            front_wing_flap_deg, rear_wing_flap_deg, 1 if drs_open else 0,
            baseline_run_id, priority, tags, notes, created_by
        ))
        run_id = cursor.fetchone()[0]
        conn.commit()
        return run_id


def start_run(run_id: int) -> None:
    """Mark run as started (state: running)."""
    execute_non_query("""
        UPDATE runs 
        SET state_id = 2, ts_start = GETDATE()
        WHERE run_id = ?
    """, (run_id,))


def complete_run(
    run_id: int,
    tunnel_speed_actual: Optional[float] = None,
    tunnel_aoa_actual: Optional[float] = None,
    tunnel_yaw_actual: Optional[float] = None,
    tunnel_temp_actual: Optional[float] = None,
    air_density_actual: Optional[float] = None,
    sample_count: Optional[int] = None
) -> None:
    """Mark run as completed with actual conditions."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE runs 
            SET state_id = 3,
                ts_end = GETDATE(),
                duration_actual_sec = DATEDIFF(MILLISECOND, ts_start, GETDATE()) / 1000.0,
                tunnel_speed_actual = ?,
                tunnel_aoa_actual = ?,
                tunnel_yaw_actual = ?,
                tunnel_temp_actual = ?,
                air_density_actual = ?,
                sample_count = ?,
                modified_at = GETDATE()
            WHERE run_id = ?
        """, (
            tunnel_speed_actual, tunnel_aoa_actual, tunnel_yaw_actual,
            tunnel_temp_actual, air_density_actual, sample_count, run_id
        ))
        conn.commit()


def update_run_state(run_id: int, state_name: str, user_id: int = 1) -> None:
    """Update run state by state name."""
    state_map = {
        'draft': 1, 'running': 2, 'completed': 3, 'processing': 4,
        'validated': 5, 'rejected': 6, 'archived': 7
    }
    state_id = state_map.get(state_name.lower(), 3)
    
    execute_non_query("""
        UPDATE runs 
        SET state_id = ?, modified_at = GETDATE(), modified_by = ?
        WHERE run_id = ?
    """, (state_id, user_id, run_id))


def get_run(run_id: int) -> Optional[Dict[str, Any]]:
    """Get run with all related data."""
    results = execute_query("""
        SELECT r.*, 
               rs.state_name,
               rt.type_name as run_type_name,
               s.session_name,
               m.model_name
        FROM runs r
        LEFT JOIN run_states rs ON r.state_id = rs.state_id
        LEFT JOIN run_types rt ON r.run_type_id = rt.run_type_id
        LEFT JOIN test_sessions s ON r.session_id = s.session_id
        LEFT JOIN models m ON s.model_id = m.model_id
        WHERE r.run_id = ?
    """, (run_id,))
    return results[0] if results else None


def list_runs(
    session_id: Optional[int] = None,
    state: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """List runs with optional filters."""
    sql = """
        SELECT r.run_id, r.run_number, r.run_name, r.ts_start, r.ts_end,
               r.tunnel_speed_setpoint, r.tunnel_aoa_setpoint,
               r.sample_count, r.data_quality_score,
               rs.state_name, rt.type_name
        FROM runs r
        LEFT JOIN run_states rs ON r.state_id = rs.state_id
        LEFT JOIN run_types rt ON r.run_type_id = rt.run_type_id
        WHERE 1=1
    """
    params = []
    
    if session_id:
        sql += " AND r.session_id = ?"
        params.append(session_id)
    
    if state:
        sql += " AND rs.state_name = ?"
        params.append(state)
    
    sql += f" ORDER BY r.ts_start DESC OFFSET 0 ROWS FETCH NEXT {limit} ROWS ONLY"
    
    return execute_query(sql, tuple(params))


# =============================================================================
# BULK INSERT OPERATIONS
# =============================================================================

def bulk_insert_samples(
    samples: List[Dict[str, Any]],
    run_id: int,
    batch_size: int = 5000
) -> int:
    """
    Bulk insert samples using pyodbc fast_executemany.
    
    Args:
        samples: List of dicts with channel_id, ts, value, quality_flag (optional)
        run_id: Run ID
        batch_size: Rows per batch
        
    Returns:
        Total rows inserted
    """
    if not samples:
        return 0
    
    total_inserted = 0
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.fast_executemany = True
        
        sql = """
            INSERT INTO samples (run_id, channel_id, ts, value, quality_flag) 
            VALUES (?, ?, ?, ?, ?)
        """
        
        for i in range(0, len(samples), batch_size):
            batch = samples[i:i + batch_size]
            
            params = [
                (
                    run_id,
                    s["channel_id"],
                    s["ts"] if isinstance(s["ts"], datetime) else datetime.fromisoformat(str(s["ts"])),
                    float(s["value"]),
                    s.get("quality_flag", 0)
                )
                for s in batch
            ]
            
            cursor.executemany(sql, params)
            total_inserted += len(batch)
        
        conn.commit()
    
    return total_inserted


# =============================================================================
# STATISTICS OPERATIONS
# =============================================================================

def save_run_statistics(run_id: int, stats: Dict[str, Any]) -> int:
    """Save computed statistics for a run."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Check if already exists
        cursor.execute("SELECT stat_id FROM run_statistics WHERE run_id = ?", (run_id,))
        existing = cursor.fetchone()
        
        if existing:
            cursor.execute("""
                UPDATE run_statistics SET
                    total_samples = ?, valid_samples = ?, spike_count = ?,
                    lift_mean = ?, lift_std = ?, drag_mean = ?, drag_std = ?,
                    cl_mean = ?, cd_mean = ?, efficiency = ?, aero_balance_pct = ?,
                    computed_at = GETDATE()
                WHERE run_id = ?
            """, (
                stats.get('total_samples'), stats.get('valid_samples'), stats.get('spike_count'),
                stats.get('lift_mean'), stats.get('lift_std'),
                stats.get('drag_mean'), stats.get('drag_std'),
                stats.get('cl_mean'), stats.get('cd_mean'),
                stats.get('efficiency'), stats.get('aero_balance_pct'),
                run_id
            ))
            stat_id = existing[0]
        else:
            cursor.execute("""
                INSERT INTO run_statistics (
                    run_id, total_samples, valid_samples, spike_count,
                    lift_mean, lift_std, drag_mean, drag_std,
                    cl_mean, cd_mean, efficiency, aero_balance_pct
                )
                OUTPUT INSERTED.stat_id
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run_id,
                stats.get('total_samples'), stats.get('valid_samples'), stats.get('spike_count'),
                stats.get('lift_mean'), stats.get('lift_std'),
                stats.get('drag_mean'), stats.get('drag_std'),
                stats.get('cl_mean'), stats.get('cd_mean'),
                stats.get('efficiency'), stats.get('aero_balance_pct')
            ))
            stat_id = cursor.fetchone()[0]
        
        conn.commit()
        return stat_id


# =============================================================================
# QC OPERATIONS
# =============================================================================

def save_qc_result(
    run_id: int,
    rule_id: int,
    status: str,
    measured_value: Optional[float] = None,
    threshold_used: Optional[float] = None,
    details: str = "",
    channel_id: Optional[int] = None
) -> int:
    """Save a QC check result."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO qc_results (
                run_id, rule_id, channel_id, status,
                measured_value, threshold_used, details
            )
            OUTPUT INSERTED.result_id
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (run_id, rule_id, channel_id, status, measured_value, threshold_used, details))
        result_id = cursor.fetchone()[0]
        conn.commit()
        return result_id


def save_qc_summary(
    run_id: int,
    overall_status: str,
    total_checks: int,
    passed_checks: int,
    warning_checks: int,
    failed_checks: int,
    critical_issues: str = "",
    recommendations: str = ""
) -> int:
    """Save QC summary for a run."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Upsert
        cursor.execute("SELECT summary_id FROM qc_summaries WHERE run_id = ?", (run_id,))
        existing = cursor.fetchone()
        
        if existing:
            cursor.execute("""
                UPDATE qc_summaries SET
                    overall_status = ?, total_checks = ?, passed_checks = ?,
                    warning_checks = ?, failed_checks = ?, skipped_checks = ?,
                    critical_issues = ?, recommendations = ?, computed_at = GETDATE()
                WHERE run_id = ?
            """, (
                overall_status, total_checks, passed_checks,
                warning_checks, failed_checks, 0,
                critical_issues, recommendations, run_id
            ))
            summary_id = existing[0]
        else:
            cursor.execute("""
                INSERT INTO qc_summaries (
                    run_id, overall_status, total_checks, passed_checks,
                    warning_checks, failed_checks, skipped_checks,
                    critical_issues, recommendations
                )
                OUTPUT INSERTED.summary_id
                VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
            """, (
                run_id, overall_status, total_checks, passed_checks,
                warning_checks, failed_checks, critical_issues, recommendations
            ))
            summary_id = cursor.fetchone()[0]
        
        # Update run state to validated or rejected
        if overall_status == 'pass':
            execute_non_query("UPDATE runs SET state_id = 5 WHERE run_id = ?", (run_id,))
        elif overall_status == 'fail':
            execute_non_query("UPDATE runs SET state_id = 6 WHERE run_id = ?", (run_id,))
        
        conn.commit()
        return summary_id


# =============================================================================
# AUDIT OPERATIONS
# =============================================================================

def log_audit(
    table_name: str,
    record_id: int,
    action: str,
    user_id: int = 1,
    changed_fields: str = "",
    old_values: str = "",
    new_values: str = ""
) -> None:
    """Log an audit entry."""
    execute_non_query("""
        INSERT INTO audit_log (
            table_name, record_id, action, changed_fields,
            old_values, new_values, user_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (table_name, record_id, action, changed_fields, old_values, new_values, user_id))


if __name__ == "__main__":
    # Test the module
    print("Testing database operations...")
    
    # Create a test session
    session_id = create_test_session(
        session_name="Test Session",
        objective="Module testing"
    )
    print(f"Created session_id: {session_id}")
    
    # Create a run
    run_id = create_run(
        run_name="Test Run",
        session_id=session_id,
        tunnel_speed_setpoint=50.0
    )
    print(f"Created run_id: {run_id}")
    
    # Get run details
    run = get_run(run_id)
    print(f"Run state: {run['state_name']}")
    
    print("✅ Database operations module working!")
