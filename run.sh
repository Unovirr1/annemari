#!/usr/bin/env bash
# Start the Счастливая Долина server in the background and print its URL.
#   ./run.sh          normal
#   ./run.sh --e2e    also exposes the /__e2e__ test harness route
#   ./run.sh --stop   stop it
set -euo pipefail

cd "$(dirname "$0")"
PIDFILE=".run/server.pid"
LOG=".run/server.log"

case "${1:-}" in
  --stop)
    if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
      kill "$(cat "$PIDFILE")" && echo "stopped $(cat "$PIDFILE")"
      rm -f "$PIDFILE"
    else
      echo "not running (no live pidfile)"
    fi
    exit 0
    ;;
  --e2e)
    export E2E=1
    ;;
  "")
    ;;
  *)
    echo "usage: $0 [--e2e|--stop]" >&2
    exit 2
    ;;
esac

# Reuse an instance we already started, rather than fighting over the port.
if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "already running (pid $(cat "$PIDFILE"))"
  grep -oE "http://127\.0\.0\.1:[0-9]+" "$LOG" | head -1
  exit 0
fi

mkdir -p .run
# setsid so the server survives the shell that launched it.
setsid nohup ./.venv/bin/python app.py > "$LOG" 2>&1 < /dev/null &
echo $! > "$PIDFILE"

# Wait for the port banner instead of guessing with a fixed sleep.
for _ in $(seq 1 60); do
  if grep -q "Running on" "$LOG" 2>/dev/null; then
    grep -oE "http://127\.0\.0\.1:[0-9]+" "$LOG" | head -1
    exit 0
  fi
  if ! kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    echo "server died on startup:" >&2
    cat "$LOG" >&2
    exit 1
  fi
  sleep 0.5
done

echo "server did not report a port in time:" >&2
cat "$LOG" >&2
exit 1
