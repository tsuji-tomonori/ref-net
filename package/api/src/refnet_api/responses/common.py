"""共通レスポンスモデル."""

from .base import BaseResponse


class HealthResponse(BaseResponse):
    """ヘルスチェックレスポンス."""

    status: str
    message: str


class MessageResponse(BaseResponse):
    """汎用メッセージレスポンス."""

    message: str
