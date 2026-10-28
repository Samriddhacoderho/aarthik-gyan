"""API-only settings.

This module deliberately does not import ``config``. The V3 configuration module
validates database and LLM credentials at import time, which would make the API
impossible to start (or health-check) when those services are unavailable.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def _split_origins(raw: str) -> list[str]:
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


@dataclass(frozen=True)
class ApiSettings:
    service_name: str = "aarthik-gyan-api"
    version: str = "4.0.0"
    cors_origins: tuple[str, ...] = tuple(
        _split_origins(
            os.getenv(
                "API_CORS_ORIGINS",
                "http://localhost:5173,http://127.0.0.1:5173",
            )
        )
    )
    upload_dir: Path = Path(os.getenv("API_UPLOAD_DIR", "data/uploads"))
    report_dir: Path = Path(os.getenv("API_REPORT_DIR", "reports/output"))
    max_upload_mb: int = int(os.getenv("API_MAX_UPLOAD_MB", "25"))
    graph_max_nodes: int = int(os.getenv("API_GRAPH_MAX_NODES", "220"))
    graph_max_edges: int = int(os.getenv("API_GRAPH_MAX_EDGES", "400"))

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def upload_path(self) -> Path:
        return self.upload_dir if self.upload_dir.is_absolute() else ROOT_DIR / self.upload_dir

    @property
    def report_path(self) -> Path:
        return self.report_dir if self.report_dir.is_absolute() else ROOT_DIR / self.report_dir

    def ensure_runtime_dirs(self) -> None:
        self.upload_path.mkdir(parents=True, exist_ok=True)
        self.report_path.mkdir(parents=True, exist_ok=True)


settings = ApiSettings()
