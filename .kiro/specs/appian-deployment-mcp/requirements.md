# Requirements Document

## Introduction

This document defines the requirements for an MCP (Model Context Protocol) server that wraps the Appian Deployment REST API v2. The MCP server enables AI agents to perform conversational CI/CD workflows by exposing each Appian deployment API endpoint as an MCP tool. The server is Python-based, distributed via `uvx`, and supports multi-environment configuration through environment variables.

## Glossary

- **MCP_Server**: The Python-based Model Context Protocol server that exposes Appian Deployment REST API v2 endpoints as MCP tools
- **MCP_Tool**: A callable function registered with the MCP server that an AI agent can invoke to interact with the Appian API
- **Appian_API**: The Appian Deployment REST API v2 at `https://<domain>/suite/deployment-management/v2`
- **Agent**: An AI assistant (e.g., Kiro) that invokes MCP tools through the Model Context Protocol
- **Environment_Config**: A named set of connection parameters (domain, credentials) for a specific Appian environment (e.g., dev, staging, prod)
- **API_Key_Auth**: Authentication using the `appian-api-key` HTTP header
- **OAuth_Auth**: Authentication using an OAuth 2.0 Bearer token in the `Authorization` header
- **Export_Operation**: An asynchronous operation that exports an Appian application or package as a .zip file
- **Import_Operation**: An asynchronous operation that deploys (imports) a package into an Appian environment
- **Inspection_Operation**: An asynchronous operation that inspects a package for potential deployment issues
- **Polling**: Repeatedly checking the status of an asynchronous operation until it reaches a terminal state
- **ICF**: Import Customization File — a `.properties` file that customizes deployment behavior
- **Package_UUID**: A unique identifier for an Appian deployment package

## Requirements

### Requirement 1: MCP Server Initialization and Configuration

**User Story:** As a developer, I want the MCP server to load connection settings from environment variables, so that I can connect to different Appian environments without modifying code.

#### Acceptance Criteria

1. WHEN the MCP_Server starts, THE MCP_Server SHALL read the `APPIAN_DOMAIN` environment variable to determine the base URL for the Appian_API
2. WHEN the MCP_Server starts, THE MCP_Server SHALL read the `APPIAN_API_KEY` environment variable to configure API_Key_Auth
3. WHEN the MCP_Server starts and `APPIAN_API_KEY` is not set, THE MCP_Server SHALL read the `APPIAN_OAUTH_TOKEN` environment variable to configure OAuth_Auth
4. IF neither `APPIAN_API_KEY` nor `APPIAN_OAUTH_TOKEN` is set at startup, THEN THE MCP_Server SHALL return a clear error message stating that authentication credentials are required
5. IF `APPIAN_DOMAIN` is not set at startup, THEN THE MCP_Server SHALL return a clear error message stating that the Appian domain is required
6. THE MCP_Server SHALL construct the Appian_API base URL as `https://<APPIAN_DOMAIN>/suite/deployment-management/v2`

### Requirement 2: Multi-Environment Support

**User Story:** As a developer, I want to configure multiple Appian environments, so that I can promote packages across dev, staging, and production from a single MCP server session.

#### Acceptance Criteria

1. WHEN environment variables with the pattern `APPIAN_<ENV_NAME>_DOMAIN` and `APPIAN_<ENV_NAME>_API_KEY` (or `APPIAN_<ENV_NAME>_OAUTH_TOKEN`) are set, THE MCP_Server SHALL register each as a named Environment_Config
2. WHEN an MCP_Tool is invoked with an optional `environment` parameter, THE MCP_Server SHALL use the corresponding Environment_Config for that request
3. WHEN an MCP_Tool is invoked without an `environment` parameter, THE MCP_Server SHALL use the default Environment_Config derived from `APPIAN_DOMAIN` and `APPIAN_API_KEY` or `APPIAN_OAUTH_TOKEN`
4. THE MCP_Server SHALL expose a `list_environments` MCP_Tool that returns the names of all configured Environment_Configs

### Requirement 3: Application Package Details Tool

**User Story:** As a developer, I want to retrieve package metadata for an Appian application, so that I can identify the correct Package_UUID to export.

#### Acceptance Criteria

1. THE MCP_Server SHALL expose a `get_application_packages` MCP_Tool that accepts an application UUID as a required parameter
2. WHEN the `get_application_packages` MCP_Tool is invoked, THE MCP_Server SHALL send a `GET` request to `/applications/<UUID>/packages` on the Appian_API
3. WHEN the Appian_API returns a successful response, THE MCP_Server SHALL return the list of packages including each package's uuid, name, description, objectCount, databaseScriptCount, pluginCount, and createdTimestamp
4. IF the Appian_API returns an error response, THEN THE MCP_Server SHALL return the HTTP status code and error message to the Agent

### Requirement 4: Export Package Tool

**User Story:** As a developer, I want to export an Appian package or application, so that I can obtain the deployment artifact for inspection and deployment to another environment.

#### Acceptance Criteria

1. THE MCP_Server SHALL expose an `export_package` MCP_Tool that accepts the following parameters: `uuids` (required list of UUIDs), `export_type` (required, either "package" or "application"), `name` (optional string), and `description` (optional string)
2. WHEN the `export_package` MCP_Tool is invoked, THE MCP_Server SHALL send a `POST` request to `/deployments` with the `Action-Type: export` header and the provided parameters as JSON body
3. WHEN the Appian_API returns a successful response, THE MCP_Server SHALL return the deployment UUID, URL, and status to the Agent
4. IF the Appian_API returns an error response, THEN THE MCP_Server SHALL return the HTTP status code and error message to the Agent

### Requirement 5: Inspect Package Tool

**User Story:** As a developer, I want to inspect a package before deploying it, so that I can identify potential issues and avoid failed deployments.

#### Acceptance Criteria

1. THE MCP_Server SHALL expose an `inspect_package` MCP_Tool that accepts the following parameters: `package_file_path` (required path to the .zip file), `customization_file_path` (optional path to the .properties ICF file), and `admin_console_settings_file_path` (optional path to the admin console settings .zip)
2. WHEN the `inspect_package` MCP_Tool is invoked, THE MCP_Server SHALL send a `POST` request to `/inspections` using `multipart/form-data` encoding, attaching the package .zip as the `zipFile` part and including the JSON metadata in the `json` part
3. WHEN a customization_file_path is provided, THE MCP_Server SHALL include the ICF file as the `ICF` part of the multipart request
4. WHEN the Appian_API returns a successful response, THE MCP_Server SHALL return the inspection UUID and URL to the Agent
5. IF the specified file path does not exist or is not readable, THEN THE MCP_Server SHALL return an error message identifying the missing file

### Requirement 6: Get Inspection Results Tool

**User Story:** As a developer, I want to retrieve inspection results, so that I can review warnings and errors before proceeding with deployment.

#### Acceptance Criteria

1. THE MCP_Server SHALL expose a `get_inspection_results` MCP_Tool that accepts an inspection UUID as a required parameter
2. WHEN the `get_inspection_results` MCP_Tool is invoked, THE MCP_Server SHALL send a `GET` request to `/inspections/<uuid>` on the Appian_API
3. WHEN the Appian_API returns a response with status `COMPLETED`, THE MCP_Server SHALL return the status, total objects expected, objects expected to succeed, objects expected to fail, objects expected to be skipped, total errors, total warnings, and the lists of errors and warnings
4. WHEN the Appian_API returns a response with status `IN_PROGRESS`, THE MCP_Server SHALL return the status indicating the inspection is still running
5. IF the Appian_API returns an error response, THEN THE MCP_Server SHALL return the HTTP status code and error message to the Agent

### Requirement 7: Deploy (Import) Package Tool

**User Story:** As a developer, I want to deploy a package to an Appian environment, so that I can release application changes.

#### Acceptance Criteria

1. THE MCP_Server SHALL expose a `deploy_package` MCP_Tool that accepts the following parameters: `name` (required string), `package_file_path` (optional path to the .zip file), `customization_file_path` (optional path to the .properties ICF file), `admin_console_settings_file_path` (optional path to the admin console settings .zip), `plugins_file_path` (optional path to the plugins .zip), `data_source` (optional string for data source name or UUID), `database_scripts` (optional list of objects with `fileName` and `orderId`), and `description` (optional string)
2. WHEN the `deploy_package` MCP_Tool is invoked, THE MCP_Server SHALL send a `POST` request to `/deployments` with the `Action-Type: import` header using `multipart/form-data` encoding
3. WHEN file path parameters are provided, THE MCP_Server SHALL attach each file to the appropriate multipart form part
4. IF none of `package_file_path`, `admin_console_settings_file_path`, `plugins_file_path`, or the combination of `data_source` and `database_scripts` is provided, THEN THE MCP_Server SHALL return an error message stating that at least one deployable artifact is required
5. WHEN the Appian_API returns a successful response, THE MCP_Server SHALL return the deployment UUID, URL, and status to the Agent
6. IF a specified file path does not exist or is not readable, THEN THE MCP_Server SHALL return an error message identifying the missing file

### Requirement 8: Get Deployment Results Tool

**User Story:** As a developer, I want to check the status and results of a deployment, so that I can confirm whether an export or import succeeded.

#### Acceptance Criteria

1. THE MCP_Server SHALL expose a `get_deployment_results` MCP_Tool that accepts a deployment UUID as a required parameter
2. WHEN the `get_deployment_results` MCP_Tool is invoked, THE MCP_Server SHALL send a `GET` request to `/deployments/<uuid>` on the Appian_API
3. WHEN the Appian_API returns an import deployment response with a terminal status, THE MCP_Server SHALL return the status, object counts (total, imported, failed, skipped), plugin counts, admin console settings counts, database script count, and the deployment log URL
4. WHEN the Appian_API returns an export deployment response with a terminal status, THE MCP_Server SHALL return the status, the package .zip download URL, data source info, database scripts with download URLs, plugins .zip URL, customization file URL, customization file template URL, and the deployment log URL
5. WHEN the Appian_API returns a response with status `IN_PROGRESS`, THE MCP_Server SHALL return the status indicating the operation is still running
6. IF the Appian_API returns an error response, THEN THE MCP_Server SHALL return the HTTP status code and error message to the Agent

### Requirement 9: Get Deployment Log Tool

**User Story:** As a developer, I want to retrieve the deployment log, so that I can diagnose issues with a deployment.

#### Acceptance Criteria

1. THE MCP_Server SHALL expose a `get_deployment_log` MCP_Tool that accepts a deployment UUID as a required parameter
2. WHEN the `get_deployment_log` MCP_Tool is invoked, THE MCP_Server SHALL send a `GET` request to `/deployments/<uuid>/log` on the Appian_API
3. WHEN the Appian_API returns a successful response, THE MCP_Server SHALL return the plain text deployment log content to the Agent
4. IF the Appian_API returns an error response, THEN THE MCP_Server SHALL return the HTTP status code and error message to the Agent

### Requirement 10: Status Polling Tool

**User Story:** As a developer, I want to poll the status of async operations until completion, so that I do not have to manually check status repeatedly.

#### Acceptance Criteria

1. THE MCP_Server SHALL expose a `poll_deployment_status` MCP_Tool that accepts a deployment UUID as a required parameter, a `poll_interval_seconds` optional parameter (default 5), and a `max_wait_seconds` optional parameter (default 300)
2. WHEN the `poll_deployment_status` MCP_Tool is invoked, THE MCP_Server SHALL repeatedly call `GET /deployments/<uuid>` at the specified interval until the status reaches a terminal state (`COMPLETED`, `COMPLETED_WITH_ERRORS`, `COMPLETED_WITH_IMPORT_ERRORS`, `COMPLETED_WITH_PUBLISH_ERRORS`, `COMPLETED_WITH_EXPORT_ERRORS`, `FAILED`, `PENDING_REVIEW`, `REJECTED`)
3. WHEN the operation reaches a terminal status, THE MCP_Server SHALL return the full deployment results to the Agent
4. IF the max_wait_seconds is exceeded before a terminal status is reached, THEN THE MCP_Server SHALL return the last known status and a message indicating the timeout was reached
5. THE MCP_Server SHALL expose a `poll_inspection_status` MCP_Tool that accepts an inspection UUID as a required parameter, a `poll_interval_seconds` optional parameter (default 5), and a `max_wait_seconds` optional parameter (default 300)
6. WHEN the `poll_inspection_status` MCP_Tool is invoked, THE MCP_Server SHALL repeatedly call `GET /inspections/<uuid>` at the specified interval until the status reaches a terminal state (`COMPLETED` or `FAILED`)
7. WHEN the inspection reaches a terminal status, THE MCP_Server SHALL return the full inspection results to the Agent
8. IF the max_wait_seconds is exceeded before a terminal status is reached, THEN THE MCP_Server SHALL return the last known status and a message indicating the timeout was reached

### Requirement 11: Download Exported Package Tool

**User Story:** As a developer, I want to download an exported package .zip file, so that I can inspect it locally or deploy it to another environment.

#### Acceptance Criteria

1. THE MCP_Server SHALL expose a `download_exported_package` MCP_Tool that accepts a deployment UUID as a required parameter and a `save_directory` optional parameter (defaults to the current working directory)
2. WHEN the `download_exported_package` MCP_Tool is invoked, THE MCP_Server SHALL first call `GET /deployments/<uuid>` to retrieve the export results and obtain the `packageZip` download URL
3. WHEN the packageZip URL is available, THE MCP_Server SHALL download the .zip file and save it to the specified directory
4. WHEN the download completes, THE MCP_Server SHALL return the local file path of the saved .zip file to the Agent
5. IF the deployment UUID does not correspond to a completed export, THEN THE MCP_Server SHALL return an error message stating that the export is not complete or the UUID is invalid

### Requirement 12: HTTP Error Handling

**User Story:** As a developer, I want clear error messages when API calls fail, so that I can quickly diagnose and resolve issues.

#### Acceptance Criteria

1. IF the Appian_API returns HTTP status 401, THEN THE MCP_Server SHALL return an error message indicating invalid or expired authentication credentials
2. IF the Appian_API returns HTTP status 403, THEN THE MCP_Server SHALL return an error message indicating insufficient permissions for the requested operation
3. IF the Appian_API returns HTTP status 404, THEN THE MCP_Server SHALL return an error message indicating the requested resource was not found
4. IF the Appian_API returns HTTP status 409, THEN THE MCP_Server SHALL return an error message indicating a concurrency limit has been reached and the Agent should retry later
5. IF the Appian_API is unreachable due to a network error, THEN THE MCP_Server SHALL return an error message indicating a connection failure with the domain name
6. IF the Appian_API returns an unexpected HTTP status code, THEN THE MCP_Server SHALL return the status code and response body to the Agent

### Requirement 13: MCP Server Transport and Distribution

**User Story:** As a developer, I want to run the MCP server using standard MCP transport, so that it integrates with AI agents using the Model Context Protocol.

#### Acceptance Criteria

1. THE MCP_Server SHALL support the `stdio` transport for communication with MCP clients
2. THE MCP_Server SHALL be distributable as a Python package installable via `uvx` or `pip`
3. THE MCP_Server SHALL declare all MCP tools with descriptive names, descriptions, and typed input schemas so that the Agent can discover available operations
