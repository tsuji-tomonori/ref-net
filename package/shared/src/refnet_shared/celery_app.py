"""統一されたCeleryアプリケーション設定."""

import os
from typing import Any

import structlog
from celery import Celery
from celery.schedules import crontab
from kombu import Exchange, Queue  # type: ignore[import-untyped]

from refnet_shared.config.environment import load_environment_settings

logger = structlog.get_logger(__name__)
settings = load_environment_settings()

# Celeryアプリケーション作成
app = Celery("refnet")

# Celery設定
app.conf.update(
    broker_url=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
    result_backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0"),
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Tokyo",
    enable_utc=True,
    task_track_started=True,  # タスクの開始時刻を記録
    # タスクルーティング
    task_routes={
        "refnet_crawler.tasks.*": {"queue": "crawler"},
        "refnet_summarizer.tasks.*": {"queue": "summarizer"},
        "refnet_generator.tasks.*": {"queue": "generator"},
        "refnet_shared.tasks.*": {"queue": "default"},
    },
    # キューの定義
    task_queues=(
        Queue("default", Exchange("default"), routing_key="default"),
        Queue("crawler", Exchange("crawler"), routing_key="crawler"),
        Queue("summarizer", Exchange("summarizer"), routing_key="summarizer"),
        Queue("generator", Exchange("generator"), routing_key="generator"),
    ),
    # Beatスケジュール
    beat_schedule={
        "check-new-papers": {
            "task": "refnet_crawler.tasks.crawl_task.check_and_crawl_new_papers",
            "schedule": crontab(minute="*/30"),  # 30分ごと
            "options": {
                "queue": "crawler",
                "expires": 1800,  # 30分で期限切れ
            },
        },
        "process-pending-summarizations": {
            "task": "refnet_summarizer.tasks.summarize_task.process_pending_summarizations",
            "schedule": crontab(minute="*/15"),  # 15分ごと
            "options": {
                "queue": "summarizer",
                "expires": 900,  # 15分で期限切れ
            },
        },
        "generate-markdown-updates": {
            "task": "refnet_generator.tasks.generate_task.generate_pending_markdowns",
            "schedule": crontab(minute="*/10"),  # 10分ごと
            "options": {
                "queue": "generator",
                "expires": 600,  # 10分で期限切れ
            },
        },
        "cleanup-old-data": {
            "task": "refnet_shared.tasks.maintenance.cleanup_old_data",
            "schedule": crontab(hour=3, minute=0),  # 毎日午前3時
            "options": {
                "queue": "default",
                "expires": 3600,  # 1時間で期限切れ
            },
        },
        "health-check-all-services": {
            "task": "refnet_shared.tasks.monitoring.health_check_all_services",
            "schedule": crontab(minute="*/5"),  # 5分ごと
            "options": {
                "queue": "default",
                "expires": 300,  # 5分で期限切れ
            },
        },
        # 既存のテストで期待されるタスク
        "daily-paper-collection": {
            "task": "refnet_shared.tasks.scheduled_tasks.collect_new_papers",
            "schedule": crontab(hour=0, minute=0),  # 毎日午前0時
            "options": {
                "queue": "default",
                "expires": 3600,
            },
        },
        "daily-summarization": {
            "task": "refnet_shared.tasks.scheduled_tasks.process_pending_summaries",
            "schedule": crontab(hour=1, minute=0),  # 毎日午前1時
            "options": {
                "queue": "default",
                "expires": 3600,
            },
        },
        "daily-markdown-generation": {
            "task": "refnet_shared.tasks.scheduled_tasks.generate_markdown_files",
            "schedule": crontab(hour=2, minute=0),  # 毎日午前2時
            "options": {
                "queue": "default",
                "expires": 3600,
            },
        },
        "weekly-db-maintenance": {
            "task": "refnet_shared.tasks.scheduled_tasks.database_maintenance",
            "schedule": crontab(hour=0, minute=0, day_of_week=0),  # 毎週日曜日午前0時
            "options": {
                "queue": "default",
                "expires": 7200,
            },
        },
        "system-health-check": {
            "task": "refnet_shared.tasks.scheduled_tasks.system_health_check",
            "schedule": crontab(minute="*/30"),  # 30分ごと
            "options": {
                "queue": "default",
                "expires": 1800,
            },
        },
    },
    # 結果の有効期限
    result_expires=3600,  # 1時間
    # タスクの実行時間制限
    task_time_limit=3600,  # 1時間
    task_soft_time_limit=3300,  # 55分
    # ワーカー設定
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    worker_disable_rate_limits=False,
    # ログ設定
    worker_log_format="[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
    worker_task_log_format="[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s",
)


# タスクの自動発見
app.autodiscover_tasks(
    [
        "refnet_crawler.tasks",
        "refnet_summarizer.tasks",
        "refnet_generator.tasks",
        "refnet_shared.tasks",
    ]
)

# 後方互換性のため
celery_app = app


@app.task(bind=True)  # type: ignore[misc]
def debug_task(self: Any) -> None:
    """デバッグタスク."""
    print(f"Request: {self.request!r}")
