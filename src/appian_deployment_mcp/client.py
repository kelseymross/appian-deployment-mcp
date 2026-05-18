"""Async HTTP client wrapping httpx for Appian API communication."""

import json
from pathlib import Path

import httpx

from .config import EnvironmentConfig
from .errors import AppianAPIError, format_network_error, handle_response


class AppianClient:
    """Thin async wrapper around httpx.AsyncClient for the Appian Deployment API."""

    def __init__(self, config: EnvironmentConfig):
        self._config = config
        self._client = httpx.AsyncClient(
            base_url=config.base_url,
            headers=config.auth_headers,
            timeout=httpx.Timeout(30.0, read=120.0),
        )

    async def get(self, path: str) -> dict:
        """GET request returning parsed JSON with error handling."""
        try:
            response = await self._client.get(path)
            return handle_response(response)
        except AppianAPIError as exc:
            return {"error": True, "status_code": exc.status_code, "message": exc.message}
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            return format_network_error(self._config.domain, exc)

    async def post_json(self, path: str, body: dict, headers: dict | None = None) -> dict:
        """POST JSON body with optional extra headers."""
        try:
            response = await self._client.post(path, json=body, headers=headers)
            return handle_response(response)
        except AppianAPIError as exc:
            return {"error": True, "status_code": exc.status_code, "message": exc.message}
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            return format_network_error(self._config.domain, exc)

    async def post_multipart(
        self, path: str, json_part: dict, files: dict[str, tuple], headers: dict | None = None
    ) -> dict:
        """POST multipart/form-data with JSON metadata and file parts."""
        try:
            multipart_files: dict[str, tuple] = {
                "json": ("json", json.dumps(json_part).encode(), "application/json"),
            }
            multipart_files.update(files)
            response = await self._client.post(path, files=multipart_files, headers=headers)
            return handle_response(response)
        except AppianAPIError as exc:
            return {"error": True, "status_code": exc.status_code, "message": exc.message}
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            return format_network_error(self._config.domain, exc)

    async def download_file(self, url: str, save_path: Path) -> Path:
        """Download a file from a URL and save to disk using streaming."""
        try:
            save_path.parent.mkdir(parents=True, exist_ok=True)
            async with self._client.stream("GET", url) as response:
                if not response.is_success:
                    await response.aread()
                    raise httpx.HTTPStatusError(
                        f"HTTP {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                with open(save_path, "wb") as f:
                    async for chunk in response.aiter_bytes():
                        f.write(chunk)
            return save_path
        except httpx.HTTPStatusError as exc:
            await exc.response.aread()
            raise AppianAPIError(exc.response.status_code, exc.response.text) from exc
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise exc

    async def get_text(self, path: str) -> str | dict:
        """GET request returning plain text response."""
        try:
            response = await self._client.get(path)
            if not response.is_success:
                from .errors import ERROR_MESSAGES

                status_code = response.status_code
                if status_code in ERROR_MESSAGES:
                    return {"error": True, "status_code": status_code, "message": ERROR_MESSAGES[status_code]}
                return {"error": True, "status_code": status_code, "message": response.text}
            return response.text
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            return format_network_error(self._config.domain, exc)

    async def close(self):
        """Clean up the httpx client."""
        await self._client.aclose()
