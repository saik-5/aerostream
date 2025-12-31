#!/usr/bin/env python3
"""
Run the Kafka -> SQL Server consumer as a long-running process.

Usage:
  python scripts/streaming_consumer.py
  python scripts/streaming_consumer.py --max-seconds 600 --batch-size 20000
  python scripts/streaming_consumer.py --benchmark  # Interview demo mode
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import get_config  # noqa: E402
from src.streaming.consumer import SensorDataConsumer  # noqa: E402


def main() -> int:
    import argparse
    import time

    parser = argparse.ArgumentParser(description="AeroStream Kafka consumer (Kafka -> SQL Server)")
    parser.add_argument("--max-seconds", type=int, default=600, help="Stop after N seconds (default 600)")
    parser.add_argument("--batch-size", type=int, default=20000, help="DB insert batch size (default 20000)")
    parser.add_argument("--group-id", type=str, default="aerostream-consumer-demo", help="Kafka consumer group id")
    parser.add_argument("--progress-interval", type=int, default=20000, help="Progress print interval (messages)")
    parser.add_argument("--benchmark", action="store_true", help="Benchmark mode: 30s test with summary table")
    args = parser.parse_args()

    cfg = get_config()

    # Benchmark mode overrides
    if args.benchmark:
        args.max_seconds = 30
        args.group_id = f"benchmark-{int(time.time())}"
        print("🏎️  BENCHMARK MODE (30 seconds)")
        print("=" * 60)
    else:
        print("🔄 AeroStream Kafka Consumer (Kafka -> SQL Server)")
        print("=" * 60)
    
    print(f"Kafka:  {cfg.kafka.bootstrap_servers}  topic={cfg.kafka.topic}")
    print(f"DB:     {cfg.db.host}:{cfg.db.port}/{cfg.db.database}")
    print(f"Batch:  {args.batch_size:,}")
    print("")

    with SensorDataConsumer(
        bootstrap_servers=cfg.kafka.bootstrap_servers,
        topic=cfg.kafka.topic,
        group_id=args.group_id,
        batch_size=args.batch_size,
    ) as consumer:
        stats = consumer.consume(
            max_messages=None,
            max_time_seconds=args.max_seconds,
            progress_interval=args.progress_interval,
        )
    
    # Benchmark summary table
    if args.benchmark and stats.get('messages_processed', 0) > 0:
        print("\n" + "=" * 60)
        print("📊 BENCHMARK SUMMARY")
        print("=" * 60)
        print(f"{'Metric':<25} {'Value':>15}")
        print("-" * 42)
        print(f"{'Messages Processed':<25} {stats.get('messages_processed', 0):>15,}")
        print(f"{'Samples Inserted':<25} {stats.get('samples_inserted', 0):>15,}")
        print(f"{'Batches':<25} {stats.get('batches_inserted', 0):>15,}")
        print(f"{'Batch Size':<25} {args.batch_size:>15,}")
        print(f"{'Elapsed (s)':<25} {stats.get('elapsed_seconds', 0):>15.2f}")
        print(f"{'Rate (samples/sec)':<25} {stats.get('rate_per_second', 0):>15,.0f}")
        print("=" * 60)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
