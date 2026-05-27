"""Environment configuration loaded from environment variables."""

import os
import re
import tempfile
from dataclasses import dataclass

from .keychain import read_from_keychain


SUPPORTED_API_VERSIONS = ("v1", "v2", "v3")
DEFAULT_API_VERSION = "v2"
DEFAULT_KEYCHAIN_ACCOUNT = "appian-deployment-mcp"


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


def _resolve_api_key(prefix: str) -> str | None:
    """Resolve an API key from env var or keychain.

    Resolution order:
    1. Direct env var (e.g., APPIAN_API_KEY or APPIAN_DEV_API_KEY)
    2. Keychain lookup if _API_KEY_SOURCE=keychain is set

    Args:
        prefix: The env var prefix (e.g., "APPIAN" or "APPIAN_DEV").

    Returns:
        The API key string, or None if not found.
    """
    # 1. Direct plaintext value
    api_key = os.environ.get(f"{prefix}_API_KEY")
    if api_key:
        return api_key

    # 2. Keychain lookup
    key_source = os.environ.get(f"{prefix}_API_KEY_SOURCE", "").lower()
    if key_source == "keychain":
        service = os.environ.get(
            f"{prefix}_API_KEY_SERVICE",
            f"{prefix.lower().replace('_', '-')}-api-key",
        )
        account = os.environ.get(
            f"{prefix}_API_KEY_ACCOUNT",
            DEFAULT_KEYCHAIN_ACCOUNT,
        )
        keychain_value = read_from_keychain(service, account)
        if keychain_value:
            return keychain_value
        raise ValueError(
            f"Keychain lookup failed for service='{service}', account='{account}'. "
            f"Store your API key with:\n"
            f"  macOS:  security add-generic-password -s \"{service}\" "
            f"-a \"{account}\" -w \"<your-api-key>\"\n"
            f"  Linux:  secret-tool store --label=\"{service}\" "
            f"service \"{service}\" account \"{account}\""
        )

    return None


def load_environments() -> dict[str, EnvironmentConfig]:
    """Load all environments from environment variables.

    Reads ``APPIAN_DOMAIN`` + ``APPIAN_API_KEY`` / ``APPIAN_OAUTH_TOKEN`` as the
    default environment, then scans for ``APPIAN_<ENV>_DOMAIN`` patterns to
    discover additional named environments.

    Credentials can be provided directly via env vars or loaded from the
    system keychain by setting ``APPIAN_API_KEY_SOURCE=keychain``.

    Returns a dict keyed by environment name.

    Raises:
        ValueError: If ``APPIAN_DOMAIN`` is not set or no credentials are
            provided for an environment.
    """
    environments: dict[str, EnvironmentConfig] = {}

    # --- default environment ---
    default_domain = os.environ.get("APPIAN_DOMAIN")
    if default_domain:
        api_key = _resolve_api_key("APPIAN")
        oauth_token = os.environ.get("APPIAN_OAUTH_TOKEN")
        api_version = os.environ.get("APPIAN_API_VERSION", DEFAULT_API_VERSION)
        if not api_key and not oauth_token:
            raise ValueError(
                "Authentication credentials are required. "
                "Set APPIAN_API_KEY, APPIAN_OAUTH_TOKEN, or "
                "APPIAN_API_KEY_SOURCE=keychain."
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
        env_prefix = f"APPIAN_{match.group(1)}"
        api_key = _resolve_api_key(env_prefix)
        oauth_token = os.environ.get(f"{env_prefix}_OAUTH_TOKEN")
        api_version = os.environ.get(
            f"{env_prefix}_API_VERSION", DEFAULT_API_VERSION
        )
        if not api_key and not oauth_token:
            raise ValueError(
                f"Authentication credentials are required for environment '{env_name}'. "
                f"Set {env_prefix}_API_KEY, {env_prefix}_OAUTH_TOKEN, or "
                f"{env_prefix}_API_KEY_SOURCE=keychain."
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
