#!/usr/bin/env python3
"""Create moon.yml files for all packages."""

from pathlib import Path

MOON_TEMPLATE = """type: {type}
language: python

tasks:
  lint:
    command: ruff check .
    inputs:
      - "**/*.py"

  format:
    command: ruff format .
    inputs:
      - "**/*.py"

  typecheck:
    command: mypy .
    inputs:
      - "**/*.py"

  test:
    command: pytest tests/ -v
    inputs:
      - "**/*.py"
      - "tests/**/*.py"

  check:
    deps:
      - lint
      - typecheck
      - test
"""

PACKAGES = {
    "api": "application",
    "crawler": "application",
    "summarizer": "application",
    "generator": "application",
    "shared": "library"
}

def main():
    base_dir = Path(__file__).parent.parent / "package"

    for package_name, package_type in PACKAGES.items():
        package_dir = base_dir / package_name
        moon_path = package_dir / "moon.yml"

        content = MOON_TEMPLATE.format(type=package_type)
        moon_path.write_text(content)
        print(f"Created: {moon_path}")

if __name__ == "__main__":
    main()
