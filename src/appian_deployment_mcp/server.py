"""MCP server entry point using FastMCP with stdio transport."""

from mcp.server.fastmcp import FastMCP

from .config import EnvironmentConfig, load_environments
from .pipeline.engine import PipelineEngine
from .pipeline.store import PipelineStore

mcp = FastMCP(
    name="appian-deployment",
    instructions="Appian Deployment REST API (v1/v2/v3) — export, inspect, deploy, and monitor Appian packages.",
)

_environments: dict[str, EnvironmentConfig] = {}
_pipeline_store: PipelineStore = PipelineStore()
_pipeline_engine: PipelineEngine | None = None


def get_environments() -> dict[str, EnvironmentConfig]:
    """Return the loaded environment configurations."""
    return _environments


def get_pipeline_store() -> PipelineStore:
    """Return the pipeline store instance."""
    return _pipeline_store


def get_pipeline_engine() -> PipelineEngine:
    """Return the pipeline engine instance."""
    global _pipeline_engine
    if _pipeline_engine is None:
        _pipeline_engine = PipelineEngine(
            environments=_environments,
            store=_pipeline_store,
        )
    return _pipeline_engine


# Import tool modules so their @mcp.tool() decorators register against this mcp instance.
# These imports MUST come after mcp and get_environments are defined to avoid circular imports.
from .tools import (  # noqa: E402, F401
    deploy_from_export,
    deployment_review,
    deployments,
    downloads,
    environments,
    exports,
    inspections,
    packages,
    pipeline_approvals,
    pipeline_definitions,
    pipeline_runs,
    polling,
)


def main():
    """Run the MCP server with stdio transport."""
    global _environments, _pipeline_store, _pipeline_engine
    _environments = load_environments()
    _pipeline_store = PipelineStore()
    _pipeline_engine = PipelineEngine(
        environments=_environments,
        store=_pipeline_store,
    )
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
