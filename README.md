# AeroStream

**Wind Tunnel Data Processing Platform for Motorsport Aerodynamics**

A production-ready web application for streaming, storing, and analyzing wind tunnel sensor data with real-time quality control and comparison tools.

## Features

- 📊 **72-Channel Sensor Simulation** – Realistic motorsport wind tunnel data with variable sample rates
- ⚡ **High-Performance Ingestion** – 50,000+ samples/second via Kafka streaming
- 🔍 **Quality Control** – Automated checks for missing data, spikes, and sensor failures
- 📈 **Interactive Visualization** – Time-series plots with multi-channel comparison
- 🔄 **Run Comparison** – Baseline vs variant delta analysis
- 📤 **Export** – Download processed data as CSV or Parquet

## Tech Stack

| Component | Technology |
|-----------|------------|
| Database | SQL Server 2022 (Linux) |
| Streaming | Redpanda (Kafka-compatible) |
| Backend | Python 3.11+, FastAPI |
| Processing | NumPy, SciPy, Pandas |
| Frontend | Angular 19 + Angular Material + D3.js |
| Infrastructure | Docker Compose |

---

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- Node.js 18+ & npm
- ODBC Driver 18 for SQL Server

### 1. Start Infrastructure

```bash
git clone <repo-url>
cd aero

# Start SQL Server and Redpanda
docker-compose up -d

# Wait for SQL Server to be ready (~30 seconds)
docker-compose logs -f sqlserver
```

### 2. Initialize Database

```bash
docker exec -it aerostream-sqlserver /opt/mssql-tools18/bin/sqlcmd \
  -S localhost -U sa -P 'AeroStream_Secure_123!' -C \
  -i /scripts/init.sql
```

### 3. Setup Python Environment

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

### 4. Run the Application

```bash
# Terminal A: Start the API
uvicorn src.api.main:app --reload --port 8000

# Terminal B: Start the Angular UI
cd ui
npm install
npm run start -- --port 4200
```

Open:
- **Dashboard**: http://localhost:4200
- **API docs**: http://localhost:8000/docs

---

## Kafka Demo Flow (Recommended)

After DB is initialized, ingest data via Kafka streaming:

```bash
# Terminal A: start consumer (Kafka → SQL Server)
python scripts/streaming_consumer.py --max-seconds 600

# Terminal B: create a run + stream simulator samples
python scripts/streaming_produce_run.py --duration 5

# Then process the run for QC + metrics (replace <RUN_ID>)
python scripts/process_run.py --run-id <RUN_ID>
```

Or use the **one-shot demo script**:

```bash
./scripts/kafka_demo.sh
```

To reset test data (keeps config tables):

```bash
docker exec aerostream-sqlserver /opt/mssql-tools18/bin/sqlcmd \
  -S localhost -U sa -P 'AeroStream_Secure_123!' -C \
  -i /scripts/reset_demo.sql
```

---

## Public Demo Mode (No Login)

AeroStream supports a **request/approve** workflow for public demos:

- **Public users** submit demo run requests and check status
- **Admin** approves requests and attaches resulting `run_id`

### Admin Token

```bash
export ADMIN_TOKEN='your-secret-token'
```

### Public Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/demo/requests` | Submit request |
| GET | `/demo/requests/{id}` | Check status |

### Admin Endpoints (requires `X-Admin-Token` header)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/demo/requests` | List all requests |
| POST | `/demo/requests/{id}/admin` | Approve/reject/fulfill |

### One-Command Fulfill

```bash
python scripts/admin_fulfill_demo_request.py <REQUEST_ID> --start-consumer
```

---

## Project Structure

```
aero/
├── docker-compose.yml      # Infrastructure (SQL Server, Redpanda)
├── requirements.txt        # Python dependencies
├── scripts/
│   ├── init.sql            # Database schema + seed data
│   ├── reset_demo.sql      # Truncate test data
│   ├── kafka_demo.sh       # One-shot demo script
│   └── process_run.py      # QC + metrics processing
├── src/
│   ├── config.py           # Settings & secrets
│   ├── db/                 # Database layer
│   ├── simulator/          # Sensor data generator
│   ├── streaming/          # Kafka producer/consumer
│   ├── processing/         # Resample, despike, QC
│   └── api/                # FastAPI endpoints
├── ui/                     # Angular dashboard
│   ├── src/app/pages/      # Run Explorer, Detail, QC, Compare
│   └── src/app/core/       # API client, types
└── docs/
    ├── STEP_BY_STEP_RUNBOOK.md
    └── MOCK_INTERVIEW_PACK.md
```

---

## Sensor Channels

72 channels organized in 9 categories:

| Category | Channels | Rate |
|----------|----------|------|
| Force Balance | 6 | 1000 Hz |
| Component Loads | 8 | 500 Hz |
| Pressure Taps | 44 | 500 Hz |
| Velocity/Flow | 6 | 1000 Hz |
| Environment | 4 | 100 Hz |
| Position | 4 | 100 Hz |

**Total throughput: ~38,800 samples/second**

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/runs` | List runs (paginated) |
| GET | `/runs/{id}` | Run details |
| GET | `/runs/{id}/data` | Time-series data |
| GET | `/runs/{id}/statistics` | Aero metrics |
| GET | `/runs/{id}/qc` | QC report |
| POST | `/runs/compare` | Compare two runs |
| GET | `/sessions` | List sessions |
| GET | `/channels` | List 72 channels |

---

## Documentation

- **Step-by-step runbook**: `docs/STEP_BY_STEP_RUNBOOK.md`
- **Mock interview pack**: `docs/MOCK_INTERVIEW_PACK.md`
- **Architecture overview**: `architecture.md`

---

## License

MIT
