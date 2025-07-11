"""Celeryタスクセキュリティのテスト."""

from unittest.mock import MagicMock, patch

import pytest
from celery.exceptions import Reject

from refnet_shared.security.celery_security import (
    CelerySecurityMiddleware,
    CeleryTaskPermission,
    _check_admin_permission,
    _check_user_permission,
    _is_scheduled_execution,
    log_task_execution,
    require_admin_permission,
    require_user_permission,
    system_task_only,
)


class TestCeleryTaskPermission:
    """CeleryTaskPermissionのテスト."""

    def test_is_admin_required(self) -> None:
        """管理者権限必要タスクの判定テスト."""
        assert CeleryTaskPermission.is_admin_required("refnet.scheduled.database_maintenance")
        assert CeleryTaskPermission.is_admin_required("refnet.admin.reset_system")
        assert not CeleryTaskPermission.is_admin_required("refnet.crawler.crawl_paper")

    def test_is_high_risk(self) -> None:
        """高リスクタスクの判定テスト."""
        assert CeleryTaskPermission.is_high_risk("refnet.scheduled.backup_database")
        assert CeleryTaskPermission.is_high_risk("refnet.admin.purge_cache")
        assert not CeleryTaskPermission.is_high_risk("refnet.crawler.crawl_paper")

    def test_is_user_allowed(self) -> None:
        """ユーザー実行可能タスクの判定テスト."""
        assert CeleryTaskPermission.is_user_allowed("refnet.crawler.crawl_paper")
        assert CeleryTaskPermission.is_user_allowed("refnet.summarizer.summarize_paper")
        assert not CeleryTaskPermission.is_user_allowed("refnet.admin.reset_system")

    def test_is_system_only(self) -> None:
        """システム専用タスクの判定テスト."""
        assert CeleryTaskPermission.is_system_only("refnet.scheduled.system_health_check")
        assert CeleryTaskPermission.is_system_only("refnet.internal.process_queue")
        assert not CeleryTaskPermission.is_system_only("refnet.crawler.crawl_paper")


class TestCelerySecurityDecorators:
    """Celeryセキュリティデコレーターのテスト."""

    def test_require_admin_permission_success(self) -> None:
        """管理者権限デコレーター成功テスト."""
        @require_admin_permission
        def test_task(*args, **kwargs):
            return "success"

        with patch("refnet_shared.security.celery_security.current_task") as mock_task:
            mock_task.name = "test_task"
            with patch("refnet_shared.security.celery_security._check_admin_permission", return_value=True):
                result = test_task(user_id="admin")
                assert result == "success"

    def test_require_admin_permission_fail(self) -> None:
        """管理者権限デコレーター失敗テスト."""
        @require_admin_permission
        def test_task(*args, **kwargs):
            return "success"

        with patch("refnet_shared.security.celery_security.current_task") as mock_task:
            mock_task.name = "test_task"
            with patch("refnet_shared.security.celery_security._check_admin_permission", return_value=False):
                with pytest.raises(Reject):
                    test_task(user_id="user")

    def test_require_user_permission_success(self) -> None:
        """ユーザー権限デコレーター成功テスト."""
        @require_user_permission
        def test_task(*args, **kwargs):
            return "success"

        with patch("refnet_shared.security.celery_security.current_task") as mock_task:
            mock_task.name = "test_task"
            with patch("refnet_shared.security.celery_security._check_user_permission", return_value=True):
                result = test_task(user_id="user")
                assert result == "success"

    def test_require_user_permission_fail(self) -> None:
        """ユーザー権限デコレーター失敗テスト."""
        @require_user_permission
        def test_task(*args, **kwargs):
            return "success"

        with patch("refnet_shared.security.celery_security.current_task") as mock_task:
            mock_task.name = "test_task"
            with patch("refnet_shared.security.celery_security._check_user_permission", return_value=False):
                with pytest.raises(Reject):
                    test_task(user_id=None)

    def test_system_task_only_success(self) -> None:
        """システムタスクデコレーター成功テスト."""
        @system_task_only
        def test_task(*args, **kwargs):
            return "success"

        with patch("refnet_shared.security.celery_security.current_task") as mock_task:
            mock_task.name = "test_task"
            with patch("refnet_shared.security.celery_security._is_scheduled_execution", return_value=True):
                result = test_task()
                assert result == "success"

    def test_system_task_only_fail(self) -> None:
        """システムタスクデコレーター失敗テスト."""
        @system_task_only
        def test_task(*args, **kwargs):
            return "success"

        with patch("refnet_shared.security.celery_security.current_task") as mock_task:
            mock_task.name = "test_task"
            with patch("refnet_shared.security.celery_security._is_scheduled_execution", return_value=False):
                with pytest.raises(Reject):
                    test_task()

    def test_log_task_execution_success(self) -> None:
        """タスク実行ログデコレーター成功テスト."""
        @log_task_execution
        def test_task(*args, **kwargs):
            return "success"

        with patch("refnet_shared.security.celery_security.current_task") as mock_task:
            mock_task.name = "test_task"
            mock_task.request.id = "task_id"
            with patch("refnet_shared.security.celery_security.logger") as mock_logger:
                result = test_task()
                assert result == "success"
                assert mock_logger.info.call_count == 2

    def test_log_task_execution_error(self) -> None:
        """タスク実行ログデコレーターエラーテスト."""
        @log_task_execution
        def test_task(*args, **kwargs):
            raise ValueError("test error")

        with patch("refnet_shared.security.celery_security.current_task") as mock_task:
            mock_task.name = "test_task"
            mock_task.request.id = "task_id"
            with patch("refnet_shared.security.celery_security.logger") as mock_logger:
                with pytest.raises(ValueError):
                    test_task()
                mock_logger.error.assert_called_once()


class TestCelerySecurityFunctions:
    """Celeryセキュリティ関数のテスト."""

    def test_check_admin_permission(self) -> None:
        """管理者権限チェック関数テスト."""
        assert _check_admin_permission("admin")
        assert _check_admin_permission("system")
        assert not _check_admin_permission("user")
        assert not _check_admin_permission(None)

    def test_check_user_permission(self) -> None:
        """ユーザー権限チェック関数テスト."""
        assert _check_user_permission("user")
        assert _check_user_permission("admin")
        assert not _check_user_permission(None)
        assert not _check_user_permission("")

    def test_is_scheduled_execution(self) -> None:
        """スケジュール実行チェック関数テスト."""
        # current_taskがNoneの場合
        with patch("refnet_shared.security.celery_security.current_task", None):
            assert not _is_scheduled_execution()

        # etaが設定されている場合
        with patch("refnet_shared.security.celery_security.current_task") as mock_task:
            mock_request = MagicMock()
            mock_request.eta = "2024-01-01T00:00:00"
            mock_task.request = mock_request
            assert _is_scheduled_execution()

        # countdownが設定されている場合
        with patch("refnet_shared.security.celery_security.current_task") as mock_task:
            mock_request = MagicMock()
            mock_request.countdown = 60
            mock_task.request = mock_request
            assert _is_scheduled_execution()

        # どちらも設定されていない場合
        with patch("refnet_shared.security.celery_security.current_task") as mock_task:
            mock_request = MagicMock(spec=[])  # 空のspecでeta/countdownがない
            mock_task.request = mock_request
            assert not _is_scheduled_execution()


class TestCelerySecurityMiddleware:
    """CelerySecurityMiddlewareのテスト."""

    def test_check_task_permission_admin(self) -> None:
        """タスク権限チェック（管理者）テスト."""
        middleware = CelerySecurityMiddleware()
        with patch("refnet_shared.security.celery_security._check_admin_permission", return_value=True):
            assert middleware.check_task_permission("refnet.admin.reset_system", "admin")

    def test_check_task_permission_system(self) -> None:
        """タスク権限チェック（システム）テスト."""
        middleware = CelerySecurityMiddleware()
        # system_health_checkは管理者権限も必要なので、両方チェックする
        with patch("refnet_shared.security.celery_security._check_admin_permission", return_value=True):
            assert middleware.check_task_permission("refnet.scheduled.system_health_check", "admin")

        # 管理者権限がない場合は失敗
        with patch("refnet_shared.security.celery_security._check_admin_permission", return_value=False):
            assert not middleware.check_task_permission("refnet.scheduled.system_health_check", "user")

    def test_check_task_permission_user(self) -> None:
        """タスク権限チェック（ユーザー）テスト."""
        middleware = CelerySecurityMiddleware()
        with patch("refnet_shared.security.celery_security._check_user_permission", return_value=True):
            assert middleware.check_task_permission("refnet.crawler.crawl_paper", "user")

    def test_check_task_permission_unknown(self) -> None:
        """タスク権限チェック（未定義）テスト."""
        middleware = CelerySecurityMiddleware()
        assert not middleware.check_task_permission("unknown.task", "user")

    def test_get_task_security_info(self) -> None:
        """タスクセキュリティ情報取得テスト."""
        middleware = CelerySecurityMiddleware()

        # 管理者タスク
        info = middleware.get_task_security_info("refnet.admin.reset_system")
        assert info["admin_required"]
        assert info["high_risk"]
        assert not info["user_allowed"]
        assert not info["system_only"]

        # ユーザータスク
        info = middleware.get_task_security_info("refnet.crawler.crawl_paper")
        assert not info["admin_required"]
        assert not info["high_risk"]
        assert info["user_allowed"]
        assert not info["system_only"]

        # システムタスク
        info = middleware.get_task_security_info("refnet.scheduled.system_health_check")
        assert info["admin_required"]
        assert not info["high_risk"]
        assert not info["user_allowed"]
        assert info["system_only"]

    def test_check_admin_permission_system_user(self) -> None:
        """システムユーザーの管理者権限チェックテスト."""
        assert _check_admin_permission("system")
        assert _check_admin_permission("root")

    def test_check_user_permission_edge_cases(self) -> None:
        """ユーザー権限チェックのエッジケーステスト."""
        assert not _check_user_permission("")
        # 空白文字をテストしてline 263をカバー
        assert _check_user_permission("   ")  # len("   ") > 0のためTrue
        assert _check_user_permission("valid_user")

    def test_is_scheduled_execution_edge_cases(self) -> None:
        """スケジュール実行チェックのエッジケーステスト."""
        # countdownが設定されている場合
        with patch("refnet_shared.security.celery_security.current_task") as mock_task:
            mock_request = MagicMock()
            mock_request.eta = None
            mock_request.countdown = 0
            mock_task.request = mock_request
            assert _is_scheduled_execution()  # hasattr(request, 'countdown')がTrue

        # hasattrでチェックするため、属性が存在するだけでTrueになる
        with patch("refnet_shared.security.celery_security.current_task") as mock_task:
            mock_request = MagicMock()
            # MagicMockはデフォルトで任意の属性へのアクセスを許可するため
            # hasattr(mock_request, 'eta')やhasattr(mock_request, 'countdown')はTrueになる
            mock_task.request = mock_request
            assert _is_scheduled_execution()  # hasattrがTrueを返すため

    def test_decorator_without_current_task(self) -> None:
        """タスクコンテキストがない場合のデコレーターテスト."""
        @log_task_execution
        def test_task_no_context():
            return "success"

        # current_taskがNoneの場合はそのまま実行される
        with patch("refnet_shared.security.celery_security.current_task", None):
            result = test_task_no_context()
            assert result == "success"

    def test_check_admin_permission_edge_cases(self) -> None:
        """管理者権限チェックのエッジケーステスト."""
        # Empty string
        assert not _check_admin_permission("")
        # Space characters
        assert not _check_admin_permission("   ")
        # Case sensitive admin roles
        assert _check_admin_permission("admin")
        assert not _check_admin_permission("Admin")  # case sensitive

    def test_is_scheduled_execution_has_attr_cases(self) -> None:
        """スケジュール実行のhasattrチェックテスト."""
        # current_taskの属性がない場合
        with patch("refnet_shared.security.celery_security.current_task") as mock_task:
            mock_task.request = object()  # eta/countdown属性を持たないオブジェクト
            assert not _is_scheduled_execution()
