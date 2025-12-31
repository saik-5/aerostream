"""
AeroStream Configuration Module
===============================
Handles environment variables and secret management.
Supports both .env files (dev) and OpenBao (prod).
"""

import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()


@dataclass
class DatabaseConfig:
    """SQL Server database configuration."""
    host: str
    port: int
    database: str
    username: str
    password: str
    driver: str = "ODBC Driver 18 for SQL Server"
    
    @property
    def connection_string(self) -> str:
        """Generate pyodbc connection string."""
        return (
            f"DRIVER={{{self.driver}}};"
            f"SERVER={self.host},{self.port};"
            f"DATABASE={self.database};"
            f"UID={self.username};"
            f"PWD={self.password};"
            f"TrustServerCertificate=yes;"
        )
    
    @property
    def sqlalchemy_url(self) -> str:
        """Generate SQLAlchemy connection URL."""
        return (
            f"mssql+pyodbc://{self.username}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
            f"?driver={self.driver.replace(' ', '+')}&TrustServerCertificate=yes"
        )


@dataclass
class KafkaConfig:
    """Kafka/Redpanda configuration."""
    bootstrap_servers: str
    topic: str = "wind-tunnel-data"


@dataclass
class Config:
    """Main application configuration."""
    db: DatabaseConfig
    kafka: KafkaConfig
    api_host: str = "0.0.0.0"
    api_port: int = 8000


def _get_from_openbao() -> Optional[dict]:
    """
    Fetch secrets from OpenBao/Vault if configured.
    Returns None if OpenBao is not configured.
    """
    openbao_addr = os.getenv("OPENBAO_ADDR")
    openbao_token = os.getenv("OPENBAO_TOKEN")
    
    if not openbao_addr or not openbao_token:
        return None
    
    try:
        import hvac
        client = hvac.Client(url=openbao_addr, token=openbao_token)
        
        if not client.is_authenticated():
            print("Warning: OpenBao authentication failed, falling back to .env")
            return None
        
        # Read database secrets
        db_secrets = client.secrets.kv.v2.read_secret_version(
            path="aerostream/db"
        )["data"]["data"]
        
        # Read kafka secrets
        kafka_secrets = client.secrets.kv.v2.read_secret_version(
            path="aerostream/kafka"
        )["data"]["data"]
        
        return {
            "db": db_secrets,
            "kafka": kafka_secrets
        }
    except Exception as e:
        print(f"Warning: OpenBao error ({e}), falling back to .env")
        return None


def load_config() -> Config:
    """
    Load configuration from OpenBao (prod) or .env (dev).
    OpenBao takes precedence if configured.
    """
    # Try OpenBao first
    secrets = _get_from_openbao()
    
    if secrets:
        # Production mode: use OpenBao secrets
        db_config = DatabaseConfig(
            host=secrets["db"].get("host", "localhost"),
            port=int(secrets["db"].get("port", 1433)),
            database=secrets["db"].get("database", "aerostream"),
            username=secrets["db"].get("username", "sa"),
            password=secrets["db"]["password"],
        )
        kafka_config = KafkaConfig(
            bootstrap_servers=secrets["kafka"].get("bootstrap_servers", "localhost:9092"),
            topic=secrets["kafka"].get("topic", "wind-tunnel-data"),
        )
    else:
        # Development mode: use .env variables
        db_config = DatabaseConfig(
            host=os.getenv("SQL_SERVER_HOST", "localhost"),
            port=int(os.getenv("SQL_SERVER_PORT", "1433")),
            database=os.getenv("SQL_SERVER_DATABASE", "aerostream"),
            username="sa",
            password=os.getenv("SQL_SERVER_PASSWORD", ""),
        )
        kafka_config = KafkaConfig(
            bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
            topic=os.getenv("KAFKA_TOPIC", "wind-tunnel-data"),
        )
    
    return Config(
        db=db_config,
        kafka=kafka_config,
        api_host=os.getenv("API_HOST", "0.0.0.0"),
        api_port=int(os.getenv("API_PORT", "8000")),
    )


# Singleton config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the application configuration (singleton)."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


if __name__ == "__main__":
    # Test configuration loading
    config = get_config()
    print("Configuration loaded successfully!")
    print(f"  Database: {config.db.host}:{config.db.port}/{config.db.database}")
    print(f"  Kafka: {config.kafka.bootstrap_servers}")
    print(f"  API: {config.api_host}:{config.api_port}")
