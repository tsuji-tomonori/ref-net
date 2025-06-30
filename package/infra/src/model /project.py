from pathlib import Path
from typing import Any

import tomllib

PYPROJECT_PATH = Path.cwd() / "pyproject.toml"


class Project:
    """Project class to manage project metadata."""

    def __init__(self) -> None:
        """Initialize Project with metadata from pyproject.toml."""
        self._metadata = self._load_metadata()

    def _load_metadata(self) -> dict[str, Any]:
        """Load project metadata from pyproject.toml."""
        with open(PYPROJECT_PATH, "rb") as f:
            data = tomllib.load(f)
            return data["project"]  # type: ignore[no-any-return]

    @property
    def name(self) -> str:
        """Get the project name."""
        return str(self._metadata["name"])

    @property
    def camel_case_name(self) -> str:
        """Get the camel case project name."""
        return self.name[0].upper() + self.name[1:]

    @property
    def description(self) -> str:
        """Get the project description."""
        return f"[{self.name}] {self._metadata['description']}"

    @property
    def semantic_version(self) -> str:
        """Get the project semantic version."""
        return str(self._metadata["version"])

    @property
    def major_version(self) -> str:
        """Get the project version."""
        return f"v{self.semantic_version.split('.')[0]}"
