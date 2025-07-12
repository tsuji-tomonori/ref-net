"""Celeryアプリケーションのテスト."""

from celery import Celery  # type: ignore[import-untyped]

from refnet_generator.celery_app import celery_app


class TestCeleryApp:
    """Celeryアプリケーションのテストクラス."""

    def test_celery_app_is_instance(self) -> None:
        """Celeryアプリケーションインスタンスが正しく作成されているかテスト."""
        assert isinstance(celery_app, Celery)
        assert celery_app.main == "refnet"

    def test_celery_app_config(self) -> None:
        """Celeryアプリケーションの設定が正しいかテスト."""
        config = celery_app.conf
        assert config.broker_url == "redis://redis:6379/0"
        assert config.result_backend == "redis://redis:6379/0"
        assert config.task_serializer == "json"
        assert config.result_serializer == "json"
        assert config.timezone == "Asia/Tokyo"
        assert config.enable_utc is True

    def test_celery_app_task_routes(self) -> None:
        """タスクルーティングが正しく設定されているかテスト."""
        routes = celery_app.conf.task_routes
        assert "refnet_generator.tasks.*" in routes
        assert routes["refnet_generator.tasks.*"]["queue"] == "generator"

    def test_celery_app_registered_tasks(self) -> None:
        """タスクが正しく登録されているかテスト."""
        # 統一Celeryアプリから登録されたタスクを確認
        tasks = celery_app.tasks
        assert "refnet_generator.tasks.generate_task.generate_pending_markdowns" in tasks
        assert "refnet_generator.tasks.generate_task.generate_markdown" in tasks
