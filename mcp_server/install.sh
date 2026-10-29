#!/usr/bin/env bash
# 在 ECS 上安装并启动 fundtrace MCP 服务，然后自检。可重复执行。
# 用法（在仓库根目录或解压后的 fundtrace 目录）：
#   bash mcp_server/install.sh
# 目录下有 wheels_linux/ 时自动离线安装（由本机 mcp_server/pack_for_ecs.ps1 生成）
# 可选环境变量：
#   MCP_TRANSPORT=sse|streamable-http（默认 sse）  MCP_PORT=8900
#   FASTMCP_VERSION=4.1.4   PIP_INDEX_URL=<pip 镜像地址>   WHEEL_DIR=<离线 wheel 目录>
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
TRANSPORT="${MCP_TRANSPORT:-sse}"
PORT="${MCP_PORT:-8900}"
FASTMCP_VERSION="${FASTMCP_VERSION:-4.1.4}"
WHEEL_DIR="${WHEEL_DIR:-$ROOT/wheels_linux}"
if [ "$TRANSPORT" = "sse" ]; then SUFFIX="/sse"; else SUFFIX="/mcp"; fi

say()  { printf '\n== %s\n' "$*"; }
fail() { printf '\n[失败] %s\n' "$*" >&2; exit 1; }

# 1. 选 Python：优先 3.13/3.12/3.11（甲的 pandas 3.x 需要 >= 3.11），最低 3.10（fastmcp 要求）
say "1/5 检查 Python"
PY=""
for c in python3.13 python3.12 python3.11 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)'; then
    PY="$c"; break
  fi
done
[ -n "$PY" ] || fail "没有找到 Python 3.10 及以上版本"
PYVER="$("$PY" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
echo "使用 $PY（$PYVER，$(uname -m)）"
if ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)'; then
  echo "[提醒] Python $PYVER 能跑 MCP，但第 3 天装 requirements.txt 里的 pandas 3.0.0 需要 3.11 及以上"
fi

# 2. 虚拟环境
say "2/5 虚拟环境 .venv"
if [ ! -x .venv/bin/python ]; then
  "$PY" -m venv .venv || fail "创建 venv 失败。Ubuntu 上先执行：sudo apt install -y python${PYVER}-venv"
fi
VPY="$ROOT/.venv/bin/python"
echo "venv：$("$VPY" --version)"

# 3. 安装 fastmcp：有离线 wheel 目录就离线装，否则联网装
say "3/5 安装 fastmcp==$FASTMCP_VERSION"
if [ -d "$WHEEL_DIR" ]; then
  echo "离线安装，wheel 目录：$WHEEL_DIR"
  "$VPY" -m pip install -q --no-index --find-links "$WHEEL_DIR" "fastmcp==$FASTMCP_VERSION" \
    || fail "离线安装失败。多半是打包时填的 Python 版本或 CPU 架构与本机（Python $PYVER，$(uname -m)）不一致，按本机重新打包"
else
  "$VPY" -m pip install -q --upgrade pip
  "$VPY" -m pip install -q "fastmcp==$FASTMCP_VERSION"
fi
"$VPY" -c 'import fastmcp; print("fastmcp", fastmcp.__version__)'

# 4. (重新)启动服务
say "4/5 启动服务（$TRANSPORT，端口 $PORT）"
pkill -f "mcp_server/server.py" 2>/dev/null || true
sleep 1
MCP_TRANSPORT="$TRANSPORT" MCP_PORT="$PORT" nohup "$VPY" mcp_server/server.py > mcp.log 2>&1 &
echo "PID $!，日志 $ROOT/mcp.log"

# 5. 自检：用 MCP 客户端真正调用一次 hello（最多等 15 秒）
say "5/5 自检"
"$VPY" mcp_server/selftest.py "http://127.0.0.1:$PORT$SUFFIX" \
  || { tail -n 20 mcp.log; fail "MCP 客户端调用失败，见上面的日志"; }

IP="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"
DOCKER_GW="$(ip -4 addr show docker0 2>/dev/null | awk '/inet /{sub("/.*","",$2); print $2}' || true)"
cat <<TXT

[完成] 本机自检通过。Nexent 在容器里，地址不能写 localhost，按顺序试：
  1. http://${IP:-<ECS内网IP>}:$PORT$SUFFIX
  2. http://host.docker.internal:$PORT$SUFFIX
  3. http://${DOCKER_GW:-172.17.0.1}:$PORT$SUFFIX
服务名称填 fundtrace。三个都不通时检查防火墙（sudo ufw status / sudo firewall-cmd --list-all），
只放行 Docker 网段访问 $PORT，不要对公网开放。
停止服务：pkill -f mcp_server/server.py
TXT
