"""auto_recoveryモジュールのテスト."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from refnet_shared.utils.auto_recovery import (
    AutoRecoveryManager,
    RecoveryActionType,
    RecoveryResult,
    RecoveryStatus,
    check_system_health,
    get_auto_recovery_manager,
    trigger_recovery,
)


class TestAutoRecoveryManager:
    """AutoRecoveryManagerクラスのテスト."""

    def test_init(self) -> None:
        """初期化テスト."""
        manager = AutoRecoveryManager()
        assert manager.recovery_actions is not None
        assert len(manager.recovery_actions) > 0
        assert manager.recovery_history == []
        assert manager.circuit_breakers == {}
        assert manager.cooldown_timers == {}

    @pytest.mark.asyncio
    @patch("refnet_shared.utils.auto_recovery.AutoRecoveryManager._execute_recovery_action")
    async def test_execute_recovery_success(self, mock_execute: AsyncMock) -> None:
        """回復実行成功テスト."""
        manager = AutoRecoveryManager()
        mock_execute.return_value = RecoveryResult(
            action_type=RecoveryActionType.RESTART_DATABASE_CONNECTION,
            name="Test Action",
            status=RecoveryStatus.SUCCESS,
            attempts=1,
            duration=1.0
        )

        result = await manager.execute_recovery("database_connection_failed", {"error": "test"})

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].status == RecoveryStatus.SUCCESS
        mock_execute.assert_called()

    @pytest.mark.asyncio
    @patch("refnet_shared.utils.auto_recovery.AutoRecoveryManager._execute_recovery_action")
    async def test_execute_recovery_no_matching_action(self, mock_execute: AsyncMock) -> None:
        """マッチするアクションなしテスト."""
        manager = AutoRecoveryManager()

        result = await manager.execute_recovery("unknown_condition", {"error": "test"})

        assert isinstance(result, list)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_recover_database_connection(self) -> None:
        """データベース接続回復テスト."""
        manager = AutoRecoveryManager()

        with patch("refnet_shared.utils.auto_recovery.create_engine") as mock_engine:
            mock_conn = MagicMock()
            mock_engine.return_value.connect.return_value.__enter__.return_value = mock_conn

            result = await manager._recover_database_connection({"database_url": "test://db"})

            assert result is True

    @pytest.mark.asyncio
    async def test_clear_redis_cache(self) -> None:
        """Redisキャッシュクリアテスト."""
        manager = AutoRecoveryManager()

        with patch("refnet_shared.utils.auto_recovery.redis.Redis") as mock_redis:
            mock_client = MagicMock()
            mock_redis.from_url.return_value = mock_client

            # Mock redis operations
            mock_client.info.return_value = {"used_memory": 1000}
            mock_client.keys.return_value = ["cache:key1", "cache:key2"]

            result = await manager._clear_redis_cache({"cache_patterns": ["cache:*"]})

            assert result is True
            mock_client.keys.assert_called_with("cache:*")
            mock_client.delete.assert_called_once_with("cache:key1", "cache:key2")

    @pytest.mark.asyncio
    async def test_clean_temp_files(self) -> None:
        """一時ファイルクリーンアップテスト."""
        manager = AutoRecoveryManager()

        with patch("tempfile.gettempdir", return_value="/tmp"), \
             patch("pathlib.Path") as mock_path:

            # Mock Path objects and methods
            mock_temp_path = MagicMock()
            mock_temp_path.exists.return_value = True

            mock_file_path = MagicMock()
            mock_file_path.is_file.return_value = True
            mock_file_path.stat.return_value.st_size = 1024
            mock_temp_path.glob.return_value = [mock_file_path]

            mock_path.return_value = mock_temp_path

            result = await manager._clean_temp_files({"temp_dirs": ["/tmp/test"]})

            assert result is True
            mock_file_path.unlink.assert_called_once()

    @pytest.mark.asyncio
    async def test_restart_celery_worker(self) -> None:
        """Celeryワーカー再起動テスト."""
        manager = AutoRecoveryManager()

        result = await manager._restart_celery_worker({"worker_id": "test"})

        assert result is True

    @pytest.mark.asyncio
    async def test_reset_circuit_breaker(self) -> None:
        """サーキットブレーカーリセットテスト."""
        manager = AutoRecoveryManager()
        manager.circuit_breakers["test"] = {"failure_count": 5, "last_failure": 1000}

        result = await manager._reset_circuit_breaker({"circuit_breaker_name": "test"})

        assert result is True
        assert manager.circuit_breakers["test"]["failure_count"] == 0

    def test_is_in_cooldown(self) -> None:
        """クールダウンチェックテスト."""
        manager = AutoRecoveryManager()

        # クールダウン中でない場合
        assert not manager._is_in_cooldown("test_action")

        # クールダウンを設定
        import time
        manager.cooldown_timers["test_action"] = time.time() + 10

        # クールダウン中の場合
        assert manager._is_in_cooldown("test_action")

    def test_set_cooldown(self) -> None:
        """クールダウン設定テスト."""
        manager = AutoRecoveryManager()

        manager._set_cooldown("test_action", 30)

        assert "test_action" in manager.cooldown_timers
        assert manager.cooldown_timers["test_action"] > 0

    def test_get_recovery_history(self) -> None:
        """回復履歴取得テスト."""
        manager = AutoRecoveryManager()

        # 空の履歴
        history = manager.get_recovery_history()
        assert history == []

        # 履歴を追加
        from refnet_shared.utils.auto_recovery import RecoveryActionType, RecoveryResult, RecoveryStatus
        manager.recovery_history.append(
            RecoveryResult(
                action_type=RecoveryActionType.RESTART_SERVICE,
                name="test_action",
                status=RecoveryStatus.SUCCESS,
                attempts=1,
                duration=1.0
            )
        )

        history = manager.get_recovery_history()
        assert len(history) == 1
        assert history[0].name == "test_action"

    def test_get_recovery_statistics(self) -> None:
        """回復統計取得テスト."""
        manager = AutoRecoveryManager()

        # Empty history should return empty dict
        stats = manager.get_recovery_statistics()
        assert isinstance(stats, dict)
        assert stats == {}

        # Add some history and test again
        from refnet_shared.utils.auto_recovery import RecoveryActionType, RecoveryResult, RecoveryStatus
        manager.recovery_history.append(
            RecoveryResult(
                action_type=RecoveryActionType.RESTART_SERVICE,
                name="test_action",
                status=RecoveryStatus.SUCCESS,
                attempts=1,
                duration=1.0
            )
        )

        stats = manager.get_recovery_statistics()
        assert isinstance(stats, dict)
        assert "total_actions" in stats
        assert "success_rate" in stats


class TestCheckSystemHealth:
    """check_system_health関数のテスト."""

    @patch("refnet_shared.utils.auto_recovery.psutil.cpu_percent")
    @patch("refnet_shared.utils.auto_recovery.psutil.virtual_memory")
    @patch("refnet_shared.utils.auto_recovery.psutil.disk_usage")
    def test_check_system_health_normal(self, mock_disk: MagicMock, mock_memory: MagicMock, mock_cpu: MagicMock) -> None:
        """システム正常テスト."""
        mock_cpu.return_value = 30.0
        mock_memory.return_value = MagicMock(percent=50.0)
        mock_disk.return_value = MagicMock(total=1000, used=400)

        with patch("refnet_shared.utils.auto_recovery.create_engine") as mock_engine:
            mock_engine.return_value.connect.return_value.__enter__.return_value = MagicMock()

            result = check_system_health()

            assert isinstance(result, dict)
            assert "cpu_usage" in result
            assert "memory_usage" in result
            assert "disk_usage" in result

    @patch("refnet_shared.utils.auto_recovery.psutil.cpu_percent")
    @patch("refnet_shared.utils.auto_recovery.psutil.virtual_memory")
    @patch("refnet_shared.utils.auto_recovery.psutil.disk_usage")
    def test_check_system_health_high_usage(self, mock_disk: MagicMock, mock_memory: MagicMock, mock_cpu: MagicMock) -> None:
        """システム高負荷テスト."""
        mock_cpu.return_value = 95.0
        mock_memory.return_value = MagicMock(percent=90.0)
        mock_disk.return_value = MagicMock(total=1000, used=850)

        with patch("refnet_shared.utils.auto_recovery.create_engine") as mock_engine:
            mock_engine.return_value.connect.return_value.__enter__.return_value = MagicMock()

            result = check_system_health()

            assert isinstance(result, dict)
            assert result["cpu_usage"] == 95.0
            assert result["memory_usage"] == 90.0
            assert result["disk_usage"] == 85.0


class TestTriggerRecovery:
    """trigger_recovery関数のテスト."""

    @pytest.mark.asyncio
    @patch("refnet_shared.utils.auto_recovery._auto_recovery_manager")
    async def test_trigger_recovery_success(self, mock_manager: MagicMock) -> None:
        """回復トリガー成功テスト."""
        mock_manager.execute_recovery = AsyncMock(return_value=[])

        result = await trigger_recovery("database_connection_failed", {"error": "test"})

        assert isinstance(result, list)
        mock_manager.execute_recovery.assert_called_once_with("database_connection_failed", {"error": "test"})

    @pytest.mark.asyncio
    @patch("refnet_shared.utils.auto_recovery._auto_recovery_manager")
    async def test_trigger_recovery_with_context(self, mock_manager: MagicMock) -> None:
        """コンテキスト付き回復トリガーテスト."""
        mock_manager.execute_recovery = AsyncMock(return_value=[])

        context = {"severity": "high", "source": "test"}
        result = await trigger_recovery("high_memory", context)

        assert isinstance(result, list)
        mock_manager.execute_recovery.assert_called_once_with("high_memory", context)


class TestGetAutoRecoveryManager:
    """get_auto_recovery_manager関数のテスト."""

    def test_get_auto_recovery_manager_singleton(self) -> None:
        """シングルトンテスト."""
        manager1 = get_auto_recovery_manager()
        manager2 = get_auto_recovery_manager()

        assert manager1 is manager2
        assert isinstance(manager1, AutoRecoveryManager)

    def test_get_auto_recovery_manager_type(self) -> None:
        """マネージャータイプテスト."""
        manager = get_auto_recovery_manager()

        assert hasattr(manager, "execute_recovery")
        assert hasattr(manager, "get_recovery_history")
        assert hasattr(manager, "get_recovery_statistics")
