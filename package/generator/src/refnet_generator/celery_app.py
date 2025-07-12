"""Generatorサービス用Celeryアプリケーション."""

from refnet_shared.celery_app import app

# 共有アプリケーションを使用
celery_app = app
