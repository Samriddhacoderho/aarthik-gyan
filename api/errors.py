from __future__ import annotations

from typing import Any


class ApiError(Exception):
    """A safe, client-facing API error.

    ``message`` is deliberately generic enough to be returned to a browser.
    Never put credentials, connection strings, or stack traces in it.
    """

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


def service_unavailable(service: str) -> ApiError:
    return ApiError(
        503,
        "service_unavailable",
        f"{service} is not available. Check the backend configuration and connectivity.",
    )
