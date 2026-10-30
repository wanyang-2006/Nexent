#!/usr/bin/env bash
# Run as the project owner, not with sudo: bash mcp_server/install_systemd.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE="fundtrace-mcp.service"
PYTHON="$ROOT/.venv/bin/python"
RUN_USER="$(id -un)"
RUN_GROUP="$(id -gn)"
MODE="${MCP_MODE:-hybrid}"

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
[[ "$MODE" == fixture || "$MODE" == hybrid || "$MODE" == real ]] || fail "MCP_MODE must be fixture, hybrid, or real."

[[ "$(uname -s)" == Linux ]] || fail "This installer requires Linux."
[[ "$EUID" -ne 0 ]] || fail "Run without sudo as the project owner. The script requests sudo only for systemd installation."
[[ -d /run/systemd/system ]] || fail "systemd is not running on this host."
command -v ss >/dev/null || fail "Missing ss (iproute2)."
command -v sudo >/dev/null || fail "Missing sudo; ask the server administrator to install the service."
[[ -x "$PYTHON" ]] || fail "Missing $PYTHON; create the virtual environment and install requirements first."
[[ -f "$ROOT/mcp_server/server.py" ]] || fail "Missing server.py."
# Reject characters requiring systemd directive escaping instead of writing an invalid unit.
[[ "$ROOT" =~ ^/[a-zA-Z0-9_./-]+$ ]] || fail "Project path must contain only ASCII letters, digits, underscores, dots, slashes and hyphens."
[[ "$RUN_USER" =~ ^[a-zA-Z_][a-zA-Z0-9_-]*$ ]] || fail "Unsupported service user name."
[[ "$RUN_GROUP" =~ ^[a-zA-Z_][a-zA-Z0-9_-]*$ ]] || fail "Unsupported service group name."

sudo -v
if ss -H -ltn 'sport = :8900' | grep -q .; then
    if ! sudo systemctl is-active --quiet "$SERVICE"; then
        printf '\nPort 8900 is occupied, probably by the existing nohup process.\n'
        sudo ss -lntp 'sport = :8900'
        fail "Identify the old fundtrace Python PID above, confirm it with ps -fp PID, then run kill PID and retry this installer. Other processes are not stopped automatically."
    fi
fi

PYTHONDONTWRITEBYTECODE=1 "$PYTHON" -c 'import fastmcp; print("FastMCP:", fastmcp.__version__)'
MCP_MODE="$MODE" PYTHONDONTWRITEBYTECODE=1 "$PYTHON" "$ROOT/mcp_server/selftest.py" --in-process

UNIT="$(mktemp --suffix=.service)"
trap 'rm -f -- "$UNIT"' EXIT
cat > "$UNIT" <<UNITFILE
[Unit]
Description=Fundtrace MCP server for Nexent
Wants=network-online.target
After=network-online.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=$RUN_USER
Group=$RUN_GROUP
WorkingDirectory=$ROOT
Environment=MCP_MODE=$MODE
Environment=MCP_HOST=0.0.0.0
Environment=MCP_PORT=8900
Environment=MCP_TRANSPORT=sse
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=$PYTHON $ROOT/mcp_server/server.py
Restart=always
RestartSec=5
TimeoutStopSec=20
KillSignal=SIGTERM
NoNewPrivileges=true
PrivateTmp=true
UMask=0027
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
UNITFILE

sudo systemd-analyze verify "$UNIT"
sudo install -m 0644 "$UNIT" "/etc/systemd/system/$SERVICE"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE"
sudo systemctl restart "$SERVICE"

SUCCEEDED=0
for attempt in {1..15}; do
    if MCP_MODE="$MODE" "$PYTHON" "$ROOT/mcp_server/selftest.py" http://127.0.0.1:8900/sse; then
        SUCCEEDED=1
        break
    fi
    sleep 1
done
if [[ "$SUCCEEDED" -ne 1 ]]; then
    sudo journalctl -u "$SERVICE" -n 50 --no-pager
    fail "Service installed but protocol test failed. Inspect the logs; do not start a second nohup process."
fi
sudo systemctl is-enabled "$SERVICE"
sudo systemctl is-active "$SERVICE"
printf '\nInstalled: boot startup and restart after process exit are enabled.\n'
printf 'Status: sudo systemctl status %s --no-pager\n' "$SERVICE"
printf 'Logs:   sudo journalctl -u %s -n 50 --no-pager\n' "$SERVICE"
printf 'Nexent URL is unchanged. Refresh the fundtrace connection if necessary.\n'
