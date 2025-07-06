#!/usr/bin/env python3
"""Create README.md files for all packages."""

from pathlib import Path

README_TEMPLATE = """# {package_title}

## 概要

{description}

## 機能

- 詳細は実装時に追加

## 使用方法

```python
# 使用例は実装時に追加
```

## 開発

```bash
# テスト実行
moon run test

# 品質チェック
moon run check
```

## 依存関係

- 実装時に追加
"""

PACKAGES = {
    "api": {
        "title": "RefNet API",
        "description": "FastAPI APIゲートウェイサービス"
    },
    "crawler": {
        "title": "RefNet Crawler",
        "description": "Semantic Scholar APIクローラーサービス"
    },
    "summarizer": {
        "title": "RefNet Summarizer",
        "description": "PDF処理・LLM要約サービス"
    },
    "generator": {
        "title": "RefNet Generator",
        "description": "Obsidian Markdown生成サービス"
    },
    "shared": {
        "title": "RefNet Shared",
        "description": "共通ライブラリ（モデル、設定、ユーティリティ）"
    }
}

def main():
    base_dir = Path(__file__).parent.parent / "package"

    for package_name, info in PACKAGES.items():
        package_dir = base_dir / package_name
        readme_path = package_dir / "README.md"

        content = README_TEMPLATE.format(
            package_title=info["title"],
            description=info["description"]
        )
        readme_path.write_text(content)
        print(f"Created: {readme_path}")

if __name__ == "__main__":
    main()
