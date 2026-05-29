"""Tests for tools/polling.py — poll_deployment_status and poll_inspection_status tools."""

import pytest

from appian_deployment_mcp.config import EnvironmentConfig
from appian_deployment_mcp.tools import polling as polling_module
from appian_deployment_mcp.tools.polling import (
    DEPLOYMENT_TERMINAL_STATUSES,
    INSPECTION_TERMINAL_STATUSES,
)


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


class TestPollDeploymentStatus:
    """Tests for the poll_deployment_status tool function."""

    @pytest.mark.asyncio
    async def test_returns_immediately_on_terminal_status(
        self, monkeypatch, default_envs
    ):
        """Returns completed=True when the first response has a terminal status."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        async def fake_get(self, path):
            return {"status": "COMPLETED", "summary": {"objects": {"total": 5}}}

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.polling.AppianClient.get", fake_get
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.polling.AppianClient.close", fake_close
        )

        result = await polling_module.poll_deployment_status(
            deployment_uuid="deploy-uuid-001"
        )

        assert result["completed"] is True
        assert result["timed_out"] is False
        assert result["result"]["status"] == "COMPLETED"
        assert isinstance(result["elapsed_seconds"], float)

    @pytest.mark.asyncio
    async def test_polls_until_terminal_status(self, monkeypatch, default_envs):
        """Polls multiple times until a terminal status is reached."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        responses = [
            {"status": "IN_PROGRESS"},
            {"status": "IN_PROGRESS"},
            {"status": "COMPLETED_WITH_ERRORS", "summary": {}},
        ]
        call_count = {"n": 0}

        async def fake_get(self, path):
            idx = call_count["n"]
            call_count["n"] += 1
            return responses[idx]

        async def fake_close(self):
            pass

        async def fake_sleep(seconds):
            pass  # Don't actually sleep in tests

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.polling.AppianClient.get", fake_get
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.polling.AppianClient.close", fake_close
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.polling.asyncio.sleep", fake_sleep
        )

        result = await polling_module.poll_deployment_status(
            deployment_uuid="deploy-uuid-001",
            poll_interval_seconds=1,
        )

        assert result["completed"] is True
        assert result["timed_out"] is False
        assert result["result"]["status"] == "COMPLETED_WITH_ERRORS"
        assert call_count["n"] == 3

    @pytest.mark.asyncio
    async def test_times_out_when_never_terminal(self, monkeypatch, default_envs):
        """Returns timed_out=True when max_wait_seconds is exceeded."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        async def fake_get(self, path):
            return {"status": "IN_PROGRESS"}

        async def fake_close(self):
            pass

        # Simulate time advancing past max_wait
        time_values = [0.0, 0.0, 301.0]  # start, first check, after sleep
        time_idx = {"i": 0}

        def fake_monotonic():
            idx = time_idx["i"]
            time_idx["i"] += 1
            if idx < len(time_values):
                return time_values[idx]
            return time_values[-1]

        async def fake_sleep(seconds):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.polling.AppianClient.get", fake_get
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.polling.AppianClient.close", fake_close
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.polling.time.monotonic", fake_monotonic
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.polling.asyncio.sleep", fake_sleep
        )

        result = await polling_module.poll_deployment_status(
            deployment_uuid="deploy-uuid-001",
            poll_interval_seconds=1,
            max_wait_seconds=300,
        )

        assert result["completed"] is False
        assert result["timed_out"] is True
        assert result["result"]["status"] == "IN_PROGRESS"

    @pytest.mark.asyncio
    async def test_returns_on_api_error(self, monkeypatch, default_envs):
        """Returns completed=True with error result when API returns an error."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        async def fake_get(self, path):
            return {"error": True, "status_code": 404, "message": "Not found"}

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.polling.AppianClient.get", fake_get
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.polling.AppianClient.close", fake_close
        )

        result = await polling_module.poll_deployment_status(
            deployment_uuid="bad-uuid"
        )

        assert result["completed"] is True
        assert result["timed_out"] is False
        assert result["result"]["error"] is True

    @pytest.mark.asyncio
    async def test_all_deployment_terminal_statuses(self, monkeypatch, default_envs):
        """Each deployment terminal status causes immediate return."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.polling.AppianClient.close", fake_close
        )

        for status in DEPLOYMENT_TERMINAL_STATUSES:

            async def make_fake_get(s):
                async def fake_get(self, path):
                    return {"status": s}
                return fake_get

            monkeypatch.setattr(
                "appian_deployment_mcp.tools.polling.AppianClient.get",
                await make_fake_get(status),
            )

            result = await polling_module.poll_deployment_status(
                deployment_uuid="deploy-uuid-001"
            )

            assert result["completed"] is True, f"Expected completed for status {status}"
            assert result["result"]["status"] == status

    @pytest.mark.asyncio
    async def test_uses_specified_environment(self, monkeypatch, default_envs):
        """Resolves the specified environment for the API call."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        captured_config = {}

        def fake_init(self, config):
            captured_config["name"] = config.name

        async def fake_get(self, path):
            return {"status": "COMPLETED"}

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.polling.AppianClient.__init__", fake_init
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.polling.AppianClient.get", fake_get
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.polling.AppianClient.close", fake_close
        )

        await polling_module.poll_deployment_status(
            deployment_uuid="deploy-uuid-001", environment="staging"
        )

        assert captured_config["name"] == "staging"

    @pytest.mark.asyncio
    async def test_client_closed_on_success(self, monkeypatch, default_envs):
        """The client is closed after a successful poll."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        closed = {"called": False}

        async def fake_get(self, path):
            return {"status": "COMPLETED"}

        async def fake_close(self):
            closed["called"] = True

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.polling.AppianClient.get", fake_get
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.polling.AppianClient.close", fake_close
        )

        await polling_module.poll_deployment_status(deployment_uuid="deploy-uuid-001")
        assert closed["called"] is True

    @pytest.mark.asyncio
    async def test_client_closed_on_error(self, monkeypatch, default_envs):
        """The client is closed even when GET raises an exception."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        closed = {"called": False}

        async def fake_get(self, path):
            raise RuntimeError("boom")

        async def fake_close(self):
            closed["called"] = True

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.polling.AppianClient.get", fake_get
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.polling.AppianClient.close", fake_close
        )

        with pytest.raises(RuntimeError, match="boom"):
            await polling_module.poll_deployment_status(
                deployment_uuid="deploy-uuid-001"
            )

        assert closed["called"] is True

    @pytest.mark.asyncio
    async def test_correct_api_path(self, monkeypatch, default_envs):
        """Calls the correct API path with the deployment UUID."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        captured = {}

        async def fake_get(self, path):
            captured["path"] = path
            return {"status": "COMPLETED"}

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.polling.AppianClient.get", fake_get
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.polling.AppianClient.close", fake_close
        )

        await polling_module.poll_deployment_status(
            deployment_uuid="my-deploy-uuid"
        )

        assert captured["path"] == "/deployments/my-deploy-uuid"


class TestPollInspectionStatus:
    """Tests for the poll_inspection_status tool function."""

    @pytest.mark.asyncio
    async def test_returns_immediately_on_terminal_status(
        self, monkeypatch, default_envs
    ):
        """Returns completed=True when the first response has a terminal status."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        async def fake_get(self, path):
            return {"status": "COMPLETED", "summary": {}}

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.polling.AppianClient.get", fake_get
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.polling.AppianClient.close", fake_close
        )

        result = await polling_module.poll_inspection_status(
            inspection_uuid="insp-uuid-001"
        )

        assert result["completed"] is True
        assert result["timed_out"] is False
        assert result["result"]["status"] == "COMPLETED"

    @pytest.mark.asyncio
    async def test_polls_until_terminal_status(self, monkeypatch, default_envs):
        """Polls multiple times until a terminal status is reached."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        responses = [
            {"status": "IN_PROGRESS"},
            {"status": "FAILED"},
        ]
        call_count = {"n": 0}

        async def fake_get(self, path):
            idx = call_count["n"]
            call_count["n"] += 1
            return responses[idx]

        async def fake_close(self):
            pass

        async def fake_sleep(seconds):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.polling.AppianClient.get", fake_get
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.polling.AppianClient.close", fake_close
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.polling.asyncio.sleep", fake_sleep
        )

        result = await polling_module.poll_inspection_status(
            inspection_uuid="insp-uuid-001",
            poll_interval_seconds=1,
        )

        assert result["completed"] is True
        assert result["result"]["status"] == "FAILED"
        assert call_count["n"] == 2

    @pytest.mark.asyncio
    async def test_times_out_when_never_terminal(self, monkeypatch, default_envs):
        """Returns timed_out=True when max_wait_seconds is exceeded."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        async def fake_get(self, path):
            return {"status": "IN_PROGRESS"}

        async def fake_close(self):
            pass

        time_values = [0.0, 0.0, 301.0]
        time_idx = {"i": 0}

        def fake_monotonic():
            idx = time_idx["i"]
            time_idx["i"] += 1
            if idx < len(time_values):
                return time_values[idx]
            return time_values[-1]

        async def fake_sleep(seconds):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.polling.AppianClient.get", fake_get
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.polling.AppianClient.close", fake_close
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.polling.time.monotonic", fake_monotonic
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.polling.asyncio.sleep", fake_sleep
        )

        result = await polling_module.poll_inspection_status(
            inspection_uuid="insp-uuid-001",
            poll_interval_seconds=1,
            max_wait_seconds=300,
        )

        assert result["completed"] is False
        assert result["timed_out"] is True
        assert result["result"]["status"] == "IN_PROGRESS"

    @pytest.mark.asyncio
    async def test_returns_on_api_error(self, monkeypatch, default_envs):
        """Returns completed=True with error result when API returns an error."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        async def fake_get(self, path):
            return {"error": True, "status_code": 404, "message": "Not found"}

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.polling.AppianClient.get", fake_get
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.polling.AppianClient.close", fake_close
        )

        result = await polling_module.poll_inspection_status(
            inspection_uuid="bad-uuid"
        )

        assert result["completed"] is True
        assert result["timed_out"] is False
        assert result["result"]["error"] is True

    @pytest.mark.asyncio
    async def test_all_inspection_terminal_statuses(self, monkeypatch, default_envs):
        """Each inspection terminal status causes immediate return."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.polling.AppianClient.close", fake_close
        )

        for status in INSPECTION_TERMINAL_STATUSES:

            async def make_fake_get(s):
                async def fake_get(self, path):
                    return {"status": s}
                return fake_get

            monkeypatch.setattr(
                "appian_deployment_mcp.tools.polling.AppianClient.get",
                await make_fake_get(status),
            )

            result = await polling_module.poll_inspection_status(
                inspection_uuid="insp-uuid-001"
            )

            assert result["completed"] is True, f"Expected completed for status {status}"
            assert result["result"]["status"] == status

    @pytest.mark.asyncio
    async def test_uses_specified_environment(self, monkeypatch, default_envs):
        """Resolves the specified environment for the API call."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        captured_config = {}

        def fake_init(self, config):
            captured_config["name"] = config.name

        async def fake_get(self, path):
            return {"status": "COMPLETED"}

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.polling.AppianClient.__init__", fake_init
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.polling.AppianClient.get", fake_get
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.polling.AppianClient.close", fake_close
        )

        await polling_module.poll_inspection_status(
            inspection_uuid="insp-uuid-001", environment="staging"
        )

        assert captured_config["name"] == "staging"

    @pytest.mark.asyncio
    async def test_client_closed_on_success(self, monkeypatch, default_envs):
        """The client is closed after a successful poll."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        closed = {"called": False}

        async def fake_get(self, path):
            return {"status": "COMPLETED"}

        async def fake_close(self):
            closed["called"] = True

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.polling.AppianClient.get", fake_get
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.polling.AppianClient.close", fake_close
        )

        await polling_module.poll_inspection_status(inspection_uuid="insp-uuid-001")
        assert closed["called"] is True

    @pytest.mark.asyncio
    async def test_client_closed_on_error(self, monkeypatch, default_envs):
        """The client is closed even when GET raises an exception."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        closed = {"called": False}

        async def fake_get(self, path):
            raise RuntimeError("boom")

        async def fake_close(self):
            closed["called"] = True

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.polling.AppianClient.get", fake_get
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.polling.AppianClient.close", fake_close
        )

        with pytest.raises(RuntimeError, match="boom"):
            await polling_module.poll_inspection_status(
                inspection_uuid="insp-uuid-001"
            )

        assert closed["called"] is True

    @pytest.mark.asyncio
    async def test_correct_api_path(self, monkeypatch, default_envs):
        """Calls the correct API path with the inspection UUID."""
        monkeypatch.setattr("appian_deployment_mcp.server._environments", default_envs)

        captured = {}

        async def fake_get(self, path):
            captured["path"] = path
            return {"status": "COMPLETED"}

        async def fake_close(self):
            pass

        monkeypatch.setattr(
            "appian_deployment_mcp.tools.polling.AppianClient.get", fake_get
        )
        monkeypatch.setattr(
            "appian_deployment_mcp.tools.polling.AppianClient.close", fake_close
        )

        await polling_module.poll_inspection_status(
            inspection_uuid="my-insp-uuid"
        )

        assert captured["path"] == "/inspections/my-insp-uuid"


class TestTerminalStatusSets:
    """Tests for the terminal status set definitions."""

    def test_deployment_terminal_statuses_contains_expected(self):
        """DEPLOYMENT_TERMINAL_STATUSES contains all documented terminal statuses."""
        expected = {
            "COMPLETED",
            "COMPLETED_WITH_ERRORS",
            "COMPLETED_WITH_IMPORT_ERRORS",
            "COMPLETED_WITH_PUBLISH_ERRORS",
            "COMPLETED_WITH_EXPORT_ERRORS",
            "FAILED",
            "REJECTED",
        }
        assert DEPLOYMENT_TERMINAL_STATUSES == expected

    def test_pending_review_not_terminal(self):
        """PENDING_REVIEW is not a terminal status — polling should continue."""
        assert "PENDING_REVIEW" not in DEPLOYMENT_TERMINAL_STATUSES

    def test_inspection_terminal_statuses_contains_expected(self):
        """INSPECTION_TERMINAL_STATUSES contains all documented terminal statuses."""
        assert INSPECTION_TERMINAL_STATUSES == {"COMPLETED", "FAILED"}

    def test_in_progress_not_in_deployment_terminal(self):
        """IN_PROGRESS is not a terminal deployment status."""
        assert "IN_PROGRESS" not in DEPLOYMENT_TERMINAL_STATUSES

    def test_in_progress_not_in_inspection_terminal(self):
        """IN_PROGRESS is not a terminal inspection status."""
        assert "IN_PROGRESS" not in INSPECTION_TERMINAL_STATUSES
