#!/usr/bin/env python3
"""
Admin helper: fulfill a public demo request (no-login workflow).

Usage:
  python scripts/admin_fulfill_demo_request.py 123

What it does:
  - Loads request from SQL Server (demo_run_requests)
  - Marks request status -> running
  - Starts Kafka consumer (optional)
  - Creates a run and streams simulator data to Kafka using the request parameters
  - Waits for ingestion to reach the produced sample target
  - Completes the run + runs QC/metrics processing
  - Marks request status -> completed and attaches run_id

Notes:
  - This updates the DB directly (does not require the API to be running).
  - Default consumer group id matches scripts/streaming_consumer.py to avoid re-consuming old topic data.
"""

import os
import sys
import time
import signal
import subprocess
from typing import Optional


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.config import get_config  # noqa: E402
from src.simulator.sensor_simulator import WindTunnelSimulator, RunConfiguration  # noqa: E402
from src.streaming.producer import SensorDataProducer, create_topic_if_not_exists  # noqa: E402
from src.db.connection import execute_query  # noqa: E402
from src.db.operations import (  # noqa: E402
    create_test_session,
    create_run,
    start_run,
    complete_run,
    get_demo_run_request,
    update_demo_run_request_status,
    attach_run_to_demo_request,
)


def _int(s: Optional[str], default: int) -> int:
    try:
        return int(s) if s is not None else default
    except Exception:
        return default


def _float(s: Optional[str], default: float) -> float:
    try:
        return float(s) if s is not None else default
    except Exception:
        return default


def _wait_for_ingestion(run_id: int, target: int, max_wait_seconds: int) -> int:
    """Wait until samples(run_id) reaches target (or timeout). Returns final inserted count."""
    last = -1
    stable_ticks = 0
    t0 = time.time()
    while True:
        rows = execute_query("SELECT COUNT(*) AS cnt FROM samples WHERE run_id = ?", (run_id,))
        inserted = int(rows[0]["cnt"]) if rows else 0

        if target and inserted >= target:
            return inserted

        if inserted == last:
            stable_ticks += 1
        else:
            stable_ticks = 0
            last = inserted

        # If no target (shouldn't happen), allow a conservative early exit once stabilized.
        if not target and stable_ticks >= 10 and inserted > 0:
            return inserted

        if time.time() - t0 >= max_wait_seconds:
            return inserted

        time.sleep(1)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Fulfill a demo_run_requests row (admin helper).")
    parser.add_argument("request_id", type=int, help="demo_run_requests.request_id")
    parser.add_argument("--start-consumer", action="store_true", help="Start consumer automatically (recommended locally)")
    parser.add_argument("--consumer-max-seconds", type=int, default=600, help="Consumer max seconds (default 600)")
    parser.add_argument("--consumer-batch-size", type=int, default=20000, help="Consumer batch size (default 20000)")
    parser.add_argument(
        "--consumer-group-id",
        type=str,
        default="aerostream-consumer-demo",
        help="Kafka consumer group id (default matches scripts/streaming_consumer.py)",
    )
    parser.add_argument("--ingest-wait-seconds", type=int, default=180, help="Max seconds to wait for ingestion (default 180)")
    parser.add_argument("--real-time", action="store_true", help="Throttle producer to approximate real-time")
    parser.add_argument("--force", action="store_true", help="Run even if request is already completed/rejected")
    args = parser.parse_args()

    cfg = get_config()

    req = get_demo_run_request(args.request_id)
    if not req:
        print(f"ERROR: request_id={args.request_id} not found")
        return 2

    status = (req.get("status") or "").lower()
    if status in {"completed", "rejected"} and not args.force:
        print(f"ERROR: request_id={args.request_id} status={status} (use --force to override)")
        return 2

    requested_variant = (req.get("requested_variant") or "baseline").strip()
    if requested_variant not in {"baseline", "variant_a", "variant_b"}:
        print(f"ERROR: request_id={args.request_id} invalid requested_variant={requested_variant!r}")
        return 2

    duration_sec = _float(req.get("requested_duration_sec"), 5.0)
    speed_ms = _float(req.get("requested_speed_ms"), 50.0)
    aoa_deg = _float(req.get("requested_aoa_deg"), 0.0)
    yaw_deg = _float(req.get("requested_yaw_deg"), 0.0)

    # Mark request running
    update_demo_run_request_status(args.request_id, "running", reviewer_notes="Running (admin helper)")

    consumer_proc: Optional[subprocess.Popen] = None
    try:
        # Ensure topic exists
        create_topic_if_not_exists(cfg.kafka.bootstrap_servers, cfg.kafka.topic, num_partitions=6)

        if args.start_consumer:
            consumer_cmd = [
                sys.executable,
                os.path.join(ROOT, "scripts", "streaming_consumer.py"),
                "--max-seconds",
                str(args.consumer_max_seconds),
                "--batch-size",
                str(args.consumer_batch_size),
                "--group-id",
                args.consumer_group_id,
            ]
            consumer_proc = subprocess.Popen(
                consumer_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            # Give the consumer a head start
            time.sleep(2)

        # Create session + run
        session_id = create_test_session(
            session_name="Website Demo Requests",
            objective="Auto-fulfilled from demo_run_requests (admin helper)",
        )
        run_name = f"Website Request #{args.request_id} - {requested_variant} - {duration_sec:.0f}s"
        run_id = create_run(
            run_name=run_name,
            session_id=session_id,
            tunnel_speed_setpoint=speed_ms,
            tunnel_aoa_setpoint=aoa_deg,
            tunnel_yaw_setpoint=yaw_deg,
            notes=f"Created by scripts/admin_fulfill_demo_request.py for request_id={args.request_id}",
        )
        attach_run_to_demo_request(args.request_id, run_id)
        start_run(run_id)

        # Stream simulator data
        run_config = RunConfiguration(
            name=run_name,
            tunnel_speed=speed_ms,
            tunnel_aoa=aoa_deg,
            tunnel_yaw=yaw_deg,
            variant=requested_variant,
            duration_seconds=duration_sec,
        )
        simulator = WindTunnelSimulator(run_config)

        print("📝 Fulfilling demo request")
        print("=" * 60)
        print(f"request_id: {args.request_id}  status: running")
        print(f"run_id:     {run_id}")
        print(f"variant:    {requested_variant}")
        print(f"duration:   {duration_sec}s")
        print(f"speed:      {speed_ms} m/s")
        print(f"aoa:        {aoa_deg} deg")
        print(f"yaw:        {yaw_deg} deg")
        print("")

        with SensorDataProducer(cfg.kafka.bootstrap_servers, cfg.kafka.topic) as producer:
            stats = producer.stream_run(
                simulator=simulator,
                run_id=run_id,
                session_id=session_id,
                real_time=args.real_time,
                progress_interval=20000,
            )

        target = int(stats.get("samples_sent", 0))
        inserted = _wait_for_ingestion(run_id, target=target, max_wait_seconds=args.ingest_wait_seconds)
        complete_run(run_id=run_id, tunnel_speed_actual=speed_ms, sample_count=inserted)

        # Process run for QC + metrics
        subprocess.run(
            [sys.executable, os.path.join(ROOT, "scripts", "process_run.py"), "--run-id", str(run_id)],
            check=True,
        )

        # Grab QC status for a nice completion note (best-effort)
        qc_rows = execute_query(
            "SELECT TOP 1 overall_status FROM qc_summaries WHERE run_id = ? ORDER BY computed_at DESC",
            (run_id,),
        )
        qc_status = (qc_rows[0]["overall_status"] if qc_rows else None) or "unknown"

        update_demo_run_request_status(
            args.request_id,
            "completed",
            reviewer_notes=f"Executed (run_id={run_id}) QC={qc_status}",
        )

        print("")
        print("✅ Request fulfilled")
        print(f"  request_id: {args.request_id}")
        print(f"  run_id:     {run_id}")
        print(f"  inserted:   {inserted:,} / target {target:,}")
        print(f"  QC:         {qc_status}")
        return 0

    except Exception as e:
        update_demo_run_request_status(args.request_id, "failed", reviewer_notes=f"Failed: {type(e).__name__}: {e}")
        raise

    finally:
        if consumer_proc and consumer_proc.poll() is None:
            # Try graceful stop first (flush + commit)
            try:
                consumer_proc.send_signal(signal.SIGINT)
                consumer_proc.wait(timeout=10)
            except Exception:
                try:
                    consumer_proc.terminate()
                    consumer_proc.wait(timeout=5)
                except Exception:
                    try:
                        consumer_proc.kill()
                    except Exception:
                        pass


if __name__ == "__main__":
    raise SystemExit(main())


