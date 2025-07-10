# よくある問題と解決方法

## 概要

RefNetシステムで頻繁に発生する問題とその解決方法を記載します。

## 起動・接続問題

### 1. Docker起動エラー

#### 問題: `docker-compose up` でサービスが起動しない

**症状**:
```bash
ERROR: for api  Cannot start service api: driver failed programming external connectivity
```

**原因**:
- ポート競合
- Docker デーモン停止
- 権限不足

**解決方法**:
```bash
# 1. ポート使用状況確認
sudo netstat -tulpn | grep :8000

# 2. 競合プロセスの停止
sudo lsof -ti:8000 | xargs sudo kill -9

# 3. Dockerデーモン再起動
sudo systemctl restart docker

# 4. 権限確認
sudo usermod -aG docker $USER
# 再ログイン後に確認
```

#### 問題: コンテナが `Exited` 状態になる

**症状**:
```bash
ref-net_api_1 exited with code 1
```

**原因**:
- 環境変数の設定不備
- 依存サービスの未起動
- 設定ファイルエラー

**解決方法**:
```bash
# 1. ログ確認
docker-compose logs api

# 2. 環境変数確認
docker-compose exec api env | grep -E "POSTGRES|REDIS"

# 3. 依存サービス確認
docker-compose ps postgres redis

# 4. 設定ファイル確認
docker-compose config
```

### 2. データベース接続エラー

#### 問題: `psycopg2.OperationalError: could not connect to server`

**症状**:
```
psycopg2.OperationalError: could not connect to server: Connection refused
```

**原因**:
- PostgreSQL未起動
- 接続設定エラー
- ネットワーク問題

**解決方法**:
```bash
# 1. PostgreSQL状態確認
docker-compose exec postgres pg_isready -U refnet

# 2. 接続テスト
docker-compose exec api psql -h postgres -U refnet -d refnet -c "SELECT 1;"

# 3. ネットワーク確認
docker-compose exec api ping postgres

# 4. 接続設定確認
docker-compose exec api env | grep DATABASE_URL
```

### 3. Redis接続エラー

#### 問題: `redis.exceptions.ConnectionError: Connection refused`

**症状**:
```
redis.exceptions.ConnectionError: Error connecting to Redis
```

**原因**:
- Redis未起動
- 接続設定エラー
- 認証エラー

**解決方法**:
```bash
# 1. Redis状態確認
docker-compose exec redis redis-cli ping

# 2. 接続テスト
docker-compose exec api redis-cli -h redis ping

# 3. 認証確認
docker-compose exec redis redis-cli info | grep requirepass

# 4. 接続設定確認
docker-compose exec api env | grep REDIS_URL
```

## パフォーマンス問題

### 1. API応答が遅い

#### 問題: APIリクエストが10秒以上かかる

**症状**:
- API応答時間が異常に長い
- タイムアウトエラーが発生

**原因**:
- データベースの長時間クエリ
- 外部API呼び出しの遅延
- リソース不足

**解決方法**:
```bash
# 1. 長時間実行クエリ確認
docker-compose exec postgres psql -U refnet -c "
SELECT
  pid,
  now() - pg_stat_activity.query_start AS duration,
  query,
  state
FROM pg_stat_activity
WHERE (now() - pg_stat_activity.query_start) > interval '5 seconds';
"

# 2. 外部API応答時間確認
curl -w "@curl-format.txt" -s -o /dev/null https://api.semanticscholar.org/v1/paper/search?query=test

# 3. システムリソース確認
docker stats

# 4. 対処
# - 長時間クエリの最適化
# - インデックス追加
# - 外部APIタイムアウト設定
```

### 2. メモリ不足

#### 問題: `MemoryError` または OOM Killer

**症状**:
```
MemoryError: Unable to allocate memory
```

**原因**:
- メモリリーク
- 大きなデータの処理
- 不適切なメモリ設定

**解決方法**:
```bash
# 1. メモリ使用状況確認
docker stats
free -h

# 2. メモリ使用量の多いプロセス確認
docker-compose exec api ps aux --sort=-%mem | head -10

# 3. メモリ制限設定
# docker-compose.yml で制限設定
services:
  api:
    deploy:
      resources:
        limits:
          memory: 1G

# 4. 対処
# - メモリリークの修正
# - バッチサイズの調整
# - スワップファイルの追加
```

## Celery問題

### 1. タスクが実行されない

#### 問題: Celeryタスクがキューに溜まるが実行されない

**症状**:
- Flowerでタスクが `PENDING` のまま
- ワーカーが応答しない

**原因**:
- ワーカープロセス停止
- キューの詰まり
- タスクの無限ループ

**解決方法**:
```bash
# 1. ワーカー状態確認
docker-compose exec flower curl -s http://localhost:5555/api/workers

# 2. キューの状態確認
docker-compose exec redis redis-cli llen celery

# 3. ワーカーログ確認
docker-compose logs crawler

# 4. 対処
# - ワーカーの再起動
docker-compose restart crawler summarizer generator

# - キューのクリア（注意：実行中タスクも削除される）
docker-compose exec redis redis-cli del celery
```

### 2. タスクが失敗し続ける

#### 問題: 特定のタスクが繰り返し失敗する

**症状**:
```
Task failed with exception: ConnectionError
```

**原因**:
- 外部APIエラー
- データの不整合
- 設定エラー

**解決方法**:
```bash
# 1. 失敗タスクの詳細確認
docker-compose exec flower curl -s http://localhost:5555/api/tasks | jq '.[] | select(.state == "FAILURE")'

# 2. 具体的なエラー確認
docker-compose logs crawler | grep -A 10 -B 10 "ERROR"

# 3. 対処
# - 失敗したタスクの削除
# - 設定の修正
# - 外部API状態確認
```

## 監視・ログ問題

### 1. Grafana にデータが表示されない

#### 問題: Grafanaダッシュボードが空白

**症状**:
- グラフにデータが表示されない
- "No data" メッセージが表示される

**原因**:
- Prometheusからのデータ取得失敗
- メトリクスの設定エラー
- 時間範囲の設定問題

**解決方法**:
```bash
# 1. Prometheus接続確認
curl -s http://localhost:9090/api/v1/query?query=up

# 2. メトリクス確認
curl -s http://localhost:8000/metrics | grep refnet

# 3. Grafanaデータソース確認
# http://localhost:3000/datasources

# 4. 対処
# - Prometheusの再起動
# - メトリクスエンドポイントの確認
# - 時間範囲の調整
```

### 2. ログが出力されない

#### 問題: アプリケーションログが記録されない

**症状**:
- `docker-compose logs` で出力が少ない
- エラーが発生しているはずなのにログがない

**原因**:
- ログレベルの設定
- ログ出力先の設定
- ログローテーション設定

**解決方法**:
```bash
# 1. ログ設定確認
docker-compose exec api env | grep LOG_LEVEL

# 2. ログファイル確認
docker-compose exec api ls -la /var/log/

# 3. ログ出力テスト
docker-compose exec api python -c "import logging; logging.error('test error')"

# 4. 対処
# - ログレベルの調整
# - ログ出力先の設定
# - ログローテーション設定の確認
```

## データ問題

### 1. データ不整合

#### 問題: データベースのデータが矛盾している

**症状**:
- 論文データが重複している
- 参照関係が正しくない
- 欠損データがある

**原因**:
- 同期処理の問題
- 重複処理の実行
- 外部APIデータの変更

**解決方法**:
```bash
# 1. データ整合性チェック
docker-compose exec postgres psql -U refnet -c "
SELECT
  COUNT(*) as total,
  COUNT(DISTINCT arxiv_id) as unique_arxiv,
  COUNT(DISTINCT semantic_scholar_id) as unique_ss
FROM papers;
"

# 2. 重複データの確認
docker-compose exec postgres psql -U refnet -c "
SELECT arxiv_id, COUNT(*)
FROM papers
GROUP BY arxiv_id
HAVING COUNT(*) > 1;
"

# 3. 対処
# - 重複データの削除
# - データ同期の修正
# - 外部APIからの再取得
```

### 2. バックアップエラー

#### 問題: 自動バックアップが失敗する

**症状**:
```
pg_dump: error: connection to database failed
```

**原因**:
- データベース接続エラー
- 権限不足
- ディスク容量不足

**解決方法**:
```bash
# 1. バックアップの手動実行
docker-compose exec postgres pg_dump -U refnet refnet > test_backup.sql

# 2. ディスク容量確認
df -h

# 3. 権限確認
docker-compose exec postgres psql -U refnet -c "\du"

# 4. 対処
# - 権限の修正
# - ディスク容量の確保
# - バックアップ設定の修正
```

## 外部API問題

### 1. Semantic Scholar API エラー

#### 問題: `HTTP 429 Too Many Requests`

**症状**:
```
HTTP 429: Too Many Requests
```

**原因**:
- レート制限超過
- APIキーの問題
- 大量リクエスト

**解決方法**:
```bash
# 1. APIキー確認
docker-compose exec api env | grep SEMANTIC_SCHOLAR_API_KEY

# 2. レート制限確認
curl -I https://api.semanticscholar.org/v1/paper/search?query=test

# 3. 対処
# - リクエスト間隔の調整
# - APIキーの確認
# - バッチサイズの削減
```

### 2. LLM API エラー

#### 問題: `HTTP 401 Unauthorized`

**症状**:
```
HTTP 401: Unauthorized
```

**原因**:
- APIキーの期限切れ
- 認証設定エラー
- 使用量制限

**解決方法**:
```bash
# 1. APIキー確認
docker-compose exec api env | grep -E "CLAUDE_API_KEY|OPENAI_API_KEY"

# 2. 認証テスト
curl -H "Authorization: Bearer $CLAUDE_API_KEY" https://api.anthropic.com/v1/messages

# 3. 対処
# - APIキーの更新
# - 使用量制限の確認
# - 認証設定の修正
```

## 緊急対応チェックリスト

### システム全体が応答しない場合

```bash
# 1. システム状態確認
docker-compose ps
docker stats

# 2. 基本的な復旧試行
docker-compose restart

# 3. 個別サービス確認
docker-compose logs nginx
docker-compose logs api
docker-compose logs postgres

# 4. 最後の手段
docker-compose down
docker-compose up -d
```

### データベースが応答しない場合

```bash
# 1. PostgreSQL状態確認
docker-compose exec postgres pg_isready -U refnet

# 2. 接続数確認
docker-compose exec postgres psql -U refnet -c "SELECT count(*) FROM pg_stat_activity;"

# 3. 長時間クエリ確認
docker-compose exec postgres psql -U refnet -c "SELECT pid, query FROM pg_stat_activity WHERE state = 'active' AND query_start < now() - interval '5 minutes';"

# 4. 復旧作業
docker-compose restart postgres
# または
docker-compose down && docker-compose up -d
```

### 外部通信ができない場合

```bash
# 1. ネットワーク確認
docker-compose exec api ping 8.8.8.8

# 2. DNS確認
docker-compose exec api nslookup api.semanticscholar.org

# 3. 外部API確認
curl -s https://api.semanticscholar.org/v1/paper/search?query=test

# 4. プロキシ設定確認（必要に応じて）
docker-compose exec api env | grep -i proxy
```
