#!/usr/bin/env python3
"""
Process a run and persist results (statistics + QC + aggregates) to SQL Server.

Typical usage (after generating demo runs):
  python scripts/process_run.py --run-id 123

This script is intentionally small and demo-friendly:
- Loads raw samples from `samples`
- Runs processing pipeline (resample -> despike -> aero metrics -> QC)
- Saves to `run_statistics`, `qc_summaries`, `qc_results`
- Refreshes `samples_1sec` aggregates for faster charting
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.processing.processor import RunProcessor
from src.db.timeseries import refresh_aggregates
from src.db.connection import execute_query, execute_non_query


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Process an existing run and persist results to DB")
    parser.add_argument("--run-id", type=int, required=True, help="Run ID to process")
    parser.add_argument("--target-hz", type=float, default=100.0, help="Resample target rate (Hz)")
    parser.add_argument("--despike-threshold", type=float, default=3.5, help="MAD threshold for spike detection")
    args = parser.parse_args()

    # Sync runs.sample_count to the true raw sample count before processing.
    # This prevents stale/partial metadata (common during streaming catch-up).
    rows = execute_query("SELECT COUNT(*) AS cnt FROM samples WHERE run_id = ?", (args.run_id,))
    sample_cnt = int(rows[0]["cnt"]) if rows else 0
    execute_non_query("UPDATE runs SET sample_count = ? WHERE run_id = ?", (sample_cnt, args.run_id))

    processor = RunProcessor(target_hz=args.target_hz, despike_threshold=args.despike_threshold)
    result = processor.process_from_database(run_id=args.run_id)
    processor.save_results(result)

    try:
        refresh_aggregates(args.run_id)
    except Exception as e:
        # Aggregates are an optimization; don't fail the whole script for this.
        print(f"Warning: could not refresh aggregates: {e}")

    print("")
    print("✅ Processing complete")
    print(f"  Run ID: {args.run_id}")
    print(f"  Raw samples (samples table): {sample_cnt:,}")
    if result.aero_metrics:
        print(f"  Cl mean: {result.aero_metrics.Cl_mean:.4f}")
        print(f"  Cd mean: {result.aero_metrics.Cd_mean:.4f}")
        print(f"  L/D mean: {result.aero_metrics.efficiency_mean:.2f}")
    if result.qc_summary:
        print(f"  QC: {result.qc_summary.overall_status.value.upper()} "
              f"({result.qc_summary.passed_checks}/{result.qc_summary.total_checks} passed)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


