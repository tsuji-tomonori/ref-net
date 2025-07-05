# Task: Docker環境構築

## タスクの目的

Docker Composeを使用してマイクロサービスアーキテクチャの統合環境を構築し、全サービスが連携して動作する環境を整備する。Phase 4の基盤となるコンテナオーケストレーション環境を構築する。

## 前提条件

- Phase 3 が完了している
- 全サービスが個別に動作確認済み
- 各サービスのDockerfileが作成済み
- 環境設定管理システムが動作

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
      POSTGRES_PASSWORD: ${DATABASE_PASSWORD:-refnet_password}
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
      retries: 3
    networks:
      - refnet

  # API Gateway (Nginx)
  nginx:
    image: nginx:alpine
    container_name: refnet-nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./docker/nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./docker/nginx/ssl:/etc/nginx/ssl
    depends_on:
      - api
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    networks:
      - refnet

  # API サービス
  api:
    build:
      context: ./package/api
      dockerfile: Dockerfile
    container_name: refnet-api
    environment:
      NODE_ENV: ${NODE_ENV:-development}
      DATABASE__HOST: postgres
      DATABASE__PASSWORD: ${DATABASE_PASSWORD:-refnet_password}
      REDIS__HOST: redis
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      SEMANTIC_SCHOLAR_API_KEY: ${SEMANTIC_SCHOLAR_API_KEY}
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    volumes:
      - ./output:/app/output
    networks:
      - refnet

  # クローラーワーカー
  crawler-worker:
    build:
      context: ./package/crawler
      dockerfile: Dockerfile
    container_name: refnet-crawler
    environment:
      NODE_ENV: ${NODE_ENV:-development}
      DATABASE__HOST: postgres
      DATABASE__PASSWORD: ${DATABASE_PASSWORD:-refnet_password}
      REDIS__HOST: redis
      SEMANTIC_SCHOLAR_API_KEY: ${SEMANTIC_SCHOLAR_API_KEY}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    deploy:
      replicas: 2
    networks:
      - refnet

  # 要約ワーカー
  summarizer-worker:
    build:
      context: ./package/summarizer
      dockerfile: Dockerfile
    container_name: refnet-summarizer
    environment:
      NODE_ENV: ${NODE_ENV:-development}
      DATABASE__HOST: postgres
      DATABASE__PASSWORD: ${DATABASE_PASSWORD:-refnet_password}
      REDIS__HOST: redis
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    deploy:
      replicas: 1
    networks:
      - refnet

  # ジェネレーターワーカー
  generator-worker:
    build:
      context: ./package/generator
      dockerfile: Dockerfile
    container_name: refnet-generator
    environment:
      NODE_ENV: ${NODE_ENV:-development}
      DATABASE__HOST: postgres
      DATABASE__PASSWORD: ${DATABASE_PASSWORD:-refnet_password}
      REDIS__HOST: redis
      OUTPUT_DIR: /app/output
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./output:/app/output
    networks:
      - refnet

  # Celery Beat スケジューラー
  celery-beat:
    build:
      context: ./package/shared
      dockerfile: Dockerfile.beat
    container_name: refnet-celery-beat
    environment:
      NODE_ENV: ${NODE_ENV:-development}
      DATABASE__HOST: postgres
      DATABASE__PASSWORD: ${DATABASE_PASSWORD:-refnet_password}
      REDIS__HOST: redis
    command: celery -A refnet_shared.celery_app beat --loglevel=info
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - refnet

  # 監視用 Flower (Celeryモニタリング)
  flower:
    build:
      context: ./package/shared
      dockerfile: Dockerfile.flower
    container_name: refnet-flower
    environment:
      CELERY_BROKER_URL: redis://redis:6379/0
    ports:
      - "5555:5555"
    depends_on:
      - redis
    networks:
      - refnet

volumes:
  postgres_data:
  redis_data:

networks:
  refnet:
    driver: bridge
```

### 2. Nginx設定

#### docker/nginx/nginx.conf

```nginx
events {
    worker_connections 1024;
}

http {
    upstream api_backend {
        server api:8000;
    }

    upstream flower_backend {
        server flower:5555;
    }

    # ログ設定
    access_log /var/log/nginx/access.log;
    error_log /var/log/nginx/error.log;

    # セキュリティヘッダー
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Referrer-Policy strict-origin-when-cross-origin;

    # API サーバー
    server {
        listen 80;
        server_name localhost;

        # ヘルスチェック
        location /health {
            access_log off;
            return 200 "healthy\n";
            add_header Content-Type text/plain;
        }

        # API プロキシ
        location /api/ {
            proxy_pass http://api_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # タイムアウト設定
            proxy_connect_timeout 30s;
            proxy_send_timeout 30s;
            proxy_read_timeout 30s;
        }

        # Flower モニタリング
        location /flower/ {
            proxy_pass http://flower_backend/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # 静的ファイル（生成されたMarkdown）
        location /output/ {
            alias /app/output/;
            autoindex on;
            autoindex_exact_size off;
            autoindex_localtime on;
        }

        # デフォルトページ
        location / {
            return 200 'RefNet API Gateway\n';
            add_header Content-Type text/plain;
        }
    }
}
```

### 3. 開発用設定ファイル

#### .env.docker

```bash
# Docker開発環境用設定
NODE_ENV=development
DEBUG=true

# データベース設定
DATABASE_PASSWORD=refnet_docker_password

# 外部APIキー（開発用）
SEMANTIC_SCHOLAR_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=

# セキュリティ設定
SECURITY__JWT_SECRET=docker-development-jwt-secret-key
```

#### docker-compose.override.yml (開発用オーバーライド)

```yaml
version: '3.8'

services:
  # 開発時の追加設定
  api:
    volumes:
      - ./package/api/src:/app/src
    environment:
      - DEBUG=true
    command: uvicorn refnet_api.main:app --host 0.0.0.0 --port 8000 --reload

  crawler-worker:
    volumes:
      - ./package/crawler/src:/app/src

  summarizer-worker:
    volumes:
      - ./package/summarizer/src:/app/src

  generator-worker:
    volumes:
      - ./package/generator/src:/app/src

  # 開発用データベース管理ツール
  adminer:
    image: adminer
    container_name: refnet-adminer
    ports:
      - "8080:8080"
    environment:
      ADMINER_DEFAULT_SERVER: postgres
    networks:
      - refnet
```

### 4. データベース初期化スクリプト

#### scripts/init-db.sql

```sql
-- RefNet データベース初期化

-- 拡張機能の有効化
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 初期インデックスの作成（パフォーマンス最適化）
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_papers_year
    ON papers(year) WHERE year IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_papers_citation_count
    ON papers(citation_count) WHERE citation_count > 0;

-- 全文検索インデックス
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_papers_title_fts
    ON papers USING gin(to_tsvector('english', title));

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_papers_abstract_fts
    ON papers USING gin(to_tsvector('english', abstract));

-- パフォーマンス設定
ALTER SYSTEM SET shared_preload_libraries = 'pg_stat_statements';
ALTER SYSTEM SET log_statement = 'all';
ALTER SYSTEM SET log_duration = on;

-- 統計情報更新
ANALYZE;

SELECT 'RefNet database initialized successfully' as status;
```

### 5. 管理スクリプト

#### scripts/docker-dev.sh

```bash
#!/bin/bash

# RefNet Docker開発環境管理スクリプト

set -e

COMPOSE_FILE="docker-compose.yml"
OVERRIDE_FILE="docker-compose.override.yml"

case "$1" in
    "up")
        echo "🚀 Starting RefNet development environment..."
        docker-compose -f $COMPOSE_FILE -f $OVERRIDE_FILE up -d
        echo "✅ Environment started. Access:"
        echo "   API: http://localhost/api/"
        echo "   Flower: http://localhost/flower/"
        echo "   Adminer: http://localhost:8080/"
        echo "   Output: http://localhost/output/"
        ;;

    "down")
        echo "🛑 Stopping RefNet environment..."
        docker-compose -f $COMPOSE_FILE -f $OVERRIDE_FILE down
        ;;

    "reset")
        echo "🔄 Resetting RefNet environment..."
        docker-compose -f $COMPOSE_FILE -f $OVERRIDE_FILE down -v
        docker-compose -f $COMPOSE_FILE -f $OVERRIDE_FILE up -d
        ;;

    "logs")
        service=${2:-}
        if [ -n "$service" ]; then
            docker-compose -f $COMPOSE_FILE -f $OVERRIDE_FILE logs -f "$service"
        else
            docker-compose -f $COMPOSE_FILE -f $OVERRIDE_FILE logs -f
        fi
        ;;

    "exec")
        service=${2:-api}
        docker-compose -f $COMPOSE_FILE -f $OVERRIDE_FILE exec "$service" bash
        ;;

    "migrate")
        echo "🔧 Running database migrations..."
        docker-compose -f $COMPOSE_FILE -f $OVERRIDE_FILE exec api refnet-shared migrate upgrade
        ;;

    "test")
        echo "🧪 Running tests..."
        docker-compose -f $COMPOSE_FILE -f $OVERRIDE_FILE exec api moon run shared:check
        ;;

    "status")
        echo "📊 RefNet services status:"
        docker-compose -f $COMPOSE_FILE -f $OVERRIDE_FILE ps
        ;;

    *)
        echo "RefNet Docker Management Script"
        echo ""
        echo "Usage: $0 {up|down|reset|logs|exec|migrate|test|status}"
        echo ""
        echo "Commands:"
        echo "  up      - Start all services"
        echo "  down    - Stop all services"
        echo "  reset   - Reset environment (remove volumes)"
        echo "  logs    - Show logs (optionally for specific service)"
        echo "  exec    - Execute bash in service container"
        echo "  migrate - Run database migrations"
        echo "  test    - Run tests"
        echo "  status  - Show service status"
        exit 1
        ;;
esac
```

### 6. テスト設定

#### tests/test_docker_integration.py

```python
"""Docker統合テスト."""

import pytest
import time
import requests
from urllib.parse import urljoin


class TestDockerIntegration:
    """Docker環境統合テスト."""

    BASE_URL = "http://localhost"

    def test_nginx_health_check(self):
        """Nginxヘルスチェック."""
        response = requests.get(f"{self.BASE_URL}/health")
        assert response.status_code == 200
        assert "healthy" in response.text

    def test_api_health_check(self):
        """APIサービスヘルスチェック."""
        response = requests.get(f"{self.BASE_URL}/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_api_root_endpoint(self):
        """APIルートエンドポイント."""
        response = requests.get(f"{self.BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert "RefNet API" in data["message"]

    def test_flower_monitoring(self):
        """Flower監視システム."""
        response = requests.get(f"{self.BASE_URL}/flower/")
        assert response.status_code == 200

    def test_database_connection(self):
        """データベース接続テスト."""
        # APIを通じてデータベース接続確認
        response = requests.get(f"{self.BASE_URL}/api/v1/papers/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_redis_connection(self):
        """Redis接続テスト（Celeryタスク経由）."""
        # 簡単なタスクを送信して確認
        pass  # 実装はタスクエンドポイント次第

    @pytest.mark.slow
    def test_service_startup_time(self):
        """サービス起動時間テスト."""
        start_time = time.time()

        # 全サービスが利用可能になるまで待機
        services_ready = False
        max_wait = 120  # 2分

        while not services_ready and (time.time() - start_time) < max_wait:
            try:
                # 主要サービスの確認
                nginx_ok = requests.get(f"{self.BASE_URL}/health").status_code == 200
                api_ok = requests.get(f"{self.BASE_URL}/api/health").status_code == 200

                if nginx_ok and api_ok:
                    services_ready = True
                else:
                    time.sleep(5)

            except requests.exceptions.ConnectionError:
                time.sleep(5)

        assert services_ready, "Services did not start within expected time"
        startup_time = time.time() - start_time
        assert startup_time < max_wait
```

## スコープ

- Docker Composeによる全サービス統合
- Nginxリバースプロキシ設定
- 開発環境の構築
- 基本的な統合テスト
- 管理スクリプト

**スコープ外:**
- 本番環境クラウドデプロイ
- Kubernetes設定
- 高可用性設定
- 自動スケーリング

## 参照するドキュメント

- `/docs/infrastructure/docker.md`
- `/docs/development/coding-standards.md`
- `/docs/tasks/phase_03/` - 各サービス実装

## 完了条件

### 必須条件
- [ ] Docker Composeで全サービスが起動
- [ ] Nginxプロキシが正常動作
- [ ] サービス間通信が確立
- [ ] ヘルスチェックが正常動作
- [ ] 管理スクリプトが動作
- [ ] 統合テストが成功

### 動作確認
- [ ] `./scripts/docker-dev.sh up` でサービス起動
- [ ] `http://localhost/api/health` が200応答
- [ ] `http://localhost/flower/` でCelery監視可能
- [ ] データベースマイグレーションが実行可能
- [ ] 各ワーカーがタスクを処理

### テスト条件
- [ ] 統合テストが作成されている
- [ ] サービス起動時間が許容範囲内
- [ ] ヘルスチェックが適切に動作
- [ ] エラー処理が適切に動作

## トラブルシューティング

### よくある問題

1. **コンテナ起動失敗**
   - 解決策: ポート競合、メモリ不足を確認

2. **サービス間通信失敗**
   - 解決策: ネットワーク設定、サービス名解決を確認

3. **データベース接続失敗**
   - 解決策: ヘルスチェック、認証情報を確認

4. **Nginxプロキシエラー**
   - 解決策: upstream設定、サービス可用性を確認

## 次のタスクへの引き継ぎ

### 01_monitoring_observability.md への前提条件
- Docker環境が正常稼働
- 全サービスがコンテナ化済み
- ヘルスチェックエンドポイントが利用可能

### 引き継ぎファイル
- `docker-compose.yml` - メインサービス定義
- `docker/nginx/` - プロキシ設定
- `scripts/` - 管理スクリプト
- 統合テスト
