#!/bin/bash
# Install the Fundtrace A2A northbound server on the ECS.
# Run as root on the ECS after uploading a2a_server.py.
set -euo pipefail

DEPLOY_DIR=/home/Liu/fundtrace-mcp
VENV=${DEPLOY_DIR}/.venv
A2A_FILE=${DEPLOY_DIR}/a2a_server/a2a_server.py
SERVICE=/etc/systemd/system/fundtrace-a2a.service

echo "==> Creating a2a_server directory"
mkdir -p ${DEPLOY_DIR}/a2a_server

echo "==> Copying a2a_server.py"
cp /tmp/a2a_server.py ${A2A_FILE}

echo "==> Installing extra pip dependencies (if any)"
${VENV}/bin/pip install --quiet uvicorn 2>&1 | tail -3 || true

echo "==> Writing systemd unit"
cat > ${SERVICE} <<'EOF'
[Unit]
Description=Fundtrace A2A northbound server
Wants=network-online.target fundtrace-mcp.service
After=network-online.target fundtrace-mcp.service
StartLimitIntervalSec=0

[Service]
Type=simple
User=Liu
Group=Liu
WorkingDirectory=/home/Liu/fundtrace-mcp
Environment=MCP_URL=http://127.0.0.1:8900/sse
Environment=A2A_PORT=8901
Environment=A2A_PUBLIC_URL=http://60.205.124.241:8901
Environment=PYTHONUNBUFFERED=1
ExecStart=/home/Liu/fundtrace-mcp/.venv/bin/uvicorn a2a_server.a2a_server:app --host 0.0.0.0 --port 8901
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

echo "==> Enabling and starting fundtrace-a2a"
systemctl daemon-reload
systemctl enable fundtrace-a2a
systemctl restart fundtrace-a2a
sleep 3
systemctl status fundtrace-a2a --no-pager
echo "==> Done"
