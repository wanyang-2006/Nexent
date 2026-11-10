"""
One-shot: connect to ECS with password, install local pubkey, run a probe command.
Usage: python ssh_setup.py
"""
import paramiko, os, sys

HOST = "60.205.124.241"
PORT = 22
USER = "root"
PASS = "Nexent2026"
PUBKEY_PATH = "C:/Users/yang/.ssh/id_ed25519.pub"

def run():
    with open(PUBKEY_PATH) as f:
        pubkey = f.read().strip()

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)

    # Install pubkey
    cmd_install = (
        "mkdir -p ~/.ssh && chmod 700 ~/.ssh && "
        f"grep -qxF '{pubkey}' ~/.ssh/authorized_keys 2>/dev/null "
        f"|| echo '{pubkey}' >> ~/.ssh/authorized_keys && "
        "chmod 600 ~/.ssh/authorized_keys && echo PUBKEY_INSTALLED"
    )
    _, stdout, stderr = client.exec_command(cmd_install)
    out = stdout.read().decode()
    err = stderr.read().decode()
    print("install:", out.strip(), err.strip())

    # Probe
    _, stdout, _ = client.exec_command(
        "echo OK; uname -a; "
        "systemctl is-active fundtrace-mcp 2>/dev/null; "
        "ls ~/fundtrace-mcp/ 2>/dev/null | head -20"
    )
    print(stdout.read().decode())
    client.close()

if __name__ == "__main__":
    run()
