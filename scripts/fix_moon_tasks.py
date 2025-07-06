#!/usr/bin/env python3
"""Fix moon task commands to use venv binaries."""

from pathlib import Path

packages = ["api", "crawler", "summarizer", "generator"]

replacements = [
    ("command: ruff check .", "command: .venv/bin/ruff check ."),
    ("command: ruff format .", "command: .venv/bin/ruff format ."),
    ("command: mypy .", "command: .venv/bin/mypy ."),
    ("command: pytest tests/ -v", "command: .venv/bin/pytest tests/ -v")
]

for package in packages:
    moon_path = Path(f"package/{package}/moon.yml")
    if moon_path.exists():
        content = moon_path.read_text()
        for old, new in replacements:
            content = content.replace(old, new)
        moon_path.write_text(content)
        print(f"Fixed: {moon_path}")
