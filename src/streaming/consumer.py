"""
Kafka Consumer for Wind Tunnel Sensor Data
===========================================
Consumes sensor data from Redpanda/Kafka and bulk inserts into SQL Server.
"""

import json
import time
import signal
import threading
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

from kafka import KafkaConsumer
from kafka.errors import KafkaError

from src.config import get_config
from src.db.operations import bulk_insert_samples, start_run, complete_run


class SensorDataConsumer:
    """
    Consumes wind tunnel sensor data from Kafka/Redpanda.
    Batches samples and bulk inserts to SQL Server.
    """
    
    def __init__(
        self,
        bootstrap_servers: str = "localhost:9092",
        topic: str = "wind-tunnel-data",
        group_id: str = "aerostream-consumer",
        batch_size: int = 20000,
        batch_timeout_ms: int = 1000
    ):
        """
        Initialize the Kafka consumer.
        
        Args:
            bootstrap_servers: Kafka/Redpanda broker address
            topic: Topic to consume from
            group_id: Consumer group ID
            batch_size: Samples to batch before insert
            batch_timeout_ms: Max wait time before flush
        """
        self.topic = topic
        self.batch_size = batch_size
        self.batch_timeout_ms = batch_timeout_ms
        
        # Create consumer
        self.consumer = KafkaConsumer(
            topic,
            bootstrap_servers=bootstrap_servers,
            group_id=group_id,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            key_deserializer=lambda k: int(k.decode('utf-8')) if k else None,
            auto_offset_reset='earliest',
            enable_auto_commit=False,  # Manual commit after insert
            max_poll_records=batch_size,
            fetch_max_wait_ms=batch_timeout_ms
        )
        
        self._running = False
        self._stats = defaultdict(int)
        self._buffer: Dict[int, List[Dict]] = defaultdict(list)  # run_id -> samples
        self._last_flush = time.time()
        
        # Timing instrumentation
        self._time_parsing = 0.0
        self._time_batching = 0.0
        self._time_db_insert = 0.0
        self._time_commit = 0.0
    
    def _flush_buffer(self, run_id: int) -> int:
        """
        Flush buffered samples to database.
        
        Args:
            run_id: Run ID to flush
            
        Returns:
            Number of samples inserted
        """
        samples = self._buffer.get(run_id, [])
        if not samples:
            return 0
        
        try:
            t0 = time.perf_counter()
            inserted = bulk_insert_samples(samples, run_id, batch_size=self.batch_size)
            self._time_db_insert += time.perf_counter() - t0
            self._stats['samples_inserted'] += inserted
            self._stats['batches_inserted'] += 1
            self._buffer[run_id] = []
            return inserted
        except Exception as e:
            self._stats['insert_errors'] += 1
            print(f"Error inserting batch: {e}")
            return 0
    
    def _flush_all_buffers(self) -> Tuple[int, bool]:
        """Flush all buffered data. Returns (total_inserted, all_succeeded)."""
        total = 0
        all_succeeded = True
        for run_id in list(self._buffer.keys()):
            inserted = self._flush_buffer(run_id)
            total += inserted
            if inserted == 0 and len(self._buffer.get(run_id, [])) > 0:
                all_succeeded = False  # Flush failed, don't commit offsets
        self._last_flush = time.time()
        return total, all_succeeded
    
    def _process_message(self, message) -> None:
        """
        Process a single Kafka message.
        
        Args:
            message: Kafka message with sensor data
        """
        try:
            data = message.value
            run_id = data['run_id']
            
            # Convert timestamp (support both epoch ms and ISO string)
            t0 = time.perf_counter()
            ts_raw = data['ts']
            if isinstance(ts_raw, int):
                # Epoch milliseconds (new, faster path)
                ts = datetime.fromtimestamp(ts_raw / 1000.0)
            else:
                # ISO string (backward compat)
                ts = datetime.fromisoformat(ts_raw)
            self._time_parsing += time.perf_counter() - t0
            
            t1 = time.perf_counter()
            sample = {
                'channel_id': data['channel_id'],
                'ts': ts,
                'value': data['value'],
                'quality_flag': data.get('quality_flag', 0)
            }
            
            self._buffer[run_id].append(sample)
            self._time_batching += time.perf_counter() - t1
            self._stats['messages_processed'] += 1
            
            # Flush if buffer is full
            if len(self._buffer[run_id]) >= self.batch_size:
                self._flush_buffer(run_id)
                
        except Exception as e:
            self._stats['parse_errors'] += 1
            print(f"Error processing message: {e}")
    
    def consume(
        self,
        max_messages: Optional[int] = None,
        max_time_seconds: Optional[int] = None,
        progress_interval: int = 10000
    ) -> Dict[str, int]:
        """
        Consume messages from Kafka and insert to database.
        
        Args:
            max_messages: Stop after N messages (None = unlimited)
            max_time_seconds: Stop after N seconds (None = unlimited)
            progress_interval: Print progress every N messages
            
        Returns:
            Stats dictionary
        """
        self._running = True
        self._stats = defaultdict(int)
        start_time = time.time()
        last_progress = 0
        
        print(f"Consuming from '{self.topic}'...")
        print(f"  Batch size: {self.batch_size}")
        print(f"  Batch timeout: {self.batch_timeout_ms}ms")
        
        try:
            while self._running:
                # Check time limit
                elapsed = time.time() - start_time
                if max_time_seconds and elapsed >= max_time_seconds:
                    print(f"\nTime limit reached ({max_time_seconds}s)")
                    break
                
                # Poll for messages
                records = self.consumer.poll(timeout_ms=self.batch_timeout_ms)
                
                for topic_partition, messages in records.items():
                    for message in messages:
                        self._process_message(message)
                        
                        # Check message limit
                        if max_messages and self._stats['messages_processed'] >= max_messages:
                            self._running = False
                            break
                    
                    if not self._running:
                        break
                
                # Flush on timeout or buffer full
                flush_needed = time.time() - self._last_flush > (self.batch_timeout_ms / 1000)
                if flush_needed or any(len(buf) >= self.batch_size for buf in self._buffer.values()):
                    total_flushed, flush_ok = self._flush_all_buffers()
                    
                    # Commit offsets ONLY after successful DB flush (at-least-once semantics)
                    if flush_ok and total_flushed > 0:
                        t_commit = time.perf_counter()
                        self.consumer.commit()
                        self._time_commit += time.perf_counter() - t_commit
                
                # Progress reporting
                processed = self._stats['messages_processed']
                if processed - last_progress >= progress_interval:
                    rate = processed / (time.time() - start_time)
                    inserted = self._stats['samples_inserted']
                    print(f"  Processed: {processed:,} | Inserted: {inserted:,} | Rate: {rate:,.0f}/sec")
                    last_progress = processed
                
        except KeyboardInterrupt:
            print("\nShutdown requested...")
        finally:
            # Final flush
            self._flush_all_buffers()
            self.consumer.commit()
        
        self._stats['elapsed_seconds'] = time.time() - start_time
        self._stats['rate_per_second'] = (
            self._stats['messages_processed'] / self._stats['elapsed_seconds']
            if self._stats['elapsed_seconds'] > 0 else 0
        )
        
        print(f"\n✅ Consumer stopped")
        print(f"   Messages processed: {self._stats['messages_processed']:,}")
        print(f"   Samples inserted: {self._stats['samples_inserted']:,}")
        print(f"   Elapsed: {self._stats['elapsed_seconds']:.2f}s")
        
        # Timing breakdown
        total_instrumented = self._time_parsing + self._time_batching + self._time_db_insert + self._time_commit
        if total_instrumented > 0:
            print(f"\n📊 Timing Breakdown:")
            print(f"   Parsing:    {self._time_parsing:.3f}s ({100*self._time_parsing/total_instrumented:.1f}%)")
            print(f"   Batching:   {self._time_batching:.3f}s ({100*self._time_batching/total_instrumented:.1f}%)")
            print(f"   DB Insert:  {self._time_db_insert:.3f}s ({100*self._time_db_insert/total_instrumented:.1f}%)")
            print(f"   Commit:     {self._time_commit:.3f}s ({100*self._time_commit/total_instrumented:.1f}%)")
        
        return dict(self._stats)
    
    def stop(self):
        """Signal consumer to stop."""
        self._running = False
    
    def close(self):
        """Close the consumer."""
        self._flush_all_buffers()
        self.consumer.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class EventConsumer:
    """
    Consumes run lifecycle events from Kafka.
    Handles run_start, run_complete, run_error events.
    """
    
    def __init__(
        self,
        bootstrap_servers: str = "localhost:9092",
        topic: str = "wind-tunnel-data-events",
        group_id: str = "aerostream-events"
    ):
        self.topic = topic
        self.consumer = KafkaConsumer(
            topic,
            bootstrap_servers=bootstrap_servers,
            group_id=group_id,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='earliest',
            enable_auto_commit=True
        )
    
    def process_events(self, timeout_seconds: int = 10):
        """Process run events for a limited time."""
        print(f"Processing events from '{self.topic}'...")
        
        end_time = time.time() + timeout_seconds
        
        while time.time() < end_time:
            records = self.consumer.poll(timeout_ms=1000)
            
            for topic_partition, messages in records.items():
                for message in messages:
                    event = message.value
                    event_type = event.get('event_type')
                    run_id = event.get('run_id')
                    
                    print(f"  Event: {event_type} for run {run_id}")
                    
                    if event_type == 'run_start':
                        try:
                            start_run(run_id)
                            print(f"    Started run {run_id}")
                        except Exception as e:
                            print(f"    Error starting run: {e}")
                    
                    elif event_type == 'run_complete':
                        metadata = event.get('metadata', {})
                        try:
                            complete_run(
                                run_id=run_id,
                                sample_count=metadata.get('sample_count')
                            )
                            print(f"    Completed run {run_id}")
                        except Exception as e:
                            print(f"    Error completing run: {e}")
        
        self.consumer.close()


def main():
    """Test the Kafka consumer."""
    print("=" * 60)
    print("🌪️  Kafka Consumer Test")
    print("=" * 60)
    
    config = get_config()
    bootstrap_servers = config.kafka.bootstrap_servers
    topic = config.kafka.topic
    
    print(f"\nConnecting to {bootstrap_servers}...")
    print(f"Topic: {topic}")
    
    with SensorDataConsumer(bootstrap_servers, topic) as consumer:
        stats = consumer.consume(
            max_messages=50000,  # Process up to 50K messages
            max_time_seconds=30,  # Or stop after 30 seconds
            progress_interval=10000
        )
    
    print(f"\n✅ Consumer test complete!")


if __name__ == "__main__":
    main()
