"""
Time-Series Database Utilities
==============================
Optimized queries for SQL Server time-series data.
Uses stored procedures and pre-aggregated tables for performance.
"""

from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import numpy as np

from src.db.connection import execute_query, execute_non_query, get_connection


def refresh_aggregates(run_id: int) -> int:
    """
    Refresh the 1-second aggregates for a run.
    Calls the sp_refresh_samples_1sec stored procedure.
    
    Args:
        run_id: Run ID to refresh
        
    Returns:
        Number of rows created
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("EXEC sp_refresh_samples_1sec @run_id = ?", (run_id,))
        conn.commit()
        
        # Get row count
        result = execute_query(
            "SELECT COUNT(*) as cnt FROM samples_1sec WHERE run_id = ?",
            (run_id,)
        )
        return result[0]['cnt'] if result else 0
    finally:
        cursor.close()
        conn.close()


def get_downsampled_data(
    run_id: int,
    channel_id: Optional[int] = None,
    bucket_seconds: int = 1,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None
) -> List[Dict[str, Any]]:
    """
    Get downsampled time-series data.
    Uses pre-aggregated data when available for 1-second buckets.
    
    Args:
        run_id: Run ID
        channel_id: Optional channel filter
        bucket_seconds: Time bucket size in seconds (1, 5, 10, 60, etc.)
        start_time: Optional start time filter
        end_time: Optional end time filter
        
    Returns:
        List of dicts with ts, value, min_value, max_value, sample_count
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            EXEC sp_get_downsampled_data 
                @run_id = ?,
                @channel_id = ?,
                @bucket_seconds = ?,
                @start_time = ?,
                @end_time = ?
        """, (run_id, channel_id, bucket_seconds, start_time, end_time))
        
        columns = [column[0] for column in cursor.description]
        rows = []
        for row in cursor.fetchall():
            rows.append(dict(zip(columns, row)))
        
        return rows
    finally:
        cursor.close()
        conn.close()


def get_channel_statistics(
    run_id: int,
    channel_id: int
) -> Dict[str, float]:
    """
    Get statistics for a channel using columnstore-optimized query.
    
    Args:
        run_id: Run ID
        channel_id: Channel ID
        
    Returns:
        Dict with mean, std, min, max, count
    """
    # This query benefits from the columnstore index
    result = execute_query("""
        SELECT 
            AVG(value) AS mean,
            STDEV(value) AS std,
            MIN(value) AS min_value,
            MAX(value) AS max_value,
            COUNT(*) AS sample_count
        FROM samples
        WHERE run_id = ? AND channel_id = ?
    """, (run_id, channel_id))
    
    if result:
        return {
            'mean': result[0]['mean'],
            'std': result[0]['std'],
            'min': result[0]['min_value'],
            'max': result[0]['max_value'],
            'count': result[0]['sample_count']
        }
    return {}


def get_time_range(run_id: int) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Get the time range for a run.
    
    Args:
        run_id: Run ID
        
    Returns:
        Tuple of (start_time, end_time)
    """
    result = execute_query("""
        SELECT MIN(ts) AS start_time, MAX(ts) AS end_time
        FROM samples
        WHERE run_id = ?
    """, (run_id,))
    
    if result:
        return result[0]['start_time'], result[0]['end_time']
    return None, None


def get_sample_count(run_id: int) -> int:
    """
    Get total sample count for a run.
    
    Args:
        run_id: Run ID
        
    Returns:
        Sample count
    """
    result = execute_query(
        "SELECT COUNT(*) AS cnt FROM samples WHERE run_id = ?",
        (run_id,)
    )
    return result[0]['cnt'] if result else 0


def get_raw_data(
    run_id: int,
    channel_ids: Optional[List[int]] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 100000
) -> List[Dict[str, Any]]:
    """
    Get raw sample data with optional filters.
    
    Args:
        run_id: Run ID
        channel_ids: Optional list of channels to include
        start_time: Optional start time filter
        end_time: Optional end time filter
        limit: Maximum rows to return
        
    Returns:
        List of sample dicts
    """
    query = "SELECT TOP (?) run_id, channel_id, ts, value, quality_flag FROM samples WHERE run_id = ?"
    params = [limit, run_id]
    
    if channel_ids:
        placeholders = ','.join(['?' for _ in channel_ids])
        query += f" AND channel_id IN ({placeholders})"
        params.extend(channel_ids)
    
    if start_time:
        query += " AND ts >= ?"
        params.append(start_time)
    
    if end_time:
        query += " AND ts <= ?"
        params.append(end_time)
    
    query += " ORDER BY channel_id, ts"
    
    return execute_query(query, tuple(params))


def get_data_as_arrays(
    run_id: int,
    channel_id: int,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Get channel data as numpy arrays for processing.
    
    Args:
        run_id: Run ID
        channel_id: Channel ID
        start_time: Optional start filter
        end_time: Optional end filter
        
    Returns:
        Tuple of (timestamps, values) as numpy arrays
    """
    query = "SELECT ts, value FROM samples WHERE run_id = ? AND channel_id = ?"
    params = [run_id, channel_id]
    
    if start_time:
        query += " AND ts >= ?"
        params.append(start_time)
    
    if end_time:
        query += " AND ts <= ?"
        params.append(end_time)
    
    query += " ORDER BY ts"
    
    rows = execute_query(query, tuple(params))
    
    if not rows:
        return np.array([]), np.array([])
    
    # Convert to arrays
    base_ts = rows[0]['ts']
    timestamps = np.array([
        (row['ts'] - base_ts).total_seconds() 
        for row in rows
    ])
    values = np.array([row['value'] for row in rows])
    
    return timestamps, values


if __name__ == "__main__":
    print("🗄️ Time-Series Utilities Test")
    print("=" * 50)
    
    # Quick test of module imports
    print("✅ Module loaded successfully")
    print("\nAvailable functions:")
    print("  - refresh_aggregates(run_id)")
    print("  - get_downsampled_data(run_id, channel_id, bucket_seconds)")
    print("  - get_channel_statistics(run_id, channel_id)")
    print("  - get_time_range(run_id)")
    print("  - get_sample_count(run_id)")
    print("  - get_raw_data(run_id, channel_ids, start, end)")
    print("  - get_data_as_arrays(run_id, channel_id)")
