# Database Module

from src.db.connection import get_connection, execute_query, execute_non_query
from src.db.operations import (
    create_test_session,
    create_run,
    start_run,
    complete_run,
    bulk_insert_samples,
    save_run_statistics,
    save_qc_result,
    save_qc_summary,
    get_run,
    list_runs
)
from src.db.timeseries import (
    refresh_aggregates,
    get_downsampled_data,
    get_channel_statistics,
    get_time_range,
    get_sample_count,
    get_raw_data,
    get_data_as_arrays
)

__all__ = [
    # Connection
    'get_connection',
    'execute_query',
    'execute_non_query',
    
    # Operations
    'create_test_session',
    'create_run',
    'start_run',
    'complete_run',
    'bulk_insert_samples',
    'save_run_statistics',
    'save_qc_result',
    'save_qc_summary',
    'get_run',
    'list_runs',
    
    # Time-series
    'refresh_aggregates',
    'get_downsampled_data',
    'get_channel_statistics',
    'get_time_range',
    'get_sample_count',
    'get_raw_data',
    'get_data_as_arrays',
]
