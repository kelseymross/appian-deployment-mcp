"""Error handling and HTTP status code mapping for Appian API responses."""

import httpx

ERROR_MESSAGES: dict[int, str] = {
    401: "Invalid or expired authentication credentials. Check your APPIAN_API_KEY or APPIAN_OAUTH_TOKEN.",
    403: "Insufficient permissions for the requested operation. Verify the service account has the required role.",
    404: "The requested resource was not found. Verify the UUID is correct.",
    409: "Concurrency limit reached. Retry the operation after a short delay.",
}


class AppianAPIError(Exception):
    """Raised when the Appian API returns a non-2xx response."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"HTTP {status_code}: {message}")


def handle_response(response: httpx.Response) -> dict:
    """Raise AppianAPIError for non-2xx responses; return JSON body for 2xx."""
    if response.is_success:
        return response.json()

    status_code = response.status_code
    if status_code in ERROR_MESSAGES:
        raise AppianAPIError(status_code, ERROR_MESSAGES[status_code])

    raise AppianAPIError(status_code, response.text)


def format_network_error(domain: str, error: Exception) -> dict:
    """Return a structured error dict for network-level failures."""
    return {
        "error": True,
        "message": f"Connection error reaching {domain}: {error}",
    }
