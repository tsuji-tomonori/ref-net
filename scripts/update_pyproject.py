#!/usr/bin/env python3
"""Update pyproject.toml files for all packages."""

import os
from pathlib import Path

TEMPLATE = """[project]
name = "{package_name}"
version = "0.1.0"
description = "{description}"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "mypy>=1.16.1",
    "pytest>=8.4.1",
    "ruff>=0.12.1",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "UP",  # pyupgrade
]
ignore = []

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
skip-magic-trailing-comma = false
line-ending = "auto"

[tool.mypy]
python_version = "3.12"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
disallow_untyped_decorators = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
warn_unreachable = true
strict_equality = true
extra_checks = true
"""

PACKAGES = {
    "refnet-api": "FastAPI APIゲートウェイサービス",
    "refnet-crawler": "Semantic Scholar APIクローラーサービス",
    "refnet-summarizer": "PDF処理・LLM要約サービス",
    "refnet-generator": "Obsidian Markdown生成サービス",
    "refnet-shared": "共通ライブラリ（モデル、設定、ユーティリティ）"
}

def main():
    base_dir = Path(__file__).parent.parent / "package"

    for package_name, description in PACKAGES.items():
        package_dir = base_dir / package_name.replace("refnet-", "")
        pyproject_path = package_dir / "pyproject.toml"

        if pyproject_path.exists():
            content = TEMPLATE.format(
                package_name=package_name,
                description=description
            )
            pyproject_path.write_text(content)
            print(f"Updated: {pyproject_path}")

if __name__ == "__main__":
    main()
