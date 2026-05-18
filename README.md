# Appian Deployment MCP Server

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) server that wraps the [Appian Deployment REST API](https://docs.appian.com/suite/help/latest/Deployment_Rest_API.html). It lets AI assistants export, inspect, deploy, and monitor Appian packages on your behalf.
 
## Tools

| Tool | Description |
|------|-------------|
| `list_environments` | List all configured Appian environments |
| `get_application_packages` | List packages for an application by UUID |
| `export_package` | Export a package or application from Appian |
| `inspect_package` | Run a pre-deployment inspection on a package zip |
| `get_inspection_results` | Get results of a completed inspection |
| `deploy_package` | Import/deploy a package to an Appian environment |
| `get_deployment_results` | Get the status and results of a deployment |
| `get_deployment_log` | Retrieve the plain-text deployment log |
| `download_exported_package` | Download the zip from a completed export |
| `poll_deployment_status` | Poll a deployment until it reaches a terminal state |
| `poll_inspection_status` | Poll an inspection until it completes |

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (recommended) or pip
- An Appian environment with the Deployment API enabled
- An [Appian API key](https://docs.appian.com/suite/help/latest/Deployment_Rest_API.html#authentication) or OAuth token

## Installation

```bash
git clone https://github.com/kelseymross/appian-deployment-mcp.git
cd appian-deployment-mcp
uv sync
```

Or with pip:

```bash
pip install -e .
```

## Configuration

### Environment variables

The server reads Appian connection details from environment variables:

**Default environment:**

| Variable | Required | Description |
|----------|----------|-------------|
| `APPIAN_DOMAIN` | Yes | Your Appian site domain (e.g. `mysite.appiancloud.com`) |
| `APPIAN_API_KEY` | One of these | API key for authentication |
| `APPIAN_OAUTH_TOKEN` | One of these | OAuth bearer token for authentication |

**Named environments** (for multi-environment workflows):

Use the pattern `APPIAN_<ENV>_DOMAIN`, `APPIAN_<ENV>_API_KEY`, etc. For example:

```bash
APPIAN_PROD_DOMAIN=prod.appiancloud.com
APPIAN_PROD_API_KEY=your-prod-key

APPIAN_DEV_DOMAIN=dev.appiancloud.com
APPIAN_DEV_API_KEY=your-dev-key
```

Then pass `environment="prod"` or `environment="dev"` to any tool.

### MCP client configuration

Add this to your MCP client config (e.g. `.kiro/settings/mcp.json`, `claude_desktop_config.json`, etc.):

```json
{
  "mcpServers": {
    "appian-deployment": {
      "command": "path/to/appian-deployment-mcp/.venv/bin/python",
      "args": ["-m", "appian_deployment_mcp.server"],
      "env": {
        "APPIAN_DOMAIN": "your-site.appiancloud.com",
        "APPIAN_API_KEY": "your-api-key"
      }
    }
  }
}
```

Or if installed globally:

```json
{
  "mcpServers": {
    "appian-deployment": {
      "command": "appian-deployment",
      "env": {
        "APPIAN_DOMAIN": "your-site.appiancloud.com",
        "APPIAN_API_KEY": "your-api-key"
      }
    }
  }
}
```

## Usage examples

### Export a package

1. Find the package UUID:
   > "List the packages for application `fd6eac3b-f943-46ab-95f5-03ea0a0a9209`"

2. Export it:
   > "Export package `ed806b78-e61a-4a17-bc7f-3ddf032ecf11`"

3. Wait for completion:
   > "Poll the export until it's done"

4. Download the zip:
   > "Download the exported package"

### Deploy a package

1. Inspect first (optional but recommended):
   > "Inspect the package at `./my-package.zip`"

2. Deploy:
   > "Deploy `./my-package.zip` with the customization file `./prod.properties`"

3. Check results:
   > "Get the deployment log"

### Multi-environment workflow

> "Export the package from dev, then deploy it to prod"

The server handles routing to the correct environment when you specify `environment="dev"` or `environment="prod"`.

## Development

```bash
# Install with dev dependencies
uv sync --extra dev

# Run tests
uv run pytest

# Run the server directly
uv run appian-deployment
```

## License

MIT

## Getting an API key

Generate an API key from your Appian environment's Admin Console under **Settings → API Keys**. The key must belong to a user with system administrator privileges or a service account with deployment permissions. See the [Appian docs](https://docs.appian.com/suite/help/latest/Deployment_Rest_API.html#authentication) for details.

## Enabling the Deployment API

The Deployment API is not enabled by default on all Appian environments. A system administrator needs to turn it on:

1. Go to **Admin Console → System → Deployment API**
2. Toggle the API to **Enabled**

Without this, all API calls will return 403 errors.

## Python version

This project requires Python 3.11 or later. If you're on an older version:

```bash
# With uv (recommended)
uv python install 3.11

# Or with pyenv
pyenv install 3.11
pyenv local 3.11
```

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| 401 Unauthorized | Invalid or expired API key / OAuth token | Regenerate your API key in Admin Console |
| 403 Forbidden | Deployment API not enabled, or user lacks permissions | Enable the API in Admin Console; ensure the user has deployment rights |
| 404 Not Found | Invalid UUID for deployment, inspection, or application | Double-check the UUID — copy it from the Appian Designer URL |
| 409 Conflict | Concurrency limit — only one export/import runs at a time per environment | Wait for the current operation to finish, then retry |
| Connection timeout | Network issue or incorrect domain | Verify `APPIAN_DOMAIN` is correct and reachable from your machine |

## Contributing

1. Fork the repo and create a feature branch
2. Install dev dependencies: `uv sync --extra dev`
3. Make your changes and add tests for new functionality
4. Run the test suite: `uv run pytest`
5. Ensure all tests pass before opening a PR
6. Open a pull request against `main` with a clear description of the change
