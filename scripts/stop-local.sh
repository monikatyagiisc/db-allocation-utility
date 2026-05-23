#!/usr/bin/env bash
# Stop processes started by start-local.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$ROOT_DIR/.local/pids"

if [[ ! -f "$PID_FILE" ]]; then
  echo "No running local stack found (.local/pids missing)."
  exit 0
fi

while read -r pid name; do
  if kill -0 "$pid" 2>/dev/null; then
    echo "Stopping $name (pid $pid)"
    kill "$pid" 2>/dev/null || true
  fi
done <"$PID_FILE"

rm -f "$PID_FILE"
echo "Stopped."
