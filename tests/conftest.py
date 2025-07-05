"""pytest設定."""

import pytest
import os
import sys

# プロジェクトルートをPYTHONPATHに追加
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, "package"))

@pytest.fixture
def project_root_path():
    """プロジェクトルートパス."""
    return project_root
