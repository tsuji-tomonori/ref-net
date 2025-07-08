"""ベースレスポンスモデル."""

from pydantic import BaseModel, ConfigDict


class BaseResponse(BaseModel):
    """全レスポンスの基底クラス."""

    model_config = ConfigDict(
        # 追加の属性を許可しない
        extra="forbid",
        # JSONシリアライズ時にaliasを使用
        populate_by_name=True,
    )
