"""RefNet Generator main.pyのテスト."""

import importlib
import runpy
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

    def test_main_script_execution(self) -> None:
        """if __name__ == "__main__"の実行テスト."""
        with patch("refnet_generator.main.main"):
            # if __name__ == "__main__" ブロックをシミュレート
            with patch("__main__.__name__", "__main__"):
                # モジュールを実行としてインポート
                with pytest.raises(SystemExit):
                    runpy.run_module("refnet_generator.main", run_name="__main__")

    def test_logger_initialization(self) -> None:
        """ロガーの初期化テスト."""
        with patch("structlog.get_logger") as mock_get_logger:
            from refnet_generator import main

            importlib.reload(main)
            mock_get_logger.assert_called_with("refnet_generator.main")
