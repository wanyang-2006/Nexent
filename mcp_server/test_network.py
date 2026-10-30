"""Start disposable SSE and Streamable HTTP servers and exercise all tools."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

def main():
    for mode in ("fixture", "hybrid", "real"):
        for transport, endpoint in (("sse", "sse"), ("streamable-http", "mcp")):
            with tempfile.TemporaryDirectory() as directory:
                with socket.socket() as sock:
                    sock.bind(("127.0.0.1", 0))
                    port = sock.getsockname()[1]
                env = dict(os.environ, MCP_MODE=mode, MCP_HOST="127.0.0.1", MCP_PORT=str(port), MCP_TRANSPORT=transport, MCP_DEMO_TICKETS_DIR=directory, FUNDTRACE_TICKET_DIR=directory, PYTHONDONTWRITEBYTECODE="1")
                with tempfile.TemporaryFile(mode="w+b") as log:
                    proc = subprocess.Popen([sys.executable, str(Path(__file__).with_name("server.py"))], env=env, stdout=log, stderr=log)
                    try:
                        for _ in range(100):
                            if proc.poll() is not None:
                                raise RuntimeError(f"Server exited: {proc.returncode}")
                            try:
                                with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                                    break
                            except OSError:
                                time.sleep(0.1)
                        else:
                            raise TimeoutError("Server startup timed out")
                        client = subprocess.run(
                            [sys.executable, str(Path(__file__).with_name("selftest.py")), f"http://127.0.0.1:{port}/{endpoint}"],
                            env=env,
                            capture_output=True,
                            text=True,
                            timeout=30,
                        )
                        if client.returncode:
                            raise RuntimeError(f"Client selftest failed:\n{client.stdout}\n{client.stderr}")
                        print(client.stdout.strip())
                        path = Path(directory) / "v1" / ("A0176.json" if mode == "real" else "A0087.json")
                        if not path.is_file():
                            raise RuntimeError("Ticket was not persisted")
                        print(f"PASS: {mode} mode, {transport} network transport and ticket persistence")
                    except Exception:
                        log.seek(0)
                        print(log.read().decode("utf-8", errors="replace"), file=sys.stderr)
                        raise
                    finally:
                        if proc.poll() is None:
                            proc.terminate()
                        proc.wait(timeout=10)


if __name__ == "__main__":
    main()
