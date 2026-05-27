"""Environment configuration loaded from environment variables."""

import os
import re
import tempfile
from dataclasses import dataclass


SUPPORTED_API_VERSIONS = ("v1", "v2", "v3")
DEFAULT_API_VERSION = "v2"


def get_save_directory() -> str:
    """Get the configured save directory for deployment artifacts.

    Resolution order:
    1. APPIAN_SAVE_DIRECTORY environment variable (if set)
    2. Default: system temp directory under 'appian-deployments/'

    Returns:
        An absolute path to the save directory.
    """
    configured = os.environ.get("APPIAN_SAVE_DIRECTORY")
    if configured:
        return configured
    return os.path.join(tempfile.gettempdir(), "appian-deployments")


@dataclass(frozen=True)
class EnvironmentConfig:
    """Connection parameters for a single Appian environment."""

    name: str
    domain: str
    api_key: str | None = None
    oauth_token: str | None = None
    api_version: str = DEFAULT_API_VERSION

    @property
    def base_url(self) -> str:
        return f"https://{self.domain}/suite/deployment-management/{self.api_version}"

    @property
    def auth_headers(self) -> dict[str, str]:
        if self.api_key:
            return {"appian-api-key": self.api_key}
        return {"Authorization": f"Bearer {self.oauth_token}"}


def load_environments() -> dict[str, EnvironmentConfig]:
    """Load all environments from environment variables.

    Reads ``APPIAN_DOMAIN`` + ``APPIAN_API_KEY`` / ``APPIAN_OAUTH_TOKEN`` as the
    default environment, then scans for ``APPIAN_<ENV>_DOMAIN`` patterns to
    discover additional named environments.

    Returns a dict keyed by environment name.

    Raises:
        ValueError: If ``APPIAN_DOMAIN`` is not set or no credentials are
            provided for an environment.
    """
    environments: dict[str, EnvironmentConfig] = {}

    # --- default environment ---
    default_domain = os.environ.get("APPIAN_DOMAIN")
    if default_domain:
        api_key = os.environ.get("APPIAN_API_KEY")
        oauth_token = os.environ.get("APPIAN_OAUTH_TOKEN")
        api_version = os.environ.get("APPIAN_API_VERSION", DEFAULT_API_VERSION)
        if not api_key and not oauth_token:
            raise ValueError(
                "Authentication credentials are required. "
                "Set APPIAN_API_KEY or APPIAN_OAUTH_TOKEN."
            )
        if api_version not in SUPPORTED_API_VERSIONS:
            raise ValueError(
                f"Unsupported API version '{api_version}'. "
                f"Supported versions: {', '.join(SUPPORTED_API_VERSIONS)}"
            )
        environments["default"] = EnvironmentConfig(
            name="default",
            domain=default_domain,
            api_key=api_key or None,
            oauth_token=oauth_token or None,
            api_version=api_version,
        )

    # --- named environments (APPIAN_<ENV>_DOMAIN) ---
    env_domain_pattern = re.compile(r"^APPIAN_([A-Z][A-Z0-9_]*)_DOMAIN$")
    for var_name, domain_value in os.environ.items():
        match = env_domain_pattern.match(var_name)
        if not match:
            continue
        env_name = match.group(1).lower()
        api_key = os.environ.get(f"APPIAN_{match.group(1)}_API_KEY")
        oauth_token = os.environ.get(f"APPIAN_{match.group(1)}_OAUTH_TOKEN")
        api_version = os.environ.get(
            f"APPIAN_{match.group(1)}_API_VERSION", DEFAULT_API_VERSION
        )
        if not api_key and not oauth_token:
            raise ValueError(
                f"Authentication credentials are required for environment '{env_name}'. "
                f"Set APPIAN_{match.group(1)}_API_KEY or APPIAN_{match.group(1)}_OAUTH_TOKEN."
            )
        if api_version not in SUPPORTED_API_VERSIONS:
            raise ValueError(
                f"Unsupported API version '{api_version}' for environment '{env_name}'. "
                f"Supported versions: {', '.join(SUPPORTED_API_VERSIONS)}"
            )
        environments[env_name] = EnvironmentConfig(
            name=env_name,
            domain=domain_value,
            api_key=api_key or None,
            oauth_token=oauth_token or None,
            api_version=api_version,
        )

    if not environments:
        raise ValueError(
            "Appian domain is required. Set APPIAN_DOMAIN or APPIAN_<ENV>_DOMAIN "
            "environment variables."
        )

    return environments


def resolve_environment(
    environments: dict[str, EnvironmentConfig],
    environment: str | None = None,
) -> EnvironmentConfig:
    """Resolve the target environment. Falls back to 'default' when name is None.

    Args:
        environments: Dict of available environment configs keyed by name.
        environment: Optional environment name. When ``None``, the
            ``"default"`` environment is used.

    Returns:
        The matching ``EnvironmentConfig``.

    Raises:
        ValueError: If the requested environment name is not found in
            *environments*.
    """
    name = environment if environment is not None else "default"
    if name not in environments:
        available = ", ".join(sorted(environments.keys()))
        raise ValueError(
            f"Unknown environment '{name}'. Available environments: {available}"
        )
    return environments[name]
