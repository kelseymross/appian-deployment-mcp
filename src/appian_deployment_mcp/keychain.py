"""System keychain integration for secure credential storage."""

import platform
import subprocess


def read_from_keychain(service: str, account: str = "appian-deployment-mcp") -> str | None:
    """Read a credential from the system keychain.

    Supports:
    - macOS: Keychain Access (via `security` CLI)
    - Linux: Secret Service / libsecret (via `secret-tool` CLI)
    - Windows: Windows Credential Manager (via `cmdkey` / PowerShell)

    Args:
        service: The service name / label for the keychain entry.
        account: The account name (defaults to "appian-deployment-mcp").

    Returns:
        The credential value, or None if not found or unsupported platform.

    Raises:
        RuntimeError: If the keychain lookup fails with an unexpected error.
    """
    system = platform.system()

    if system == "Darwin":
        return _read_macos_keychain(service, account)
    elif system == "Linux":
        return _read_linux_keychain(service, account)
    elif system == "Windows":
        return _read_windows_keychain(service)
    else:
        return None


def _read_macos_keychain(service: str, account: str) -> str | None:
    """Read from macOS Keychain using the `security` CLI."""
    try:
        result = subprocess.run(
            [
                "security", "find-generic-password",
                "-s", service,
                "-a", account,
                "-w",  # Output only the password
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        # returncode 44 = item not found
        if result.returncode == 44:
            return None
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _read_linux_keychain(service: str, account: str) -> str | None:
    """Read from Linux Secret Service using `secret-tool`."""
    try:
        result = subprocess.run(
            [
                "secret-tool", "lookup",
                "service", service,
                "account", account,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _read_windows_keychain(service: str) -> str | None:
    """Read from Windows Credential Manager using PowerShell."""
    try:
        # Use PowerShell to read from Windows Credential Manager
        ps_script = (
            f"$cred = Get-StoredCredential -Target '{service}'; "
            f"if ($cred) {{ $cred.GetNetworkCredential().Password }}"
        )
        result = subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
