# 復旧手順書

## 概要

RefNetシステムの災害復旧手順を定義します。

## 復旧シナリオ

### 1. 完全システム停止からの復旧

#### 前提条件
- バックアップデータが利用可能
- 新しいハードウェア/仮想環境が利用可能
- 必要な設定ファイルが保存されている

#### 復旧手順

```bash
#!/bin/bash
# scripts/full-system-recovery.sh

echo "=== 完全システム復旧 ==="
echo "開始時刻: $(date)"

# 1. 環境準備
echo "1. 環境準備"
# Docker環境のセットアップ
sudo apt update
sudo apt install -y docker.io docker-compose
sudo usermod -aG docker $USER

# 2. リポジトリ復旧
echo "2. リポジトリ復旧"
git clone https://github.com/tsuji-tomonori/ref-net.git
cd ref-net

# 3. 設定ファイル復旧
echo "3. 設定ファイル復旧"
# バックアップから設定ファイルを復元
tar -xzf /path/to/backup/config-backup.tar.gz

# 4. データベース復旧
echo "4. データベース復旧"
# PostgreSQLコンテナの起動
docker-compose up -d postgres
sleep 30

# 最新バックアップの復元
LATEST_BACKUP=$(ls -t /path/to/backup/refnet_*.sql.gz | head -1)
zcat $LATEST_BACKUP | docker-compose exec -T postgres psql -U refnet -d refnet

# 5. サービス起動
echo "5. サービス起動"
docker-compose up -d

# 6. 復旧確認
echo "6. 復旧確認"
sleep 60
source scripts/recovery-verification.sh

echo "復旧完了時刻: $(date)"
```

### 2. データベース復旧

#### データベース完全損失からの復旧

```bash
#!/bin/bash
# scripts/database-recovery.sh

echo "=== データベース復旧 ==="

# 1. 現在のデータベースサービス停止
echo "1. データベースサービス停止"
docker-compose stop postgres

# 2. データボリュームのクリア
echo "2. データボリュームのクリア"
docker volume rm refnet_postgres_data

# 3. PostgreSQL再起動
echo "3. PostgreSQL再起動"
docker-compose up -d postgres
sleep 30

# 4. データベース作成
echo "4. データベース作成"
docker-compose exec postgres psql -U postgres -c "CREATE DATABASE refnet;"
docker-compose exec postgres psql -U postgres -c "CREATE USER refnet WITH PASSWORD 'password';"
docker-compose exec postgres psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE refnet TO refnet;"

# 5. 最新バックアップからの復元
echo "5. バックアップからの復元"
LATEST_BACKUP=$(ls -t /var/backups/refnet/refnet_*.sql.gz | head -1)
echo "復元するバックアップ: $LATEST_BACKUP"
zcat $LATEST_BACKUP | docker-compose exec -T postgres psql -U refnet -d refnet

# 6. データ整合性確認
echo "6. データ整合性確認"
docker-compose exec postgres psql -U refnet -c "
SELECT
  COUNT(*) as total_papers,
  COUNT(DISTINCT arxiv_id) as unique_arxiv,
  COUNT(DISTINCT semantic_scholar_id) as unique_ss
FROM papers;
"

# 7. サービス再起動
echo "7. サービス再起動"
docker-compose up -d

echo "データベース復旧完了"
```

#### 特定テーブルの復旧

```bash
#!/bin/bash
# scripts/table-recovery.sh

TABLE_NAME=$1
if [ -z "$TABLE_NAME" ]; then
  echo "使用方法: $0 <テーブル名>"
  exit 1
fi

echo "=== テーブル復旧: $TABLE_NAME ==="

# 1. 現在のテーブルのバックアップ
echo "1. 現在のテーブルのバックアップ"
docker-compose exec postgres pg_dump -U refnet -t $TABLE_NAME refnet > "current_${TABLE_NAME}_$(date +%Y%m%d_%H%M%S).sql"

# 2. テーブルの削除
echo "2. テーブルの削除"
docker-compose exec postgres psql -U refnet -c "DROP TABLE IF EXISTS $TABLE_NAME CASCADE;"

# 3. バックアップからの復元
echo "3. バックアップからの復元"
LATEST_BACKUP=$(ls -t /var/backups/refnet/refnet_*.sql.gz | head -1)
zcat $LATEST_BACKUP | docker-compose exec -T postgres psql -U refnet -d refnet

# 4. テーブル固有の復旧確認
echo "4. テーブル復旧確認"
docker-compose exec postgres psql -U refnet -c "SELECT COUNT(*) FROM $TABLE_NAME;"

echo "テーブル復旧完了: $TABLE_NAME"
```

### 3. 設定ファイル復旧

#### 設定ファイル損失からの復旧

```bash
#!/bin/bash
# scripts/config-recovery.sh

echo "=== 設定ファイル復旧 ==="

# 1. 設定ファイルのバックアップ確認
echo "1. 利用可能な設定バックアップ:"
ls -la /var/backups/refnet/config-*.tar.gz

# 2. 最新の設定バックアップを復元
echo "2. 設定ファイル復元"
LATEST_CONFIG=$(ls -t /var/backups/refnet/config-*.tar.gz | head -1)
echo "復元する設定: $LATEST_CONFIG"
tar -xzf $LATEST_CONFIG

# 3. 環境変数の確認
echo "3. 環境変数の確認"
if [ ! -f .env ]; then
  echo "警告: .env ファイルが見つかりません"
  echo "以下の環境変数を設定してください:"
  echo "- POSTGRES_DB"
  echo "- POSTGRES_USER"
  echo "- POSTGRES_PASSWORD"
  echo "- REDIS_PASSWORD"
  echo "- CLAUDE_API_KEY"
  echo "- SEMANTIC_SCHOLAR_API_KEY"
fi

# 4. 設定ファイルの妥当性確認
echo "4. 設定ファイルの妥当性確認"
docker-compose config > /dev/null
if [ $? -eq 0 ]; then
  echo "✓ Docker Compose設定は正常です"
else
  echo "✗ Docker Compose設定にエラーがあります"
fi

echo "設定ファイル復旧完了"
```

### 4. 部分的サービス復旧

#### 特定サービスの復旧

```bash
#!/bin/bash
# scripts/service-recovery.sh

SERVICE_NAME=$1
if [ -z "$SERVICE_NAME" ]; then
  echo "使用方法: $0 <サービス名>"
  echo "利用可能なサービス: api, crawler, summarizer, generator, nginx, postgres, redis"
  exit 1
fi

echo "=== サービス復旧: $SERVICE_NAME ==="

# 1. サービス停止
echo "1. サービス停止"
docker-compose stop $SERVICE_NAME

# 2. コンテナとボリュームの削除
echo "2. コンテナとボリュームの削除"
docker-compose rm -f $SERVICE_NAME

# 3. イメージの再構築（必要に応じて）
echo "3. イメージの再構築"
docker-compose build $SERVICE_NAME

# 4. サービス起動
echo "4. サービス起動"
docker-compose up -d $SERVICE_NAME

# 5. サービス確認
echo "5. サービス確認"
sleep 30
docker-compose ps $SERVICE_NAME

# 6. サービス固有の確認
case $SERVICE_NAME in
  "api")
    curl -f http://localhost/health
    ;;
  "postgres")
    docker-compose exec postgres pg_isready -U refnet
    ;;
  "redis")
    docker-compose exec redis redis-cli ping
    ;;
  *)
    echo "サービス $SERVICE_NAME の固有確認はスキップされました"
    ;;
esac

echo "サービス復旧完了: $SERVICE_NAME"
```

### 5. 外部依存関係の復旧

#### 外部API接続の復旧

```bash
#!/bin/bash
# scripts/external-api-recovery.sh

echo "=== 外部API接続復旧 ==="

# 1. Semantic Scholar API接続確認
echo "1. Semantic Scholar API接続確認"
API_KEY=$(docker-compose exec api env | grep SEMANTIC_SCHOLAR_API_KEY | cut -d'=' -f2)
if [ -z "$API_KEY" ]; then
  echo "警告: Semantic Scholar API keyが設定されていません"
else
  response=$(curl -s -w "%{http_code}" -o /dev/null -H "x-api-key: $API_KEY" https://api.semanticscholar.org/v1/paper/search?query=test)
  if [ $response -eq 200 ]; then
    echo "✓ Semantic Scholar API接続正常"
  else
    echo "✗ Semantic Scholar API接続エラー (HTTP: $response)"
  fi
fi

# 2. Claude API接続確認
echo "2. Claude API接続確認"
CLAUDE_KEY=$(docker-compose exec api env | grep CLAUDE_API_KEY | cut -d'=' -f2)
if [ -z "$CLAUDE_KEY" ]; then
  echo "警告: Claude API keyが設定されていません"
else
  response=$(curl -s -w "%{http_code}" -o /dev/null -H "x-api-key: $CLAUDE_KEY" https://api.anthropic.com/v1/messages)
  if [ $response -eq 200 ] || [ $response -eq 400 ]; then
    echo "✓ Claude API接続正常"
  else
    echo "✗ Claude API接続エラー (HTTP: $response)"
  fi
fi

# 3. ネットワーク接続確認
echo "3. ネットワーク接続確認"
docker-compose exec api ping -c 1 8.8.8.8 > /dev/null
if [ $? -eq 0 ]; then
  echo "✓ インターネット接続正常"
else
  echo "✗ インターネット接続エラー"
fi

# 4. DNS解決確認
echo "4. DNS解決確認"
docker-compose exec api nslookup api.semanticscholar.org > /dev/null
if [ $? -eq 0 ]; then
  echo "✓ DNS解決正常"
else
  echo "✗ DNS解決エラー"
fi

echo "外部API接続復旧確認完了"
```

## 復旧確認

### 全体的な復旧確認

```bash
#!/bin/bash
# scripts/recovery-verification.sh

echo "=== 復旧確認 ==="

# 1. サービス稼働確認
echo "1. サービス稼働確認"
services=("nginx" "api" "postgres" "redis" "crawler" "summarizer" "generator")
for service in "${services[@]}"; do
  status=$(docker-compose ps $service | grep -c "Up")
  if [ $status -eq 1 ]; then
    echo "✓ $service: 稼働中"
  else
    echo "✗ $service: 停止中"
    docker-compose logs $service | tail -5
  fi
done

# 2. データベース確認
echo "2. データベース確認"
paper_count=$(docker-compose exec postgres psql -U refnet -t -c "SELECT COUNT(*) FROM papers;" | xargs)
echo "論文数: $paper_count"

if [ $paper_count -gt 0 ]; then
  echo "✓ データベースデータは正常です"
else
  echo "✗ データベースデータがありません"
fi

# 3. API機能確認
echo "3. API機能確認"
api_response=$(curl -s -w "%{http_code}" -o /tmp/api_test.json http://localhost/health)
if [ $api_response -eq 200 ]; then
  echo "✓ API正常応答"
else
  echo "✗ API応答エラー (HTTP: $api_response)"
fi

# 4. Celery確認
echo "4. Celery確認"
queue_length=$(docker-compose exec redis redis-cli llen celery)
echo "キュー長: $queue_length"

# 5. 監視システム確認
echo "5. 監視システム確認"
prometheus_response=$(curl -s -w "%{http_code}" -o /dev/null http://localhost:9090/-/healthy)
if [ $prometheus_response -eq 200 ]; then
  echo "✓ Prometheus正常"
else
  echo "✗ Prometheus異常"
fi

grafana_response=$(curl -s -w "%{http_code}" -o /dev/null http://localhost:3000/api/health)
if [ $grafana_response -eq 200 ]; then
  echo "✓ Grafana正常"
else
  echo "✗ Grafana異常"
fi

# 6. 外部API接続確認
echo "6. 外部API接続確認"
semantic_scholar_response=$(curl -s -w "%{http_code}" -o /dev/null https://api.semanticscholar.org/v1/paper/search?query=test)
if [ $semantic_scholar_response -eq 200 ]; then
  echo "✓ Semantic Scholar API正常"
else
  echo "✗ Semantic Scholar API異常"
fi

echo "復旧確認完了"
```

### 機能別復旧確認

#### 論文収集機能の確認

```bash
#!/bin/bash
# scripts/verify-crawler-function.sh

echo "=== 論文収集機能確認 ==="

# 1. テスト用論文の収集
echo "1. テスト用論文の収集"
test_paper_id="1706.03762"  # Transformer論文
curl -X POST "http://localhost/papers/collect" -H "Content-Type: application/json" -d "{\"arxiv_id\": \"$test_paper_id\"}"

# 2. 収集結果の確認
echo "2. 収集結果の確認"
sleep 30
result=$(docker-compose exec postgres psql -U refnet -t -c "SELECT COUNT(*) FROM papers WHERE arxiv_id = '$test_paper_id';" | xargs)
if [ $result -eq 1 ]; then
  echo "✓ 論文収集機能正常"
else
  echo "✗ 論文収集機能異常"
fi

echo "論文収集機能確認完了"
```

#### 要約生成機能の確認

```bash
#!/bin/bash
# scripts/verify-summarizer-function.sh

echo "=== 要約生成機能確認 ==="

# 1. テスト用要約の生成
echo "1. テスト用要約の生成"
test_paper_id="1706.03762"
curl -X POST "http://localhost/papers/$test_paper_id/summarize"

# 2. 要約結果の確認
echo "2. 要約結果の確認"
sleep 60
result=$(docker-compose exec postgres psql -U refnet -t -c "SELECT COUNT(*) FROM summaries WHERE paper_id = (SELECT id FROM papers WHERE arxiv_id = '$test_paper_id');" | xargs)
if [ $result -eq 1 ]; then
  echo "✓ 要約生成機能正常"
else
  echo "✗ 要約生成機能異常"
fi

echo "要約生成機能確認完了"
```

## 復旧後の対応

### 1. 運用再開

```bash
#!/bin/bash
# scripts/post-recovery-actions.sh

echo "=== 復旧後対応 ==="

# 1. 監視の再開
echo "1. 監視の再開"
# アラートの有効化
# 監視ダッシュボードの確認

# 2. バックアップの再開
echo "2. バックアップの再開"
# バックアップスケジュールの確認
# 手動バックアップの実行

# 3. ログの確認
echo "3. ログの確認"
# エラーログの確認
# 性能ログの確認

# 4. 利用者への通知
echo "4. 利用者への通知"
# 復旧完了の通知
# 影響範囲の説明

echo "復旧後対応完了"
```

### 2. 事後検証

```bash
#!/bin/bash
# scripts/post-recovery-verification.sh

echo "=== 事後検証 ==="

# 1. 24時間後の安定性確認
echo "1. 24時間後の安定性確認"
# システムの安定稼働確認
# エラー発生状況の確認

# 2. 性能の確認
echo "2. 性能の確認"
# 応答時間の確認
# スループットの確認

# 3. データの整合性確認
echo "3. データの整合性確認"
# 復旧前後のデータ比較
# 欠損データの確認

# 4. バックアップの検証
echo "4. バックアップの検証"
# 復旧に使用したバックアップの検証
# バックアップ手順の見直し

echo "事後検証完了"
```

## 復旧手順書の更新

### 1. 手順書の見直し

- 復旧作業で発見した問題点の記録
- 手順の改善点の特定
- 新しい復旧パターンの追加

### 2. 訓練の実施

- 定期的な復旧訓練の実施
- 新しい手順の習得
- 復旧時間の短縮化

### 3. 自動化の推進

- 復旧作業の自動化
- 監視と復旧の連携
- 人為的エラーの削減
