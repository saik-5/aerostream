#!/usr/bin/env bash
set -euo pipefail

# Kafka-only one-shot demo:
# - starts consumer in background
# - runs producer to create a run + stream simulator samples to Kafka
# - extracts run_id from producer output
# - runs processing to populate QC + metrics for that run
# - stops consumer

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${ROOT_DIR}/venv/bin/python"

if [[ ! -x "${PY}" ]]; then
  echo "ERROR: Python venv not found at ${PY}"
  echo "Create it and install deps: python3 -m venv venv && ./venv/bin/pip install -r requirements.txt"
  exit 1
fi

MAX_SECONDS="${MAX_SECONDS:-600}"
DURATION="${DURATION:-5}"

echo "🏎️  AeroStream Kafka Demo (one-shot)"
echo "============================================================"
echo "Consumer max seconds: ${MAX_SECONDS}"
echo "Producer duration:    ${DURATION}"
echo ""

CONSUMER_LOG="$(mktemp -t aerostream-consumer.XXXXXX.log)"
PRODUCER_LOG="$(mktemp -t aerostream-producer.XXXXXX.log)"

cleanup() {
  if [[ -n "${CONSUMER_PID:-}" ]] && kill -0 "${CONSUMER_PID}" 2>/dev/null; then
    kill "${CONSUMER_PID}" 2>/dev/null || true
    wait "${CONSUMER_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "1) Starting consumer (background)..."
set +e
("${PY}" "${ROOT_DIR}/scripts/streaming_consumer.py" --max-seconds "${MAX_SECONDS}") >"${CONSUMER_LOG}" 2>&1 &
CONSUMER_PID=$!
set -e
echo "   Consumer PID: ${CONSUMER_PID}"
echo "   Consumer log: ${CONSUMER_LOG}"
echo ""

sleep 2

echo "2) Running producer (streaming simulator -> Kafka)..."
PRODUCER_OUT="$("${PY}" "${ROOT_DIR}/scripts/streaming_produce_run.py" --duration "${DURATION}" | tee "${PRODUCER_LOG}")"

# Extract run_id from producer output.
# Expected lines include either:
#   "DB run_id:  6  session_id: 2"
# or "Run ID: 6"
RUN_ID="$(echo "${PRODUCER_OUT}" | sed -nE 's/.*DB run_id:[[:space:]]*([0-9]+).*/\1/p' | tail -n 1)"
if [[ -z "${RUN_ID}" ]]; then
  RUN_ID="$(echo "${PRODUCER_OUT}" | sed -nE 's/.*Run ID:[[:space:]]*([0-9]+).*/\1/p' | tail -n 1)"
fi

if [[ -z "${RUN_ID}" ]]; then
  echo ""
  echo "ERROR: Could not extract run_id from producer output."
  echo "Producer log saved at: ${PRODUCER_LOG}"
  exit 1
fi

echo ""
echo "3) Processing run_id=${RUN_ID} for QC + metrics..."
("${PY}" "${ROOT_DIR}/scripts/process_run.py" --run-id "${RUN_ID}") || {
  echo "WARNING: Processing failed for run_id=${RUN_ID}. Check logs above."
  exit 1
}

echo ""
echo "✅ Kafka one-shot demo complete"
echo "  Run ID: ${RUN_ID}"
echo "  Next: open dashboard and refresh Explorer"
echo "    UI:  http://localhost:4200"
echo "    API: http://localhost:8000/docs"


