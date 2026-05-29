# Appian Deployment MCP Server

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) server that wraps the [Appian Deployment REST API](https://docs.appian.com/suite/help/latest/Deployment_Rest_API.html). It lets AI assistants export, inspect, deploy, and monitor Appian packages on your behalf.

## Quick Start

**From tarball:**
```bash
tar -xzf appian-deployment-mcp.tar.gz
cd appian-deployment-mcp
./setup.sh
```

**From git:**
```bash
git clone https://github.com/kelseymross/appian-deployment-mcp.git
cd appian-deployment-mcp
./setup.sh
```

The setup script installs dependencies, prompts for your Appian environments, optionally stores API keys in your system keychain, and generates the MCP config. See [Manual Configuration](#manual-configuration) if you prefer to set things up yourself.

## What You Can Do

Once connected, just talk to your AI assistant naturally:

```
"List the packages for my application"
"Export the Events package from dev and deploy it to test"
"Create a pipeline called release with stages dev, test, prod"
"Run the release pipeline for my application"
```

### Example Workflows

**Deploy a package:**
> "Export package `ed806b78-...` from dev, inspect it on test, and deploy if it looks good"

**Promote across environments:**
> "Run the release pipeline to promote my app from dev through test to prod, require approval before prod"

**Check on a deployment:**
> "What's the status of my pipeline run?"
> "Get the deployment log for the last import"

---

## Tools Reference

### Core Deployment

| Tool | Description |
|------|-------------|
| `list_environments` | List configured Appian environments |
| `get_application_packages` | List packages for an application |
| `export_package` | Export a package or application |
| `inspect_package` | Pre-deployment inspection |
| `deploy_package` | Import a package to an environment |
| `get_deployment_results` | Get deployment status and results |
| `get_deployment_log` | Retrieve the deployment log |
| `approve_deployment` | Approve a deployment pending review |
| `reject_deployment` | Reject a deployment pending review |

### Downloads

| Tool | Description |
|------|-------------|
| `download_exported_package` | Download the package zip from an export |
| `download_exported_database_scripts` | Download DB script files from an export |
| `download_exported_plugins` | Download the plugins zip from an export |
| `download_exported_customization_file` | Download the ICF (values or template) |

### Workflow & Polling

| Tool | Description |
|------|-------------|
| `export_and_deploy` | End-to-end: export → inspect → deploy |
| `cleanup_deployment_artifacts` | Remove temp files from workflows |
| `poll_deployment_status` | Poll until deployment completes |
| `poll_inspection_status` | Poll until inspection completes |

### Pipelines

| Tool | Description |
|------|-------------|
| `create_pipeline` | Define a named promotion path |
| `list_pipelines` / `get_pipeline` | View pipeline definitions |
| `run_pipeline` / `run_adhoc_pipeline` | Execute a pipeline |
| `get_pipeline_run_status` / `list_pipeline_runs` | Monitor runs |
| `cancel_pipeline_run` | Stop a running pipeline |
| `approve_pipeline_stage` / `reject_pipeline_stage` | Approval gates |

---

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (recommended) or pip
- An Appian environment with the [Deployment API enabled](#enabling-external-deployments)
- An [Appian API key](#getting-an-api-key) or OAuth token

---

## Manual Configuration

If you didn't use `./setup.sh`, configure the server manually.

### 1. Install

```bash
uv sync        # or: pip install -e .
```

### 2. Add to your MCP client

Add this to your MCP config file:

| IDE | Config file location |
|-----|---------------------|
| Kiro | `.kiro/settings/mcp.json` (workspace) or `~/.kiro/settings/mcp.json` (global) |
| Claude Code | `.mcp.json` (project) or `~/.claude.json` (global) |
| Cursor | `~/.cursor/mcp.json` |
| VS Code | Per the MCP extension settings |
| Claude Desktop | `~/Library/Application Support/Claude/claude_desktop_config.json` |

**Single environment:**

```json
{
  "mcpServers": {
    "appian-deployment": {
      "command": "<PATH_TO_REPO>/.venv/bin/appian-deployment",
      "args": [],
      "env": {
        "APPIAN_DOMAIN": "mysite.appiancloud.com",
        "APPIAN_API_KEY": "<YOUR_API_KEY>"
      }
    }
  }
}
```

**Multiple environments:**

```json
{
  "mcpServers": {
    "appian-deployment": {
      "command": "<PATH_TO_REPO>/.venv/bin/appian-deployment",
      "args": [],
      "env": {
        "APPIAN_DEV_DOMAIN": "dev.appiancloud.com",
        "APPIAN_DEV_API_KEY": "<DEV_KEY>",
        "APPIAN_TEST_DOMAIN": "test.appiancloud.com",
        "APPIAN_TEST_API_KEY": "<TEST_KEY>",
        "APPIAN_PROD_DOMAIN": "prod.appiancloud.com",
        "APPIAN_PROD_API_KEY": "<PROD_KEY>"
      }
    }
  }
}
```

**Alternative — `uv run` style (no binary path needed):**

```json
{
  "mcpServers": {
    "appian-deployment": {
      "command": "uv",
      "args": ["run", "--directory", "<PATH_TO_REPO>", "python", "-m", "appian_deployment_mcp"],
      "env": {
        "APPIAN_DOMAIN": "mysite.appiancloud.com",
        "APPIAN_API_KEY": "<YOUR_API_KEY>"
      }
    }
  }
}
```

### 3. Environment variables reference

| Variable | Description |
|----------|-------------|
| `APPIAN_DOMAIN` | Site domain (e.g. `mysite.appiancloud.com`) |
| `APPIAN_API_KEY` | API key (plaintext) |
| `APPIAN_OAUTH_TOKEN` | OAuth bearer token (alternative to API key) |
| `APPIAN_API_VERSION` | `v1` or `v2` (default: `v2`) |
| `APPIAN_SAVE_DIRECTORY` | Where to save downloaded artifacts (default: system temp) |
| `APPIAN_<ENV>_DOMAIN` | Domain for a named environment |
| `APPIAN_<ENV>_API_KEY` | API key for a named environment |
| `APPIAN_<ENV>_API_KEY_SOURCE` | Set to `keychain` for secure storage |
| `APPIAN_<ENV>_API_KEY_SERVICE` | Keychain service name (default: `appian-<env>-api-key`) |

---

## Secure Credential Storage (Keychain)

Instead of storing API keys in plaintext, store them in your system keychain.

### Store your key

**macOS:**
```bash
security add-generic-password -s "appian-dev-api-key" -a "appian-deployment-mcp" -w "<your-api-key>"
```

**Linux:**
```bash
secret-tool store --label="appian-dev-api-key" service "appian-dev-api-key" account "appian-deployment-mcp"
```

**Windows:**
```powershell
cmdkey /generic:"appian-dev-api-key" /user:"appian-deployment-mcp" /pass:"<your-api-key>"
```

### Configure the MCP to use it

```json
"env": {
  "APPIAN_DEV_DOMAIN": "dev.appiancloud.com",
  "APPIAN_DEV_API_KEY_SOURCE": "keychain",
  "APPIAN_DEV_API_KEY_SERVICE": "appian-dev-api-key"
}
```

The server checks for a plaintext key first, then falls back to keychain if `_API_KEY_SOURCE=keychain` is set.

> **Tip:** To update a key on macOS, delete first: `security delete-generic-password -s "appian-dev-api-key" -a "appian-deployment-mcp"`

---

## Appian Environment Setup

### Enabling external deployments

A system administrator must enable the Deployment API:

1. Go to **Admin Console → DEVOPS → INFRASTRUCTURE**
2. In **External Deployments**, enable **incoming** and/or **outgoing** as needed

Without this, API calls return 403 errors.

### Getting an API key

1. Go to **Admin Console → AUTHENTICATION → Web API Authentication**
2. Create an API key linked to a service account with deployment permissions

See the [Appian docs](https://docs.appian.com/suite/help/latest/Deployment_Rest_API.html#authentication) for details.

---

## Development

```bash
uv sync --extra dev    # Install with dev dependencies
uv run pytest          # Run tests
uv run appian-deployment  # Run the server directly
```

### Python version

Requires Python 3.11+. If you're on an older version:

```bash
uv python install 3.11    # or: pyenv install 3.11
```

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| 401 Unauthorized | Invalid/expired credentials | Regenerate API key in Admin Console |
| 403 Forbidden | API not enabled or insufficient permissions | Enable in Admin Console; check service account roles |
| 404 Not Found | Invalid UUID | Verify the UUID from Appian Designer |
| 409 Conflict | Concurrency limit | Wait for current operation to finish |
| Connection timeout | Network issue or wrong domain | Verify `APPIAN_DOMAIN` is reachable |

---

## Contributing

1. Fork and create a feature branch
2. `uv sync --extra dev`
3. Make changes and add tests
4. `uv run pytest` — all tests must pass
5. Open a PR against `main`

## License

MIT
