"""
Runs Router
===========
Endpoints for wind tunnel run data.
"""

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query

from src.api.schemas import (
    RunSummary, RunDetail, RunListResponse,
    RunDataResponse, ChannelData, DataPoint,
    QCReport, QCCheck, RunStatistics,
    CompareRequest, CompareResponse, DeltaMetric
)
from src.db.connection import execute_query
from src.db.timeseries import get_downsampled_data, get_channel_statistics


router = APIRouter()


@router.get("", response_model=RunListResponse)
async def list_runs(
    session_id: Optional[int] = None,
    state: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100)
):
    """List all runs with optional filters."""
    # Use actual column names from schema + LEFT JOIN qc_summaries for qc_status
    query = """
        SELECT 
            r.run_id, r.run_number, r.run_name, r.session_id,
            rs.state_name as state,
            rt.type_name as run_type,
            r.ts_start, r.ts_end, r.sample_count,
            qs.overall_status as qc_status
        FROM runs r
        LEFT JOIN run_states rs ON r.state_id = rs.state_id
        LEFT JOIN run_types rt ON r.run_type_id = rt.run_type_id
        LEFT JOIN qc_summaries qs ON r.run_id = qs.run_id
        WHERE 1=1
    """
    params = []
    
    if session_id:
        query += " AND r.session_id = ?"
        params.append(session_id)
    
    if state:
        query += " AND rs.state_name = ?"
        params.append(state)
    
    # Get total count
    count_query = f"""
        SELECT COUNT(*) as total
        FROM runs r
        LEFT JOIN run_states rs ON r.state_id = rs.state_id
        WHERE 1=1
        {'AND r.session_id = ?' if session_id else ''}
        {'AND rs.state_name = ?' if state else ''}
    """
    count_params = []
    if session_id:
        count_params.append(session_id)
    if state:
        count_params.append(state)
    
    count_result = execute_query(count_query, tuple(count_params))
    total = count_result[0]['total'] if count_result else 0
    
    # Get QC stats (single efficient query)
    qc_stats_query = """
        SELECT 
            COUNT(*) as total_runs,
            SUM(CASE WHEN qs.overall_status = 'pass' THEN 1 ELSE 0 END) as passed,
            SUM(CASE WHEN qs.overall_status = 'warn' THEN 1 ELSE 0 END) as warned,
            SUM(CASE WHEN qs.overall_status = 'fail' THEN 1 ELSE 0 END) as failed,
            SUM(CASE WHEN qs.overall_status IS NULL THEN 1 ELSE 0 END) as not_run
        FROM runs r
        LEFT JOIN qc_summaries qs ON r.run_id = qs.run_id
    """
    qc_result = execute_query(qc_stats_query, ())
    qc_row = qc_result[0] if qc_result else {}
    
    total_runs = qc_row.get('total_runs', 0) or 0
    passed = qc_row.get('passed', 0) or 0
    pass_rate = (passed / total_runs * 100) if total_runs > 0 else 0.0
    
    from src.api.schemas import QCStats
    qc_stats = QCStats(
        total_runs=total_runs,
        passed=passed,
        warned=qc_row.get('warned', 0) or 0,
        failed=qc_row.get('failed', 0) or 0,
        not_run=qc_row.get('not_run', 0) or 0,
        pass_rate=round(pass_rate, 1)
    )
    
    # Add pagination
    offset = (page - 1) * page_size
    query += f" ORDER BY r.run_id DESC OFFSET {offset} ROWS FETCH NEXT {page_size} ROWS ONLY"
    
    rows = execute_query(query, tuple(params))
    
    runs = [RunSummary(
        run_id=row['run_id'],
        run_number=row['run_number'],
        run_name=row['run_name'],
        session_id=row['session_id'],
        state=row['state'] or 'unknown',
        run_type=row['run_type'],
        ts_start=row['ts_start'],
        ts_end=row['ts_end'],
        sample_count=row['sample_count'] or 0,
        qc_status=row['qc_status']  # From qc_summaries JOIN
    ) for row in rows]
    
    return RunListResponse(runs=runs, total=total, page=page, page_size=page_size, qc_stats=qc_stats)


@router.get("/{run_id}", response_model=RunDetail)
async def get_run(run_id: int):
    """Get detailed information about a specific run."""
    # Use actual column names from schema
    query = """
        SELECT 
            r.run_id, r.run_number, r.run_name, r.session_id,
            rs.state_name as state,
            rt.type_name as run_type,
            r.ts_start, r.ts_end, r.sample_count,
            r.tunnel_speed_setpoint as velocity_setpoint,
            r.tunnel_aoa_setpoint as aoa_setpoint,
            r.tunnel_yaw_setpoint as yaw_setpoint,
            r.roll_angle_deg as roll_setpoint,
            r.ride_height_f as ride_height_front,
            r.ride_height_r as ride_height_rear,
            r.notes
        FROM runs r
        LEFT JOIN run_states rs ON r.state_id = rs.state_id
        LEFT JOIN run_types rt ON r.run_type_id = rt.run_type_id
        WHERE r.run_id = ?
    """
    rows = execute_query(query, (run_id,))
    
    if not rows:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    row = rows[0]
    duration = None
    if row['ts_start'] and row['ts_end']:
        duration = (row['ts_end'] - row['ts_start']).total_seconds()
    
    return RunDetail(
        run_id=row['run_id'],
        run_number=row['run_number'],
        run_name=row['run_name'],
        session_id=row['session_id'],
        state=row['state'] or 'unknown',
        run_type=row['run_type'],
        ts_start=row['ts_start'],
        ts_end=row['ts_end'],
        duration_seconds=duration,
        sample_count=row['sample_count'] or 0,
        velocity_setpoint=row['velocity_setpoint'],
        aoa_setpoint=row['aoa_setpoint'],
        yaw_setpoint=row['yaw_setpoint'],
        roll_setpoint=row['roll_setpoint'],
        ride_height_front=row['ride_height_front'],
        ride_height_rear=row['ride_height_rear'],
        notes=row['notes']
    )


@router.get("/{run_id}/data", response_model=RunDataResponse)
async def get_run_data(
    run_id: int,
    channel_ids: Optional[str] = Query(default=None, description="Comma-separated channel IDs"),
    bucket_seconds: int = Query(default=1, ge=1, le=3600),
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None
):
    """
    Get time-series data for a run.
    Uses downsampled data for efficient D3.js rendering.
    """
    # Parse channel IDs
    channels_list = None
    if channel_ids:
        channels_list = [int(c.strip()) for c in channel_ids.split(",")]
    
    # Get channel info (using correct column names)
    channel_query = "SELECT channel_id, name as channel_code FROM channels"
    if channels_list:
        placeholders = ','.join(['?' for _ in channels_list])
        channel_query += f" WHERE channel_id IN ({placeholders})"
        channel_rows = execute_query(channel_query, tuple(channels_list))
    else:
        channel_rows = execute_query(channel_query, ())
    
    channel_codes = {row['channel_id']: row['channel_code'] for row in channel_rows}
    
    # Get downsampled data
    result_channels = []
    total_points = 0
    
    for ch_id in (channels_list or list(channel_codes.keys())[:10]):  # Limit to 10 channels
        data = get_downsampled_data(
            run_id=run_id,
            channel_id=ch_id,
            bucket_seconds=bucket_seconds,
            start_time=start_time,
            end_time=end_time
        )
        
        if data:
            points = [DataPoint(
                ts=row['ts'],
                value=row['value'],
                min_value=row.get('min_value'),
                max_value=row.get('max_value'),
                sample_count=row.get('sample_count')
            ) for row in data]
            
            result_channels.append(ChannelData(
                channel_id=ch_id,
                channel_code=channel_codes.get(ch_id),
                data=points
            ))
            total_points += len(points)
    
    return RunDataResponse(
        run_id=run_id,
        channels=result_channels,
        bucket_seconds=bucket_seconds,
        total_points=total_points
    )


@router.get("/{run_id}/statistics", response_model=RunStatistics)
async def get_run_statistics(run_id: int):
    """Get computed statistics for a run."""
    query = """
        SELECT * FROM run_statistics WHERE run_id = ?
    """
    rows = execute_query(query, (run_id,))
    
    if not rows:
        # No pre-computed stats, return basic info
        sample_count = execute_query(
            "SELECT COUNT(*) as cnt FROM samples WHERE run_id = ?",
            (run_id,)
        )
        return RunStatistics(
            run_id=run_id,
            total_samples=sample_count[0]['cnt'] if sample_count else 0,
            valid_samples=0,
            spike_count=0
        )
    
    row = rows[0]
    return RunStatistics(
        run_id=run_id,
        total_samples=row.get('total_samples', 0),
        valid_samples=row.get('valid_samples', 0),
        spike_count=row.get('spike_count', 0),
        cl_mean=row.get('cl_mean'),
        cl_std=row.get('cl_std'),
        cd_mean=row.get('cd_mean'),
        cd_std=row.get('cd_std'),
        efficiency=row.get('efficiency'),
        aero_balance_pct=row.get('aero_balance_pct')
    )


@router.get("/{run_id}/qc", response_model=QCReport)
async def get_run_qc(run_id: int):
    """Get QC report for a run."""
    # Get summary
    summary_query = "SELECT * FROM qc_summaries WHERE run_id = ?"
    summary_rows = execute_query(summary_query, (run_id,))
    
    if not summary_rows:
        # Return empty QC report if none exists
        return QCReport(
            run_id=run_id,
            overall_status="not_run",
            total_checks=0,
            passed_checks=0,
            warning_checks=0,
            failed_checks=0,
            checks=[],
            critical_issues=[],
            recommendations=["Run QC analysis first"]
        )
    
    summary = summary_rows[0]
    
    # Get individual checks
    checks_query = """
        SELECT 
            qr.rule_id, qr.status, qr.measured_value, qr.threshold_used, 
            qr.details, qr.channel_id,
            r.rule_code, r.rule_name
        FROM qc_results qr
        JOIN qc_rules r ON qr.rule_id = r.rule_id
        WHERE qr.run_id = ?
    """
    check_rows = execute_query(checks_query, (run_id,))
    
    checks = [QCCheck(
        rule_code=row['rule_code'],
        rule_name=row['rule_name'],
        status=row['status'],
        measured_value=row['measured_value'],
        threshold=row['threshold_used'],
        details=row['details'] or '',
        channel_id=row['channel_id']
    ) for row in check_rows]
    
    # Parse critical issues and recommendations
    critical = summary.get('critical_issues', '') or ''
    recommendations = summary.get('recommendations', '') or ''
    
    return QCReport(
        run_id=run_id,
        overall_status=summary['overall_status'],
        total_checks=summary['total_checks'],
        passed_checks=summary['passed_checks'],
        warning_checks=summary['warning_checks'],
        failed_checks=summary['failed_checks'],
        checks=checks,
        critical_issues=critical.split('; ') if critical else [],
        recommendations=recommendations.split('; ') if recommendations else []
    )


@router.post("/compare", response_model=CompareResponse)
async def compare_runs(request: CompareRequest):
    """Compare two runs and return deltas."""
    # Get statistics for both runs
    baseline_stats = await get_run_statistics(request.baseline_run_id)
    variant_stats = await get_run_statistics(request.variant_run_id)
    
    deltas = []
    
    # Compare key metrics
    metrics = [
        ('cl_mean', 'Lift Coefficient'),
        ('cd_mean', 'Drag Coefficient'),
        ('efficiency', 'L/D Efficiency'),
        ('aero_balance_pct', 'Aero Balance %')
    ]
    
    for metric_key, metric_name in metrics:
        baseline_val = getattr(baseline_stats, metric_key, None)
        variant_val = getattr(variant_stats, metric_key, None)
        
        if baseline_val is not None and variant_val is not None:
            delta = variant_val - baseline_val
            delta_pct = (delta / abs(baseline_val) * 100) if baseline_val != 0 else 0
            
            deltas.append(DeltaMetric(
                metric=metric_name,
                baseline_value=baseline_val,
                variant_value=variant_val,
                delta=delta,
                delta_pct=delta_pct
            ))
    
    # Generate summary
    summary_parts = []
    for d in deltas:
        if abs(d.delta_pct) > 1:
            direction = "increased" if d.delta > 0 else "decreased"
            summary_parts.append(f"{d.metric} {direction} by {abs(d.delta_pct):.1f}%")
    
    summary = "; ".join(summary_parts) if summary_parts else "No significant changes"
    
    return CompareResponse(
        baseline_run_id=request.baseline_run_id,
        variant_run_id=request.variant_run_id,
        deltas=deltas,
        summary=summary
    )
