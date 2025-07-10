# 起動・停止手順書

## 概要

RefNetシステムの起動・停止手順を定義します。

## 前提条件

### 必要なソフトウェア

- Docker Engine 20.10+
- Docker Compose 2.0+
- Git
- 8GB以上のメモリ
- 20GB以上のディスク容量

### 環境変数

以下の環境変数を設定してください：

```bash
# .env ファイル例
POSTGRES_DB=refnet
POSTGRES_USER=refnet
POSTGRES_PASSWORD=your_secure_password
REDIS_PASSWORD=your_redis_password
CLAUDE_API_KEY=your_claude_api_key
SEMANTIC_SCHOLAR_API_KEY=your_semantic_scholar_key
```

## 起動手順

### 1. 通常起動（推奨）

```bash
# 1. リポジトリのクローン
git clone https://github.com/tsuji-tomonori/ref-net.git
cd ref-net

# 2. 環境変数の設定
cp .env.example .env
# .env ファイルを編集

# 3. 全サービスの起動
docker-compose up -d
```

### 2. 段階的起動

サービスの依存関係を考慮した段階的起動：

```bash
# 1. データストア層の起動
docker-compose up -d postgres redis

# 2. データベースの初期化完了を待機
docker-compose exec postgres pg_isready -U refnet

# 3. APIサービスの起動
docker-compose up -d api

# 4. ワーカーサービスの起動
docker-compose up -d crawler summarizer generator celery-beat

# 5. プロキシ・監視サービスの起動
docker-compose up -d nginx flower prometheus grafana
```

### 3. 開発環境起動

```bash
# 開発用の起動（ログを表示）
docker-compose up --build

# 特定のサービスのみ起動
docker-compose up api postgres redis
```

## 停止手順

### 1. 通常停止

```bash
# 全サービスの停止
docker-compose down

# データボリュームも削除する場合
docker-compose down -v
```

### 2. 段階的停止

サービス間の依存関係を考慮した段階的停止：

```bash
# 1. 監視・プロキシサービスの停止
docker-compose stop grafana prometheus flower nginx

# 2. ワーカーサービスの停止
docker-compose stop celery-beat crawler summarizer generator

# 3. APIサービスの停止
docker-compose stop api

# 4. データストアの停止
docker-compose stop postgres redis
```

### 3. 緊急停止

```bash
# 強制停止
docker-compose kill

# コンテナの削除
docker-compose rm -f
```

## 起動確認

### 1. サービス状態確認

```bash
# 全サービスの状態確認
docker-compose ps

# 特定サービスの状態確認
docker-compose ps api
```

### 2. ヘルスチェック

```bash
# API ヘルスチェック
curl -f http://localhost/health

# PostgreSQL 接続確認
docker-compose exec postgres pg_isready -U refnet

# Redis 接続確認
docker-compose exec redis redis-cli ping
```

### 3. ログ確認

```bash
# 全サービスのログ
docker-compose logs

# 特定サービスのログ
docker-compose logs api

# リアルタイムログ表示
docker-compose logs -f api
```

## 監視URL

起動後、以下のURLでサービスにアクセスできます：

| サービス | URL | 説明 |
|---------|-----|------|
| RefNet API | http://localhost/docs | API仕様書 |
| Grafana | http://localhost:3000 | 監視ダッシュボード |
| Flower | http://localhost:5555 | Celery監視 |
| Prometheus | http://localhost:9090 | メトリクス収集 |

## トラブルシューティング

### 起動に失敗する場合

#### 1. ポート競合

```bash
# ポート使用状況確認
netstat -tulpn | grep :80
netstat -tulpn | grep :5432

# 競合サービスの停止
sudo systemctl stop nginx
sudo systemctl stop postgresql
```

#### 2. メモリ不足

```bash
# メモリ使用量確認
free -h

# 不要なコンテナの削除
docker container prune
docker image prune
```

#### 3. 権限エラー

```bash
# Dockerグループに追加
sudo usermod -aG docker $USER

# 再ログイン後に確認
docker run hello-world
```

### サービスが応答しない場合

#### 1. コンテナ再起動

```bash
# 特定サービスの再起動
docker-compose restart api

# 全サービスの再起動
docker-compose restart
```

#### 2. データベース復旧

```bash
# PostgreSQL 復旧
docker-compose exec postgres pg_resetwal -f /var/lib/postgresql/data

# Redis 復旧
docker-compose exec redis redis-cli FLUSHALL
```

### ログファイルの場所

```bash
# Docker Composeログ
docker-compose logs > refnet-logs.txt

# 個別サービスログ
docker-compose logs api > api-logs.txt
```

## 自動起動設定

### systemd サービス（Linux）

```ini
# /etc/systemd/system/refnet.service
[Unit]
Description=RefNet System
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/path/to/ref-net
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

```bash
# サービス有効化
sudo systemctl enable refnet.service
sudo systemctl start refnet.service
```

## 定期メンテナンス

### 1. 週次メンテナンス

```bash
#!/bin/bash
# scripts/weekly-maintenance.sh

# ログローテーション
docker-compose logs > logs/refnet-$(date +%Y%m%d).log

# 不要なDockerリソース削除
docker system prune -f

# データベース統計更新
docker-compose exec postgres psql -U refnet -c "ANALYZE;"
```

### 2. 月次メンテナンス

```bash
#!/bin/bash
# scripts/monthly-maintenance.sh

# データベースバックアップ
docker-compose exec postgres pg_dump -U refnet refnet > backups/refnet-$(date +%Y%m%d).sql

# ディスク使用量確認
df -h

# メモリ使用量確認
free -h
```

### 3. 四半期メンテナンス

```bash
#!/bin/bash
# scripts/quarterly-maintenance.sh

# Dockerイメージ更新
docker-compose pull
docker-compose up -d

# 設定ファイルのバックアップ
tar -czf backups/config-$(date +%Y%m%d).tar.gz docker-compose.yml .env monitoring/
```
