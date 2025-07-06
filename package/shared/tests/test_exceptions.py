"""例外クラステスト."""

import pytest
from refnet_shared.exceptions import (
    RefNetException,
    ConfigurationError,
    DatabaseError,
    ExternalAPIError,
    ProcessingError,
    ValidationError,
)


def test_base_exception():
    """基底例外クラステスト."""
    with pytest.raises(RefNetException):
        raise RefNetException("Test error")


def test_configuration_error():
    """設定エラーテスト."""
    with pytest.raises(ConfigurationError):
        raise ConfigurationError("Configuration error")

    # RefNetExceptionの継承確認
    with pytest.raises(RefNetException):
        raise ConfigurationError("Configuration error")


def test_database_error():
    """データベースエラーテスト."""
    with pytest.raises(DatabaseError):
        raise DatabaseError("Database error")


def test_external_api_error():
    """外部APIエラーテスト."""
    with pytest.raises(ExternalAPIError):
        raise ExternalAPIError("API error")


def test_processing_error():
    """処理エラーテスト."""
    with pytest.raises(ProcessingError):
        raise ProcessingError("Processing error")


def test_validation_error():
    """検証エラーテスト."""
    with pytest.raises(ValidationError):
        raise ValidationError("Validation error")
