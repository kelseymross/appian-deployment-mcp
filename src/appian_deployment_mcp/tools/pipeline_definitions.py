"""MCP tools for managing pipeline definitions."""

from ..pipeline.store import PipelineStore
from ..pipeline.validation import validate_pipeline_stages
from ..server import get_environments, get_pipeline_store, mcp


@mcp.tool()
async def create_pipeline(
    name: str,
    stages: list[str],
) -> dict:
    """Create a named deployment pipeline as an ordered list of environments.

    Defines a repeatable promotion path for packages. If a pipeline with the
    same name already exists, it will be overwritten with the new stage list.

    Args:
        name: Pipeline name (1-128 characters).
        stages: Ordered list of environment names (1-20 entries, no duplicates).

    Returns:
        The created pipeline definition with name, stages, and created_at,
        or an error dict if validation fails.
    """
    # Validate name length
    if not name or len(name) > 128:
        return {
            "error": "Pipeline name must be between 1 and 128 characters."
        }

    # Validate stages list size
    if not stages or len(stages) < 1:
        return {
            "error": "stages must contain at least 1 environment name."
        }
    if len(stages) > 20:
        return {
            "error": f"stages must contain at most 20 entries, got {len(stages)}."
        }

    # Validate stages against configured environments
    environments = get_environments()
    validation_error = validate_pipeline_stages(stages, environments)
    if validation_error is not None:
        return validation_error

    # Create the definition
    store = get_pipeline_store()
    definition = store.create_definition(name, stages)

    return {
        "name": definition.name,
        "stages": definition.stages,
        "created_at": definition.created_at.isoformat(),
    }


@mcp.tool()
async def list_pipelines() -> list[dict]:
    """List all defined deployment pipelines.

    Returns:
        List of pipeline definitions, each with name, stages, and created_at.
    """
    store = get_pipeline_store()
    definitions = store.list_definitions()

    return [
        {
            "name": d.name,
            "stages": d.stages,
            "created_at": d.created_at.isoformat(),
        }
        for d in definitions
    ]


@mcp.tool()
async def get_pipeline(name: str) -> dict:
    """Get a pipeline definition by name.

    Args:
        name: The pipeline name to look up.

    Returns:
        The pipeline definition with name, stages, and created_at,
        or an error dict if not found.
    """
    store = get_pipeline_store()
    definition = store.get_definition(name)

    if definition is None:
        return {
            "error": f"No pipeline found with name '{name}'."
        }

    return {
        "name": definition.name,
        "stages": definition.stages,
        "created_at": definition.created_at.isoformat(),
    }
