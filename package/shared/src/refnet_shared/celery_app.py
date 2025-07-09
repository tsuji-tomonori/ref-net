"""Celery アプリケーション設定."""

import structlog
from celery import Celery
from celery.schedules import crontab

from refnet_shared.config.environment import load_environment_settings

logger = structlog.get_logger(__name__)
settings = load_environment_settings()

# Celeryアプリケーション作成
celery_app = Celery(
    "refnet",
    broker=settings.celery_broker_url or settings.redis.url,
    backend=settings.celery_result_backend or settings.redis.url,
    include=["refnet_shared.tasks.scheduled_tasks", "refnet_crawler.tasks", "refnet_summarizer.tasks", "refnet_generator.tasks"],
)

# Celery設定
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Tokyo",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1時間
    task_soft_time_limit=3300,  # 55分
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    # スケジュール設定
    beat_schedule={
        # 論文データ収集（毎日 2:00）
        "daily-paper-collection": {
            "task": "refnet.scheduled.collect_new_papers",
            "schedule": crontab(hour=2, minute=0),
            "kwargs": {"max_papers": 100},
        },
        # 要約生成（毎日 3:00）
        "daily-summarization": {
            "task": "refnet.scheduled.process_pending_summaries",
            "schedule": crontab(hour=3, minute=0),
            "kwargs": {"batch_size": 50},
        },
        # Markdown生成（毎日 4:00）
        "daily-markdown-generation": {
            "task": "refnet.scheduled.generate_markdown_files",
            "schedule": crontab(hour=4, minute=0),
            "kwargs": {"batch_size": 100},
        },
        # データベースメンテナンス（毎週日曜 1:00）
        "weekly-db-maintenance": {
            "task": "refnet.scheduled.database_maintenance",
            "schedule": crontab(hour=1, minute=0, day_of_week=0),
        },
        # システムヘルスチェック（30分毎）
        "system-health-check": {
            "task": "refnet.scheduled.system_health_check",
            "schedule": crontab(minute="*/30"),
        },
        # ログクリーンアップ（毎日 0:30）
        "daily-log-cleanup": {"task": "refnet.scheduled.cleanup_old_logs", "schedule": crontab(hour=0, minute=30), "kwargs": {"days_to_keep": 30}},
        # データバックアップ（毎日 1:00、本番環境のみ）
        "daily-backup": {"task": "refnet.scheduled.backup_database", "schedule": crontab(hour=1, minute=0), "options": {"queue": "backup"}}
        if settings.is_production()
        else {},
        # 統計レポート生成（毎週月曜 8:00）
        "weekly-stats-report": {
            "task": "refnet.scheduled.generate_stats_report",
            "schedule": crontab(hour=8, minute=0, day_of_week=1),
        },
    },
)


@celery_app.task(bind=True)
def debug_task(self):
    """デバッグタスク."""
    print(f"Request: {self.request!r}")
