#!/usr/bin/env bash
# Aarthik Gyan V4 - single-terminal launcher.
#
# Starts the V3 MCP server, the V4 FastAPI adapter, and the Vite dev server,
# prefixes their logs, waits for readiness, and stops everything on Ctrl+C.
#
# Usage:
#   ./start.sh                 start everything
#   ./start.sh --install       install frontend dependencies if missing
#   ./start.sh --force         stop existing listeners on ports 8000/8001/5173
#   ./start.sh --no-open       do not open the browser
#   PYTHON=/path/to/python ./start.sh
#
# Logs are written to .run/logs/.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

RUN_DIR="$ROOT_DIR/.run"
LOG_DIR="$RUN_DIR/logs"
MCP_PORT=8000
API_PORT=8001
WEB_PORT=5173
MCP_URL="http://127.0.0.1:$MCP_PORT/mcp"
API_URL="http://127.0.0.1:$API_PORT"
WEB_URL="http://127.0.0.1:$WEB_PORT"

OPEN_BROWSER=1
FORCE=0
INSTALL=0

MCP_PID=""
API_PID=""
VITE_PID=""
LAST_PID=""
MCP_REUSED=0
CLEANED=0

if [ -t 1 ]; then
  C_RESET=$'\033[0m'
  C_RED=$'\033[31m'
  C_GREEN=$'\033[32m'
  C_YELLOW=$'\033[33m'
  C_BLUE=$'\033[34m'
  C_MAGENTA=$'\033[35m'
  C_CYAN=$'\033[36m'
else
  C_RESET=""
  C_RED=""
  C_GREEN=""
  C_YELLOW=""
  C_BLUE=""
  C_MAGENTA=""
  C_CYAN=""
fi

usage() {
  cat <<'EOF'
Aarthik Gyan V4 - single-terminal launcher

Usage:
  ./start.sh                 start MCP, API, and frontend
  ./start.sh --install       install frontend dependencies if missing
  ./start.sh --force         stop existing listeners on ports 8000/8001/5173
  ./start.sh --no-open       do not open the browser
  ./start.sh --help          show this help

Environment:
  PYTHON=/path/to/python     use a specific interpreter
  API_CORS_ORIGINS=...       override API CORS origins

Press Ctrl+C to stop all three services.
EOF
}

for arg in "$@"; do
  case "$arg" in
    --install) INSTALL=1 ;;
    --force) FORCE=1 ;;
    --no-open) OPEN_BROWSER=0 ;;
    -h|--help) usage; exit 0 ;;
    *)
      printf 'Unknown option: %s\n\n' "$arg" >&2
      usage >&2
      exit 2
      ;;
  esac
done

info() { printf '%s[start]%s %s\n' "$C_BLUE" "$C_RESET" "$*"; }
ok() { printf '%s[ ok ]%s %s\n' "$C_GREEN" "$C_RESET" "$*"; }
warn() { printf '%s[warn]%s %s\n' "$C_YELLOW" "$C_RESET" "$*"; }
err() { printf '%s[error]%s %s\n' "$C_RED" "$C_RESET" "$*" >&2; }
die() { err "$*"; exit 1; }

port_pids() {
  lsof -nP -iTCP:"$1" -sTCP:LISTEN -t 2>/dev/null || true
}

pids_desc() {
  local pid
  for pid in $1; do
    printf '  PID %s: %s\n' "$pid" "$(ps -p "$pid" -o command= 2>/dev/null | sed 's/^ *//')"
  done
}

stop_pids() {
  local pids="$1"
  local port="$2"
  local pid i alive
  [ -n "$pids" ] || return 0

  warn "Stopping existing listener(s) on port $port..."
  for pid in $pids; do
    kill -TERM "$pid" 2>/dev/null || true
  done

  i=0
  while [ "$i" -lt 20 ]; do
    alive=0
    for pid in $pids; do
      if kill -0 "$pid" 2>/dev/null; then
        alive=1
      fi
    done
    if [ "$alive" -eq 0 ]; then
      return 0
    fi
    sleep 0.25
    i=$((i + 1))
  done

  for pid in $pids; do
    kill -KILL "$pid" 2>/dev/null || true
  done
}

require_free_port() {
  local port="$1"
  local name="$2"
  local pids
  pids="$(port_pids "$port")"
  [ -n "$pids" ] || return 0

  if [ "$FORCE" -eq 1 ]; then
    stop_pids "$pids" "$port"
    return 0
  fi

  err "$name port $port is already in use:"
  pids_desc "$pids" >&2
  die "Stop the process above, or rerun with: ./start.sh --force"
}

wait_for_http() {
  local url="$1"
  local timeout="$2"
  local code i
  i=0
  while [ "$i" -lt $((timeout * 2)) ]; do
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 2 "$url" 2>/dev/null || true)"
    if [ "$code" = "200" ]; then
      return 0
    fi
    sleep 0.5
    i=$((i + 1))
  done
  return 1
}

wait_for_any_http() {
  local url="$1"
  local timeout="$2"
  local i
  i=0
  while [ "$i" -lt $((timeout * 2)) ]; do
    if curl -s -o /dev/null --max-time 2 "$url" 2>/dev/null; then
      return 0
    fi
    sleep 0.5
    i=$((i + 1))
  done
  return 1
}

prefix() {
  local label="$1"
  local color="$2"
  local line
  while IFS= read -r line; do
    printf '%s[%s]%s %s\n' "$color" "$label" "$C_RESET" "$line"
  done
}

start_service() {
  local name="$1"
  local logfile="$2"
  local color="$3"
  local workdir="$4"
  shift 4

  : > "$logfile"
  ( cd "$workdir" && exec "$@" ) > >(tee -a "$logfile" | prefix "$name" "$color") 2>&1 &
  LAST_PID=$!
  # Keep bash from printing "Terminated" notices for the log-pipe jobs during
  # shutdown. PIDs are tracked explicitly, so job-table entries are not needed.
  disown -a 2>/dev/null || true
}

terminate_tree() {
  local pid="$1"
  local child
  local cmd
  [ -n "$pid" ] || return 0
  kill -0 "$pid" 2>/dev/null || return 0
  for child in $(pgrep -P "$pid" 2>/dev/null || true); do
    cmd="$(ps -p "$child" -o command= 2>/dev/null || true)"
    case "$cmd" in
      # Log pipes exit on their own when the service closes stdout. Killing
      # them produces noisy bash "Terminated" job notices.
      *"tee -a"*) continue ;;
    esac
    terminate_tree "$child"
  done
  kill -TERM "$pid" 2>/dev/null || true
}

cleanup() {
  [ "$CLEANED" -eq 1 ] && return 0
  CLEANED=1
  trap - EXIT INT TERM

  if [ -n "$MCP_PID$API_PID$VITE_PID" ]; then
    printf '\n'
    info "Shutting down MCP, API, and frontend..."

    # Bash prints job-control notices such as "Terminated: 15 tee ..." when
    # the log pipes close. Keep stderr silenced through process exit.
    exec 2>/dev/null

    terminate_tree "$VITE_PID"
    terminate_tree "$API_PID"
    terminate_tree "$MCP_PID"

    local i=0
    local alive
    local p
    while [ "$i" -lt 20 ]; do
      alive=0
      for p in "$MCP_PID" "$API_PID" "$VITE_PID"; do
        if [ -n "$p" ] && kill -0 "$p" 2>/dev/null; then
          alive=1
        fi
      done
      if [ "$alive" -eq 0 ]; then
        break
      fi
      sleep 0.25
      i=$((i + 1))
    done

    for p in "$MCP_PID" "$API_PID" "$VITE_PID"; do
      if [ -n "$p" ]; then
        kill -KILL "$p" 2>/dev/null || true
      fi
    done

    wait 2>/dev/null || true

    # Keep stderr silenced through process exit so bash does not print job
    # notices for the log pipes while the shell shuts down.
    ok "All services stopped. Logs are in .run/logs/."
  fi
}

trap cleanup EXIT
trap 'cleanup; exit 130' INT TERM

# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------

if [ ! -f "$ROOT_DIR/.env" ]; then
  err "No .env file found in $ROOT_DIR"
  die "Create one first: cp .env.example .env  (then fill in Neo4j, Qdrant, and LLM credentials)"
fi

if grep -Eq 'x{6,}' "$ROOT_DIR/.env"; then
  warn ".env still contains placeholder-looking values (xxxxxx). Ingestion and analysis will fail until they are replaced."
fi

for key in NEO4J_URI NEO4J_USERNAME NEO4J_PASSWORD GROQ_API_KEY GOOGLE_API_KEY QDRANT_URL QDRANT_API_KEY; do
  if ! grep -Eq "^[[:space:]]*$key[[:space:]]*=" "$ROOT_DIR/.env"; then
    warn ".env does not define $key"
  fi
done

if ! command -v curl >/dev/null 2>&1; then
  die "curl is required but was not found on PATH."
fi

if ! command -v npm >/dev/null 2>&1; then
  die "npm is required but was not found on PATH. Install Node.js 20+ first."
fi

if command -v node >/dev/null 2>&1; then
  NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)"
  if [ "$NODE_MAJOR" -lt 20 ]; then
    warn "Node.js $NODE_MAJOR detected; Vite expects Node.js 20 or newer."
  fi
fi

if [ ! -x "$ROOT_DIR/frontend/node_modules/.bin/vite" ]; then
  if [ "$INSTALL" -eq 1 ]; then
    info "Installing frontend dependencies..."
    npm --prefix "$ROOT_DIR/frontend" install
  else
    die "Frontend dependencies are missing. Run: npm --prefix frontend install  (or ./start.sh --install)"
  fi
fi

# ---------------------------------------------------------------------------
# Interpreter selection
# ---------------------------------------------------------------------------

REQUIRED_MODULES="fastapi uvicorn multipart neo4j qdrant_client langgraph fastmcp pypdf sentence_transformers langchain_google_genai langchain_groq langchain_mcp_adapters reportlab"

missing_modules() {
  local py="$1"
  "$py" - "$REQUIRED_MODULES" <<'PY' 2>/dev/null
import importlib.util
import sys

missing = []
for name in sys.argv[1].split():
    try:
        found = importlib.util.find_spec(name) is not None
    except Exception:
        found = False
    if not found:
        missing.append(name)
print(" ".join(missing))
PY
}

interpreter_report() {
  local candidate="$1"
  local missing="$2"
  printf '  %s\n    missing: %s\n' "$candidate" "$missing"
}

PY=""
PY_REPORT=""

if [ -n "${PYTHON:-}" ]; then
  if ! command -v "$PYTHON" >/dev/null 2>&1; then
    die "PYTHON=$PYTHON is not executable or not on PATH."
  fi
  PY="$(command -v "$PYTHON")"
  PY_MISSING="$(missing_modules "$PY" || true)"
  if [ -n "$PY_MISSING" ]; then
    err "PYTHON=$PY is missing required packages:"
    printf '  %s\n' "$PY_MISSING" >&2
    die "Install them with: $PY -m pip install -r requirements-api.txt"
  fi
else
  CANDIDATES="$ROOT_DIR/.venv/bin/python /opt/anaconda3/envs/ai/bin/python python3 python"
  TRIED=""
  for candidate in $CANDIDATES; do
    case " $TRIED " in
      *" $candidate "*) continue ;;
    esac
    TRIED="$TRIED $candidate"

    resolved="$(command -v "$candidate" 2>/dev/null || true)"
    [ -n "$resolved" ] || continue

    missing="$(missing_modules "$resolved" || true)"
    if [ -z "$missing" ]; then
      PY="$resolved"
      break
    fi
    PY_REPORT="${PY_REPORT}$(interpreter_report "$resolved" "$missing")"$'\n'
  done

  if [ -z "$PY" ]; then
    err "No Python interpreter has the full V3 + V4 dependency set."
    printf '%s' "$PY_REPORT" >&2
    cat >&2 <<'EOF'

Fix one of these, then rerun:

  1. Use the conda environment that already has the stack:
       PYTHON=/opt/anaconda3/envs/ai/bin/python ./start.sh

  2. Install the missing packages into this project's venv:
       .venv/bin/python -m pip install -r requirements-api.txt

  3. Recreate the venv with access to an existing V3 environment:
       python3 -m venv --system-site-packages .venv
       .venv/bin/python -m pip install -r requirements-api.txt
EOF
    exit 1
  fi
fi

info "Using Python: $PY"

# ---------------------------------------------------------------------------
# Ports
# ---------------------------------------------------------------------------

MCP_PIDS="$(port_pids "$MCP_PORT")"
if [ -n "$MCP_PIDS" ]; then
  if [ "$FORCE" -eq 1 ]; then
    stop_pids "$MCP_PIDS" "$MCP_PORT"
  elif wait_for_any_http "$MCP_URL" 3; then
    warn "Port $MCP_PORT already has a running service; reusing it as the MCP server:"
    pids_desc "$MCP_PIDS"
    MCP_REUSED=1
  else
    err "Port $MCP_PORT is in use by a process that does not answer HTTP:"
    pids_desc "$MCP_PIDS" >&2
    die "Stop that process, or rerun with: ./start.sh --force"
  fi
fi

require_free_port "$API_PORT" "API"
require_free_port "$WEB_PORT" "Frontend"

mkdir -p "$LOG_DIR"

# ---------------------------------------------------------------------------
# Start services
# ---------------------------------------------------------------------------

export PYTHONUNBUFFERED=1

if [ "$MCP_REUSED" -eq 0 ]; then
  start_service "MCP" "$LOG_DIR/mcp.log" "$C_MAGENTA" "$ROOT_DIR" \
    "$PY" -m mcp_server.server
  MCP_PID="$LAST_PID"
  info "Starting MCP server (PID $MCP_PID)..."

  if ! wait_for_any_http "$MCP_URL" 45; then
    err "MCP server did not become reachable. Last log lines:"
    tail -n 40 "$LOG_DIR/mcp.log" >&2 || true
    die "Startup failed."
  fi
  ok "MCP server is listening on 127.0.0.1:$MCP_PORT"
else
  ok "Reusing the existing MCP server on 127.0.0.1:$MCP_PORT"
fi

start_service "API" "$LOG_DIR/api.log" "$C_CYAN" "$ROOT_DIR" \
  "$PY" -m uvicorn api.main:app --host 127.0.0.1 --port "$API_PORT"
API_PID="$LAST_PID"
info "Starting API (PID $API_PID)..."

if ! wait_for_http "$API_URL/api/health/live" 60; then
  err "API did not become ready. Last log lines:"
  tail -n 40 "$LOG_DIR/api.log" >&2 || true
  die "Startup failed."
fi
ok "API is listening on $API_URL"

start_service "Frontend" "$LOG_DIR/frontend.log" "$C_GREEN" "$ROOT_DIR/frontend" \
  "$ROOT_DIR/frontend/node_modules/.bin/vite" --host 127.0.0.1 --port "$WEB_PORT" --strictPort
VITE_PID="$LAST_PID"
info "Starting frontend (PID $VITE_PID)..."

if ! wait_for_http "$WEB_URL/" 60; then
  err "Frontend did not become ready. Last log lines:"
  tail -n 40 "$LOG_DIR/frontend.log" >&2 || true
  die "Startup failed."
fi
ok "Frontend is listening on $WEB_URL"

READY_CODE="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$API_URL/api/health/ready" 2>/dev/null || true)"
if [ "$READY_CODE" = "200" ]; then
  ok "Neo4j and Qdrant are reachable."
else
  warn "API is up but /api/health/ready returned $READY_CODE. Neo4j or Qdrant may be down; the UI will show degraded status."
fi

printf '\n'
info "${C_GREEN}Aarthik Gyan V4 is running${C_RESET}"
printf '  UI:        %s\n' "$WEB_URL"
printf '  API docs:  %s/api/docs\n' "$API_URL"
printf '  MCP:       %s\n' "$MCP_URL"
printf '  Logs:      %s\n' "$LOG_DIR"
printf '  Stop:      Ctrl+C\n'
printf '\n'
info "Fresh start? Open the Upload page and add a PDF. The graph stays empty until ingestion completes."

if [ "$OPEN_BROWSER" -eq 1 ]; then
  if command -v open >/dev/null 2>&1; then
    open "$WEB_URL" >/dev/null 2>&1 || true
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$WEB_URL" >/dev/null 2>&1 || true
  fi
fi

# ---------------------------------------------------------------------------
# Supervise
# ---------------------------------------------------------------------------

while :; do
  for pair in "MCP:$MCP_PID" "API:$API_PID" "Frontend:$VITE_PID"; do
    name="${pair%%:*}"
    pid="${pair#*:}"
    [ -n "$pid" ] || continue
    if ! kill -0 "$pid" 2>/dev/null; then
      err "$name exited unexpectedly. See .run/logs/ for details."
      exit 1
    fi
  done
  sleep 1
done
