"""共有Celeryタスク."""

from refnet_shared.celery_app import app

# タスクモジュールの登録
__all__ = ["app"]
