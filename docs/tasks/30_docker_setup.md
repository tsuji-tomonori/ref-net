# Task: Docker環境構築

## タスクの目的

Docker Composeを使用してマイクロサービスアーキテクチャの統合環境を構築し、全サービスが連携して動作する環境を整備する。

## 実施内容

### 1. プロジェクトルートでのDocker設定

#### docker-compose.yml の作成

```yaml
version: '3.8'

services:
  # PostgreSQL データベース
  postgres:
    image: postgres:16-alpine
    container_name: refnet-postgres
    environment:
      POSTGRES_DB: refnet
      POSTGRES_USER: refnet
      POSTGRES_PASSWORD: refnet_password
      POSTGRES_INITDB_ARGS: "--encoding=UTF-8 --locale=C"
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init-db.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U refnet -d refnet"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - refnet

  # Redis キャッシュ・メッセージブローカー
  redis:
    image: redis:7-alpine
    container_name: refnet-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - refnet

  # API Gateway
  api:
    build:
      context: ./package/api
      dockerfile: Dockerfile
    container_name: refnet-api
    ports:
      - "8000:8000"
    environment:
      - DATABASE__HOST=postgres
      - DATABASE__PORT=5432
      - DATABASE__DATABASE=refnet
      - DATABASE__USERNAME=refnet
      - DATABASE__PASSWORD=refnet_password
      - REDIS__HOST=redis
      - REDIS__PORT=6379
      - REDIS__DATABASE=0
      - LOG_LEVEL=INFO
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./output:/app/output
    networks:
      - refnet
    restart: unless-stopped

  # Crawler Worker
  crawler:
    build:
      context: ./package/crawler
      dockerfile: Dockerfile
    container_name: refnet-crawler
    environment:
      - DATABASE__HOST=postgres
      - DATABASE__PORT=5432
      - DATABASE__DATABASE=refnet
      - DATABASE__USERNAME=refnet
      - DATABASE__PASSWORD=refnet_password
      - REDIS__HOST=redis
      - REDIS__PORT=6379
      - REDIS__DATABASE=0
      - SEMANTIC_SCHOLAR_API_KEY=${SEMANTIC_SCHOLAR_API_KEY:-}
      - LOG_LEVEL=INFO
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - refnet
    restart: unless-stopped
    deploy:
      replicas: 2

  # Summarizer Worker
  summarizer:
    build:
      context: ./package/summarizer
      dockerfile: Dockerfile
    container_name: refnet-summarizer
    environment:
      - DATABASE__HOST=postgres
      - DATABASE__PORT=5432
      - DATABASE__DATABASE=refnet
      - DATABASE__USERNAME=refnet
      - DATABASE__PASSWORD=refnet_password
      - REDIS__HOST=redis
      - REDIS__PORT=6379
      - REDIS__DATABASE=0
      - OPENAI_API_KEY=${OPENAI_API_KEY:-}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
      - LOG_LEVEL=INFO
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - refnet
    restart: unless-stopped

  # Generator Worker
  generator:
    build:
      context: ./package/generator
      dockerfile: Dockerfile
    container_name: refnet-generator
    environment:
      - DATABASE__HOST=postgres
      - DATABASE__PORT=5432
      - DATABASE__DATABASE=refnet
      - DATABASE__USERNAME=refnet
      - DATABASE__PASSWORD=refnet_password
      - REDIS__HOST=redis
      - REDIS__PORT=6379
      - REDIS__DATABASE=0
      - LOG_LEVEL=INFO
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./output:/app/output
    networks:
      - refnet
    restart: unless-stopped

  # Celery Beat (スケジューラー)
  celery-beat:
    build:
      context: ./package/crawler
      dockerfile: Dockerfile
    container_name: refnet-celery-beat
    command: celery -A refnet_crawler.tasks.celery_app beat --loglevel=info
    environment:
      - DATABASE__HOST=postgres
      - DATABASE__PORT=5432
      - DATABASE__DATABASE=refnet
      - DATABASE__USERNAME=refnet
      - DATABASE__PASSWORD=refnet_password
      - REDIS__HOST=redis
      - REDIS__PORT=6379
      - REDIS__DATABASE=0
      - LOG_LEVEL=INFO
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - refnet
    restart: unless-stopped

  # Flower (Celery監視)
  flower:
    image: mher/flower:0.9.7
    container_name: refnet-flower
    ports:
      - "5555:5555"
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
      - FLOWER_PORT=5555
    depends_on:
      - redis
    networks:
      - refnet
    restart: unless-stopped

  # Nginx リバースプロキシ（オプション）
  nginx:
    image: nginx:alpine
    container_name: refnet-nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
    depends_on:
      - api
    networks:
      - refnet
    restart: unless-stopped

volumes:
  postgres_data:
    driver: local
  redis_data:
    driver: local

networks:
  refnet:
    driver: bridge
```

### 2. 開発用Docker Compose

#### docker-compose.dev.yml の作成

```yaml
version: '3.8'

services:
  postgres:
    extends:
      file: docker-compose.yml
      service: postgres
    ports:
      - "5432:5432"

  redis:
    extends:
      file: docker-compose.yml
      service: redis
    ports:
      - "6379:6379"

  api:
    build:
      context: ./package/api
      dockerfile: Dockerfile.dev
    container_name: refnet-api-dev
    ports:
      - "8000:8000"
    environment:
      - DATABASE__HOST=postgres
      - REDIS__HOST=redis
      - LOG_LEVEL=DEBUG
    volumes:
      - ./package/api/src:/app/src
      - ./output:/app/output
    depends_on:
      - postgres
      - redis
    networks:
      - refnet
    command: uvicorn refnet_api.main:app --reload --host 0.0.0.0 --port 8000

  crawler-dev:
    build:
      context: ./package/crawler
      dockerfile: Dockerfile.dev
    container_name: refnet-crawler-dev
    environment:
      - DATABASE__HOST=postgres
      - REDIS__HOST=redis
      - LOG_LEVEL=DEBUG
    volumes:
      - ./package/crawler/src:/app/src
    depends_on:
      - postgres
      - redis
    networks:
      - refnet
    command: celery -A refnet_crawler.tasks.celery_app worker --loglevel=debug --queue=crawl

networks:
  refnet:
    driver: bridge
```

### 3. 開発用Dockerfile

各パッケージに開発用Dockerfileを作成：

#### package/api/Dockerfile.dev

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# システム依存関係
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python依存関係
COPY pyproject.toml uv.lock ./
RUN pip install uv
RUN uv sync --frozen

# 開発用依存関係追加
RUN uv add --dev pytest-cov debugpy

# アプリケーションコピー（開発時はボリュームマウント）
COPY src/ ./src/

# 環境変数
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

# デバッグポート
EXPOSE 5678

# ポート
EXPOSE 8000

# 起動コマンド（開発用）
CMD ["uvicorn", "refnet_api.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]
```

### 4. Nginx設定

#### nginx/nginx.conf

```nginx
events {
    worker_connections 1024;
}

http {
    upstream api {
        server api:8000;
    }

    upstream flower {
        server flower:5555;
    }

    server {
        listen 80;
        server_name localhost;

        # API プロキシ
        location /api/ {
            proxy_pass http://api/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Flower 監視
        location /flower/ {
            proxy_pass http://flower/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # 静的ファイル
        location /output/ {
            alias /app/output/;
            autoindex on;
        }

        # ヘルスチェック
        location /health {
            proxy_pass http://api/health;
        }

        # デフォルトページ
        location / {
            return 301 /api/docs;
        }
    }
}
```

### 5. 環境変数設定

#### .env.example

```bash
# データベース設定
DATABASE__HOST=localhost
DATABASE__PORT=5432
DATABASE__DATABASE=refnet
DATABASE__USERNAME=refnet
DATABASE__PASSWORD=refnet_password

# Redis設定
REDIS__HOST=localhost
REDIS__PORT=6379
REDIS__DATABASE=0

# API キー
SEMANTIC_SCHOLAR_API_KEY=your_semantic_scholar_api_key
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key

# ログレベル
LOG_LEVEL=INFO

# 出力ディレクトリ
OUTPUT_DIR=./output
```

### 6. データベース初期化スクリプト

#### scripts/init-db.sql

```sql
-- データベース初期化スクリプト
-- PostgreSQL用

-- 拡張機能の有効化
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- インデックス用の拡張
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- 全文検索用の設定
CREATE TEXT SEARCH CONFIGURATION refnet_config (COPY = english);

-- カスタム関数（例：論文の類似度計算）
CREATE OR REPLACE FUNCTION calculate_paper_similarity(
    paper1_id TEXT,
    paper2_id TEXT
) RETURNS FLOAT AS $$
DECLARE
    similarity_score FLOAT := 0.0;
    common_authors INTEGER := 0;
    common_keywords INTEGER := 0;
BEGIN
    -- 共通著者数の計算
    SELECT COUNT(*)
    INTO common_authors
    FROM paper_authors pa1
    JOIN paper_authors pa2 ON pa1.author_id = pa2.author_id
    WHERE pa1.paper_id = paper1_id AND pa2.paper_id = paper2_id;

    -- 共通キーワード数の計算
    SELECT COUNT(*)
    INTO common_keywords
    FROM paper_keywords pk1
    JOIN paper_keywords pk2 ON pk1.keyword = pk2.keyword
    WHERE pk1.paper_id = paper1_id AND pk2.paper_id = paper2_id;

    -- 類似度スコアの計算
    similarity_score := (common_authors * 0.3) + (common_keywords * 0.7);

    RETURN similarity_score;
END;
$$ LANGUAGE plpgsql;

-- データベースの初期化完了ログ
INSERT INTO processing_queue (paper_id, task_type, status, priority)
VALUES ('system-init', 'init', 'completed', 0);
```

### 7. Docker管理スクリプト

#### scripts/docker-dev.sh

```bash
#!/bin/bash
set -e

# 開発環境用Dockerスクリプト

COMMAND=${1:-help}

case $COMMAND in
    "up")
        echo "Starting development environment..."
        docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d
        echo "Services started. API available at http://localhost:8000"
        ;;
    "down")
        echo "Stopping development environment..."
        docker-compose -f docker-compose.yml -f docker-compose.dev.yml down
        ;;
    "logs")
        SERVICE=${2:-api}
        docker-compose -f docker-compose.yml -f docker-compose.dev.yml logs -f $SERVICE
        ;;
    "build")
        echo "Building development images..."
        docker-compose -f docker-compose.yml -f docker-compose.dev.yml build
        ;;
    "restart")
        SERVICE=${2:-}
        if [ -z "$SERVICE" ]; then
            docker-compose -f docker-compose.yml -f docker-compose.dev.yml restart
        else
            docker-compose -f docker-compose.yml -f docker-compose.dev.yml restart $SERVICE
        fi
        ;;
    "shell")
        SERVICE=${2:-api}
        docker-compose -f docker-compose.yml -f docker-compose.dev.yml exec $SERVICE /bin/bash
        ;;
    "test")
        SERVICE=${2:-api}
        docker-compose -f docker-compose.yml -f docker-compose.dev.yml exec $SERVICE pytest
        ;;
    "migrate")
        docker-compose -f docker-compose.yml -f docker-compose.dev.yml exec api python -c "
from refnet_shared.models.database_manager import db_manager
db_manager.create_tables()
print('Database tables created successfully')
"
        ;;
    "help")
        echo "Usage: $0 {up|down|logs|build|restart|shell|test|migrate|help}"
        echo ""
        echo "Commands:"
        echo "  up              Start development environment"
        echo "  down            Stop development environment"
        echo "  logs [service]  Show logs for service (default: api)"
        echo "  build           Build development images"
        echo "  restart [service] Restart service(s)"
        echo "  shell [service] Open shell in service (default: api)"
        echo "  test [service]  Run tests in service (default: api)"
        echo "  migrate         Run database migrations"
        echo "  help            Show this help message"
        ;;
    *)
        echo "Unknown command: $COMMAND"
        echo "Use '$0 help' for usage information"
        exit 1
        ;;
esac
```

#### scripts/docker-prod.sh

```bash
#!/bin/bash
set -e

# 本番環境用Dockerスクリプト

COMMAND=${1:-help}

case $COMMAND in
    "deploy")
        echo "Deploying production environment..."

        # 環境変数チェック
        if [ ! -f .env ]; then
            echo "Error: .env file not found. Copy .env.example and configure it."
            exit 1
        fi

        # イメージビルド
        docker-compose build

        # サービス起動
        docker-compose up -d

        # ヘルスチェック
        echo "Waiting for services to be healthy..."
        sleep 30

        if curl -f http://localhost:8000/health; then
            echo "Deployment successful! API available at http://localhost:8000"
        else
            echo "Deployment failed. Check logs with: $0 logs"
            exit 1
        fi
        ;;
    "stop")
        echo "Stopping production environment..."
        docker-compose down
        ;;
    "status")
        docker-compose ps
        ;;
    "logs")
        SERVICE=${2:-}
        if [ -z "$SERVICE" ]; then
            docker-compose logs -f
        else
            docker-compose logs -f $SERVICE
        fi
        ;;
    "backup")
        BACKUP_DIR="./backups/$(date +%Y%m%d_%H%M%S)"
        mkdir -p $BACKUP_DIR

        echo "Creating database backup..."
        docker-compose exec postgres pg_dump -U refnet refnet > $BACKUP_DIR/database.sql

        echo "Creating output backup..."
        tar -czf $BACKUP_DIR/output.tar.gz ./output

        echo "Backup created in $BACKUP_DIR"
        ;;
    "restore")
        BACKUP_FILE=${2:-}
        if [ -z "$BACKUP_FILE" ]; then
            echo "Usage: $0 restore <backup_file.sql>"
            exit 1
        fi

        echo "Restoring database from $BACKUP_FILE..."
        docker-compose exec -T postgres psql -U refnet refnet < $BACKUP_FILE
        ;;
    "help")
        echo "Usage: $0 {deploy|stop|status|logs|backup|restore|help}"
        echo ""
        echo "Commands:"
        echo "  deploy          Deploy production environment"
        echo "  stop            Stop production environment"
        echo "  status          Show service status"
        echo "  logs [service]  Show logs for service"
        echo "  backup          Create database and output backup"
        echo "  restore <file>  Restore database from backup file"
        echo "  help            Show this help message"
        ;;
    *)
        echo "Unknown command: $COMMAND"
        echo "Use '$0 help' for usage information"
        exit 1
        ;;
esac
```

### 8. Makefileの作成

```makefile
# RefNet プロジェクト管理

.PHONY: help dev-up dev-down prod-deploy prod-stop test lint format check build clean

# デフォルトターゲット
help:
	@echo "RefNet プロジェクト管理コマンド"
	@echo ""
	@echo "開発環境:"
	@echo "  dev-up      開発環境起動"
	@echo "  dev-down    開発環境停止"
	@echo "  dev-logs    開発環境ログ表示"
	@echo ""
	@echo "本番環境:"
	@echo "  prod-deploy 本番環境デプロイ"
	@echo "  prod-stop   本番環境停止"
	@echo ""
	@echo "開発ツール:"
	@echo "  test        全テスト実行"
	@echo "  lint        リント実行"
	@echo "  format      フォーマット実行"
	@echo "  check       全チェック実行"
	@echo "  build       全イメージビルド"
	@echo "  clean       クリーンアップ"

# 開発環境
dev-up:
	./scripts/docker-dev.sh up

dev-down:
	./scripts/docker-dev.sh down

dev-logs:
	./scripts/docker-dev.sh logs

# 本番環境
prod-deploy:
	./scripts/docker-prod.sh deploy

prod-stop:
	./scripts/docker-prod.sh stop

# 開発ツール
test:
	moon run :test

lint:
	moon run :lint

format:
	moon run :format

check:
	moon run :check

build:
	docker-compose build

clean:
	docker-compose down -v --remove-orphans
	docker system prune -f
	docker volume prune -f
```

### 9. テストの作成

#### tests/test_docker_integration.py

```python
"""Docker統合テスト."""

import pytest
import requests
import time
from typing import Generator


@pytest.fixture(scope="module")
def docker_services() -> Generator[None, None, None]:
    """Docker サービスのセットアップ・ティアダウン."""
    import subprocess

    # サービス起動
    subprocess.run(["docker-compose", "-f", "docker-compose.yml", "-f", "docker-compose.dev.yml", "up", "-d"], check=True)

    # サービスが起動するまで待機
    time.sleep(30)

    yield

    # サービス停止
    subprocess.run(["docker-compose", "-f", "docker-compose.yml", "-f", "docker-compose.dev.yml", "down"], check=True)


def test_api_health_check(docker_services):
    """API ヘルスチェックテスト."""
    response = requests.get("http://localhost:8000/health", timeout=10)
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_api_docs_access(docker_services):
    """API ドキュメントアクセステスト."""
    response = requests.get("http://localhost:8000/docs", timeout=10)
    assert response.status_code == 200


def test_flower_access(docker_services):
    """Flower 監視画面アクセステスト."""
    response = requests.get("http://localhost:5555", timeout=10)
    assert response.status_code == 200


def test_database_connection(docker_services):
    """データベース接続テスト."""
    import psycopg2

    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        database="refnet",
        user="refnet",
        password="refnet_password"
    )

    cursor = conn.cursor()
    cursor.execute("SELECT 1")
    result = cursor.fetchone()

    assert result[0] == 1

    cursor.close()
    conn.close()


def test_redis_connection(docker_services):
    """Redis接続テスト."""
    import redis

    r = redis.Redis(host="localhost", port=6379, db=0)
    r.set("test_key", "test_value")
    value = r.get("test_key")

    assert value.decode() == "test_value"

    r.delete("test_key")
```

## スコープ

- Docker Compose設定
- 開発・本番環境の分離
- サービス間ネットワーク設定
- ボリュームマウント設定
- ヘルスチェック設定
- Nginx リバースプロキシ設定
- 管理スクリプト作成

**スコープ外:**
- Kubernetes対応
- CI/CDパイプライン
- 監視・ログ集約システム
- セキュリティ強化

## 参照するドキュメント

- `/docs/infrastructure/docker-architecture.md`
- `/docs/development/coding-standards.md`
- [Docker Compose公式ドキュメント](https://docs.docker.com/compose/)

## 完了条件

- [ ] docker-compose.yml が作成されている
- [ ] 開発用・本番用設定が分離されている
- [ ] 全サービスが正常に起動する
- [ ] ヘルスチェックが正常に動作する
- [ ] 管理スクリプトが作成されている
- [ ] Makefile が作成されている
- [ ] 基本的な統合テストが作成されている
- [ ] `make dev-up` で開発環境が起動する
- [ ] `make test` で統合テストが通る
