# Fundtrace MCP deployment

As of 2026-10-29. Python >= 3.10; tested with Python 3.12 and FastMCP 4.1.4.

## Current status

Eight MCP tools are registered: hello plus seven business tools.
The default mode uses the existing JSON files in core/fixtures/.
These are fixed synthetic examples matching Data and Rules/examples/data/,
not calculations over the generated full dataset in data/.
Every successful fixture response includes _demo to make that distinction visible.

`MCP_MODE=hybrid` is available after deploying this full repository revision:
`get_account` and `get_transactions` query the generated dataset in `data/` (300
accounts, 2,973 transactions, dataset `sim-gen_profile_v1-seed42`). They include
`_demo.mode=synthetic_dataset`. `trace_chain`, `check_rules`, `make_ticket`,
`get_ticket`, and `rejudge` remain fixed fixture outputs. Never combine an
arbitrary account query with the A0087 fixture analysis. No result is live bank
data. `MCP_MODE=real` still requires all seven production APIs and is not ready.

| Tool | Fixture behavior |
| --- | --- |
| hello | Returns a greeting |
| get_account | A0087 account profile |
| get_transactions | A0087 transactions; inclusive start/end; sorted; limit 1..200 |
| trace_chain | A0087, v1, max_hops=4 only |
| check_rules | A0087, v1 only; includes counter evidence |
| make_ticket | A0087/v1 sample; writes mcp_server/demo_tickets/v1/A0087.json |
| get_ticket | Returns and saves the same marked sample in fixture mode |
| rejudge | Fixed v1-to-v2 comparison of 10 sample accounts, 3 changed |

Unsupported accounts/versions/trace depths return explicit errors; parameters are
never silently relabeled onto another account's result. Fixture files are not changed.
Sample tickets stay separate from real tickets/ outputs.

## Run on the cloud server hosting Nexent

Upload the deployment bundle or preserve this directory layout:

```text
fundtrace-mcp/
  mcp_server/
    server.py
    selftest.py
    requirements.txt
    README.md
    DEPLOY.md
    install_systemd.sh
  core/
    __init__.py
    api.py
    store.py
    fixtures/
      (fixture JSON files)
  data/
    accounts.csv
    transactions.csv
    dataset_meta.json
```

Do not upload only server.py: hybrid needs core.api, core.store, fixtures, and
the three data files. The dataset is synthetic, not real account data. Do not
include `eval/` or answer files in the deployment bundle.

From the extracted project root on Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r mcp_server/requirements.txt
MCP_MODE=hybrid .venv/bin/python mcp_server/selftest.py --in-process
MCP_MODE=hybrid MCP_HOST=0.0.0.0 MCP_PORT=8900 \
  .venv/bin/python mcp_server/server.py
```

Keep that terminal open during initial validation. In a second terminal:

```bash
MCP_MODE=hybrid .venv/bin/python mcp_server/selftest.py http://127.0.0.1:8900/sse
```

The self-test must report 8 tools and 18 successful checks. It calls make_ticket
and get_ticket, creating a marked sample ticket. A service showing only hello is
still running the old code and must be restarted.

After the foreground test passes, stop it with Ctrl+C and run in the background:

```bash
nohup env MCP_MODE=hybrid MCP_HOST=0.0.0.0 MCP_PORT=8900 \
  .venv/bin/python mcp_server/server.py > mcp.log 2>&1 < /dev/null &
```

This survives SSH logout but does not automatically restart after a reboot.
For normal operation use systemd with `bash mcp_server/install_systemd.sh`; the
installer validates hybrid mode before restarting the service.

## Nexent configuration

Use service name fundtrace, remote integration, SSE, and URL
http://<cloud-server-private-IP>:8900/sse. Keep Token and custom headers empty
for this unauthenticated private-network demo. Restrict port 8900 to the Nexent
backend or Docker network; do not open it to all public addresses.

Test reachability from the Nexent backend's network, not just the laptop browser.
After adding/updating the service, refresh its tool list and bind the business
tools to the agent. Use {"acct_id":"A0087"} for the six account tools.
For rejudge use {"old":"v1","new":"v2"}. In the agent prompt explicitly state:
"When a tool returns _demo, identify the result as fixed synthetic demonstration
data. Do not claim that other accounts or the full dataset have been analyzed."

## Modes and future real backend

- MCP_MODE=fixture is the default; legacy USE_STUB=1 also selects it.
- MCP_MODE=hybrid routes account and transaction queries to core.api and keeps other tools on fixtures.
- MCP_FIXTURES_DIR optionally points to another directory of compatible fixtures.
- MCP_MODE=real (or legacy USE_STUB=0) delegates to core.api.
- MCP_TRANSPORT=streamable-http changes the endpoint to /mcp; default SSE uses /sse.
- MCP_HOST defaults to 0.0.0.0; use 127.0.0.1 for local-only tests.

Real mode is not ready: core.api currently implements only account and transaction
queries. Deploy the backend and data before using hybrid; do not switch to real
until all tool APIs are implemented and validated. Real-mode get_ticket reads tickets/<version>/<account>.json
and calls core.api.make_ticket if absent. The wrapper never falls back to samples
when a real backend fails. Error responses follow {error, code, detail}.

## Development checks in the full repository

```bash
.venv/bin/python -m pip install jsonschema
.venv/bin/python mcp_server/test_contract.py -v
.venv/bin/python mcp_server/selftest.py --in-process
```

Contract tests verify JSON schemas, unchanged source fixtures, boundary filters,
parameter errors, separated demo tickets, and delegation to a mock real backend.
They do not establish that the missing production backend works, or that the
cloud Nexent instance has connected.
