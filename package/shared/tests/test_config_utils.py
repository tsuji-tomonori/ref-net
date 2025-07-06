"""設定管理ユーティリティテスト."""

import os
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from refnet_shared.config.environment import Environment, EnvironmentSettings
from refnet_shared.utils.config_utils import (
    get_env_file_path,
    create_env_file_from_template,
    export_settings_to_json,
    check_required_env_vars
)


def test_get_env_file_path():
    """環境ファイルパス取得テスト."""
    dev_path = get_env_file_path(Environment.DEVELOPMENT)
    assert dev_path == Path(".env.development")

    prod_path = get_env_file_path(Environment.PRODUCTION)
    assert prod_path == Path(".env.production")


def test_create_env_file_from_template():
    """テンプレートから環境ファイル作成テスト."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 作業ディレクトリを変更
        original_cwd = os.getcwd()
        os.chdir(tmpdir)

        try:
            # テンプレートファイル作成
            template_content = """# Template
DATABASE__HOST=localhost
DATABASE__PASSWORD=template_password
"""
            with open(".env.example", "w") as f:
                f.write(template_content)

            # 環境ファイル作成
            create_env_file_from_template(Environment.DEVELOPMENT)

            # 作成されたファイルを確認
            env_file = Path(".env.development")
            assert env_file.exists()

            content = env_file.read_text()
            assert "DATABASE__HOST=localhost" in content
            assert "DATABASE__PASSWORD=template_password" in content

        finally:
            os.chdir(original_cwd)


def test_create_env_file_from_template_with_overrides():
    """上書き設定でテンプレートから環境ファイル作成テスト."""
    with tempfile.TemporaryDirectory() as tmpdir:
        original_cwd = os.getcwd()
        os.chdir(tmpdir)

        try:
            # テンプレートファイル作成
            template_content = """DATABASE__HOST=localhost
DATABASE__PASSWORD=template_password
"""
            with open(".env.example", "w") as f:
                f.write(template_content)

            # 上書き設定で環境ファイル作成
            overrides = {"DATABASE__PASSWORD": "overridden_password"}
            create_env_file_from_template(Environment.DEVELOPMENT, overrides)

            # 作成されたファイルを確認
            env_file = Path(".env.development")
            content = env_file.read_text()
            assert "DATABASE__HOST=localhost" in content
            assert "DATABASE__PASSWORD=overridden_password" in content

        finally:
            os.chdir(original_cwd)


def test_create_env_file_template_not_found():
    """テンプレートファイルが存在しない場合のテスト."""
    with tempfile.TemporaryDirectory() as tmpdir:
        original_cwd = os.getcwd()
        os.chdir(tmpdir)

        try:
            with pytest.raises(FileNotFoundError, match="Template file .env.example not found"):
                create_env_file_from_template(Environment.DEVELOPMENT)
        finally:
            os.chdir(original_cwd)


def test_export_settings_to_json():
    """設定JSON エクスポートテスト."""
    # デフォルト設定をベースにして、部分的に上書き
    settings = EnvironmentSettings(environment=Environment.PRODUCTION)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        output_path = Path(f.name)

    try:
        export_settings_to_json(settings, output_path)

        # ファイルが作成されていることを確認
        assert output_path.exists()

        # JSON内容を確認
        with open(output_path, 'r') as f:
            data = json.load(f)

        # 含まれるべき情報
        assert data["environment"] == "production"
        assert data["database"]["host"] == "localhost"  # デフォルト値

        # 除外されるべき機密情報
        assert "password" not in data["database"]
        assert "jwt_secret" not in data["security"]

    finally:
        output_path.unlink()


@patch.dict(os.environ, {
    "DATABASE__HOST": "test-host",
    "DATABASE__USERNAME": "test-user",
    "DATABASE__PASSWORD": "test-pass",
    "SECURITY__JWT_SECRET": "test-secret"
})
def test_check_required_env_vars_all_set():
    """必須環境変数チェック（全て設定済み）テスト."""
    result = check_required_env_vars(Environment.STAGING)

    # ステージング環境の必須変数がすべて True
    assert result["DATABASE__HOST"] is True
    assert result["DATABASE__USERNAME"] is True
    assert result["DATABASE__PASSWORD"] is True
    assert result["SECURITY__JWT_SECRET"] is True


@patch.dict(os.environ, {
    "DATABASE__HOST": "test-host",
    # DATABASE__USERNAME と DATABASE__PASSWORD は未設定
}, clear=True)
def test_check_required_env_vars_missing():
    """必須環境変数チェック（一部未設定）テスト."""
    result = check_required_env_vars(Environment.DEVELOPMENT)

    # 設定済み
    assert result["DATABASE__HOST"] is True

    # 未設定
    assert result["DATABASE__USERNAME"] is False
    assert result["DATABASE__PASSWORD"] is False


def test_check_required_env_vars_development():
    """開発環境の必須環境変数チェックテスト."""
    result = check_required_env_vars(Environment.DEVELOPMENT)

    # 開発環境の必須変数
    expected_vars = ["DATABASE__HOST", "DATABASE__USERNAME", "DATABASE__PASSWORD"]
    assert set(result.keys()) == set(expected_vars)


def test_check_required_env_vars_production():
    """本番環境の必須環境変数チェックテスト."""
    result = check_required_env_vars(Environment.PRODUCTION)

    # 本番環境の必須変数
    expected_vars = [
        "DATABASE__HOST",
        "DATABASE__USERNAME",
        "DATABASE__PASSWORD",
        "SECURITY__JWT_SECRET",
        "OPENAI_API_KEY"
    ]
    assert set(result.keys()) == set(expected_vars)
