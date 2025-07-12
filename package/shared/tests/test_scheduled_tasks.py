"""scheduled_tasksモジュールのテスト."""

from unittest.mock import MagicMock, patch

import pytest

from refnet_shared.tasks.scheduled_tasks import (
    CallbackTask,
    backup_database,
    cleanup_old_logs,
    collect_new_papers,
    database_maintenance,
    generate_markdown_files,
    generate_stats_report,
    process_pending_summaries,
    system_health_check,
)


class TestCallbackTask:
    """CallbackTaskクラスのテスト."""

    def test_on_success(self) -> None:
        """on_success正常系テスト."""
        task = CallbackTask()
        task.name = "test_task"

        # 例外が発生しないことを確認
        try:
            task.on_success("result", "task-123", [], {})
        except Exception as e:
            pytest.fail(f"on_success failed: {e}")

    def test_on_failure(self) -> None:
        """on_failure正常系テスト."""
        task = CallbackTask()

        # 例外が発生しないことを確認
        try:
            task.on_failure(Exception("Test error"), "task-123", [], {}, None)
        except Exception as e:
            pytest.fail(f"on_failure failed: {e}")


class TestCollectNewPapers:
    """collect_new_papersのテスト."""

    @patch("refnet_shared.tasks.scheduled_tasks.db_manager")
    def test_collect_new_papers_success(self, mock_db: MagicMock) -> None:
        """論文収集成功テスト."""
        mock_session = MagicMock()
        mock_db.get_session.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter.return_value.limit.return_value.all.return_value = []

        result = collect_new_papers(max_papers=5)

        assert result["status"] == "success"
        assert "papers_scheduled" in result

    @patch("refnet_shared.tasks.scheduled_tasks.db_manager")
    def test_collect_new_papers_with_papers(self, mock_db: MagicMock) -> None:
        """論文収集（論文あり）テスト."""
        mock_session = MagicMock()
        mock_db.get_session.return_value.__enter__.return_value = mock_session

        # モック論文データ
        mock_papers = [MagicMock(paper_id=f"paper-{i}") for i in range(3)]
        mock_session.query.return_value.filter.return_value.limit.return_value.all.return_value = mock_papers

        # The function will catch ImportError and continue
        result = collect_new_papers(max_papers=5)

        assert result["status"] == "success"
        assert result["papers_scheduled"] == 0  # Due to ImportError handling


class TestProcessPendingSummaries:
    """process_pending_summariesのテスト."""

    @patch("refnet_shared.tasks.scheduled_tasks.db_manager")
    def test_process_pending_summaries_success(self, mock_db: MagicMock) -> None:
        """要約処理成功テスト."""
        mock_session = MagicMock()
        mock_db.get_session.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter.return_value.limit.return_value.all.return_value = []

        result = process_pending_summaries(batch_size=5)

        assert result["status"] == "success"
        assert "summaries_scheduled" in result


class TestGenerateMarkdownFiles:
    """generate_markdown_filesのテスト."""

    @patch("refnet_shared.tasks.scheduled_tasks.db_manager")
    def test_generate_markdown_files_success(self, mock_db: MagicMock) -> None:
        """Markdown生成成功テスト."""
        mock_session = MagicMock()
        mock_db.get_session.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter.return_value.limit.return_value.all.return_value = []

        result = generate_markdown_files(batch_size=5)

        assert result["status"] == "success"
        assert "markdown_files_scheduled" in result


class TestDatabaseMaintenance:
    """database_maintenanceのテスト."""

    @patch("refnet_shared.tasks.scheduled_tasks.db_manager")
    def test_database_maintenance_success(self, mock_db: MagicMock) -> None:
        """データベースメンテナンス成功テスト."""
        mock_session = MagicMock()
        mock_db.get_session.return_value.__enter__.return_value = mock_session

        # VACUUMとANALYZE操作をモック
        mock_session.execute.return_value = None

        # Query chain for delete operation
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.delete.return_value = 5  # Mock deleted items count

        result = database_maintenance()

        assert result["status"] == "success"
        assert "maintenance_tasks" in result
        mock_session.execute.assert_called()

    @patch("refnet_shared.tasks.scheduled_tasks.db_manager")
    def test_database_maintenance_exception(self, mock_db: MagicMock) -> None:
        """データベースメンテナンス例外テスト."""
        mock_db.get_session.side_effect = Exception("Database error")

        result = database_maintenance()

        assert result["status"] == "error"
        assert "Database error" in result["error"]


class TestSystemHealthCheck:
    """system_health_checkのテスト."""

    @patch("refnet_shared.tasks.scheduled_tasks.db_manager")
    @patch("refnet_shared.tasks.scheduled_tasks.MetricsCollector.update_paper_counts")
    def test_system_health_check_healthy(self, mock_metrics: MagicMock, mock_db: MagicMock) -> None:
        """システムヘルスチェック正常テスト."""
        mock_session = MagicMock()
        mock_db.get_session.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.count.return_value = 100
        mock_session.query.return_value.filter.return_value.count.return_value = 50

        with patch("refnet_shared.middleware.rate_limiter.rate_limiter") as mock_rate_limiter:
            mock_rate_limiter.redis_client.ping.return_value = True

            result = system_health_check()

            assert result["overall_status"] == "healthy"
            assert "services" in result

    @patch("refnet_shared.tasks.scheduled_tasks.db_manager")
    def test_system_health_check_unhealthy(self, mock_db: MagicMock) -> None:
        """システムヘルスチェック異常テスト."""
        mock_db.get_session.side_effect = Exception("Database error")

        result = system_health_check()

        assert result["status"] == "error"
        assert "Database error" in result["error"]


class TestBackupDatabase:
    """backup_databaseのテスト."""

    @patch("refnet_shared.config.environment.load_environment_settings")
    @patch("refnet_shared.tasks.scheduled_tasks.subprocess.run")
    @patch("refnet_shared.tasks.scheduled_tasks.Path")
    def test_backup_database_production(self, mock_path: MagicMock, mock_run: MagicMock, mock_settings: MagicMock) -> None:
        """本番環境バックアップテスト."""
        mock_settings.return_value.is_production.return_value = True
        mock_settings.return_value.database.host = "localhost"
        mock_settings.return_value.database.port = 5432
        mock_settings.return_value.database.username = "user"
        mock_settings.return_value.database.database = "refnet"
        mock_settings.return_value.database.password = "pass"

        mock_run.return_value = MagicMock(returncode=0)
        mock_path.return_value.stat.return_value.st_size = 1024

        result = backup_database()

        assert result["status"] == "success"
        mock_run.assert_called_once()

    @patch("refnet_shared.config.environment.load_environment_settings")
    def test_backup_database_non_production(self, mock_settings: MagicMock) -> None:
        """非本番環境バックアップテスト."""
        mock_settings.return_value.is_production.return_value = False

        result = backup_database()

        assert result["status"] == "skipped"
        assert result["reason"] == "non-production environment"

    @patch("refnet_shared.config.environment.load_environment_settings")
    @patch("refnet_shared.tasks.scheduled_tasks.subprocess.run")
    def test_backup_database_failure(self, mock_run: MagicMock, mock_settings: MagicMock) -> None:
        """バックアップ失敗テスト."""
        mock_settings.return_value.is_production.return_value = True
        mock_run.side_effect = Exception("Backup failed")

        result = backup_database()

        assert result["status"] == "error"
        assert "Backup failed" in result["error"]


class TestCleanupOldLogs:
    """cleanup_old_logsのテスト."""

    @patch("glob.glob")
    @patch("os.path.exists")
    def test_cleanup_old_logs_success(self, mock_exists: MagicMock, mock_glob: MagicMock) -> None:
        """ログクリーンアップ成功テスト."""
        mock_exists.return_value = True
        mock_glob.return_value = ["/var/log/test.log"]

        with patch("refnet_shared.tasks.scheduled_tasks.Path") as mock_path:
            # Mock path object for file operations
            mock_file_path = MagicMock()
            mock_file_path.stat.return_value.st_mtime = 1000000  # Old timestamp
            mock_file_path.stat.return_value.st_size = 1024  # File size
            mock_path.return_value = mock_file_path

            with patch("refnet_shared.tasks.scheduled_tasks.datetime") as mock_datetime:
                # Mock datetime for comparison
                mock_datetime.utcnow.return_value = MagicMock()
                mock_datetime.fromtimestamp.return_value = MagicMock()
                # Make the comparison return True (old file)
                mock_datetime.fromtimestamp.return_value.__lt__ = MagicMock(return_value=True)

                result = cleanup_old_logs(days_to_keep=7)

            assert result["status"] == "success"
            assert result["files_cleaned"] == 3

    @patch("refnet_shared.tasks.scheduled_tasks.Path")
    def test_cleanup_old_logs_no_files(self, mock_path: MagicMock) -> None:
        """ログクリーンアップ（ファイルなし）テスト."""
        mock_path.return_value.glob.return_value = []

        result = cleanup_old_logs(days_to_keep=7)

        assert result["status"] == "success"
        assert result["files_cleaned"] == 0


class TestGenerateStatsReport:
    """generate_stats_reportのテスト."""

    @patch("refnet_shared.tasks.scheduled_tasks.db_manager")
    @patch("builtins.open", create=True)
    @patch("refnet_shared.tasks.scheduled_tasks.os.makedirs")
    def test_generate_stats_report_success(self, mock_makedirs: MagicMock, mock_open: MagicMock, mock_db: MagicMock) -> None:
        """統計レポート生成成功テスト."""
        mock_session = MagicMock()
        mock_db.get_session.return_value.__enter__.return_value = mock_session

        # Mock query chains for different counts
        mock_count_query = MagicMock()
        mock_count_query.count.return_value = 100
        mock_session.query.return_value = mock_count_query

        mock_filter_query = MagicMock()
        mock_filter_query.count.return_value = 50
        mock_count_query.filter.return_value = mock_filter_query

        # Mock year stats query
        mock_session.query.return_value.group_by.return_value.all.return_value = [(2023, 50), (2024, 50)]

        # Mock file operations
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file

        result = generate_stats_report()

        assert result["status"] == "success"
        assert "stats" in result
        assert "report_file" in result

    @patch("refnet_shared.tasks.scheduled_tasks.db_manager")
    def test_generate_stats_report_exception(self, mock_db: MagicMock) -> None:
        """統計レポート生成例外テスト."""
        mock_db.get_session.side_effect = Exception("Stats error")

        result = generate_stats_report()

        assert result["status"] == "error"
        assert "Stats error" in result["error"]
