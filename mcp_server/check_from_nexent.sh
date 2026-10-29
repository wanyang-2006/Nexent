#!/usr/bin/env bash
# 站在 Nexent 容器里面，逐个试 MCP 地址，找出 Nexent 真正能连上的那一个。
# 原理：Nexent 后端（nexent-config 负责添加/连通性校验，nexent-runtime 负责对话时调用）
# 自带 fastmcp 客户端，这里直接 docker exec 进去做一次 list_tools，结果与页面上的“连通性校验”一致。
# 用法：bash mcp_server/check_from_nexent.sh            （docker 需要 sudo 时：sudo bash ...）
# 可选环境变量：MCP_PORT=8900  MCP_TRANSPORT=sse|streamable-http  NEXENT_CONTAINERS="nexent-config nexent-runtime"
set -uo pipefail

PORT="${MCP_PORT:-8900}"
TRANSPORT="${MCP_TRANSPORT:-sse}"
if [ "$TRANSPORT" = "sse" ]; then SUFFIX="/sse"; else SUFFIX="/mcp"; fi
NET="${NEXENT_NETWORK:-nexent_network}"

command -v docker >/dev/null 2>&1 || { echo "[跳过] 本机没有 docker 命令，无法从容器内检查"; exit 2; }
if ! docker ps >/dev/null 2>&1; then
  echo "[跳过] 当前用户无权访问 docker，请用：sudo bash mcp_server/check_from_nexent.sh"; exit 2
fi

# 1. 找 Nexent 容器
RUNNING="$(docker ps --format '{{.Names}}')"
CONTAINERS=""
for c in ${NEXENT_CONTAINERS:-nexent-config nexent-runtime}; do
  grep -qx "$c" <<<"$RUNNING" && CONTAINERS="$CONTAINERS $c"
done
[ -n "$CONTAINERS" ] || { echo "[失败] 没找到运行中的 nexent-config / nexent-runtime 容器（docker ps 看一下实际名字，用 NEXENT_CONTAINERS 指定）"; exit 1; }

# 2. 候选地址：ECS 内网 IP、Nexent 网络网关、docker0 网关、host.docker.internal
HOST_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
NET_GW="$(docker network inspect "$NET" -f '{{range .IPAM.Config}}{{.Gateway}} {{end}}' 2>/dev/null | awk '{print $1}')"
NET_SUBNET="$(docker network inspect "$NET" -f '{{range .IPAM.Config}}{{.Subnet}} {{end}}' 2>/dev/null | awk '{print $1}')"
DOCKER0_GW="$(ip -4 addr show docker0 2>/dev/null | awk '/inet /{sub("/.*","",$2); print $2}')"
CANDIDATES=""
for h in "$HOST_IP" "$NET_GW" "${DOCKER0_GW:-172.17.0.1}" host.docker.internal; do
  [ -n "$h" ] && ! grep -qw -- "$h" <<<"$CANDIDATES" && CANDIDATES="$CANDIDATES $h"
done

# 3. 容器内执行的探测代码：优先用 MCP 协议 list_tools，没有 fastmcp 时退化为 TCP 连接测试
read -r -d '' PROBE <<'PY'
import asyncio, os, socket, sys
# Nexent 自己的 httpx 客户端 trust_env=False，不走代理；这里也去掉代理变量，保证结果一致
for k in [k for k in os.environ if k.lower() in ("http_proxy", "https_proxy", "all_proxy")]:
    del os.environ[k]
from urllib.parse import urlparse
url = sys.argv[1]
try:
    from fastmcp import Client
except Exception:
    u = urlparse(url)
    try:
        socket.create_connection((u.hostname, u.port), timeout=5).close()
        print("TCP_OK（容器内无 fastmcp，只测了端口）")
    except Exception as e:
        print(f"FAIL {type(e).__name__}: {e}"); sys.exit(1)
    sys.exit(0)
async def main():
    async with Client(url) as c:
        return [t.name for t in await c.list_tools()]
try:
    names = asyncio.run(asyncio.wait_for(main(), 8))
    print("OK 工具: " + ",".join(names))
except BaseException as e:
    msg = str(e).splitlines()[0][:120] if str(e) else ""
    print(f"FAIL {type(e).__name__}: {msg}"); sys.exit(1)
PY

echo "检查端口 $PORT（$TRANSPORT，后缀 $SUFFIX），容器：$CONTAINERS"
GOOD=""
for h in $CANDIDATES; do
  url="http://$h:$PORT$SUFFIX"
  all_ok=1
  for c in $CONTAINERS; do
    out="$(printf '%s\n' "$PROBE" | timeout 15 docker exec -i "$c" python - "$url" 2>&1 | tail -n 1)"
    case "$out" in OK*|TCP_OK*) mark="通过";; *) mark="不通"; all_ok=0;; esac
    printf '  %-45s %-15s %s  %s\n' "$url" "$c" "$mark" "$out"
  done
  [ $all_ok -eq 1 ] && [ -z "$GOOD" ] && GOOD="$url"
done

echo
if [ -n "$GOOD" ]; then
  echo "[结果] 在 Nexent 里填这个地址：$GOOD   （服务名称 fundtrace）"
  exit 0
fi
echo "[结果] 所有地址都不通。依次排查："
echo "  1. 服务是否在跑、是否监听 0.0.0.0：ss -lntp | grep $PORT （应看到 0.0.0.0:$PORT，而不是 127.0.0.1:$PORT）"
echo "  2. 主机防火墙是否拦截了容器网段 ${NET_SUBNET:-<nexent_network 网段>}："
echo "       ufw：      sudo ufw allow from ${NET_SUBNET:-172.18.0.0/16} to any port $PORT proto tcp"
echo "       firewalld：sudo firewall-cmd --permanent --zone=trusted --add-source=${NET_SUBNET:-172.18.0.0/16} && sudo firewall-cmd --reload"
echo "     只放行这个网段即可，不要在阿里云安全组对公网开放 $PORT"
exit 1
