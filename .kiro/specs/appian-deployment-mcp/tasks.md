# Implementation Plan: Appian Deployment MCP Server

## Overview

Build a Python MCP server that wraps the Appian Deployment REST API v2 using FastMCP, httpx, and environment-variable-based configuration. Implementation proceeds bottom-up: config → error handling → HTTP client → tool modules → entry point → wiring and integration.

## Tasks

- [x] 1. Set up project structure and dependencies
  - Create the Python package directory structure: `src/appian_deployment_mcp/` with `__init__.py`, `server.py`, `config.py`, `client.py`, `errors.py`, and `tools/` subdirectory with `__init__.py`, `environments.py`, `packages.py`, `exports.py`, `inspections.py`, `deployments.py`, `polling.py`, `downloads.py`
  - Create `pyproject.toml` with dependencies: `mcp[cli]`, `httpx`, and dev dependencies: `pytest`, `pytest-asyncio`, `hypothesis`, `respx`
  - Define the `appian-deployment` console entry point pointing to `appian_deployment_mcp.server:main`
  - Create `tests/` directory with `__init__.py`, `conftest.py` (shared fixtures for EnvironmentConfig, mocked httpx clients)
  - _Requirements: 13.1, 13.2_

- [x] 2. Implement configuration layer
  - [x] 2.1 Implement `EnvironmentConfig` dataclass and `load_environments()` in `config.py`
    - Create frozen dataclass with `name`, `domain`, `api_key`, `oauth_token` fields
    - Implement `base_url` property returning `https://{domain}/suite/deployment-management/v2`
    - Implement `auth_headers` property returning API key header or OAuth Bearer header (API key takes precedence)
    - Implement `load_environments()` to read `APPIAN_DOMAIN` + credentials as default, scan for `APPIAN_<ENV>_DOMAIN` patterns for named environments
    - Raise clear errors when `APPIAN_DOMAIN` is missing or no credentials are set
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1_

  - [x] 2.2 Implement `resolve_environment()` in `config.py`
    - Accept environments dict and optional environment name
    - Return matching config by name, fall back to "default" when name is None
    - Raise clear error for unknown environment names
    - _Requirements: 2.2, 2.3_

  - [ ]* 2.3 Write property tests for configuration layer
    - **Property 1: Base URL construction** — For any valid domain string, `base_url` produces `https://{domain}/suite/deployment-management/v2`
    - **Validates: Requirements 1.6**

  - [ ]* 2.4 Write property tests for environment discovery
    - **Property 2: Environment discovery from env var patterns** — For any set of env vars matching `APPIAN_<ENV>_DOMAIN` + credentials, `load_environments()` returns correct configs
    - **Validates: Requirements 2.1**

  - [ ]* 2.5 Write property tests for environment resolution
    - **Property 3: Environment resolution by name** — For any dict of configs and any existing key, `resolve_environment()` returns the matching config
    - **Validates: Requirements 2.2**

- [x] 3. Implement error handling layer
  - [x] 3.1 Implement `AppianAPIError`, `handle_response()`, and `ERROR_MESSAGES` in `errors.py`
    - Define `AppianAPIError` exception with `status_code` and `message`
    - Implement `handle_response()` to raise `AppianAPIError` for non-2xx responses with mapped messages for 401, 403, 404, 409
    - For unknown error codes, include raw status code and response body
    - Implement helper to format network errors with the domain name
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6_

  - [ ]* 3.2 Write property tests for HTTP error mapping
    - **Property 6: HTTP error status mapping** — For any known status code {401, 403, 404, 409}, error handler returns mapped message; for unknown codes, returns raw status and body
    - **Validates: Requirements 12.1, 12.2, 12.3, 12.4, 12.6**

  - [ ]* 3.3 Write property tests for network error messages
    - **Property 12: Network error includes domain** — For any domain string, connection error message contains that domain
    - **Validates: Requirements 12.5**

- [x] 4. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement HTTP client layer
  - [x] 5.1 Implement `AppianClient` class in `client.py`
    - Create `AppianClient` accepting `EnvironmentConfig`, initializing `httpx.AsyncClient` with base URL, auth headers, and timeouts
    - Implement `get(path)` method for JSON GET requests with error handling
    - Implement `post_json(path, body, headers)` method for JSON POST requests
    - Implement `post_multipart(path, json_part, files)` method for multipart/form-data uploads
    - Implement `download_file(url, save_path)` method for streaming file downloads
    - Implement `get_text(path)` method for plain text GET responses
    - Implement `close()` method to clean up the httpx client
    - Catch `httpx.ConnectError` and `httpx.TimeoutException`, convert to structured error responses including the domain name
    - _Requirements: 3.2, 4.2, 5.2, 6.2, 7.2, 8.2, 9.2, 11.3, 12.5_

  - [ ]* 5.2 Write property tests for API path construction
    - **Property 4: API path construction** — For any UUID and endpoint type, the constructed path matches the documented pattern
    - **Validates: Requirements 3.2, 6.2, 8.2, 9.2**

  - [ ]* 5.3 Write unit tests for `AppianClient` methods
    - Test GET, POST JSON, POST multipart, download, and text responses using `respx` mocks
    - Test error handling for connection errors and timeouts
    - _Requirements: 12.5_

- [x] 6. Implement tool modules — core CRUD tools
  - [x] 6.1 Implement `list_environments` tool in `tools/environments.py`
    - Register `list_environments` tool with FastMCP that returns names of all configured environments
    - _Requirements: 2.4_

  - [x] 6.2 Implement `get_application_packages` tool in `tools/packages.py`
    - Register tool accepting `application_uuid` (required) and `environment` (optional)
    - Send GET to `/applications/<uuid>/packages`, return package list with uuid, name, description, objectCount, databaseScriptCount, pluginCount, createdTimestamp
    - Return HTTP status code and error message on API errors
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [x] 6.3 Implement `export_package` tool in `tools/exports.py`
    - Register tool accepting `uuids` (required list), `export_type` (required), `name` (optional), `description` (optional), `environment` (optional)
    - Validate `export_type` is "package" or "application"
    - Send POST to `/deployments` with `Action-Type: export` header and JSON body
    - Return deployment UUID, URL, and status
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [ ]* 6.4 Write property tests for export request construction
    - **Property 7: Export request construction** — For any valid export params, the POST request includes `Action-Type: export` header and all provided parameters in the JSON body
    - **Validates: Requirements 4.2**

  - [ ]* 6.5 Write property tests for API response field preservation
    - **Property 5: API response field preservation** — For any valid API response dict, the tool response preserves all specified fields with original values
    - **Validates: Requirements 3.3, 4.3, 5.4, 6.3, 7.5, 8.3, 8.4**

- [x] 7. Implement tool modules — inspection tools
  - [x] 7.1 Implement `inspect_package` tool in `tools/inspections.py`
    - Register tool accepting `package_file_path` (required), `customization_file_path` (optional), `admin_console_settings_file_path` (optional), `environment` (optional)
    - Validate all file paths exist before making API call
    - Send POST to `/inspections` with multipart/form-data: `zipFile` part for package, `ICF` part for customization file, `json` part for metadata
    - Return inspection UUID and URL
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [x] 7.2 Implement `get_inspection_results` tool in `tools/inspections.py`
    - Register tool accepting `inspection_uuid` (required) and `environment` (optional)
    - Send GET to `/inspections/<uuid>`, return status, object counts, errors, and warnings for COMPLETED; return status for IN_PROGRESS
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [ ]* 7.3 Write property tests for file path validation
    - **Property 8: File path validation error identifies the path** — For any non-existent file path, the error message contains that path string
    - **Validates: Requirements 5.5, 7.6**

- [x] 8. Implement tool modules — deployment tools
  - [x] 8.1 Implement `deploy_package` tool in `tools/deployments.py`
    - Register tool accepting `name` (required), `package_file_path`, `customization_file_path`, `admin_console_settings_file_path`, `plugins_file_path`, `data_source`, `database_scripts`, `description`, `environment` (all optional)
    - Validate at least one deployable artifact is provided
    - Validate all file paths exist before making API call
    - Send POST to `/deployments` with `Action-Type: import` header and multipart/form-data
    - Return deployment UUID, URL, and status
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [x] 8.2 Implement `get_deployment_results` tool in `tools/deployments.py`
    - Register tool accepting `deployment_uuid` (required) and `environment` (optional)
    - Send GET to `/deployments/<uuid>`, return import results (object/plugin/admin counts, log URL) or export results (zip URLs, data source, scripts) based on response shape
    - Return status for IN_PROGRESS
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

  - [x] 8.3 Implement `get_deployment_log` tool in `tools/deployments.py`
    - Register tool accepting `deployment_uuid` (required) and `environment` (optional)
    - Send GET to `/deployments/<uuid>/log`, return plain text log content
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

  - [ ]* 8.4 Write property tests for deploy artifact validation
    - **Property 9: Deploy artifact validation** — For any invocation where all artifact parameters are absent, the tool returns an error indicating at least one artifact is required
    - **Validates: Requirements 7.4**

- [x] 9. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Implement tool modules — polling and download tools
  - [x] 10.1 Implement `poll_deployment_status` and `poll_inspection_status` tools in `tools/polling.py`
    - Register `poll_deployment_status` accepting `deployment_uuid` (required), `poll_interval_seconds` (default 5), `max_wait_seconds` (default 300), `environment` (optional)
    - Register `poll_inspection_status` accepting `inspection_uuid` (required), `poll_interval_seconds` (default 5), `max_wait_seconds` (default 300), `environment` (optional)
    - Implement async polling loop using `asyncio.sleep` between calls
    - Check against `DEPLOYMENT_TERMINAL_STATUSES` and `INSPECTION_TERMINAL_STATUSES` sets
    - Return `{completed, timed_out, elapsed_seconds, result}` wrapper
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8_

  - [ ]* 10.2 Write property tests for polling termination
    - **Property 10: Polling terminates at terminal status** — For any response sequence ending in a terminal status, polling stops and returns the terminal response; API call count equals position of first terminal status
    - **Validates: Requirements 10.2, 10.6**

  - [ ]* 10.3 Write property tests for polling timeout
    - **Property 11: Polling timeout returns last status** — For any all-IN_PROGRESS sequence exceeding max_wait_seconds, polling returns `timed_out: true` with last known status
    - **Validates: Requirements 10.4, 10.8**

  - [x] 10.4 Implement `download_exported_package` tool in `tools/downloads.py`
    - Register tool accepting `deployment_uuid` (required), `save_directory` (optional, defaults to cwd), `environment` (optional)
    - First call `get_deployment_results` to obtain `packageZip` URL
    - Download .zip file to specified directory using `AppianClient.download_file()`
    - Return `{file_path, file_size_bytes}`
    - Return error if deployment is not a completed export
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

- [x] 11. Implement MCP server entry point and wire everything together
  - [x] 11.1 Implement `server.py` entry point
    - Create `FastMCP` instance with name `"appian-deployment"` and descriptive instructions
    - Import all tool modules so they register against the mcp instance
    - Implement `main()` function calling `mcp.run(transport="stdio")`
    - Initialize `load_environments()` at startup, store in module-level state accessible to tools
    - _Requirements: 13.1, 13.3_

  - [x] 11.2 Wire tool modules to shared MCP instance and environment config
    - Ensure each tool module imports the shared `mcp` instance and `resolve_environment` / `AppianClient`
    - Ensure each tool creates an `AppianClient` per request using the resolved environment config
    - Verify all 12 tools are registered: `list_environments`, `get_application_packages`, `export_package`, `inspect_package`, `get_inspection_results`, `deploy_package`, `get_deployment_results`, `get_deployment_log`, `poll_deployment_status`, `poll_inspection_status`, `download_exported_package`
    - _Requirements: 13.3_

  - [ ]* 11.3 Write property tests for tool metadata completeness
    - **Property 13: All tools have complete metadata** — For every registered tool, verify non-empty name, non-empty description, and typed input schema with at least one parameter
    - **Validates: Requirements 13.3**

- [x] 12. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document using Hypothesis
- Unit tests validate specific examples and edge cases using pytest + respx
- All tools use Python with FastMCP, httpx, and async/await patterns as specified in the design
