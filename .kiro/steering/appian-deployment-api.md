---
inclusion: manual
---

# Appian Deployment REST API Reference (v2)

Source: [Appian Docs 26.3](https://docs.appian.com/suite/help/26.3/Deployment_Rest_API.html)

## Overview

Base URL: `https://<domain>/suite/deployment-management/v2`

Authentication: API key (`appian-api-key` header) or OAuth 2.0 Bearer token linked to a service account.

Mutual TLS (mTLS) supported on port 8443.

## Recommended Workflow

1. Get package UUID via Application Package Details
2. Export package (`POST /deployments`, `Action-Type: export`)
3. Check export status (`GET /deployments/<uuid>`)
4. Inspect package (`POST /inspections`)
5. Get inspection results (`GET /inspections/<uuid>`)
6. Deploy/import package (`POST /deployments`, `Action-Type: import`)
7. Get deployment results (`GET /deployments/<uuid>`)
8. Get deployment log (`GET /deployments/<uuid>/log`)

---

## 1. Application Package Details

- **Endpoint:** `GET /applications/<UUID>/packages`
- **v2 only**
- **Note:** Not controlled by Admin Console infrastructure toggles — always accessible if service account has app access.

### Response Attributes

| Attribute | Description |
|---|---|
| `totalPackageCount` | Total packages in the application (max 100) |
| `packages[].uuid` | Package UUID (use for export) |
| `packages[].name` | Package name |
| `packages[].description` | Package description |
| `packages[].objectCount` | Number of design objects |
| `packages[].databaseScriptCount` | Number of DB scripts |
| `packages[].pluginCount` | Number of plug-ins |
| `packages[].hasCustomizationFile` | Boolean |
| `packages[].ticketLink` | URL for the ticket |
| `packages[].createdTimestamp` | Creation timestamp |
| `packages[].lastModifiedTimestamp` | Last modified timestamp |
| `packages[].datasourceUuid` | Data source name or UUID |

### Example

```bash
curl --location --request \
GET https://mysite.appiancloud.com/suite/deployment-management/v2/applications/<UUID>/packages \
--header 'Authorization: Bearer <access_token>'
```

---

## 2. Export Package

- **Endpoint:** `POST /deployments`
- **Header:** `Action-Type: export`
- **v2 only**
- **Concurrency limit:** 50 concurrent exports

### JSON Parameters

| Key | Required | Description |
|---|---|---|
| `uuids` | Yes | Array of UUIDs. Single UUID for packages, multiple for applications. |
| `exportType` | Yes | `"package"` or `"application"` |
| `name` | No | Deployment name |
| `description` | No | Deployment description |

### Example (package)

```json
{
  "exportType": "package",
  "uuids": ["d243b14c-3ba5-41c3-9f51-76da51beb8f5"],
  "name": "CR-176543 Add reports dashboard",
  "description": "Updates the executive summary view."
}
```

### Response

| Attribute | Description |
|---|---|
| `uuid` | Deployment UUID |
| `url` | URL to retrieve deployment details |
| `status` | `IN_PROGRESS`, `COMPLETED`, `COMPLETED_WITH_ERRORS`, `FAILED` |

---

## 3. Inspect Package

- **Endpoint:** `POST /inspections`
- **Content-Type:** `multipart/form-data`
- **Same behavior in v1 and v2**

### JSON Parameters

| Key | Description |
|---|---|
| `adminConsoleSettingsFileName` | Admin Console settings .zip filename |
| `packageFileName` | Deployment package .zip filename |
| `customizationFileName` | Import customization .properties filename |

### Example

```bash
curl --location --request \
POST 'https://mysite.appiancloud.com/suite/deployment-management/v2/inspections' \
--header 'Authorization: Bearer <access_token>' \
--form 'json="{
  \"packageFileName\": \"MyPackage.zip\",
  \"customizationFileName\": \"MyPackage.properties\"
}"' \
--form 'zipFile=@"MyPackage.zip"' \
--form 'ICF=@"MyPackage.properties"'
```

### Response

| Attribute | Description |
|---|---|
| `uuid` | Inspection UUID |
| `url` | URL to retrieve inspection details |

---

## 4. Get Inspection Results

- **Endpoint:** `GET /inspections/<uuid>`
- **Same behavior in v1 and v2**

### Response Attributes

| Attribute | Description |
|---|---|
| `status` | `IN_PROGRESS`, `COMPLETED`, or `FAILED` |
| `summary.objectsExpected.total` | Total objects in package |
| `summary.objectsExpected.imported` | Expected to succeed |
| `summary.objectsExpected.failed` | Expected to fail |
| `summary.objectsExpected.skipped` | No changes, will be skipped |
| `summary.problems.totalErrors` | Total errors |
| `summary.problems.totalWarnings` | Total warnings |
| `summary.problems.errors[]` | Array: `errorMessage`, `objectName`, `objectUuid` |
| `summary.problems.warnings[]` | Array: `warningMessage`, `objectName`, `objectUuid` |

---

## 5. Deploy (Import) Package

- **Endpoint:** `POST /deployments`
- **Header:** `Action-Type: import` (default if omitted)
- **Content-Type:** `multipart/form-data`
- **Concurrency limit:** 20 concurrent deployments

### JSON Parameters

| Key | Required | Description |
|---|---|---|
| `name` | Yes | Deployment name |
| `description` | No | Deployment description |
| `packageFileName` | No* | Package .zip filename |
| `customizationFileName` | No* | ICF .properties filename |
| `adminConsoleSettingsFileName` | No* | Admin Console settings .zip |
| `pluginsFileName` | No* | Plug-ins .zip filename |
| `dataSource` | No* | Data source name or UUID |
| `databaseScripts` | No* | Array of `{fileName, orderId}` |

*At least one of packageFileName, adminConsoleSettingsFileName, pluginsFileName, or dataSource+databaseScripts required.

### Example

```json
{
  "name": "Release 1.0",
  "description": "Base functionality",
  "packageFileName": "MyPackage.zip",
  "customizationFileName": "MyPackage.properties",
  "dataSource": "jdbc/AppianAnywhere",
  "databaseScripts": [
    {"fileName": "Create Tables.sql", "orderId": "1"},
    {"fileName": "Update Data.sql", "orderId": "2"}
  ]
}
```

### Response

| Attribute | Description |
|---|---|
| `uuid` | Deployment UUID |
| `url` | URL to retrieve deployment details |
| `status` | `IN_PROGRESS`, `COMPLETED`, `COMPLETED_WITH_ERRORS`, `FAILED`, `PENDING_REVIEW`, `REJECTED` |

---

## 6. Get Deployment Results

- **Endpoint:** `GET /deployments/<uuid>`

### Import Response Attributes

| Attribute | Description |
|---|---|
| `status` | `IN_PROGRESS`, `COMPLETED`, `COMPLETED_WITH_IMPORT_ERRORS`, `COMPLETED_WITH_PUBLISH_ERRORS`, `FAILED`, `PENDING_REVIEW`, `REJECTED` |
| `summary.objects.total/imported/failed/skipped` | Object deployment counts |
| `summary.plugins.total/imported/skipped` | Plugin deployment counts |
| `summary.adminConsoleSettings.total/imported/failed/skipped` | Admin Console settings counts |
| `summary.databaseScripts` | Total DB scripts count |
| `deploymentLogUrl` | URL for the deployment log |

### Export Response Attributes

| Attribute | Description |
|---|---|
| `status` | `IN_PROGRESS`, `COMPLETED`, `COMPLETED_WITH_EXPORT_ERRORS`, `FAILED` |
| `packageZip` | URL for exported .zip |
| `dataSource` | Data source name/UUID |
| `databaseScripts[]` | Array: `fileName`, `orderId`, `url` |
| `pluginsZip` | URL for exported plug-ins |
| `customizationFile` | URL for exported ICF |
| `customizationFileTemplate` | URL for ICF template |
| `deploymentLogUrl` | URL for deployment log |

---

## 7. Get Deployment Log

- **Endpoint:** `GET /deployments/<uuid>/log`
- **Same behavior in v1 and v2**
- **Response:** Plain text deployment log
