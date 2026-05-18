"""Tests for tools/deployments.py — deploy_package tool."""

import pytest

from appian_deployment_mcp.config import EnvironmentConfig
from appian_deployment_mcp.tools import deployments as deploy_module


@pytest.fixture
def default_envs():
    return {
        "default": EnvironmentConfig(
            name="default", domain="mysite.appiancloud.com", api_key="key-123"
        ),
        "staging": EnvironmentConfig(
            name="staging", domain="staging.appiancloud.com", api_key="key-456"
        ),
    }


SAMPLE_DEPLOY_RESPONSE = {
    "uuid": "deploy-uuid-001",
    "url": "https://mysite.appiancloud.com/suite/deployment-management/v2/deployments/deploy-uuid-001",
    "status": "IN_PROGRESS",
}


class TestDeployPackage:
    """Tests for the deploy_package tool function."""

    @pytest.mark.asyncio
    async def test_successful_deploy_with_package(
        self, monkeypatch, default_envs, tmp_path
    ):
        """Successful POST with a package file returns UUID, URL, and status."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        pkg_file = tmp_path / "app.zip"
        pkg_file.write_bytes(b"PK\x03\x04fake-zip-content")

        captured = {}

        async def fake_post_multipart(self, path, json_part, files, headers=None):
            captured["path"] = path
            captured["json_part"] = json_part
            captured["file_keys"] = list(files.keys())
            captured["headers"] = headers
            return SAMPLE_DEPLOY_RESPONSE

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.deployments.AppianClient.post_multipart",
            fake_post_multipart,
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.deployments.AppianClient.close", fake_close
        )

        result = await deploy_module.deploy_package(
            name="My Deploy", package_file_path=str(pkg_file)
        )

        assert captured["path"] == "/deployments"
        assert captured["headers"] == {"Action-Type": "import"}
        assert "zipFile" in captured["file_keys"]
        assert captured["json_part"]["name"] == "My Deploy"
        assert result == SAMPLE_DEPLOY_RESPONSE

    @pytest.mark.asyncio
    async def test_error_when_no_artifacts_provided(self, monkeypatch, default_envs):
        """Returns error when no deployable artifacts are provided."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        result = await deploy_module.deploy_package(name="Empty Deploy")

        assert result["error"] is True
        assert "at least one deployable artifact" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_error_when_only_data_source_without_scripts(
        self, monkeypatch, default_envs
    ):
        """data_source alone (without database_scripts) is not a valid artifact."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        result = await deploy_module.deploy_package(
            name="DS Only", data_source="my-ds"
        )

        assert result["error"] is True
        assert "at least one deployable artifact" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_error_when_only_database_scripts_without_data_source(
        self, monkeypatch, default_envs
    ):
        """database_scripts alone (without data_source) is not a valid artifact."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        result = await deploy_module.deploy_package(
            name="Scripts Only",
            database_scripts=[{"fileName": "script.sql", "orderId": "1"}],
        )

        assert result["error"] is True
        assert "at least one deployable artifact" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_data_source_with_scripts_is_valid_artifact(
        self, monkeypatch, default_envs
    ):
        """data_source + database_scripts together is a valid deployable artifact."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        captured = {}

        async def fake_post_multipart(self, path, json_part, files, headers=None):
            captured["json_part"] = json_part
            return SAMPLE_DEPLOY_RESPONSE

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.deployments.AppianClient.post_multipart",
            fake_post_multipart,
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.deployments.AppianClient.close", fake_close
        )

        result = await deploy_module.deploy_package(
            name="DB Deploy",
            data_source="my-ds",
            database_scripts=[{"fileName": "script.sql", "orderId": "1"}],
        )

        assert result == SAMPLE_DEPLOY_RESPONSE
        assert captured["json_part"]["dataSource"] == "my-ds"
        assert captured["json_part"]["databaseScripts"] == [
            {"fileName": "script.sql", "orderId": "1"}
        ]

    @pytest.mark.asyncio
    async def test_error_when_package_file_missing(self, monkeypatch, default_envs):
        """Returns error when the package file does not exist."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        result = await deploy_module.deploy_package(
            name="Bad Path", package_file_path="/nonexistent/app.zip"
        )

        assert result["error"] is True
        assert "/nonexistent/app.zip" in result["message"]

    @pytest.mark.asyncio
    async def test_error_when_customization_file_missing(
        self, monkeypatch, default_envs, tmp_path
    ):
        """Returns error when the customization file does not exist."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        pkg_file = tmp_path / "app.zip"
        pkg_file.write_bytes(b"PK\x03\x04fake-zip")

        result = await deploy_module.deploy_package(
            name="Bad ICF",
            package_file_path=str(pkg_file),
            customization_file_path="/nonexistent/custom.properties",
        )

        assert result["error"] is True
        assert "/nonexistent/custom.properties" in result["message"]

    @pytest.mark.asyncio
    async def test_error_when_plugins_file_missing(
        self, monkeypatch, default_envs, tmp_path
    ):
        """Returns error when the plugins file does not exist."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        result = await deploy_module.deploy_package(
            name="Bad Plugins", plugins_file_path="/nonexistent/plugins.zip"
        )

        assert result["error"] is True
        assert "/nonexistent/plugins.zip" in result["message"]

    @pytest.mark.asyncio
    async def test_error_when_admin_console_settings_file_missing(
        self, monkeypatch, default_envs
    ):
        """Returns error when the admin console settings file does not exist."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        result = await deploy_module.deploy_package(
            name="Bad ACS",
            admin_console_settings_file_path="/nonexistent/admin.zip",
        )

        assert result["error"] is True
        assert "/nonexistent/admin.zip" in result["message"]


    @pytest.mark.asyncio
    async def test_includes_all_file_parts(
        self, monkeypatch, default_envs, tmp_path
    ):
        """All file parts are included when all file paths are provided."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        pkg_file = tmp_path / "app.zip"
        pkg_file.write_bytes(b"PK\x03\x04fake-zip")
        icf_file = tmp_path / "custom.properties"
        icf_file.write_text("key=value")
        acs_file = tmp_path / "admin.zip"
        acs_file.write_bytes(b"PK\x03\x04admin")
        plug_file = tmp_path / "plugins.zip"
        plug_file.write_bytes(b"PK\x03\x04plugins")

        captured = {}

        async def fake_post_multipart(self, path, json_part, files, headers=None):
            captured["file_keys"] = list(files.keys())
            return SAMPLE_DEPLOY_RESPONSE

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.deployments.AppianClient.post_multipart",
            fake_post_multipart,
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.deployments.AppianClient.close", fake_close
        )

        result = await deploy_module.deploy_package(
            name="Full Deploy",
            package_file_path=str(pkg_file),
            customization_file_path=str(icf_file),
            admin_console_settings_file_path=str(acs_file),
            plugins_file_path=str(plug_file),
        )

        assert "zipFile" in captured["file_keys"]
        assert "ICF" in captured["file_keys"]
        assert "adminConsoleSettings" in captured["file_keys"]
        assert "plugins" in captured["file_keys"]
        assert result == SAMPLE_DEPLOY_RESPONSE

    @pytest.mark.asyncio
    async def test_json_part_includes_description(
        self, monkeypatch, default_envs, tmp_path
    ):
        """Description is included in the JSON metadata when provided."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        pkg_file = tmp_path / "app.zip"
        pkg_file.write_bytes(b"PK\x03\x04fake-zip")

        captured = {}

        async def fake_post_multipart(self, path, json_part, files, headers=None):
            captured["json_part"] = json_part
            return SAMPLE_DEPLOY_RESPONSE

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.deployments.AppianClient.post_multipart",
            fake_post_multipart,
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.deployments.AppianClient.close", fake_close
        )

        await deploy_module.deploy_package(
            name="Described Deploy",
            package_file_path=str(pkg_file),
            description="A test deployment",
        )

        assert captured["json_part"]["name"] == "Described Deploy"
        assert captured["json_part"]["description"] == "A test deployment"

    @pytest.mark.asyncio
    async def test_uses_specified_environment(
        self, monkeypatch, default_envs, tmp_path
    ):
        """When environment is provided, the tool resolves that environment."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        pkg_file = tmp_path / "app.zip"
        pkg_file.write_bytes(b"PK\x03\x04fake-zip")

        captured_config = {}

        def fake_init(self, config):
            captured_config["name"] = config.name
            captured_config["domain"] = config.domain

        async def fake_post_multipart(self, path, json_part, files, headers=None):
            return SAMPLE_DEPLOY_RESPONSE

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.deployments.AppianClient.__init__", fake_init
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.deployments.AppianClient.post_multipart",
            fake_post_multipart,
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.deployments.AppianClient.close", fake_close
        )

        await deploy_module.deploy_package(
            name="Staging Deploy",
            package_file_path=str(pkg_file),
            environment="staging",
        )

        assert captured_config["name"] == "staging"
        assert captured_config["domain"] == "staging.appiancloud.com"

    @pytest.mark.asyncio
    async def test_client_closed_on_success(
        self, monkeypatch, default_envs, tmp_path
    ):
        """The client is closed after a successful call."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        pkg_file = tmp_path / "app.zip"
        pkg_file.write_bytes(b"PK\x03\x04fake-zip")

        closed = {"called": False}

        async def fake_post_multipart(self, path, json_part, files, headers=None):
            return SAMPLE_DEPLOY_RESPONSE

        async def fake_close(self):
            closed["called"] = True

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.deployments.AppianClient.post_multipart",
            fake_post_multipart,
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.deployments.AppianClient.close", fake_close
        )

        await deploy_module.deploy_package(
            name="Close Test", package_file_path=str(pkg_file)
        )
        assert closed["called"] is True

    @pytest.mark.asyncio
    async def test_client_closed_on_error(
        self, monkeypatch, default_envs, tmp_path
    ):
        """The client is closed even when the POST raises an exception."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        pkg_file = tmp_path / "app.zip"
        pkg_file.write_bytes(b"PK\x03\x04fake-zip")

        closed = {"called": False}

        async def fake_post_multipart(self, path, json_part, files, headers=None):
            raise RuntimeError("boom")

        async def fake_close(self):
            closed["called"] = True

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.deployments.AppianClient.post_multipart",
            fake_post_multipart,
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.deployments.AppianClient.close", fake_close
        )

        with pytest.raises(RuntimeError, match="boom"):
            await deploy_module.deploy_package(
                name="Error Test", package_file_path=str(pkg_file)
            )

        assert closed["called"] is True

    @pytest.mark.asyncio
    async def test_admin_console_settings_only_is_valid_artifact(
        self, monkeypatch, default_envs, tmp_path
    ):
        """admin_console_settings_file_path alone is a valid deployable artifact."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        acs_file = tmp_path / "admin.zip"
        acs_file.write_bytes(b"PK\x03\x04admin")

        captured = {}

        async def fake_post_multipart(self, path, json_part, files, headers=None):
            captured["file_keys"] = list(files.keys())
            return SAMPLE_DEPLOY_RESPONSE

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.deployments.AppianClient.post_multipart",
            fake_post_multipart,
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.deployments.AppianClient.close", fake_close
        )

        result = await deploy_module.deploy_package(
            name="ACS Deploy",
            admin_console_settings_file_path=str(acs_file),
        )

        assert "adminConsoleSettings" in captured["file_keys"]
        assert result == SAMPLE_DEPLOY_RESPONSE

    @pytest.mark.asyncio
    async def test_plugins_only_is_valid_artifact(
        self, monkeypatch, default_envs, tmp_path
    ):
        """plugins_file_path alone is a valid deployable artifact."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        plug_file = tmp_path / "plugins.zip"
        plug_file.write_bytes(b"PK\x03\x04plugins")

        captured = {}

        async def fake_post_multipart(self, path, json_part, files, headers=None):
            captured["file_keys"] = list(files.keys())
            return SAMPLE_DEPLOY_RESPONSE

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.deployments.AppianClient.post_multipart",
            fake_post_multipart,
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.deployments.AppianClient.close", fake_close
        )

        result = await deploy_module.deploy_package(
            name="Plugin Deploy",
            plugins_file_path=str(plug_file),
        )

        assert "plugins" in captured["file_keys"]
        assert result == SAMPLE_DEPLOY_RESPONSE


# --- Sample responses for get_deployment_results ---

SAMPLE_IMPORT_COMPLETED_RESPONSE = {
    "status": "COMPLETED",
    "summary": {
        "objects": {"total": 10, "imported": 8, "failed": 1, "skipped": 1},
        "plugins": {"total": 2, "imported": 2, "skipped": 0},
        "adminConsoleSettings": {"total": 1, "imported": 1, "failed": 0, "skipped": 0},
        "databaseScripts": 3,
    },
    "deploymentLogUrl": "https://mysite.appiancloud.com/suite/deployment-management/v2/deployments/deploy-uuid-001/log",
}

SAMPLE_EXPORT_COMPLETED_RESPONSE = {
    "status": "COMPLETED",
    "packageZip": "https://mysite.appiancloud.com/suite/deployment-management/v2/deployments/deploy-uuid-002/package.zip",
    "dataSource": "my-data-source",
    "databaseScripts": [
        {"fileName": "script1.sql", "orderId": "1", "url": "https://example.com/script1.sql"},
    ],
    "pluginsZip": "https://example.com/plugins.zip",
    "customizationFile": "https://example.com/custom.properties",
    "customizationFileTemplate": "https://example.com/custom-template.properties",
    "deploymentLogUrl": "https://mysite.appiancloud.com/suite/deployment-management/v2/deployments/deploy-uuid-002/log",
}

SAMPLE_IN_PROGRESS_RESPONSE = {
    "status": "IN_PROGRESS",
}


class TestGetDeploymentResults:
    """Tests for the get_deployment_results tool function."""

    @pytest.mark.asyncio
    async def test_returns_import_results(self, monkeypatch, default_envs):
        """Returns full import results for a completed import deployment."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        captured = {}

        async def fake_get(self, path):
            captured["path"] = path
            return SAMPLE_IMPORT_COMPLETED_RESPONSE

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.deployments.AppianClient.get", fake_get
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.deployments.AppianClient.close", fake_close
        )

        result = await deploy_module.get_deployment_results(
            deployment_uuid="deploy-uuid-001"
        )

        assert captured["path"] == "/deployments/deploy-uuid-001"
        assert result == SAMPLE_IMPORT_COMPLETED_RESPONSE
        assert result["status"] == "COMPLETED"
        assert result["summary"]["objects"]["total"] == 10

    @pytest.mark.asyncio
    async def test_returns_export_results(self, monkeypatch, default_envs):
        """Returns full export results for a completed export deployment."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        async def fake_get(self, path):
            return SAMPLE_EXPORT_COMPLETED_RESPONSE

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.deployments.AppianClient.get", fake_get
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.deployments.AppianClient.close", fake_close
        )

        result = await deploy_module.get_deployment_results(
            deployment_uuid="deploy-uuid-002"
        )

        assert result == SAMPLE_EXPORT_COMPLETED_RESPONSE
        assert result["status"] == "COMPLETED"
        assert "packageZip" in result

    @pytest.mark.asyncio
    async def test_returns_in_progress_status(self, monkeypatch, default_envs):
        """Returns status when deployment is still in progress."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        async def fake_get(self, path):
            return SAMPLE_IN_PROGRESS_RESPONSE

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.deployments.AppianClient.get", fake_get
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.deployments.AppianClient.close", fake_close
        )

        result = await deploy_module.get_deployment_results(
            deployment_uuid="deploy-uuid-003"
        )

        assert result["status"] == "IN_PROGRESS"

    @pytest.mark.asyncio
    async def test_returns_api_error(self, monkeypatch, default_envs):
        """Returns error dict when the API returns an error."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        error_response = {
            "error": True,
            "status_code": 404,
            "message": "The requested resource was not found. Verify the UUID is correct.",
        }

        async def fake_get(self, path):
            return error_response

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.deployments.AppianClient.get", fake_get
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.deployments.AppianClient.close", fake_close
        )

        result = await deploy_module.get_deployment_results(
            deployment_uuid="nonexistent-uuid"
        )

        assert result["error"] is True
        assert result["status_code"] == 404

    @pytest.mark.asyncio
    async def test_uses_specified_environment(self, monkeypatch, default_envs):
        """Resolves the specified environment for the API call."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        captured_config = {}

        def fake_init(self, config):
            captured_config["name"] = config.name
            captured_config["domain"] = config.domain

        async def fake_get(self, path):
            return SAMPLE_IN_PROGRESS_RESPONSE

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.deployments.AppianClient.__init__", fake_init
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.deployments.AppianClient.get", fake_get
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.deployments.AppianClient.close", fake_close
        )

        await deploy_module.get_deployment_results(
            deployment_uuid="deploy-uuid-001", environment="staging"
        )

        assert captured_config["name"] == "staging"
        assert captured_config["domain"] == "staging.appiancloud.com"

    @pytest.mark.asyncio
    async def test_client_closed_on_success(self, monkeypatch, default_envs):
        """The client is closed after a successful call."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        closed = {"called": False}

        async def fake_get(self, path):
            return SAMPLE_IMPORT_COMPLETED_RESPONSE

        async def fake_close(self):
            closed["called"] = True

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.deployments.AppianClient.get", fake_get
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.deployments.AppianClient.close", fake_close
        )

        await deploy_module.get_deployment_results(deployment_uuid="deploy-uuid-001")
        assert closed["called"] is True

    @pytest.mark.asyncio
    async def test_client_closed_on_error(self, monkeypatch, default_envs):
        """The client is closed even when the GET raises an exception."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        closed = {"called": False}

        async def fake_get(self, path):
            raise RuntimeError("boom")

        async def fake_close(self):
            closed["called"] = True

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.deployments.AppianClient.get", fake_get
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.deployments.AppianClient.close", fake_close
        )

        with pytest.raises(RuntimeError, match="boom"):
            await deploy_module.get_deployment_results(
                deployment_uuid="deploy-uuid-001"
            )

        assert closed["called"] is True


# --- Tests for get_deployment_log ---

SAMPLE_LOG_TEXT = (
    "[2024-01-15 10:00:00] Starting deployment...\n"
    "[2024-01-15 10:00:05] Importing objects...\n"
    "[2024-01-15 10:00:30] Deployment completed successfully."
)


class TestGetDeploymentLog:
    """Tests for the get_deployment_log tool function."""

    @pytest.mark.asyncio
    async def test_returns_plain_text_log(self, monkeypatch, default_envs):
        """Returns plain text log content for a valid deployment UUID."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        captured = {}

        async def fake_get_text(self, path):
            captured["path"] = path
            return SAMPLE_LOG_TEXT

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.deployments.AppianClient.get_text",
            fake_get_text,
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.deployments.AppianClient.close", fake_close
        )

        result = await deploy_module.get_deployment_log(
            deployment_uuid="deploy-uuid-001"
        )

        assert captured["path"] == "/deployments/deploy-uuid-001/log"
        assert result == SAMPLE_LOG_TEXT
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_returns_api_error(self, monkeypatch, default_envs):
        """Returns error dict when the API returns an error."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        error_response = {
            "error": True,
            "status_code": 404,
            "message": "The requested resource was not found. Verify the UUID is correct.",
        }

        async def fake_get_text(self, path):
            return error_response

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.deployments.AppianClient.get_text",
            fake_get_text,
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.deployments.AppianClient.close", fake_close
        )

        result = await deploy_module.get_deployment_log(
            deployment_uuid="nonexistent-uuid"
        )

        assert result["error"] is True
        assert result["status_code"] == 404

    @pytest.mark.asyncio
    async def test_uses_specified_environment(self, monkeypatch, default_envs):
        """Resolves the specified environment for the API call."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        captured_config = {}

        def fake_init(self, config):
            captured_config["name"] = config.name
            captured_config["domain"] = config.domain

        async def fake_get_text(self, path):
            return SAMPLE_LOG_TEXT

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.deployments.AppianClient.__init__", fake_init
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.deployments.AppianClient.get_text",
            fake_get_text,
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.deployments.AppianClient.close", fake_close
        )

        await deploy_module.get_deployment_log(
            deployment_uuid="deploy-uuid-001", environment="staging"
        )

        assert captured_config["name"] == "staging"
        assert captured_config["domain"] == "staging.appiancloud.com"

    @pytest.mark.asyncio
    async def test_client_closed_on_success(self, monkeypatch, default_envs):
        """The client is closed after a successful call."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        closed = {"called": False}

        async def fake_get_text(self, path):
            return SAMPLE_LOG_TEXT

        async def fake_close(self):
            closed["called"] = True

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.deployments.AppianClient.get_text",
            fake_get_text,
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.deployments.AppianClient.close", fake_close
        )

        await deploy_module.get_deployment_log(deployment_uuid="deploy-uuid-001")
        assert closed["called"] is True

    @pytest.mark.asyncio
    async def test_client_closed_on_error(self, monkeypatch, default_envs):
        """The client is closed even when get_text raises an exception."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        closed = {"called": False}

        async def fake_get_text(self, path):
            raise RuntimeError("boom")

        async def fake_close(self):
            closed["called"] = True

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.deployments.AppianClient.get_text",
            fake_get_text,
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.deployments.AppianClient.close", fake_close
        )

        with pytest.raises(RuntimeError, match="boom"):
            await deploy_module.get_deployment_log(deployment_uuid="deploy-uuid-001")

        assert closed["called"] is True
