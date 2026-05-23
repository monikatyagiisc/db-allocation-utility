#!/usr/bin/env bash
# Start the full DB Allocation Utility stack locally (Postgres, API, frontend).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
RUN_DIR="$ROOT_DIR/.local"
LOG_DIR="$RUN_DIR/logs"
PID_FILE="$RUN_DIR/pids"

USE_DOCKER=false
SKIP_DEPS=false

usage() {
  cat <<'EOF'
Usage: ./scripts/start-local.sh [options]

Starts PostgreSQL (optional), runs migrations, then the FastAPI backend and React frontend.

Options:
  --docker       Start Postgres via docker compose before the app
  --skip-deps    Skip uv sync / yarn install (faster restarts)
  -h, --help     Show this help

URLs (default ports from backend/.env):
  App:      http://localhost:3000
  API:      http://localhost:8080
  API docs: http://localhost:8080/docs

Stop with Ctrl+C or: ./scripts/stop-local.sh
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --docker) USE_DOCKER=true; shift ;;
    --skip-deps) SKIP_DEPS=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
done

mkdir -p "$LOG_DIR" "$(dirname "$PID_FILE")"

# Ensure uv is on PATH (common install location)
export PATH="${HOME}/.local/bin:${PATH}"

log() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!>\033[0m %s\n' "$*" >&2; }
die() { printf '\033[1;31mxx>\033[0m %s\n' "$*" >&2; exit 1; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

load_env() {
  if [[ ! -f "$BACKEND_DIR/.env" ]]; then
    if [[ -f "$BACKEND_DIR/.env.example" ]]; then
      log "Creating backend/.env from .env.example"
      cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
    else
      die "backend/.env not found and no .env.example to copy"
    fi
  fi
  set -a
  # shellcheck disable=SC1091
  source "$BACKEND_DIR/.env"
  set +a
  : "${DB_HOST:=localhost}"
  : "${DB_PORT:=5432}"
  : "${DB_USER:=postgres}"
  : "${DB_PASSWORD:=}"
  : "${DB_NAME:=db_allocation}"
  : "${API_PORT:=8080}"
  : "${FRONTEND_PORT:=3000}"
  export API_PORT FRONTEND_PORT
}

wait_for_postgres() {
  log "Waiting for PostgreSQL at ${DB_HOST}:${DB_PORT}..."
  local i
  for i in $(seq 1 45); do
    if PGPASSWORD="$DB_PASSWORD" pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" >/dev/null 2>&1; then
      log "PostgreSQL is ready"
      return 0
    fi
    sleep 1
  done
  die "PostgreSQL not available. Start it manually, use --docker, or check backend/.env"
}

ensure_database() {
  local exists
  exists="$(PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -tAc \
    "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" 2>/dev/null || true)"
  if [[ "$exists" != "1" ]]; then
    log "Creating database '${DB_NAME}'"
    PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c \
      "CREATE DATABASE \"${DB_NAME}\";"
  fi
}

start_docker_postgres() {
  require_cmd docker
  export DB_PORT=5433
  log "Starting PostgreSQL with docker compose (host port ${DB_PORT})..."
  (cd "$ROOT_DIR" && docker compose up -d db)
  wait_for_postgres
}

setup_backend() {
  require_cmd uv
  cd "$BACKEND_DIR"
  if [[ "$SKIP_DEPS" == false ]]; then
    log "Installing backend dependencies (uv sync)..."
    uv sync
  fi
  log "Applying database migrations..."
  uv run alembic upgrade head
}

setup_frontend() {
  require_cmd yarn
  cd "$FRONTEND_DIR"
  if [[ "$SKIP_DEPS" == false ]] || [[ ! -d node_modules ]]; then
    log "Installing frontend dependencies (yarn)..."
    yarn install --frozen-lockfile 2>/dev/null || yarn install
  fi
}

cleanup() {
  echo
  log "Shutting down..."
  if [[ -f "$PID_FILE" ]]; then
    while read -r pid name; do
      if kill -0 "$pid" 2>/dev/null; then
        log "Stopping $name (pid $pid)"
        kill "$pid" 2>/dev/null || true
      fi
    done < "$PID_FILE"
    rm -f "$PID_FILE"
  fi
  exit 0
}

start_process() {
  local name="$1"
  local prefix="$2"
  shift 2
  log "Starting $name..."
  # Tee to log file and stdout so [BE]/[FE] lines are visible in the terminal
  bash -c "$*" 2>&1 | while IFS= read -r line; do
    printf '%s %s\n' "$prefix" "$line"
    printf '%s %s\n' "$prefix" "$line" >>"$LOG_DIR/${name}.log"
  done &
  local pid=$!
  echo "$pid $name" >>"$PID_FILE"
  log "$name started (pid $pid, prefix=${prefix}, log: .local/logs/${name}.log)"
}

# --- main ---

require_cmd pg_isready
require_cmd psql
trap cleanup INT TERM

: >"$PID_FILE"

load_env

if [[ "$USE_DOCKER" == true ]]; then
  start_docker_postgres
else
  if ! PGPASSWORD="$DB_PASSWORD" pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" >/dev/null 2>&1; then
    if command -v docker >/dev/null 2>&1; then
      warn "PostgreSQL not reachable on port ${DB_PORT}; trying docker compose..."
      start_docker_postgres
    else
      wait_for_postgres
    fi
  else
    log "PostgreSQL already running on port ${DB_PORT}"
  fi
fi

ensure_database
setup_backend
setup_frontend

start_process backend "[BE]" "cd '$BACKEND_DIR' && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port ${API_PORT}"
start_process frontend "[FE]" "cd '$FRONTEND_DIR' && yarn dev --host 127.0.0.1 --port ${FRONTEND_PORT}"

sleep 2

echo
log "DB Allocation Utility is running"
echo "  Frontend:  http://localhost:${FRONTEND_PORT}"
echo "  Backend:   http://localhost:${API_PORT}"
echo "  API docs:  http://localhost:${API_PORT}/docs"
echo "  Postgres:  ${DB_HOST}:${DB_PORT}/${DB_NAME}"
echo
log "Press Ctrl+C to stop, or run: ./scripts/stop-local.sh"
log "Logs use prefixes: [BE] backend  [FE] frontend  (also in .local/logs/)"
echo

wait
