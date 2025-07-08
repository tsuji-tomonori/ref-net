"""ベースレスポンスモデル."""

from pydantic import BaseModel


class BaseResponse(BaseModel):
    """全レスポンスの基底クラス."""

    class Config:
        """Pydantic設定."""

        # 追加の属性を許可しない
        extra = "forbid"
        # JSONシリアライズ時にaliasを使用
        populate_by_name = True
