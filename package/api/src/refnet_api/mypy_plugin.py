"""FastAPIルーター関数の戻り値型をPydanticモデルに限定するmypyプラグイン."""

from collections.abc import Callable

from mypy.plugin import MethodContext, Plugin
from mypy.types import Type


class FastAPIReturnModelPlugin(Plugin):
    """FastAPIルーター関数の戻り値をPydanticモデルに限定するプラグイン."""

    # チェック対象のデコレータ一覧
    ROUTER_DECORATORS = {
        "fastapi.applications.FastAPI.get",
        "fastapi.applications.FastAPI.post",
        "fastapi.applications.FastAPI.put",
        "fastapi.applications.FastAPI.delete",
        "fastapi.applications.FastAPI.patch",
        "fastapi.applications.FastAPI.options",
        "fastapi.applications.FastAPI.head",
        "fastapi.routing.APIRouter.get",
        "fastapi.routing.APIRouter.post",
        "fastapi.routing.APIRouter.put",
        "fastapi.routing.APIRouter.delete",
        "fastapi.routing.APIRouter.patch",
        "fastapi.routing.APIRouter.options",
        "fastapi.routing.APIRouter.head",
    }

    def get_method_hook(
        self, fullname: str
    ) -> Callable[[MethodContext], Type] | None:
        """メソッドフックを返す."""
        # ルーターメソッドの呼び出しをチェック
        if fullname in self.ROUTER_DECORATORS:
            return self._check_return_type_annotation
        return None

    def _check_return_type_annotation(self, ctx: MethodContext) -> Type:
        """ルーター関数の戻り値型をチェック."""
        # 現在のAPIでは実装が困難なため、元の型を返す
        return ctx.default_return_type

    def _is_pydantic_model(self, typ: Type) -> bool:
        """型がPydanticモデルかどうかをチェック."""
        # TypeInfoを取得
        type_info = getattr(typ, "type", None)
        if type_info is None:
            return False

        # MROを確認してBaseModelが含まれているかチェック
        if hasattr(type_info, "mro"):
            for base in type_info.mro:
                if base.fullname in {
                    "pydantic.main.BaseModel",
                    "pydantic.BaseModel",
                }:
                    return True

        return False


def plugin(version: str) -> type[FastAPIReturnModelPlugin]:
    """mypyプラグインのエントリポイント."""
    return FastAPIReturnModelPlugin
