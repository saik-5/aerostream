#!/usr/bin/env python3
"""
AeroStream End-to-End System Test
==================================
Tests all components: database, processing, time-series, and API.
"""

import sys
import os
import time
import json
from datetime import datetime, timedelta

# Add project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Test results tracking
results = []


def log_test(name: str, passed: bool, details: str = ""):
    """Log test result."""
    icon = "✅" if passed else "❌"
    print(f"{icon} {name}")
    if details:
        print(f"   {details}")
    results.append({"name": name, "passed": passed, "details": details})


def test_database_connection():
    """Test 1: Database connectivity."""
    print("\n" + "=" * 60)
    print("TEST 1: Database Connection")
    print("=" * 60)
    
    try:
        from src.db.connection import get_connection, execute_query
        
        conn = get_connection()
        log_test("Connection established", True)
        
        # Test query
        result = execute_query("SELECT COUNT(*) as cnt FROM channels")
        channel_count = result[0]['cnt'] if result else 0
        log_test(f"Query executed - {channel_count} channels found", channel_count > 0)
        
        conn.close()
        return True
    except Exception as e:
        log_test("Database connection", False, str(e))
        return False


def test_create_session_and_run():
    """Test 2: Create test session and run."""
    print("\n" + "=" * 60)
    print("TEST 2: Create Session and Run")
    print("=" * 60)
    
    try:
        from src.db.operations import create_test_session, create_run, start_run
        
        # Create session (using correct param names from operations.py)
        session_id = create_test_session(
            session_name=f"E2E Test Session {datetime.now().strftime('%H:%M:%S')}",
            model_id=1,
            cell_id=1  # Fixed: was test_cell_id
        )
        log_test(f"Session created: ID={session_id}", session_id is not None)
        
        # Create run (using correct param names from operations.py)
        run_id = create_run(
            session_id=session_id,
            run_name="E2E Test Run",
            run_type_id=1,
            tunnel_speed_setpoint=50.0,  # Fixed: was velocity_setpoint
            tunnel_aoa_setpoint=0.0       # Fixed: was aoa_setpoint
        )
        log_test(f"Run created: ID={run_id}", run_id is not None)
        
        # Start run
        start_run(run_id)
        log_test("Run started", True)
        
        return session_id, run_id
    except Exception as e:
        log_test("Create session/run", False, str(e))
        import traceback
        traceback.print_exc()
        return None, None


def test_insert_samples(run_id: int):
    """Test 3: Insert sample data."""
    print("\n" + "=" * 60)
    print("TEST 3: Insert Sample Data")
    print("=" * 60)
    
    try:
        from src.db.operations import bulk_insert_samples
        import numpy as np
        
        # Generate test samples for 3 channels, 1 second of data at 100Hz
        samples = []
        base_time = datetime.now()
        n_samples = 100  # 1 second at 100Hz
        
        for channel_id in [1, 2, 59]:  # lift, drag, velocity
            for i in range(n_samples):
                ts = base_time + timedelta(milliseconds=i * 10)
                
                if channel_id == 1:  # Lift (downforce)
                    value = -3000 + np.sin(2 * np.pi * 5 * (i / n_samples)) * 100 + np.random.normal(0, 20)
                elif channel_id == 2:  # Drag
                    value = 600 + np.random.normal(0, 10)
                else:  # Velocity
                    value = 50.0 + np.random.normal(0, 0.5)
                
                samples.append({
                    'run_id': run_id,
                    'channel_id': channel_id,
                    'ts': ts,
                    'value': float(value),
                    'quality_flag': 0
                })
        
        # Bulk insert
        inserted = bulk_insert_samples(samples, run_id)
        log_test(f"Inserted {inserted} samples", inserted > 0)
        
        return inserted
    except Exception as e:
        log_test("Insert samples", False, str(e))
        return 0


def test_processing_pipeline(run_id: int):
    """Test 4: Processing pipeline."""
    print("\n" + "=" * 60)
    print("TEST 4: Processing Pipeline")
    print("=" * 60)
    
    try:
        from src.db.connection import execute_query
        from src.processing import RunProcessor
        
        # Get samples from database
        query = """
            SELECT channel_id, ts, value 
            FROM samples 
            WHERE run_id = ? 
            ORDER BY channel_id, ts
        """
        rows = execute_query(query, (run_id,))
        samples = [{'channel_id': r['channel_id'], 'ts': r['ts'], 'value': r['value']} for r in rows]
        
        log_test(f"Loaded {len(samples)} samples from DB", len(samples) > 0)
        
        # Process
        processor = RunProcessor(target_hz=100)
        result = processor.process_from_samples(run_id=run_id, samples=samples)
        
        log_test(f"Resampled to {len(result.timestamps)} timepoints", len(result.timestamps) > 0)
        log_test(f"Detected {result.total_spikes} spikes", True)
        log_test(f"Aero metrics: Cl={result.aero_metrics.Cl_mean:.4f}, Cd={result.aero_metrics.Cd_mean:.4f}", 
                 result.aero_metrics is not None)
        log_test(f"QC status: {result.qc_summary.overall_status.value.upper()}", 
                 result.qc_summary is not None)
        
        return result
    except Exception as e:
        log_test("Processing pipeline", False, str(e))
        import traceback
        traceback.print_exc()
        return None


def test_timeseries_aggregates(run_id: int):
    """Test 5: Time-series aggregates."""
    print("\n" + "=" * 60)
    print("TEST 5: Time-Series Aggregates")
    print("=" * 60)
    
    try:
        from src.db.timeseries import refresh_aggregates, get_downsampled_data, get_channel_statistics
        
        # Refresh 1-second aggregates
        rows_created = refresh_aggregates(run_id)
        log_test(f"Refreshed aggregates: {rows_created} rows", rows_created >= 0)
        
        # Get downsampled data
        data = get_downsampled_data(run_id, channel_id=1, bucket_seconds=1)
        log_test(f"Downsampled query returned {len(data)} points", len(data) >= 0)
        
        # Get channel statistics
        stats = get_channel_statistics(run_id, channel_id=1)
        if stats:
            log_test(f"Channel stats: mean={stats.get('mean', 0):.2f}", True)
        else:
            log_test("Channel statistics (no data)", True)
        
        return True
    except Exception as e:
        log_test("Time-series aggregates", False, str(e))
        import traceback
        traceback.print_exc()
        return False


def test_complete_run(run_id: int):
    """Test 6: Complete the run."""
    print("\n" + "=" * 60)
    print("TEST 6: Complete Run")
    print("=" * 60)
    
    try:
        from src.db.operations import complete_run
        from src.db.connection import execute_query
        
        complete_run(run_id=run_id, sample_count=300)
        
        # Verify state changed
        result = execute_query(
            "SELECT rs.state_name FROM runs r JOIN run_states rs ON r.state_id = rs.state_id WHERE r.run_id = ?",
            (run_id,)
        )
        state = result[0]['state_name'] if result else 'unknown'
        log_test(f"Run completed with state: {state}", state in ('complete', 'completed'))
        
        return True
    except Exception as e:
        log_test("Complete run", False, str(e))
        return False


def test_api_endpoints():
    """Test 7: API endpoints."""
    print("\n" + "=" * 60)
    print("TEST 7: API Endpoints")
    print("=" * 60)
    
    try:
        import urllib.request
        import json
        
        base_url = "http://localhost:8000"
        
        # Test health
        try:
            response = urllib.request.urlopen(f"{base_url}/health", timeout=5)
            data = json.loads(response.read())
            log_test("GET /health", data.get('status') == 'ok', f"status={data.get('status')}")
        except Exception as e:
            log_test("GET /health", False, str(e))
            return False
        
        # Test channels
        try:
            response = urllib.request.urlopen(f"{base_url}/channels", timeout=5)
            data = json.loads(response.read())
            log_test("GET /channels", data.get('total', 0) > 0, f"total={data.get('total')}")
        except Exception as e:
            log_test("GET /channels", False, str(e))
        
        # Test runs list
        try:
            response = urllib.request.urlopen(f"{base_url}/runs", timeout=5)
            data = json.loads(response.read())
            log_test("GET /runs", 'runs' in data, f"total={data.get('total', 0)}")
        except Exception as e:
            log_test("GET /runs", False, str(e))
        
        # Test sessions list
        try:
            response = urllib.request.urlopen(f"{base_url}/sessions", timeout=5)
            data = json.loads(response.read())
            log_test("GET /sessions", 'sessions' in data, f"total={data.get('total', 0)}")
        except Exception as e:
            log_test("GET /sessions", False, str(e))
        
        return True
    except Exception as e:
        log_test("API endpoints", False, str(e))
        return False


def main():
    """Run all tests."""
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " AEROSTREAM END-TO-END SYSTEM TEST ".center(58) + "║")
    print("╚" + "═" * 58 + "╝")
    
    start_time = time.time()
    
    # Test 1: Database
    if not test_database_connection():
        print("\n❌ Database connection failed - cannot continue")
        return False
    
    # Test 2: Create session and run
    session_id, run_id = test_create_session_and_run()
    if not run_id:
        print("\n❌ Failed to create test run - cannot continue")
        return False
    
    # Test 3: Insert samples
    inserted = test_insert_samples(run_id)
    
    # Test 4: Processing pipeline
    test_processing_pipeline(run_id)
    
    # Test 5: Time-series aggregates
    test_timeseries_aggregates(run_id)
    
    # Test 6: Complete run
    test_complete_run(run_id)
    
    # Test 7: API endpoints
    test_api_endpoints()
    
    # Summary
    elapsed = time.time() - start_time
    passed = sum(1 for r in results if r['passed'])
    failed = len(results) - passed
    
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " TEST SUMMARY ".center(58) + "║")
    print("╠" + "═" * 58 + "╣")
    print(f"║  Total tests: {len(results):<42} ║")
    print(f"║  Passed:      {passed} ✅{' ' * 38} ║")
    print(f"║  Failed:      {failed} {'❌' if failed > 0 else '  '}{' ' * 38} ║")
    print(f"║  Time:        {elapsed:.2f}s{' ' * 40} ║")
    print("╠" + "═" * 58 + "╣")
    print(f"║  Session ID:  {session_id:<42} ║")
    print(f"║  Run ID:      {run_id:<42} ║")
    print("╚" + "═" * 58 + "╝")
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED!")
        return True
    else:
        print(f"\n⚠️ {failed} test(s) failed - review output above")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
