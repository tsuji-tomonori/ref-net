"""RefNet共通例外クラス."""


class RefNetException(Exception):
    """RefNetシステムの基底例外クラス."""

    pass


class ConfigurationError(RefNetException):
    """設定エラー."""

    pass


class DatabaseError(RefNetException):
    """データベース関連エラー."""

    pass


class ExternalAPIError(RefNetException):
    """外部API関連エラー."""

    pass


class ProcessingError(RefNetException):
    """処理エラー."""

    pass


class ValidationError(RefNetException):
    """検証エラー."""

    pass
