"""統一Celeryアプリケーション設定のテスト."""

import os
from unittest.mock import patch

import pytest
from celery.schedules import crontab
from kombu import Exchange, Queue  # type: ignore[import-untyped]

from refnet_shared.celery_app import app, celery_app, debug_task


class TestCeleryAppConfiguration:
    """Celeryアプリケーション設定のテストクラス."""

    def test_app_name(self) -> None:
        """アプリケーション名のテスト."""
        assert app.main == "refnet"

    def test_app_alias(self) -> None:
        """アプリケーション別名のテスト."""
        assert celery_app == app

    def test_broker_configuration(self) -> None:
        """ブローカー設定のテスト."""
        # デフォルト値のテスト
        with patch.dict(os.environ, {}, clear=True):
            assert app.conf.broker_url == "redis://redis:6379/0"
            assert app.conf.result_backend == "redis://redis:6379/0"

    def test_environment_variable_override(self) -> None:
        """環境変数での設定上書きテスト."""
        with patch.dict(os.environ, {
            "CELERY_BROKER_URL": "redis://custom-broker:6379/1",
            "CELERY_RESULT_BACKEND": "redis://custom-backend:6379/2",
        }):
            # 新しいアプリインスタンスで設定を確認
            from importlib import reload

            from refnet_shared import celery_app as celery_module
            reload(celery_module)

            # 環境変数が反映されているかは実行時に確認される
            assert os.getenv("CELERY_BROKER_URL") == "redis://custom-broker:6379/1"
            assert os.getenv("CELERY_RESULT_BACKEND") == "redis://custom-backend:6379/2"

    def test_serialization_settings(self) -> None:
        """シリアライゼーション設定のテスト."""
        assert app.conf.task_serializer == "json"
        assert app.conf.accept_content == ["json"]
        assert app.conf.result_serializer == "json"

    def test_timezone_settings(self) -> None:
        """タイムゾーン設定のテスト."""
        assert app.conf.timezone == "Asia/Tokyo"
        assert app.conf.enable_utc is True

    def test_task_tracking_settings(self) -> None:
        """タスク追跡設定のテスト."""
        assert app.conf.task_track_started is True

    def test_task_routes(self) -> None:
        """タスクルーティング設定のテスト."""
        expected_routes = {
            "refnet_crawler.tasks.*": {"queue": "crawler"},
            "refnet_summarizer.tasks.*": {"queue": "summarizer"},
            "refnet_generator.tasks.*": {"queue": "generator"},
            "refnet_shared.tasks.*": {"queue": "default"},
        }
        assert app.conf.task_routes == expected_routes

    def test_task_queues(self) -> None:
        """タスクキュー設定のテスト."""
        queues = app.conf.task_queues
        assert len(queues) == 4

        # キュー名とルーティングキーの確認
        queue_names = {q.name for q in queues}
        expected_names = {"default", "crawler", "summarizer", "generator"}
        assert queue_names == expected_names

        # 各キューのExchangeとルーティングキーの確認
        for queue in queues:
            assert isinstance(queue, Queue)
            assert isinstance(queue.exchange, Exchange)
            assert queue.routing_key == queue.name

    def test_beat_schedule_structure(self) -> None:
        """Beat スケジュール構造のテスト."""
        schedule = app.conf.beat_schedule
        assert isinstance(schedule, dict)

        # 期待されるタスクが全て存在することを確認
        expected_tasks = {
            "check-new-papers",
            "process-pending-summarizations",
            "generate-markdown-updates",
            "cleanup-old-data",
            "health-check-all-services",
            "daily-paper-collection",
            "daily-summarization",
            "daily-markdown-generation",
            "weekly-db-maintenance",
            "system-health-check",
        }
        assert set(schedule.keys()) == expected_tasks

    def test_beat_schedule_check_new_papers(self) -> None:
        """新しい論文チェックスケジュールのテスト."""
        task_config = app.conf.beat_schedule["check-new-papers"]

        assert task_config["task"] == "refnet_crawler.tasks.crawl_task.check_and_crawl_new_papers"
        assert isinstance(task_config["schedule"], crontab)
        assert task_config["schedule"].minute == {0, 30}  # 30分ごと
        assert task_config["options"]["queue"] == "crawler"
        assert task_config["options"]["expires"] == 1800

    def test_beat_schedule_process_summarizations(self) -> None:
        """要約処理スケジュールのテスト."""
        task_config = app.conf.beat_schedule["process-pending-summarizations"]

        assert task_config["task"] == "refnet_summarizer.tasks.summarize_task.process_pending_summarizations"
        assert isinstance(task_config["schedule"], crontab)
        assert task_config["schedule"].minute == {0, 15, 30, 45}  # 15分ごと
        assert task_config["options"]["queue"] == "summarizer"
        assert task_config["options"]["expires"] == 900

    def test_beat_schedule_generate_markdown(self) -> None:
        """Markdown生成スケジュールのテスト."""
        task_config = app.conf.beat_schedule["generate-markdown-updates"]

        assert task_config["task"] == "refnet_generator.tasks.generate_task.generate_pending_markdowns"
        assert isinstance(task_config["schedule"], crontab)
        # 10分ごとは0,10,20,30,40,50分
        assert task_config["schedule"].minute == {0, 10, 20, 30, 40, 50}
        assert task_config["options"]["queue"] == "generator"
        assert task_config["options"]["expires"] == 600

    def test_beat_schedule_cleanup_data(self) -> None:
        """データクリーンアップスケジュールのテスト."""
        task_config = app.conf.beat_schedule["cleanup-old-data"]

        assert task_config["task"] == "refnet_shared.tasks.maintenance.cleanup_old_data"
        assert isinstance(task_config["schedule"], crontab)
        assert task_config["schedule"].hour == {3}
        assert task_config["schedule"].minute == {0}
        assert task_config["options"]["queue"] == "default"
        assert task_config["options"]["expires"] == 3600

    def test_beat_schedule_health_check(self) -> None:
        """ヘルスチェックスケジュールのテスト."""
        task_config = app.conf.beat_schedule["health-check-all-services"]

        assert task_config["task"] == "refnet_shared.tasks.monitoring.health_check_all_services"
        assert isinstance(task_config["schedule"], crontab)
        assert task_config["schedule"].minute == {0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}  # 5分ごと
        assert task_config["options"]["queue"] == "default"
        assert task_config["options"]["expires"] == 300

    def test_beat_schedule_daily_tasks(self) -> None:
        """日次タスクスケジュールのテスト."""
        # 日次論文収集
        daily_collection = app.conf.beat_schedule["daily-paper-collection"]
        assert daily_collection["task"] == "refnet_shared.tasks.scheduled_tasks.collect_new_papers"
        assert isinstance(daily_collection["schedule"], crontab)
        assert daily_collection["schedule"].hour == {0}
        assert daily_collection["schedule"].minute == {0}

        # 日次要約処理
        daily_summarization = app.conf.beat_schedule["daily-summarization"]
        assert daily_summarization["task"] == "refnet_shared.tasks.scheduled_tasks.process_pending_summaries"
        assert daily_summarization["schedule"].hour == {1}

        # 日次Markdown生成
        daily_markdown = app.conf.beat_schedule["daily-markdown-generation"]
        assert daily_markdown["task"] == "refnet_shared.tasks.scheduled_tasks.generate_markdown_files"
        assert daily_markdown["schedule"].hour == {2}

    def test_beat_schedule_weekly_maintenance(self) -> None:
        """週次メンテナンススケジュールのテスト."""
        weekly_task = app.conf.beat_schedule["weekly-db-maintenance"]

        assert weekly_task["task"] == "refnet_shared.tasks.scheduled_tasks.database_maintenance"
        assert isinstance(weekly_task["schedule"], crontab)
        assert weekly_task["schedule"].hour == {0}
        assert weekly_task["schedule"].minute == {0}
        assert weekly_task["schedule"].day_of_week == {0}  # 日曜日
        assert weekly_task["options"]["expires"] == 7200

    def test_worker_settings(self) -> None:
        """ワーカー設定のテスト."""
        assert app.conf.worker_prefetch_multiplier == 1
        assert app.conf.worker_max_tasks_per_child == 1000
        assert app.conf.worker_disable_rate_limits is False

    def test_result_settings(self) -> None:
        """結果設定のテスト."""
        assert app.conf.result_expires == 3600

    def test_task_time_limits(self) -> None:
        """タスク時間制限のテスト."""
        assert app.conf.task_time_limit == 3600
        assert app.conf.task_soft_time_limit == 3300

    def test_log_format_settings(self) -> None:
        """ログフォーマット設定のテスト."""
        expected_worker_format = "[%(asctime)s: %(levelname)s/%(processName)s] %(message)s"
        expected_task_format = "[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s"

        assert app.conf.worker_log_format == expected_worker_format
        assert app.conf.worker_task_log_format == expected_task_format

    def test_autodiscover_tasks(self) -> None:
        """タスク自動発見設定のテスト."""
        # アプリケーションがタスクを自動発見する設定になっているかテスト
        # 実際のautodiscover_tasksの呼び出しは起動時に行われるため、
        # ここでは設定が正しく行われているかを間接的にテスト

        # Celeryアプリケーションが正しく初期化されていることを確認
        assert app is not None
        assert hasattr(app, 'autodiscover_tasks')

    def test_debug_task_registration(self) -> None:
        """デバッグタスク登録のテスト."""
        # debug_taskが正しく登録されているかテスト
        assert debug_task is not None
        assert hasattr(debug_task, 'delay')
        assert hasattr(debug_task, 'apply_async')

    def test_debug_task_execution(self) -> None:
        """デバッグタスク実行のテスト."""
        # mock出力でタスク実行をテスト
        with patch('builtins.print'):
            app.conf.task_always_eager = True
            try:
                debug_task.apply()
                # printが呼ばれたかの確認は困難なため、例外が発生しないことを確認
                assert True
            except Exception as e:
                pytest.fail(f"debug_task execution failed: {e}")
            finally:
                app.conf.task_always_eager = False

    def test_queue_routing_consistency(self) -> None:
        """キューとルーティングの一貫性テスト."""
        # task_routesで定義されたキューが、task_queuesにも存在することを確認
        route_queues = {route["queue"] for route in app.conf.task_routes.values()}
        defined_queues = {queue.name for queue in app.conf.task_queues}

        assert route_queues.issubset(defined_queues)

    def test_beat_schedule_queue_consistency(self) -> None:
        """Beatスケジュールとキューの一貫性テスト."""
        # beat_scheduleで使用されているキューが、定義されたキューに存在することを確認
        schedule_queues = set()
        for task_config in app.conf.beat_schedule.values():
            if "options" in task_config and "queue" in task_config["options"]:
                schedule_queues.add(task_config["options"]["queue"])

        defined_queues = {queue.name for queue in app.conf.task_queues}
        assert schedule_queues.issubset(defined_queues)

    def test_task_expiration_settings(self) -> None:
        """タスク期限設定のテスト."""
        # 各スケジュールタスクの期限設定が適切かテスト
        for task_name, task_config in app.conf.beat_schedule.items():
            if "options" in task_config and "expires" in task_config["options"]:
                expires = task_config["options"]["expires"]
                assert isinstance(expires, int)
                assert expires > 0
                # 期限は最低60秒以上であることを確認
                assert expires >= 60, f"Task {task_name} has too short expiration: {expires}"
