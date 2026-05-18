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
- An [Appian API key](https://docs.appian.com/suite/help/latest/Deployment_REST_API.html#authentication) or OAuth token

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
