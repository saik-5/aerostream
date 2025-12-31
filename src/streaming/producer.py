"""
Kafka Producer for Wind Tunnel Sensor Data
===========================================
Streams simulated sensor data to Redpanda/Kafka for real-time processing.
"""

import json
import time
from datetime import datetime
from typing import Dict, Generator, Optional
from dataclasses import asdict

from kafka import KafkaProducer
from kafka.errors import KafkaError

from src.config import get_config
from src.simulator.sensor_simulator import WindTunnelSimulator, RunConfiguration


class SensorDataProducer:
    """
    Produces wind tunnel sensor data to Kafka/Redpanda.
    Streams samples in real-time with configurable batching.
    """
    
    def __init__(
        self,
        bootstrap_servers: str = "localhost:9092",
        topic: str = "wind-tunnel-data",
        batch_size: int = 100,
        linger_ms: int = 10
    ):
        """
        Initialize the Kafka producer.
        
        Args:
            bootstrap_servers: Kafka/Redpanda broker address
            topic: Topic to produce to
            batch_size: Samples to batch before sending
            linger_ms: Max wait time for batching
        """
        self.topic = topic
        self.batch_size = batch_size
        
        # Create producer with JSON serialization
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
            key_serializer=lambda k: str(k).encode('utf-8') if k else None,
            acks='all',  # Wait for all replicas
            retries=3,
            batch_size=16384,  # 16KB batches
            linger_ms=linger_ms,
            compression_type='gzip',  # Standard compression
            max_in_flight_requests_per_connection=5
        )
        
        self._message_count = 0
        self._error_count = 0
    
    def _on_success(self, metadata):
        """Callback for successful sends."""
        self._message_count += 1
    
    def _on_error(self, error):
        """Callback for failed sends."""
        self._error_count += 1
        print(f"Error sending message: {error}")
    
    def send_sample(
        self,
        run_id: int,
        session_id: int,
        channel_id: int,
        timestamp: datetime,
        value: float,
        quality_flag: int = 0
    ) -> None:
        """
        Send a single sensor sample to Kafka.
        
        Args:
            run_id: Run identifier
            session_id: Session identifier
            channel_id: Channel identifier
            timestamp: Sample timestamp
            value: Sensor value
            quality_flag: Data quality flag
        """
        message = {
            "run_id": run_id,
            "session_id": session_id,
            "channel_id": channel_id,
            "ts": int(timestamp.timestamp() * 1000),  # Epoch milliseconds (faster parsing)
            "value": value,
            "quality_flag": quality_flag,
            "produced_at": int(datetime.now().timestamp() * 1000)
        }
        
        # Use channel_id as key for partitioning
        # Same channel always goes to same partition (ordering)
        future = self.producer.send(
            self.topic,
            key=channel_id,
            value=message
        )
        future.add_callback(self._on_success)
        future.add_errback(self._on_error)
    
    def send_batch(
        self,
        samples: list,
        run_id: int,
        session_id: int
    ) -> int:
        """
        Send a batch of samples to Kafka.
        
        Args:
            samples: List of sample dicts with channel_id, ts, value
            run_id: Run identifier
            session_id: Session identifier
            
        Returns:
            Number of samples sent
        """
        for sample in samples:
            self.send_sample(
                run_id=run_id,
                session_id=session_id,
                channel_id=sample["channel_id"],
                timestamp=sample["ts"],
                value=sample["value"],
                quality_flag=sample.get("quality_flag", 0)
            )
        
        return len(samples)
    
    def stream_run(
        self,
        simulator: WindTunnelSimulator,
        run_id: int,
        session_id: int,
        real_time: bool = False,
        progress_interval: int = 10000
    ) -> Dict[str, any]:
        """
        Stream an entire run to Kafka.
        
        Args:
            simulator: Configured WindTunnelSimulator
            run_id: Run identifier
            session_id: Session identifier
            real_time: If True, stream at actual sample rates
            progress_interval: Print progress every N samples
            
        Returns:
            Stats dict with counts and timing
        """
        start_time = time.time()
        sample_count = 0
        last_progress = 0
        
        print(f"Streaming run {run_id} to Kafka topic '{self.topic}'...")
        
        for sample in simulator.generate_run():
            self.send_sample(
                run_id=run_id,
                session_id=session_id,
                channel_id=sample["channel_id"],
                timestamp=sample["ts"],
                value=sample["value"]
            )
            sample_count += 1
            
            # Progress reporting
            if sample_count - last_progress >= progress_interval:
                elapsed = time.time() - start_time
                rate = sample_count / elapsed
                print(f"  Streamed {sample_count:,} samples ({rate:,.0f}/sec)")
                last_progress = sample_count
            
            # Real-time simulation (slow down to match sample rate)
            if real_time and sample_count % 1000 == 0:
                time.sleep(0.001)  # ~1ms delay per 1000 samples
        
        # Flush remaining messages
        self.producer.flush()
        
        elapsed = time.time() - start_time
        
        stats = {
            "samples_sent": sample_count,
            "elapsed_seconds": elapsed,
            "rate_per_second": sample_count / elapsed if elapsed > 0 else 0,
            "errors": self._error_count
        }
        
        print(f"  ✅ Complete: {sample_count:,} samples in {elapsed:.2f}s")
        print(f"     Rate: {stats['rate_per_second']:,.0f} samples/sec")
        
        return stats
    
    def send_run_event(
        self,
        event_type: str,
        run_id: int,
        session_id: int,
        metadata: Dict = None
    ) -> None:
        """
        Send a run lifecycle event (start, complete, error).
        
        Args:
            event_type: 'run_start', 'run_complete', 'run_error'
            run_id: Run identifier
            session_id: Session identifier
            metadata: Additional event data
        """
        event = {
            "event_type": event_type,
            "run_id": run_id,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        
        self.producer.send(
            f"{self.topic}-events",
            key=run_id,
            value=event
        )
        self.producer.flush()
    
    def close(self):
        """Close the producer."""
        self.producer.flush()
        self.producer.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def create_topic_if_not_exists(
    bootstrap_servers: str = "localhost:9092",
    topic: str = "wind-tunnel-data",
    num_partitions: int = 6,
    replication_factor: int = 1
) -> bool:
    """
    Create Kafka topic if it doesn't exist.
    
    Args:
        bootstrap_servers: Kafka broker address
        topic: Topic name
        num_partitions: Number of partitions (recommend 6 for 72 channels)
        replication_factor: Replication factor
        
    Returns:
        True if created or exists, False on error
    """
    from kafka.admin import KafkaAdminClient, NewTopic
    from kafka.errors import TopicAlreadyExistsError
    
    try:
        admin = KafkaAdminClient(
            bootstrap_servers=bootstrap_servers,
            client_id='aerostream-admin'
        )
        
        # Check if topic exists
        existing = admin.list_topics()
        if topic in existing:
            print(f"Topic '{topic}' already exists")
            admin.close()
            return True
        
        # Create topic
        new_topic = NewTopic(
            name=topic,
            num_partitions=num_partitions,
            replication_factor=replication_factor
        )
        
        admin.create_topics([new_topic])
        print(f"Created topic '{topic}' with {num_partitions} partitions")
        
        # Also create events topic
        events_topic = NewTopic(
            name=f"{topic}-events",
            num_partitions=1,
            replication_factor=replication_factor
        )
        try:
            admin.create_topics([events_topic])
            print(f"Created topic '{topic}-events'")
        except TopicAlreadyExistsError:
            pass
        
        admin.close()
        return True
        
    except TopicAlreadyExistsError:
        print(f"Topic '{topic}' already exists")
        return True
    except Exception as e:
        print(f"Error creating topic: {e}")
        return False


def main():
    """Test the Kafka producer."""
    print("=" * 60)
    print("🌪️  Kafka Producer Test")
    print("=" * 60)
    
    # Get config
    config = get_config()
    bootstrap_servers = config.kafka.bootstrap_servers
    topic = config.kafka.topic
    
    # Create topics
    print(f"\nCreating topics on {bootstrap_servers}...")
    create_topic_if_not_exists(bootstrap_servers, topic, num_partitions=6)
    
    # Create a short test run
    run_config = RunConfiguration(
        name="Kafka Producer Test",
        tunnel_speed=50.0,
        variant="baseline",
        duration_seconds=1.0  # 1 second = 38,800 samples
    )
    
    simulator = WindTunnelSimulator(run_config)
    
    print(f"\nStreaming test run to Kafka...")
    
    with SensorDataProducer(bootstrap_servers, topic) as producer:
        stats = producer.stream_run(
            simulator=simulator,
            run_id=999,  # Test run ID
            session_id=999,
            progress_interval=10000
        )
    
    print(f"\n✅ Kafka producer test complete!")
    print(f"   Samples sent: {stats['samples_sent']:,}")
    print(f"   Rate: {stats['rate_per_second']:,.0f} samples/sec")


if __name__ == "__main__":
    main()
