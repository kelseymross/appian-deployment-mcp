# Appian Deployment MCP Server

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) server that wraps the [Appian Deployment REST API](https://docs.appian.com/suite/help/latest/Deployment_Rest_API.html). It lets AI assistants export, inspect, deploy, and monitor Appian packages on your behalf.

## Quick Start

```bash
git clone https://github.com/kelseymross/appian-deployment-mcp.git
cd appian-deployment-mcp
./setup.sh
```

The setup script will install dependencies, prompt for your Appian environment details, optionally store API keys in your system keychain, and generate the MCP config for you. See [Manual Installation](#manual-installation) below if you prefer to configure things yourself.

## Tools

### Single-Environment Tools

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
| `download_exported_database_scripts` | Download all DB script files from a completed export |
| `download_exported_plugins` | Download the plugins zip from a completed export |
| `download_exported_customization_file` | Download the ICF (values or template) from a completed export |
| `poll_deployment_status` | Poll a deployment until it reaches a terminal state |
| `poll_inspection_status` | Poll an inspection until it completes |
| `approve_deployment` | Approve a deployment in PENDING_REVIEW status |
| `reject_deployment` | Reject a deployment in PENDING_REVIEW status |

### Workflow Tools

| Tool | Description |
|------|-------------|
| `export_and_deploy` | End-to-end: export → download → inspect → deploy across environments |
| `cleanup_deployment_artifacts` | Remove temporary files from interrupted workflows |

### Pipeline Tools

Multi-environment deployment pipelines that chain export → inspect → import across an ordered sequence of environments (e.g., dev → test → prod).

| Tool | Description |
|------|-------------|
| `create_pipeline` | Define a named pipeline as an ordered list of environments |
| `list_pipelines` | List all defined pipelines |
| `get_pipeline` | Get a pipeline definition by name |
| `run_pipeline` | Execute a named pipeline to promote a package through all stages |
| `run_adhoc_pipeline` | Run a one-off pipeline without pre-defining it |
| `get_pipeline_run_status` | Get full status of a pipeline run including all stages |
| `list_pipeline_runs` | List recent pipeline runs with IDs, names, and statuses |
| `cancel_pipeline_run` | Cancel a running pipeline |
| `approve_pipeline_stage` | Approve a pipeline stage waiting at an approval gate |
| `reject_pipeline_stage` | Reject a pipeline stage, cancelling the run |

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (recommended) or pip
- An Appian environment with the Deployment API enabled
- An [Appian API key](https://docs.appian.com/suite/help/latest/Deployment_Rest_API.html#authentication) or OAuth token

## Manual Installation

If you prefer to set things up manually instead of using `./setup.sh`:

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
| `APPIAN_API_VERSION` | No | API version to use: `v1` or `v2` (defaults to `v2`) |
| `APPIAN_SAVE_DIRECTORY` | No | Directory for downloaded deployment artifacts. Defaults to system temp directory (`/tmp/appian-deployments/` on macOS/Linux). Files in the temp directory may be cleaned up by the OS. Set this to a persistent path if you want to keep downloaded artifacts. |

**Named environments** (for multi-environment workflows):

Use the pattern `APPIAN_<ENV>_DOMAIN`, `APPIAN_<ENV>_API_KEY`, etc. For example:

```bash
APPIAN_PROD_DOMAIN=prod.appiancloud.com
APPIAN_PROD_API_KEY=your-prod-key
APPIAN_PROD_API_VERSION=v3

APPIAN_DEV_DOMAIN=dev.appiancloud.com
APPIAN_DEV_API_KEY=your-dev-key
APPIAN_DEV_API_VERSION=v2
```

Then pass `environment="prod"` or `environment="dev"` to any tool.

**Using OAuth instead of an API key:**

You can use an OAuth bearer token by setting `APPIAN_OAUTH_TOKEN` instead of `APPIAN_API_KEY`:

```json
{
  "env": {
    "APPIAN_DOMAIN": "<YOUR_DOMAIN>.appiancloud.com",
    "APPIAN_OAUTH_TOKEN": "<YOUR_OAUTH_TOKEN>"
  }
}
```

> **Note:** OAuth tokens expire. When a token expires, API calls will return 401 errors and you'll need to update the token and restart the MCP server. For long-running use, API keys are simpler.

**Using system keychain (recommended for security):**

Instead of storing API keys in plaintext in your config file, you can store them in your system's keychain and have the MCP server read them at startup.

**Step 1: Store your API key in the keychain**

macOS:
```bash
security add-generic-password -s "appian-dev-api-key" -a "appian-deployment-mcp" -w "<your-api-key>"
```

Linux (requires `secret-tool` / libsecret):
```bash
secret-tool store --label="appian-dev-api-key" service "appian-dev-api-key" account "appian-deployment-mcp"
```

Windows (PowerShell):
```powershell
cmdkey /generic:"appian-dev-api-key" /user:"appian-deployment-mcp" /pass:"<your-api-key>"
```

**Step 2: Configure the MCP to use keychain**

```json
{
  "env": {
    "APPIAN_DEV_DOMAIN": "dev.appiancloud.com",
    "APPIAN_DEV_API_KEY_SOURCE": "keychain",
    "APPIAN_DEV_API_KEY_SERVICE": "appian-dev-api-key"
  }
}
```

| Variable | Required | Description |
|----------|----------|-------------|
| `APPIAN_<ENV>_API_KEY_SOURCE` | Yes | Set to `keychain` to enable keychain lookup |
| `APPIAN_<ENV>_API_KEY_SERVICE` | No | The service/label name in the keychain. Defaults to `appian-<env>-api-key` |
| `APPIAN_<ENV>_API_KEY_ACCOUNT` | No | The account name in the keychain. Defaults to `appian-deployment-mcp` |

**How it works:**
- If `APPIAN_API_KEY` (or `APPIAN_<ENV>_API_KEY`) is set directly, it's used as-is (plaintext, backward compatible)
- If not set but `_API_KEY_SOURCE=keychain` is configured, the server reads from the system keychain at startup
- If neither is set, the server falls back to OAuth token or returns an error

**Multi-environment keychain example:**

```bash
# Store keys for each environment
security add-generic-password -s "appian-dev-api-key" -a "appian-deployment-mcp" -w "<dev-key>"
security add-generic-password -s "appian-test-api-key" -a "appian-deployment-mcp" -w "<test-key>"
security add-generic-password -s "appian-prod-api-key" -a "appian-deployment-mcp" -w "<prod-key>"
```

```json
{
  "mcpServers": {
    "appian-deployment": {
      "command": "<HOME_PATH>/appian-deployment-mcp/.venv/bin/appian-deployment",
      "args": [],
      "env": {
        "APPIAN_DEV_DOMAIN": "dev.appiancloud.com",
        "APPIAN_DEV_API_KEY_SOURCE": "keychain",
        "APPIAN_DEV_API_KEY_SERVICE": "appian-dev-api-key",
        "APPIAN_TEST_DOMAIN": "test.appiancloud.com",
        "APPIAN_TEST_API_KEY_SOURCE": "keychain",
        "APPIAN_TEST_API_KEY_SERVICE": "appian-test-api-key",
        "APPIAN_PROD_DOMAIN": "prod.appiancloud.com",
        "APPIAN_PROD_API_KEY_SOURCE": "keychain",
        "APPIAN_PROD_API_KEY_SERVICE": "appian-prod-api-key"
      }
    }
  }
}
```

> **Tip:** To update a stored key on macOS, delete the old entry first: `security delete-generic-password -s "appian-dev-api-key" -a "appian-deployment-mcp"`, then add the new one.

### MCP client configuration

Add this to your MCP client config (e.g. `.kiro/settings/mcp.json`, `claude_desktop_config.json`, etc.):

First, find the full path to the entry point by running this from the repo directory:

```bash
cd appian-deployment-mcp
which .venv/bin/appian-deployment || echo "$(pwd)/.venv/bin/appian-deployment"
```

Then use that path as the `command` value in your config:

```json
{
  "mcpServers": {
    "appian-deployment": {
      "command": "<HOME_PATH>/appian-deployment-mcp/.venv/bin/appian-deployment",
      "args": [],
      "env": {
        "APPIAN_DOMAIN": "<YOUR_DOMAIN>.appiancloud.com",
        "APPIAN_API_KEY": "<SITE_DEPLOYMENT_API_KEY>",
        "APPIAN_SAVE_DIRECTORY": "/path/to/save/deployments"
      }
    }
  }
}
```

> **Note:** The `command` must be an absolute path to the `appian-deployment` script inside the project's `.venv/bin/` directory. Adjust it to match wherever you cloned the repo.
> 
> **Note:** `APPIAN_SAVE_DIRECTORY` is optional. If omitted, downloaded artifacts are stored in the system temp directory and may be cleaned up by the OS or the `cleanup_deployment_artifacts` tool.

For **multi-environment pipelines**, configure all environments in the `env` block:

```json
{
  "mcpServers": {
    "appian-deployment": {
      "command": "<HOME_PATH>/appian-deployment-mcp/.venv/bin/appian-deployment",
      "args": [],
      "env": { 
        "APPIAN_DEV_DOMAIN": "dev.appiancloud.com",
        "APPIAN_DEV_API_KEY": "<DEV_API_KEY>",
        "APPIAN_TEST_DOMAIN": "test.appiancloud.com",
        "APPIAN_TEST_API_KEY": "<TEST_API_KEY>",
        "APPIAN_PROD_DOMAIN": "prod.appiancloud.com",
        "APPIAN_PROD_API_KEY": "<PROD_API_KEY>"
      }
    }
  }
}
```

This registers three environments (`dev`, `test`, `prod`) that you can use in pipeline definitions and ad-hoc pipelines.

Or if installed globally (e.g. via `pip install .`):

```json
{
  "mcpServers": {
    "appian-deployment": {
      "command": "appian-deployment",
      "env": {
        "APPIAN_DOMAIN": "<YOUR_DOMAIN>.appiancloud.com",
        "APPIAN_API_KEY": "<SITE_DEPLOYMENT_API_KEY>"
      }
    }
  }
}
```

**Alternative: `uv run` style (no binary path needed):**

If you have `uv` installed, you can use this pattern which doesn't require finding the absolute path to the binary:

```json
{
  "mcpServers": {
    "appian-deployment": {
      "command": "uv",
      "args": ["run", "--directory", "<ABSOLUTE_PATH_TO_REPO>", "python", "-m", "appian_deployment_mcp"],
      "env": {
        "APPIAN_DOMAIN": "<YOUR_DOMAIN>.appiancloud.com",
        "APPIAN_API_KEY": "<SITE_DEPLOYMENT_API_KEY>"
      }
    }
  }
}
```

Replace `<ABSOLUTE_PATH_TO_REPO>` with the path where you cloned the repo (e.g. `/Users/you/appian-deployment-mcp`).

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

### Pipeline workflows

Pipelines automate multi-environment promotion with optional inspection and approval gates.

**Define a pipeline:**

> "Create a pipeline called 'release' with stages dev, test, prod"

**Run a pipeline:**

> "Run the 'release' pipeline to promote application `fd6eac3b-f943-46ab-95f5-03ea0a0a9209`, require approval before prod"

The pipeline will:
1. Export from dev
2. Inspect on test, then import to test
3. Inspect on prod, then pause for approval
4. After approval, import to prod

**Run an ad-hoc pipeline (no pre-definition needed):**

> "Promote package `ed806b78-e61a-4a17-bc7f-3ddf032ecf11` from dev through test to prod, inspect before each deploy"

**Check pipeline status:**

> "What's the status of my pipeline run?"

**Approve or reject at a gate:**

> "Approve the pipeline stage for prod"
> "Reject the pipeline — the inspection found issues"

**Cancel a running pipeline:**

> "Cancel the pipeline run, we found a bug"

## Development

```bash
# Install with dev dependencies
uv sync --extra dev

# Run tests
uv run pytest

# Run the server directly
uv run appian-deployment
```


## Enabling the external deployments

The Deployment API is not enabled by default on all Appian environments. A system administrator needs to turn it on:

1. Go to **Admin Console**
2. Go to the **DEVOPS** section
3. Select **INFRASTRUCTURE**
4. Depending on your environment, in the **External Deployments** section select **Enable incoming** or **Enable outgoing** to enable deployments to or from the environment.

Without this, all API calls will return 403 errors.

You will need to configure your deployment and authentication service accounts when configuring these deployment settings.

## Getting an API key

Generate an API key from your Appian environment's Admin Console under **AUTHENTICATION → Web API Authentication**. The key must belong to a user with system administrator privileges or a service account with deployment permissions. See the [Appian docs](https://docs.appian.com/suite/help/latest/Deployment_Rest_API.html#authentication) for details.

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


## License

MIT