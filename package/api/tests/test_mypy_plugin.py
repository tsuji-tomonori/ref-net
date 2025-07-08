"""mypy_plugin.pyのユニットテスト."""

from unittest.mock import MagicMock

import pytest

from refnet_api.mypy_plugin import FastAPIReturnModelPlugin


class TestFastAPIReturnModelPlugin:
    """FastAPIReturnModelPluginのテストクラス."""

    @pytest.fixture
    def plugin(self) -> FastAPIReturnModelPlugin:
        """プラグインインスタンスを生成."""
        from mypy.options import Options
        options = Options()
        return FastAPIReturnModelPlugin(options=options)

    def test_get_method_hook_returns_hook_for_fastapi_methods(
        self, plugin: FastAPIReturnModelPlugin
    ) -> None:
        """FastAPIのメソッドに対してフックを返すことを確認."""
        # FastAPIメソッドの場合
        for method in [
            "fastapi.applications.FastAPI.get",
            "fastapi.routing.APIRouter.post",
            "fastapi.applications.FastAPI.put",
            "fastapi.routing.APIRouter.delete",
        ]:
            hook = plugin.get_method_hook(method)
            assert hook is not None
            assert callable(hook)

    def test_get_method_hook_returns_none_for_non_fastapi_methods(
        self, plugin: FastAPIReturnModelPlugin
    ) -> None:
        """FastAPI以外のメソッドに対してNoneを返すことを確認."""
        hook = plugin.get_method_hook("some.other.method")
        assert hook is None

    def test_check_return_type_annotation_returns_default_type(
        self, plugin: FastAPIReturnModelPlugin
    ) -> None:
        """戻り値型チェックが元の型を返すことを確認."""
        # モックの設定
        ctx = MagicMock()
        expected_type = MagicMock()
        ctx.default_return_type = expected_type

        # 実行
        result = plugin._check_return_type_annotation(ctx)

        # 検証
        assert result == expected_type

    def test_is_pydantic_model_returns_true_for_pydantic_models(
        self, plugin: FastAPIReturnModelPlugin
    ) -> None:
        """Pydanticモデルに対してTrueを返すことを確認."""
        # Pydanticモデルのモック
        typ = MagicMock()
        base_model = MagicMock()
        base_model.fullname = "pydantic.BaseModel"
        typ.type = MagicMock()
        typ.type.mro = [MagicMock(), base_model]

        result = plugin._is_pydantic_model(typ)
        assert result is True

        # pydantic.main.BaseModelの場合もテスト
        base_model.fullname = "pydantic.main.BaseModel"
        result = plugin._is_pydantic_model(typ)
        assert result is True

    def test_is_pydantic_model_returns_false_for_non_pydantic_models(
        self, plugin: FastAPIReturnModelPlugin
    ) -> None:
        """非Pydanticモデルに対してFalseを返すことを確認."""
        # 非Pydanticモデルのモック
        typ = MagicMock()
        typ.type = MagicMock()
        typ.type.mro = [MagicMock()]  # BaseModelを含まない

        result = plugin._is_pydantic_model(typ)
        assert result is False

    def test_is_pydantic_model_returns_false_when_type_info_is_none(
        self, plugin: FastAPIReturnModelPlugin
    ) -> None:
        """TypeInfoがNoneの場合にFalseを返すことを確認."""
        typ = MagicMock()
        typ.type = None

        result = plugin._is_pydantic_model(typ)
        assert result is False

    def test_plugin_entry_point(self) -> None:
        """プラグインエントリポイントが正しく動作することを確認."""
        from refnet_api.mypy_plugin import plugin

        plugin_class = plugin("1.0.0")
        assert plugin_class == FastAPIReturnModelPlugin
