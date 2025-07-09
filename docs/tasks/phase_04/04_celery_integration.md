# Phase 4-04: Celery統合設定

## 目的
分散した各サービスのCeleryアプリケーションを統合し、Beat/Flowerを含む完全なCeleryシステムを構築する。

## 問題点
- 各サービスで個別にCeleryアプリケーションが定義されている
- 統一されたBeatスケジュール設定がない
- タスクの登録と発見メカニズムが不完全
- Dockerfile.beatとDockerfile.flowerが存在しない

## 実装内容

### 1. 統一Celeryアプリケーション

#### package/shared/src/refnet_shared/celery_app.py
```python
"""
統一されたCeleryアプリケーション設定
"""
import os
from celery import Celery
from celery.schedules import crontab
from kombu import Queue, Exchange

# Celeryアプリケーションの作成
app = Celery('refnet')

# 設定
app.conf.update(
    broker_url=os.getenv('CELERY_BROKER_URL', 'redis://redis:6379/0'),
    result_backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://redis:6379/0'),
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Tokyo',
    enable_utc=True,

    # タスクルーティング
    task_routes={
        'refnet_crawler.tasks.*': {'queue': 'crawler'},
        'refnet_summarizer.tasks.*': {'queue': 'summarizer'},
        'refnet_generator.tasks.*': {'queue': 'generator'},
        'refnet_shared.tasks.*': {'queue': 'default'},
    },

    # キューの定義
    task_queues=(
        Queue('default', Exchange('default'), routing_key='default'),
        Queue('crawler', Exchange('crawler'), routing_key='crawler'),
        Queue('summarizer', Exchange('summarizer'), routing_key='summarizer'),
        Queue('generator', Exchange('generator'), routing_key='generator'),
    ),

    # Beatスケジュール
    beat_schedule={
        'check-new-papers': {
            'task': 'refnet_crawler.tasks.crawl_task.check_and_crawl_new_papers',
            'schedule': crontab(minute='*/30'),  # 30分ごと
            'options': {
                'queue': 'crawler',
                'expires': 1800,  # 30分で期限切れ
            }
        },
        'process-pending-summarizations': {
            'task': 'refnet_summarizer.tasks.summarize_task.process_pending_summarizations',
            'schedule': crontab(minute='*/15'),  # 15分ごと
            'options': {
                'queue': 'summarizer',
                'expires': 900,  # 15分で期限切れ
            }
        },
        'generate-markdown-updates': {
            'task': 'refnet_generator.tasks.generate_task.generate_pending_markdowns',
            'schedule': crontab(minute='*/10'),  # 10分ごと
            'options': {
                'queue': 'generator',
                'expires': 600,  # 10分で期限切れ
            }
        },
        'cleanup-old-data': {
            'task': 'refnet_shared.tasks.maintenance.cleanup_old_data',
            'schedule': crontab(hour=3, minute=0),  # 毎日午前3時
            'options': {
                'queue': 'default',
                'expires': 3600,  # 1時間で期限切れ
            }
        },
        'health-check-all-services': {
            'task': 'refnet_shared.tasks.monitoring.health_check_all_services',
            'schedule': crontab(minute='*/5'),  # 5分ごと
            'options': {
                'queue': 'default',
                'expires': 300,  # 5分で期限切れ
            }
        },
    },

    # 結果の有効期限
    result_expires=3600,  # 1時間

    # タスクの実行時間制限
    task_time_limit=3600,  # 1時間
    task_soft_time_limit=3000,  # 50分

    # ワーカー設定
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,
    worker_disable_rate_limits=False,

    # ログ設定
    worker_log_format='[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
    worker_task_log_format='[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s',
)

# タスクの自動発見
app.autodiscover_tasks([
    'refnet_crawler.tasks',
    'refnet_summarizer.tasks',
    'refnet_generator.tasks',
    'refnet_shared.tasks',
])
```

### 2. Dockerfile.beat

#### package/shared/Dockerfile.beat
```dockerfile
FROM python:3.12-slim-bookworm

WORKDIR /app

# システムパッケージのインストール
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 共有パッケージのコピーとインストール
COPY shared/pyproject.toml shared/moon.yml /app/shared/
COPY shared/src /app/shared/src

# 依存関係のインストール
RUN pip install --no-cache-dir -e ./shared

# Celery Beatの実行
CMD ["celery", "-A", "refnet_shared.celery_app", "beat", "--loglevel=info"]
```

### 3. Dockerfile.flower

#### package/shared/Dockerfile.flower
```dockerfile
FROM python:3.12-slim-bookworm

WORKDIR /app

# システムパッケージのインストール
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 共有パッケージのコピーとインストール
COPY shared/pyproject.toml shared/moon.yml /app/shared/
COPY shared/src /app/shared/src

# 依存関係のインストール（Flowerを含む）
RUN pip install --no-cache-dir -e ./shared[monitoring]

# Flowerの実行
CMD ["celery", "-A", "refnet_shared.celery_app", "flower", "--port=5555", "--basic_auth=${FLOWER_USER}:${FLOWER_PASSWORD}"]
```

### 4. 共有タスクモジュール

#### package/shared/src/refnet_shared/tasks/__init__.py
```python
"""共有Celeryタスク"""
from refnet_shared.celery_app import app

# タスクモジュールの登録
__all__ = ['app']
```

#### package/shared/src/refnet_shared/tasks/maintenance.py
```python
"""メンテナンスタスク"""
from datetime import datetime, timedelta
from refnet_shared.celery_app import app
from refnet_shared.database import get_session
from refnet_shared.models import Paper, Author
from sqlalchemy import and_

@app.task(bind=True, name='refnet_shared.tasks.maintenance.cleanup_old_data')
def cleanup_old_data(self):
    """90日以上前の未処理データをクリーンアップ"""
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=90)

        with get_session() as session:
            # 古い未処理論文の削除
            deleted_papers = session.query(Paper).filter(
                and_(
                    Paper.created_at < cutoff_date,
                    Paper.is_processed == False
                )
            ).delete(synchronize_session=False)

            # 参照されていない著者の削除
            orphan_authors = session.query(Author).filter(
                ~Author.papers.any()
            ).delete(synchronize_session=False)

            session.commit()

            return {
                'status': 'success',
                'deleted_papers': deleted_papers,
                'orphan_authors': orphan_authors,
                'timestamp': datetime.utcnow().isoformat()
            }

    except Exception as e:
        self.retry(exc=e, countdown=300, max_retries=3)
```

#### package/shared/src/refnet_shared/tasks/monitoring.py
```python
"""モニタリングタスク"""
import httpx
from refnet_shared.celery_app import app
from datetime import datetime

@app.task(bind=True, name='refnet_shared.tasks.monitoring.health_check_all_services')
def health_check_all_services(self):
    """全サービスのヘルスチェック"""
    services = {
        'api': 'http://api:8000/health',
        'crawler': 'http://crawler:8001/health',
        'summarizer': 'http://summarizer:8002/health',
        'generator': 'http://generator:8003/health',
    }

    results = {}

    for service_name, url in services.items():
        try:
            response = httpx.get(url, timeout=5.0)
            results[service_name] = {
                'status': 'healthy' if response.status_code == 200 else 'unhealthy',
                'status_code': response.status_code,
                'response_time': response.elapsed.total_seconds()
            }
        except Exception as e:
            results[service_name] = {
                'status': 'error',
                'error': str(e)
            }

    results['timestamp'] = datetime.utcnow().isoformat()

    # 異常があればアラート（将来的にSlack通知等）
    unhealthy_services = [s for s, r in results.items() if r.get('status') != 'healthy']
    if unhealthy_services:
        # TODO: アラート実装
        pass

    return results
```

### 5. 各サービスのCeleryアプリケーション更新

#### package/crawler/src/refnet_crawler/celery_app.py
```python
"""Crawlerサービス用Celeryアプリケーション"""
from refnet_shared.celery_app import app

# 共有アプリケーションを使用
celery_app = app
```

#### package/summarizer/src/refnet_summarizer/celery_app.py
```python
"""Summarizerサービス用Celeryアプリケーション"""
from refnet_shared.celery_app import app

# 共有アプリケーションを使用
celery_app = app
```

#### package/generator/src/refnet_generator/celery_app.py
```python
"""Generatorサービス用Celeryアプリケーション"""
from refnet_shared.celery_app import app

# 共有アプリケーションを使用
celery_app = app
```

### 6. タスクの定期実行実装

#### package/crawler/src/refnet_crawler/tasks/crawl_task.py（追加）
```python
@celery_app.task(bind=True, name='refnet_crawler.tasks.crawl_task.check_and_crawl_new_papers')
def check_and_crawl_new_papers(self):
    """新しい論文をチェックしてクロール"""
    try:
        with get_session() as session:
            # 未処理の論文を取得
            pending_papers = session.query(Paper).filter(
                Paper.is_crawled == False
            ).limit(10).all()

            for paper in pending_papers:
                # 非同期でクロールタスクを起動
                crawl_paper.apply_async(
                    args=[paper.paper_id],
                    queue='crawler'
                )

            return {
                'status': 'success',
                'scheduled_papers': len(pending_papers)
            }
    except Exception as e:
        self.retry(exc=e, countdown=60, max_retries=3)
```

#### package/summarizer/src/refnet_summarizer/tasks/summarize_task.py（追加）
```python
@celery_app.task(bind=True, name='refnet_summarizer.tasks.summarize_task.process_pending_summarizations')
def process_pending_summarizations(self):
    """保留中の要約処理を実行"""
    try:
        with get_session() as session:
            # 要約待ちの論文を取得
            pending_papers = session.query(Paper).filter(
                and_(
                    Paper.is_crawled == True,
                    Paper.is_summarized == False
                )
            ).limit(5).all()

            for paper in pending_papers:
                # 非同期で要約タスクを起動
                summarize_paper.apply_async(
                    args=[paper.paper_id],
                    queue='summarizer'
                )

            return {
                'status': 'success',
                'scheduled_papers': len(pending_papers)
            }
    except Exception as e:
        self.retry(exc=e, countdown=60, max_retries=3)
```

#### package/generator/src/refnet_generator/tasks/generate_task.py（追加）
```python
@celery_app.task(bind=True, name='refnet_generator.tasks.generate_task.generate_pending_markdowns')
def generate_pending_markdowns(self):
    """保留中のMarkdown生成を実行"""
    try:
        with get_session() as session:
            # Markdown生成待ちの論文を取得
            pending_papers = session.query(Paper).filter(
                and_(
                    Paper.is_summarized == True,
                    Paper.is_generated == False
                )
            ).limit(10).all()

            for paper in pending_papers:
                # 非同期でMarkdown生成タスクを起動
                generate_markdown.apply_async(
                    args=[paper.paper_id],
                    queue='generator'
                )

            return {
                'status': 'success',
                'scheduled_papers': len(pending_papers)
            }
    except Exception as e:
        self.retry(exc=e, countdown=60, max_retries=3)
```

### 7. 環境変数の追加

#### .env.example（追加）
```env
# Flower認証
FLOWER_USER=admin
FLOWER_PASSWORD=changeme

# Celery設定
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
```

### 8. pyproject.toml更新

#### package/shared/pyproject.toml（監視用の依存関係追加）
```toml
[project.optional-dependencies]
monitoring = [
    "flower>=2.0.0",
]
```

## テスト項目

### 1. Celery Beatの動作確認
```bash
# Beatの起動確認
docker-compose logs celery-beat

# スケジュールタスクの実行確認
docker-compose exec celery-beat celery -A refnet_shared.celery_app inspect scheduled
```

### 2. Flowerの動作確認
```bash
# Flowerにアクセス
curl -u admin:changeme http://localhost:5555/api/workers
```

### 3. 定期タスクの実行確認
```bash
# タスクの実行履歴確認
docker-compose exec redis redis-cli KEYS "celery-task-meta-*"
```

## 確認事項

- [ ] 統一Celeryアプリケーションが全サービスで使用されている
- [ ] Beatスケジュールが正しく設定されている
- [ ] Dockerfile.beatとDockerfile.flowerが作成されている
- [ ] 定期タスクが指定された間隔で実行されている
- [ ] Flowerで全ワーカーの状態が確認できる
- [ ] タスクが適切なキューにルーティングされている

## レビュー観点

### 1. 技術的正確性
- [ ] **Celery設定の整合性**: broker_url、result_backend、task_routes、task_queuesの設定が一貫している
- [ ] **タスク名の一意性**: 各タスクの`name`パラメータが一意で、命名規則に従っている
- [ ] **タスクルーティング**: パターンマッチングによるルーティングが正しく設定されている
- [ ] **スケジュール設定**: crontab設定が正しく、実行間隔が適切である
- [ ] **autodiscover設定**: 各サービスのタスクモジュールが正しく発見される

### 2. パフォーマンス・スケーラビリティ
- [ ] **ワーカー設定**: `worker_prefetch_multiplier`、`worker_max_tasks_per_child`が適切
- [ ] **タスクの有効期限**: `expires`設定が各タスクの実行時間に適している
- [ ] **リソース使用量**: メモリ・CPU使用量が予想範囲内
- [ ] **キューの負荷分散**: タスクが適切にキューに分散されている
- [ ] **実行時間制限**: `task_time_limit`、`task_soft_time_limit`が適切に設定されている

### 3. セキュリティ
- [ ] **認証情報**: Flower認証が適切に設定されている
- [ ] **環境変数**: 機密情報が環境変数で管理されている
- [ ] **ネットワーク分離**: 内部通信のみでCeleryが動作している
- [ ] **権限管理**: 各サービスが必要最小限の権限で動作している

### 4. エラーハンドリング・可用性
- [ ] **リトライ機構**: `self.retry()`が適切に実装されている
- [ ] **エラーログ**: エラー発生時に適切なログが出力される
- [ ] **タスク失敗時の処理**: 失敗したタスクの処理が適切に定義されている
- [ ] **デッドレター処理**: 繰り返し失敗するタスクの処理が考慮されている
- [ ] **監視機能**: ヘルスチェックタスクが適切に実装されている

### 5. 保守性・運用性
- [ ] **ログ出力**: 適切なログレベルと形式が設定されている
- [ ] **設定の外部化**: 設定値が環境変数で管理されている
- [ ] **Docker設定**: DockerfileとCMDが適切に設定されている
- [ ] **依存関係管理**: 必要なパッケージが正しく定義されている
- [ ] **バージョン管理**: パッケージバージョンが適切に固定されている

### 6. テスト可能性
- [ ] **単体テスト**: 各タスクが独立してテスト可能
- [ ] **統合テスト**: サービス間の連携がテスト可能
- [ ] **モック対応**: 外部依存がモック化可能
- [ ] **設定の分離**: テスト環境用の設定が分離されている

### 7. 設定の一貫性
- [ ] **タイムゾーン**: 全サービスで一貫したタイムゾーン設定
- [ ] **シリアライゼーション**: タスクの入出力形式が統一されている
- [ ] **命名規則**: タスク名、キュー名、Exchange名が規則に従っている
- [ ] **環境変数**: 各サービスで共通の環境変数が使用されている

### 8. 運用監視
- [ ] **メトリクス**: タスクの実行状況が監視可能
- [ ] **アラート**: 異常時のアラート機能が実装されている
- [ ] **ダッシュボード**: FlowerやPrometheusでの監視が可能
- [ ] **ログ集約**: 各サービスのログが集約されている

### 9. データ整合性
- [ ] **トランザクション**: データベース操作が適切にトランザクション化されている
- [ ] **重複処理**: 同じタスクの重複実行が防止されている
- [ ] **データ競合**: 複数ワーカーでの競合状態が考慮されている
- [ ] **バックアップ**: 重要なデータの定期バックアップが実装されている

### 10. 互換性・拡張性
- [ ] **バージョン互換性**: Celeryバージョンとの互換性が確保されている
- [ ] **新サービス追加**: 新しいサービスの追加が容易
- [ ] **設定変更**: 運用中の設定変更が可能
- [ ] **スケールアウト**: ワーカーの水平スケーリングが可能
