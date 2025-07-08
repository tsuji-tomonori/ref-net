"""RefNet Generator main.pyのテスト."""

import importlib
from unittest.mock import patch

import pytest

from refnet_generator.main import main


class TestMain:
    """main関数のテスト."""

    def test_main_function(self) -> None:
        """main関数の正常実行テスト."""
        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0

    def test_main_module_name_check(self) -> None:
        """モジュール名チェックのテスト."""
        # __name__変数の存在と値をテスト
        import refnet_generator.main as main_module

        # モジュールが__name__属性を持つことを確認
        assert hasattr(main_module, "__name__")

        # __name__が文字列であることを確認
        assert isinstance(main_module.__name__, str)

        # 通常のインポート時は__main__ではないことを確認
        assert main_module.__name__ != "__main__"

    def test_logger_initialization(self) -> None:
        """ロガーの初期化テスト."""
        with patch("structlog.get_logger") as mock_get_logger:
            from refnet_generator import main

            importlib.reload(main)
            mock_get_logger.assert_called_with("refnet_generator.main")
