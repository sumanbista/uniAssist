"""Utilities for loading structured mock data."""

import json
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class DataLoader:
    """Load JSON datasets from the configured data directory."""

    def __init__(self, data_path: Path | None = None) -> None:
        self.data_path = data_path or settings.DATA_PATH

    def load_json(self, file_name: str) -> list[dict[str, Any]]:
        """Load a JSON file and return a list of records."""

        file_path = self.data_path / file_name
        try:
            with file_path.open("r", encoding="utf-8") as data_file:
                data = json.load(data_file)
        except FileNotFoundError:
            logger.error("Data file missing: %s", file_path)
            raise
        except json.JSONDecodeError as exc:
            logger.error("Invalid JSON in data file: %s", file_path)
            raise ValueError(f"Invalid JSON data in {file_name}") from exc

        if not isinstance(data, list):
            logger.error("Data file must contain a JSON list: %s", file_path)
            raise ValueError(f"Data file {file_name} must contain a list")

        return data
