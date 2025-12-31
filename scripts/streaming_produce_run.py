#!/usr/bin/env python3
"""
Create a run in SQL Server, then stream simulator samples to Kafka for that run.

This is the producer-side of the "live streaming" demo:
  WindTunnelSimulator -> Kafka topic -> (consumer inserts) -> SQL Server samples

Usage:
  python scripts/streaming_produce_run.py --duration 5
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import get_config  # noqa: E402
from src.simulator.sensor_simulator import WindTunnelSimulator, RunConfiguration  # noqa: E402
from src.streaming.producer import SensorDataProducer, create_topic_if_not_exists  # noqa: E402
from src.db.operations import create_test_session, create_run, start_run, complete_run  # noqa: E402
from src.db.connection import execute_query  # noqa: E402


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="AeroStream Kafka producer (Simulator -> Kafka)")
    parser.add_argument("--duration", type=float, default=5.0, help="Run duration seconds (default 5)")
    parser.add_argument("--variant", type=str, default="baseline", choices=["baseline", "variant_a", "variant_b"])
    parser.add_argument("--speed", type=float, default=50.0, help="Tunnel speed (m/s)")
    parser.add_argument("--aoa", type=float, default=0.0, help="Angle of attack (deg)")
    parser.add_argument("--yaw", type=float, default=0.0, help="Yaw angle (deg)")
    parser.add_argument("--name", type=str, default=None, help="Run name override")
    parser.add_argument("--real-time", action="store_true", help="Throttle to approximate real-time")
    parser.add_argument("--ingest-wait-seconds", type=int, default=60,
                        help="Max seconds to wait for consumer to ingest all samples before completing run")
    args = parser.parse_args()

    cfg = get_config()

    # Ensure topic exists
    create_topic_if_not_exists(cfg.kafka.bootstrap_servers, cfg.kafka.topic, num_partitions=6)

    # Create session + run in DB (metadata)
    session_id = create_test_session(
        session_name="Kafka Streaming Demo Session",
        objective="Live Kafka ingestion demo (simulator -> kafka -> consumer -> SQL Server)",
    )

    run_name = args.name or f"Kafka Stream - {args.variant} - {args.duration:.0f}s"
    run_id = create_run(
        run_name=run_name,
        session_id=session_id,
        tunnel_speed_setpoint=args.speed,
        tunnel_aoa_setpoint=args.aoa,
        tunnel_yaw_setpoint=args.yaw,
        notes="Created by scripts/streaming_produce_run.py",
    )

    start_run(run_id)

    # Build simulator config
    run_config = RunConfiguration(
        name=run_name,
        tunnel_speed=args.speed,
        tunnel_aoa=args.aoa,
        tunnel_yaw=args.yaw,
        variant=args.variant,
        duration_seconds=args.duration,
    )
    simulator = WindTunnelSimulator(run_config)

    expected_samples = int(args.duration * 38800)  # from README spec (72ch mixed rates)

    print("📤 AeroStream Kafka Producer (Simulator -> Kafka)")
    print("=" * 60)
    print(f"Kafka:     {cfg.kafka.bootstrap_servers}  topic={cfg.kafka.topic}")
    print(f"DB run_id:  {run_id}  session_id: {session_id}")
    print(f"Duration:  {args.duration}s  expected ~{expected_samples:,} samples")
    print("")

    # Stream samples
    with SensorDataProducer(cfg.kafka.bootstrap_servers, cfg.kafka.topic) as producer:
        stats = producer.stream_run(
            simulator=simulator,
            run_id=run_id,
            session_id=session_id,
            real_time=args.real_time,
            progress_interval=20000,
        )

    # Wait for the consumer to ingest the run before completing it.
    # This prevents runs.sample_count from being a partial "so far" value.
    target = int(stats.get("samples_sent", 0))
    inserted = 0
    last = -1
    stable_ticks = 0
    t0 = time.time()

    # Give consumer a brief head start
    time.sleep(2)

    while True:
        rows = execute_query("SELECT COUNT(*) AS cnt FROM samples WHERE run_id = ?", (run_id,))
        inserted = int(rows[0]["cnt"]) if rows else 0

        if target and inserted >= target:
            break

        if inserted == last:
            stable_ticks += 1
        else:
            stable_ticks = 0
            last = inserted

        # Defensive: if target is unknown (0), allow early exit once ingestion stabilizes.
        # When target is known (normal path), rely on the target or the explicit timeout.
        if not target and stable_ticks >= 10 and inserted > 0:
            break

        if time.time() - t0 >= args.ingest_wait_seconds:
            break

        time.sleep(1)

    complete_run(run_id=run_id, tunnel_speed_actual=args.speed, sample_count=inserted)

    print("")
    print("✅ Producer complete")
    print(f"  Kafka sent: {stats['samples_sent']:,}")
    if target:
        print(f"  DB inserted (final): {inserted:,} / target {target:,}")
    else:
        print(f"  DB inserted (final): {inserted:,}")
    print(f"  Run ID: {run_id}")
    print("")
    print("Open dashboard Explorer and refresh to see the new run.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


