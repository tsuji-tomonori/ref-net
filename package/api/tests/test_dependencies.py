"""依存関係モジュールのテスト."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from refnet_shared.exceptions import DatabaseError
from sqlalchemy.orm import Session

from refnet_api.dependencies import get_current_user, get_db


def test_get_db() -> None:
    """データベースセッション取得のテスト."""
    with patch("refnet_api.dependencies.db_manager") as mock_db_manager:
        mock_session = MagicMock(spec=Session)
        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_session
        mock_context.__exit__.return_value = None
        mock_db_manager.get_session.return_value = mock_context

        # ジェネレータを実行
        db_gen = get_db()
        db = next(db_gen)

        assert db == mock_session

        # クリーンアップ確認
        try:
            next(db_gen)
        except StopIteration:
            pass

        mock_db_manager.get_session.assert_called_once()


def test_get_db_with_database_error() -> None:
    """データベースエラーが発生した場合のテスト."""
    with patch("refnet_api.dependencies.db_manager") as mock_db_manager:
        # DatabaseError を発生させる
        mock_db_manager.get_session.side_effect = DatabaseError("Connection failed")

        # HTTPException が発生することを確認
        with pytest.raises(HTTPException) as exc_info:
            db_gen = get_db()
            next(db_gen)

        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Database connection failed"


def test_get_current_user() -> None:
    """現在のユーザー取得のテスト."""
    # 現在の実装では固定値を返す
    user = get_current_user()
    assert user == {"user_id": "system"}
