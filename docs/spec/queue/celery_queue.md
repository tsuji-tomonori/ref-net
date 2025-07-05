# Celeryジョブキュー設計書

## 1. 概要

本設計書は、論文関係性可視化システムにおけるCeleryを用いた非同期タスクキューの設計を定義する。
Celeryは、論文メタデータ収集、PDF要約処理、Markdown生成などの時間のかかるタスクを非同期で処理するために使用される。

## 2. アーキテクチャ

### 2.1 コンポーネント構成

```mermaid
graph TB
    subgraph "Client Layer"
        API[FastAPI/Flask API]
    end

    subgraph "Message Broker"
        Redis[(Redis)]
    end

    subgraph "Worker Pool"
        W1[Crawler Worker]
        W2[Summarizer Worker]
        W3[Generator Worker]
    end

    subgraph "Result Backend"
        PostgreSQL[(PostgreSQL)]
    end

    API -->|Task Queue| Redis
    Redis -->|Consume Tasks| W1
    Redis -->|Consume Tasks| W2
    Redis -->|Consume Tasks| W3
    W1 -->|Store Results| PostgreSQL
    W2 -->|Store Results| PostgreSQL
    W3 -->|Store Results| PostgreSQL
```

### 2.2 タスクフロー

1. APIがタスクをRedisキューに送信
2. 適切なワーカーがタスクを取得・実行
3. 実行結果をPostgreSQLに保存
4. タスクステータスをRedisで管理

## 3. Celery設定

### 3.1 基本設定

```python
# celery_config.py
from celery import Celery
from kombu import Queue, Exchange

# Celeryインスタンス作成
app = Celery('refnet')

# 設定
app.conf.update(
    # ブローカー設定
    broker_url='redis://redis:6379/0',
    result_backend='postgresql://user:password@postgres:5432/refnet',

    # タスク設定
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,

    # ワーカー設定
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    worker_disable_rate_limits=False,

    # タイムアウト設定
    task_soft_time_limit=300,  # 5分
    task_time_limit=600,       # 10分

    # リトライ設定
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)
```

### 3.2 キュー定義

```python
# キュー設定
app.conf.task_routes = {
    'crawler.tasks.*': {'queue': 'crawler'},
    'summarizer.tasks.*': {'queue': 'summarizer'},
    'generator.tasks.*': {'queue': 'generator'},
}

app.conf.task_queues = (
    Queue('crawler', Exchange('crawler'), routing_key='crawler',
          queue_arguments={'x-max-priority': 10}),
    Queue('summarizer', Exchange('summarizer'), routing_key='summarizer',
          queue_arguments={'x-max-priority': 5}),
    Queue('generator', Exchange('generator'), routing_key='generator',
          queue_arguments={'x-max-priority': 3}),
)
```

## 4. タスク定義

### 4.1 Crawlerタスク

```python
# crawler/tasks.py
from celery import Task
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class CrawlerTask(Task):
    """論文メタデータ収集タスクの基底クラス"""

    # リトライ設定
    autoretry_for = (Exception,)
    retry_kwargs = {'max_retries': 3}
    retry_backoff = True
    retry_backoff_max = 600  # 最大10分
    retry_jitter = True

@app.task(base=CrawlerTask, bind=True)
def fetch_paper_metadata(self, paper_id: str, depth: int = 0) -> Dict[str, Any]:
    """
    論文メタデータを収集するタスク

    Args:
        paper_id: 論文ID
        depth: 再帰的収集の深さ

    Returns:
        収集したメタデータ
    """
    try:
        logger.info(f"Fetching metadata for paper: {paper_id}, depth: {depth}")

        # Semantic Scholar APIからデータ取得
        metadata = fetch_from_semantic_scholar(paper_id)

        # PostgreSQLに保存
        save_to_database(metadata)

        # 深さ制限内なら引用・被引用論文も収集
        if depth < MAX_DEPTH:
            for ref_id in metadata.get('references', []):
                fetch_paper_metadata.apply_async(
                    args=[ref_id, depth + 1],
                    priority=calculate_priority(metadata, ref_id)
                )

        return {'status': 'success', 'paper_id': paper_id}

    except Exception as e:
        logger.error(f"Error fetching paper {paper_id}: {str(e)}")
        raise self.retry(exc=e)
```

### 4.2 Summarizerタスク

```python
# summarizer/tasks.py
@app.task(bind=True, max_retries=3)
def summarize_pdf(self, paper_id: str) -> Dict[str, Any]:
    """
    PDFを要約するタスク

    Args:
        paper_id: 論文ID

    Returns:
        要約結果
    """
    try:
        # PDFダウンロード
        pdf_content = download_pdf(paper_id)

        # テキスト抽出
        text = extract_text(pdf_content)

        # LLMで要約
        summary = generate_summary(text)

        # 結果保存
        save_summary(paper_id, summary)

        return {'status': 'success', 'paper_id': paper_id}

    except Exception as e:
        logger.error(f"Error summarizing PDF for {paper_id}: {str(e)}")
        raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))
```

### 4.3 Generatorタスク

```python
# generator/tasks.py
@app.task(bind=True)
def generate_markdown(self, paper_id: str) -> Dict[str, Any]:
    """
    Obsidian用Markdownを生成するタスク

    Args:
        paper_id: 論文ID

    Returns:
        生成結果
    """
    try:
        # メタデータと要約を取得
        data = fetch_paper_data(paper_id)

        # Markdown生成
        markdown = format_to_obsidian(data)

        # ファイル保存
        save_markdown_file(paper_id, markdown)

        return {'status': 'success', 'paper_id': paper_id}

    except Exception as e:
        logger.error(f"Error generating markdown for {paper_id}: {str(e)}")
        raise
```

## 5. ワーカー設定

### 5.1 Docker Compose設定

```yaml
# docker-compose.yml
services:
  celery-crawler:
    build: ./docker/celery
    command: celery -A celery_app worker -Q crawler -n crawler@%h --loglevel=info --concurrency=4
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
      - DATABASE_URL=postgresql://user:password@postgres:5432/refnet
    depends_on:
      - redis
      - postgres
    volumes:
      - ./package:/app
    restart: unless-stopped

  celery-summarizer:
    build: ./docker/celery
    command: celery -A celery_app worker -Q summarizer -n summarizer@%h --loglevel=info --concurrency=2
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
      - DATABASE_URL=postgresql://user:password@postgres:5432/refnet
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    depends_on:
      - redis
      - postgres
    volumes:
      - ./package:/app
    restart: unless-stopped

  celery-generator:
    build: ./docker/celery
    command: celery -A celery_app worker -Q generator -n generator@%h --loglevel=info --concurrency=4
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
      - DATABASE_URL=postgresql://user:password@postgres:5432/refnet
      - OUTPUT_DIR=/output
    depends_on:
      - redis
      - postgres
    volumes:
      - ./package:/app
      - ./output:/output
    restart: unless-stopped
```

### 5.2 ワーカー起動パラメータ

| パラメータ | Crawler | Summarizer | Generator | 説明 |
|----------|---------|------------|-----------|------|
| concurrency | 4 | 2 | 4 | 同時実行タスク数 |
| max-tasks-per-child | 1000 | 100 | 1000 | ワーカープロセス再起動閾値 |
| soft-time-limit | 300s | 600s | 120s | ソフトタイムアウト |
| time-limit | 600s | 900s | 180s | ハードタイムアウト |
| autoscale | 4,2 | 2,1 | 4,2 | 最大/最小ワーカー数 |

## 6. Redis設定

### 6.1 永続化設定

```conf
# redis.conf
# RDB永続化
save 900 1
save 300 10
save 60 10000

# AOF永続化
appendonly yes
appendfsync everysec

# メモリ設定
maxmemory 2gb
maxmemory-policy allkeys-lru

# 接続設定
timeout 0
tcp-keepalive 300
```

### 6.2 キューデータ構造

```
redis:6379> KEYS *
1) "celery"                    # デフォルトキュー
2) "_kombu.binding.crawler"    # Crawlerキューバインディング
3) "_kombu.binding.summarizer" # Summarizerキューバインディング
4) "_kombu.binding.generator"  # Generatorキューバインディング
5) "celery-task-meta-*"        # タスク結果メタデータ
```

## 7. 優先度設定

### 7.1 タスク優先度

```python
# 優先度計算ロジック
def calculate_priority(paper_metadata: Dict, reference_id: str) -> int:
    """
    引用論文の収集優先度を計算

    Returns:
        0-10の優先度（10が最高）
    """
    priority = 5  # デフォルト

    # 引用数が多い論文を優先
    citation_count = paper_metadata.get('citationCount', 0)
    if citation_count > 1000:
        priority += 3
    elif citation_count > 100:
        priority += 2
    elif citation_count > 10:
        priority += 1

    # 最近の論文を優先
    year = paper_metadata.get('year', 0)
    if year >= 2020:
        priority += 2
    elif year >= 2015:
        priority += 1

    return min(priority, 10)
```

### 7.2 キュー優先度

| キュー | 優先度 | 用途 |
|--------|--------|------|
| crawler | 10 | メタデータ収集（最優先） |
| summarizer | 5 | PDF要約（中優先度） |
| generator | 3 | Markdown生成（低優先度） |

## 8. 監視とログ

### 8.1 Flower設定

```yaml
# docker-compose.yml
services:
  flower:
    build: ./docker/celery
    command: celery -A celery_app flower --port=5555
    ports:
      - "5555:5555"
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
      - FLOWER_BASIC_AUTH=admin:password
    depends_on:
      - redis
```

### 8.2 ログ設定

```python
# logging_config.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'detailed': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'detailed',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/logs/celery.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 10,
            'formatter': 'detailed',
        },
    },
    'loggers': {
        'celery': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
        'crawler': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
        },
        'summarizer': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
        },
        'generator': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
        },
    },
}
```

## 9. エラーハンドリング

### 9.1 リトライ戦略

```python
# リトライデコレータ
from celery.exceptions import Retry

@app.task(bind=True, max_retries=3)
def robust_task(self, *args, **kwargs):
    try:
        # タスク処理
        pass
    except TemporaryError as exc:
        # 一時的なエラーはリトライ
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))
    except PermanentError as exc:
        # 永続的なエラーは失敗として記録
        logger.error(f"Permanent error: {exc}")
        return {'status': 'failed', 'error': str(exc)}
```

### 9.2 デッドレターキュー

```python
# デッドレターキュー設定
app.conf.task_dead_letter_queue = 'dlq'
app.conf.task_dead_letter_exchange = 'dlx'
app.conf.task_dead_letter_routing_key = 'dlq'

# 失敗したタスクの処理
@app.task
def process_failed_tasks():
    """デッドレターキューのタスクを処理"""
    # 失敗したタスクをログに記録
    # 必要に応じて再処理やアラート送信
    pass
```

## 10. パフォーマンスチューニング

### 10.1 メモリ管理

```python
# ワーカーメモリ制限
app.conf.worker_max_memory_per_child = 200000  # 200MB

# タスクごとのメモリプロファイリング
from memory_profiler import profile

@profile
@app.task
def memory_intensive_task():
    # メモリを大量に使用するタスク
    pass
```

### 10.2 バッチ処理

```python
# バッチタスク定義
@app.task
def batch_process_papers(paper_ids: List[str]):
    """複数の論文を一括処理"""
    with app.producer_pool.acquire(block=True) as producer:
        for paper_id in paper_ids:
            fetch_paper_metadata.apply_async(
                args=[paper_id],
                producer=producer,
                priority=5
            )
```

## 11. セキュリティ設定

### 11.1 認証設定

```python
# Redis認証
app.conf.broker_url = 'redis://:password@redis:6379/0'

# タスク署名
app.conf.task_serializer = 'json'
app.conf.result_serializer = 'json'
app.conf.accept_content = ['json']
```

### 11.2 アクセス制御

```python
# タスク実行権限チェック
from functools import wraps

def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 認証チェックロジック
        if not check_auth():
            raise PermissionError("Unauthorized")
        return f(*args, **kwargs)
    return decorated_function

@app.task
@require_auth
def secure_task():
    pass
```

## 12. 運用管理

### 12.1 ヘルスチェック

```python
# ヘルスチェックタスク
@app.task
def health_check():
    """ワーカーの健全性確認"""
    return {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'worker': current_task.request.hostname
    }

# 定期実行設定
app.conf.beat_schedule = {
    'health-check': {
        'task': 'health_check',
        'schedule': 60.0,  # 1分ごと
    },
}
```

### 12.2 メトリクス収集

```python
# Prometheusメトリクス
from celery_prometheus_exporter import PrometheusExporter

exporter = PrometheusExporter(app)
exporter.start()

# カスタムメトリクス
from prometheus_client import Counter, Histogram

task_counter = Counter('celery_tasks_total', 'Total tasks processed')
task_duration = Histogram('celery_task_duration_seconds', 'Task duration')

@app.task(bind=True)
def monitored_task(self):
    with task_duration.time():
        # タスク処理
        task_counter.inc()
```

## 13. トラブルシューティング

### 13.1 一般的な問題と対処法

| 問題 | 症状 | 対処法 |
|------|------|--------|
| ワーカー接続エラー | "Cannot connect to redis" | Redis接続設定確認、ネットワーク疎通確認 |
| タスクタイムアウト | "Task timed out" | タイムアウト値調整、タスク分割 |
| メモリリーク | ワーカーメモリ増加 | max_tasks_per_child設定、メモリプロファイリング |
| タスク滞留 | キューサイズ増加 | ワーカー数増加、タスク優先度調整 |

### 13.2 デバッグ方法

```bash
# タスク一覧確認
celery -A celery_app inspect active

# キュー状態確認
celery -A celery_app inspect stats

# タスク実行履歴
celery -A celery_app events

# 特定タスクのデバッグ
celery -A celery_app call crawler.tasks.fetch_paper_metadata --args='["paper123"]'
```
