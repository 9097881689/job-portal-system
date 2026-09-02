#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/Users/aksingh/CodexJobPortal/job-portal-system"
LOCK_DIR="$PROJECT_DIR/data/autopost.lock"
cd "$PROJECT_DIR"

if mkdir "$LOCK_DIR" 2>/dev/null; then
  trap 'rmdir "$LOCK_DIR"' EXIT
else
  if [ -d "$LOCK_DIR" ] && [ -n "$(find "$LOCK_DIR" -maxdepth 0 -mmin +30 -print -quit 2>/dev/null)" ]; then
    rmdir "$LOCK_DIR" 2>/dev/null || true
    mkdir "$LOCK_DIR"
    trap 'rmdir "$LOCK_DIR"' EXIT
  else
    echo "$(date '+%Y-%m-%d %H:%M:%S') | INFO | autopost | Previous run still active; skipping this cycle." >> "$PROJECT_DIR/logs/autopost.log"
    exit 0
  fi
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') | INFO | autopost | Starting run." >> "$PROJECT_DIR/logs/autopost.log"
set +e
PYTHONDONTWRITEBYTECODE=1 perl -e 'alarm shift; exec @ARGV' 1200 "$PROJECT_DIR/.venv/bin/python" -m app.main --limit 10 >> "$PROJECT_DIR/logs/autopost.log" 2>&1
STATUS=$?
set -e
if [ "$STATUS" -ne 0 ]; then
  echo "$(date '+%Y-%m-%d %H:%M:%S') | ERROR | autopost | Run exited with status $STATUS." >> "$PROJECT_DIR/logs/autopost.log"
fi
exit "$STATUS"
