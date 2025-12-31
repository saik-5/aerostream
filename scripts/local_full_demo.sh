#!/usr/bin/env bash
set -euo pipefail

# One-shot local demo:
# - restarts docker containers
# - initializes DB if needed (or runs migration)
# - generates one demo run via Kafka (consumer + producer + processing)
# - starts API + dashboard locally
# - prints endpoints

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${ROOT_DIR}/venv/bin/python"

if [[ ! -x "${PY}" ]]; then
  echo "ERROR: Python venv not found at ${PY}"
  echo "Create it and install deps:"
  echo "  python3 -m venv venv && ./venv/bin/pip install -r requirements.txt"
  exit 1
fi

export ADMIN_TOKEN="${ADMIN_TOKEN:-change-me}"

echo "============================================================"
echo "🏎️  AeroStream Full Local Demo"
echo "============================================================"
echo ""

echo "0) Restarting docker containers..."
cd "${ROOT_DIR}"
docker-compose down
docker-compose up -d

echo ""
echo "1) Waiting for SQL Server to become healthy..."
for i in {1..60}; do
  status="$(docker inspect -f '{{.State.Health.Status}}' aerostream-sqlserver 2>/dev/null || true)"
  if [[ "${status}" == "healthy" ]]; then
    echo "   ✅ SQL Server healthy"
    break
  fi
  sleep 1
done

echo ""
echo "2) Ensuring DB schema exists..."
set +e
docker exec aerostream-sqlserver /opt/mssql-tools18/bin/sqlcmd \
  -S localhost -U sa -P 'AeroStream_Secure_123!' -C -d aerostream -Q "SET NOCOUNT ON; SELECT TOP 1 1 FROM runs;" >/dev/null 2>&1
HAS_SCHEMA=$?
set -e

if [[ "${HAS_SCHEMA}" -ne 0 ]]; then
  echo "   Applying full init.sql..."
  docker exec aerostream-sqlserver /opt/mssql-tools18/bin/sqlcmd \
    -S localhost -U sa -P 'AeroStream_Secure_123!' -C \
    -i /scripts/init.sql
else
  echo "   Schema already present. Applying migration (demo_run_requests) if needed..."
  docker exec aerostream-sqlserver /opt/mssql-tools18/bin/sqlcmd \
    -S localhost -U sa -P 'AeroStream_Secure_123!' -C -d aerostream \
    -i /scripts/migrations/20251229_add_demo_run_requests.sql
fi

echo ""
echo "3) Generating demo data via Kafka (one-shot run + QC)..."
"${ROOT_DIR}/scripts/kafka_demo.sh"

echo ""
echo "4) Starting API + Dashboard..."
echo "   API: uvicorn src.api.main:app --reload --port 8000"
echo "   UI:  (cd ui && npm run start -- --port 4200 --host 127.0.0.1)"
echo ""

echo "Starting API in background..."
("${ROOT_DIR}/venv/bin/uvicorn" src.api.main:app --reload --port 8000) >/tmp/aerostream-api.log 2>&1 &
API_PID=$!
echo "  API PID: ${API_PID}  log: /tmp/aerostream-api.log"

echo "Starting UI in background..."
(cd "${ROOT_DIR}/ui" && npm run start -- --port 4200 --host 127.0.0.1) >/tmp/aerostream-ui.log 2>&1 &
UI_PID=$!
echo "  UI PID:  ${UI_PID}   log: /tmp/aerostream-ui.log"

echo ""
echo "✅ READY"
echo "  Dashboard: http://localhost:4200"
echo "  API:       http://localhost:8000"
echo "  API Docs:  http://localhost:8000/docs"
echo ""
echo "To stop:"
echo "  kill ${API_PID} ${UI_PID}"


