# AeroStream Architecture

## High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              AEROSTREAM                                      │
│                    Wind Tunnel Data Processing Platform                      │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  SIMULATOR   │───▶│   KAFKA      │───▶│  CONSUMER    │───▶│  SQL SERVER  │
│  (Producer)  │    │  (Redpanda)  │    │  (Streaming) │    │  (Database)  │
│              │    │              │    │              │    │              │
└──────────────┘    └──────────────┘    └──────────────┘    └──────┬───────┘
                                                                   │
                                                                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Angular    │◀───│   FastAPI    │◀───│  PROCESSING  │◀───│  TIMESERIES  │
│    (UI)      │    │   (REST)     │    │   ENGINE     │    │  (Queries)   │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
```

---

## Data Flow

```
1. DATA ACQUISITION
   Wind Tunnel Sensors → Simulator → Kafka Producer → Kafka Topic

2. INGESTION
   Kafka Consumer → Bulk Insert → SQL Server (samples table)

3. PROCESSING
   Raw Samples → Resample → Despike → Aero Metrics → QC Checks → Statistics

4. STORAGE
   Processed Data → samples_processed, run_statistics, qc_results tables

5. SERVING
   SQL Server → Time-Series Queries → FastAPI → JSON → Angular UI
```

---

## Module Structure

```
src/
├── config.py              # Environment config (OpenBao vault support)
│
├── simulator/             # Wind tunnel data simulator
│   └── sensor_simulator.py # Generates realistic wind tunnel signals
│
├── streaming/             # Real-time data pipeline
│   ├── producer.py        # Publishes sensor data to Kafka
│   └── consumer.py        # Consumes from Kafka, writes to DB
│
├── db/                    # Database layer
│   ├── connection.py      # SQL Server connection pool
│   ├── operations.py      # CRUD for runs, sessions, samples
│   ├── bulk_insert.py     # High-speed batch inserts
│   └── timeseries.py      # Aggregation & downsampling queries
│
├── processing/            # Data processing engine
│   ├── resampler.py       # Align channels to 100Hz
│   ├── despiker.py        # MAD spike detection
│   ├── aero_metrics.py    # Cl, Cd, L/D calculations
│   ├── qc_engine.py       # 8 quality checks
│   └── processor.py       # Pipeline orchestrator
│
└── api/                   # REST API
    ├── main.py            # FastAPI app + CORS
    ├── schemas.py         # Pydantic models
    └── routes/
        ├── runs.py        # /runs endpoints
        ├── sessions.py    # /sessions endpoints
        ├── channels.py    # /channels endpoints
        └── demo.py        # /demo (public run requests)

ui/                        # Angular dashboard (canonical)
├── src/
│   ├── app/
│   │   ├── core/          # API client, types
│   │   ├── pages/         # Run Explorer, Run Detail, QC, Compare, Request Run
│   │   └── components/    # Time-series chart (D3.js)
│   └── styles.scss        # Custom dark theme
└── angular.json
```

---

## Database Schema (21 Tables)

```
REFERENCE DATA          RUN MANAGEMENT         TIME-SERIES           RESULTS
├── channels (72)       ├── test_sessions      ├── samples           ├── run_statistics
├── run_types           ├── runs               ├── samples_processed ├── qc_results
├── run_states          │                      └── samples_1sec      ├── qc_summaries
├── models              │                                            └── run_deltas
├── teams               │
├── users               │
├── test_cells          │
├── qc_rules            │
└── calibrations        └── audit_log

PUBLIC DEMO
└── demo_run_requests   # Public request queue for demo runs
```

---

## Key Technologies

| Layer | Technology | Purpose |
|-------|------------|---------|
| Database | SQL Server 2022 | Time-series storage, columnstore index |
| Streaming | Redpanda (Kafka-compatible) | 50K msg/sec real-time pipeline |
| Backend | Python 3.11+ / FastAPI | REST API, processing engine |
| Frontend | Angular 19 + Angular Material | Interactive dark-themed dashboard |
| Charts | D3.js (via Angular component) | Time-series visualization |
| Infrastructure | Docker Compose | Local development |
| Secrets | OpenBao (HashiCorp Vault fork) | Secure credential storage |

---

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | /health | Health check |
| GET | /runs | List runs with pagination |
| GET | /runs/{id} | Run details |
| GET | /runs/{id}/data | Time-series samples |
| GET | /runs/{id}/qc | QC report |
| GET | /runs/{id}/statistics | Aero metrics |
| POST | /runs/compare | Compare two runs |
| GET | /sessions | List sessions |
| GET | /channels | List 72 sensor channels |
| POST | /demo/requests | Submit public demo run request |
| GET | /demo/requests/{id} | Check demo request status |

---

## Processing Pipeline

```
┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│  RESAMPLE   │──▶│   DESPIKE   │──▶│ AERO METRICS│──▶│  QC ENGINE  │
│             │   │             │   │             │   │             │
│ Multi-rate  │   │ MAD algo    │   │ Cl, Cd, L/D │   │ 8 checks    │
│ → 100Hz     │   │ spike fix   │   │ efficiency  │   │ PASS/WARN/  │
└─────────────┘   └─────────────┘   └─────────────┘   │ FAIL        │
                                                      └─────────────┘
```

---

## Performance Specs

| Metric | Target |
|--------|--------|
| Ingestion rate | 50,000 samples/sec |
| Processing time | ~3ms per run (300 samples) |
| API response | <200ms for downsampled data |
| Channels | 72 sensors across 9 categories |
| Sample rates | 1Hz to 1000Hz |
| Kafka batch size | 20,000 (tuned for SQL Server throughput) |

---

## UI Pages

| Page | Features |
|------|----------|
| Run Explorer | Paginated run list, search, QC status badges, stats cards |
| Run Detail | Channel selector, time-series chart (D3), setpoints, metrics |
| QC Reports | Per-run QC checks with PASS/WARN/FAIL breakdown |
| Compare | Baseline vs variant overlay, delta metrics table |
| Request Run | Public demo request form (no login required) |
