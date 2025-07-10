# 定期メンテナンス手順書

## 概要

RefNetシステムの定期メンテナンス作業を定義します。

## メンテナンススケジュール

### 日次メンテナンス（自動）

| 時間 | 作業内容 | 実行方法 |
|------|----------|----------|
| 02:00 | データベースバックアップ | Celery Beat |
| 03:00 | ログローテーション | Celery Beat |
| 04:00 | 不要データのクリーンアップ | Celery Beat |

### 週次メンテナンス（手動）

| 曜日 | 作業内容 | 担当 |
|------|----------|------|
| 日曜日 | システム全体チェック | 運用担当 |
| 日曜日 | データベース統計更新 | 自動 |
| 日曜日 | 不要Dockerリソース削除 | 手動 |

### 月次メンテナンス（手動）

| 日付 | 作業内容 | 担当 |
|------|----------|------|
| 第1日曜日 | システム更新 | 運用担当 |
| 第2日曜日 | セキュリティ更新 | 運用担当 |
| 第3日曜日 | 性能チューニング | 運用担当 |
| 第4日曜日 | 災害復旧テスト | 運用担当 |

## 日次メンテナンス

### 1. データベースバックアップ（自動）

```bash
#!/bin/bash
# scripts/daily-backup.sh

BACKUP_DIR="/var/backups/refnet"
DATE=$(date +%Y%m%d_%H%M%S)

# バックアップディレクトリ作成
mkdir -p $BACKUP_DIR

# PostgreSQLバックアップ
docker-compose exec postgres pg_dump -U refnet refnet > "$BACKUP_DIR/refnet_$DATE.sql"

# 圧縮
gzip "$BACKUP_DIR/refnet_$DATE.sql"

# 7日より古いバックアップを削除
find $BACKUP_DIR -name "refnet_*.sql.gz" -mtime +7 -delete

# バックアップ結果をログに記録
echo "$(date): Backup completed - refnet_$DATE.sql.gz" >> /var/log/refnet-backup.log
```

### 2. ログローテーション（自動）

```bash
#!/bin/bash
# scripts/daily-log-rotation.sh

LOG_DIR="/var/log/refnet"
DATE=$(date +%Y%m%d)

# ログディレクトリ作成
mkdir -p $LOG_DIR

# Dockerログの保存
docker-compose logs --since 24h > "$LOG_DIR/refnet_$DATE.log"

# 古いログファイルの圧縮
find $LOG_DIR -name "refnet_*.log" -mtime +1 -exec gzip {} \;

# 30日より古いログを削除
find $LOG_DIR -name "refnet_*.log.gz" -mtime +30 -delete
```

### 3. 不要データクリーンアップ（自動）

```bash
#!/bin/bash
# scripts/daily-cleanup.sh

# 1. 完了したCeleryタスクの削除（1週間以上前）
docker-compose exec redis redis-cli --eval - 0 <<'EOF'
local keys = redis.call('keys', 'celery-task-meta-*')
for i=1,#keys do
  local ttl = redis.call('ttl', keys[i])
  if ttl > 604800 then  -- 1週間 = 604800秒
    redis.call('del', keys[i])
  end
end
EOF

# 2. 古いジョブログの削除
docker-compose exec postgres psql -U refnet -c "DELETE FROM job_logs WHERE created_at < NOW() - INTERVAL '30 days';"

# 3. 一時ファイルの削除
docker-compose exec api find /tmp -type f -mtime +1 -delete
```

## 週次メンテナンス

### 1. システム全体チェック

```bash
#!/bin/bash
# scripts/weekly-system-check.sh

echo "=== RefNet週次メンテナンス ==="
echo "日時: $(date)"
echo

# 1. サービス稼働状況
echo "1. サービス稼働状況:"
docker-compose ps

# 2. システムリソース使用状況
echo "2. システムリソース:"
echo "CPU使用率:"
docker stats --no-stream | grep -v CONTAINER

echo "メモリ使用量:"
free -h

echo "ディスク使用量:"
df -h

# 3. データベース統計
echo "3. データベース統計:"
docker-compose exec postgres psql -U refnet -c "
SELECT
  schemaname,
  tablename,
  n_tup_ins,
  n_tup_upd,
  n_tup_del,
  n_dead_tup
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY n_tup_ins DESC;
"

# 4. 週次パフォーマンス
echo "4. 週次パフォーマンス:"
docker-compose exec postgres psql -U refnet -c "
SELECT
  COUNT(*) as total_papers,
  COUNT(CASE WHEN created_at >= NOW() - INTERVAL '7 days' THEN 1 END) as new_papers,
  COUNT(CASE WHEN updated_at >= NOW() - INTERVAL '7 days' THEN 1 END) as updated_papers
FROM papers;
"
```

### 2. データベース統計更新

```bash
#!/bin/bash
# scripts/weekly-db-maintenance.sh

echo "=== データベース週次メンテナンス ==="

# 1. VACUUM
echo "1. VACUUM実行:"
docker-compose exec postgres psql -U refnet -c "VACUUM ANALYZE;"

# 2. インデックス再構築
echo "2. インデックス再構築:"
docker-compose exec postgres psql -U refnet -c "REINDEX DATABASE refnet;"

# 3. 統計情報更新
echo "3. 統計情報更新:"
docker-compose exec postgres psql -U refnet -c "ANALYZE;"

# 4. データベースサイズ確認
echo "4. データベースサイズ:"
docker-compose exec postgres psql -U refnet -c "
SELECT
  pg_database.datname,
  pg_size_pretty(pg_database_size(pg_database.datname)) AS size
FROM pg_database;
"
```

### 3. 不要Dockerリソース削除

```bash
#!/bin/bash
# scripts/weekly-docker-cleanup.sh

echo "=== Docker週次クリーンアップ ==="

# 1. 停止中のコンテナ削除
echo "1. 停止中のコンテナ削除:"
docker container prune -f

# 2. 未使用のイメージ削除
echo "2. 未使用のイメージ削除:"
docker image prune -f

# 3. 未使用のネットワーク削除
echo "3. 未使用のネットワーク削除:"
docker network prune -f

# 4. 未使用のボリューム削除（注意：データが削除される）
echo "4. 未使用のボリューム確認:"
docker volume ls -f dangling=true

# 5. ディスク使用量の確認
echo "5. Docker使用ディスク量:"
docker system df
```

## 月次メンテナンス

### 1. システム更新

```bash
#!/bin/bash
# scripts/monthly-system-update.sh

echo "=== 月次システム更新 ==="

# 1. システムパッケージ更新
echo "1. システムパッケージ更新:"
sudo apt update && sudo apt upgrade -y

# 2. Docker更新
echo "2. Docker更新:"
sudo apt update && sudo apt install docker-ce docker-ce-cli containerd.io -y

# 3. Docker Compose更新
echo "3. Docker Compose更新:"
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 4. RefNetイメージ更新
echo "4. RefNetイメージ更新:"
cd /path/to/ref-net
docker-compose pull
docker-compose up -d --build

# 5. 更新確認
echo "5. 更新確認:"
docker-compose ps
```

### 2. セキュリティ更新

```bash
#!/bin/bash
# scripts/monthly-security-update.sh

echo "=== 月次セキュリティ更新 ==="

# 1. セキュリティパッケージ更新
echo "1. セキュリティパッケージ更新:"
sudo apt list --upgradable | grep -i security

# 2. 脆弱性スキャン
echo "2. 脆弱性スキャン:"
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy image refnet/api:latest

# 3. 設定ファイル確認
echo "3. 設定ファイル確認:"
# パスワード強度チェック
# アクセス権限チェック
# 不要なポート開放チェック

# 4. ログ監査
echo "4. セキュリティログ監査:"
sudo journalctl -u docker --since "1 month ago" | grep -i "error\|fail\|unauthorized"
```

### 3. 性能チューニング

```bash
#!/bin/bash
# scripts/monthly-performance-tuning.sh

echo "=== 月次性能チューニング ==="

# 1. データベース性能分析
echo "1. データベース性能分析:"
docker-compose exec postgres psql -U refnet -c "
SELECT
  query,
  calls,
  total_time,
  mean_time,
  max_time
FROM pg_stat_statements
ORDER BY total_time DESC
LIMIT 10;
"

# 2. インデックス使用状況
echo "2. インデックス使用状況:"
docker-compose exec postgres psql -U refnet -c "
SELECT
  t.tablename,
  indexname,
  c.reltuples AS num_rows,
  pg_size_pretty(pg_relation_size(quote_ident(t.tablename)::text)) AS table_size,
  pg_size_pretty(pg_relation_size(quote_ident(indexrelname)::text)) AS index_size,
  CASE WHEN indisunique THEN 'Y' ELSE 'N' END AS unique,
  idx_scan AS number_of_scans,
  idx_tup_read AS tuples_read,
  idx_tup_fetch AS tuples_fetched
FROM pg_tables t
LEFT OUTER JOIN pg_class c ON c.relname=t.tablename
LEFT OUTER JOIN (
  SELECT
    c.relname AS ctablename,
    ipg.relname AS indexname,
    x.indnatts AS number_of_columns,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch,
    indexrelname,
    indisunique
  FROM pg_index x
  JOIN pg_class c ON c.oid = x.indrelid
  JOIN pg_class ipg ON ipg.oid = x.indexrelid
  JOIN pg_stat_all_indexes psai ON x.indexrelid = psai.indexrelid
) AS foo ON t.tablename = foo.ctablename
WHERE t.schemaname='public'
ORDER BY 1,2;
"

# 3. Celeryワーカー性能
echo "3. Celeryワーカー性能:"
docker-compose exec flower curl -s http://localhost:5555/api/workers | jq '.[] | {name: .name, active: .active, processed: .processed}'
```

### 4. 災害復旧テスト

```bash
#!/bin/bash
# scripts/monthly-disaster-recovery-test.sh

echo "=== 月次災害復旧テスト ==="

# 1. バックアップからの復旧テスト
echo "1. バックアップからの復旧テスト:"
BACKUP_FILE="/var/backups/refnet/refnet_$(date +%Y%m%d -d '1 day ago')_*.sql.gz"

# テスト環境での復旧
docker-compose -f docker-compose.test.yml up -d postgres
sleep 10
zcat $BACKUP_FILE | docker-compose -f docker-compose.test.yml exec -T postgres psql -U refnet -d refnet

# 2. 設定ファイルバックアップ
echo "2. 設定ファイルバックアップ:"
tar -czf /var/backups/refnet/config-$(date +%Y%m%d).tar.gz \
  docker-compose.yml \
  .env \
  monitoring/ \
  scripts/

# 3. 復旧手順書の確認
echo "3. 復旧手順書の確認:"
echo "災害復旧手順書: docs/troubleshooting/recovery-procedures.md"
echo "最終更新: $(stat -c %y docs/troubleshooting/recovery-procedures.md)"
```

## メンテナンス結果の記録

### 1. メンテナンスログ

```bash
# /var/log/refnet-maintenance.log
echo "$(date): $(whoami) - $1" >> /var/log/refnet-maintenance.log
```

### 2. 作業完了チェックリスト

```markdown
# 週次メンテナンス完了チェックリスト

- [ ] システム全体チェック実行
- [ ] データベース統計更新
- [ ] 不要Dockerリソース削除
- [ ] 監視ダッシュボード確認
- [ ] エラーログ確認
- [ ] バックアップ状態確認
- [ ] ディスク使用量確認
- [ ] 作業結果記録

実施日: ___________
実施者: ___________
```

## トラブル時の対応

### 1. メンテナンス中のエラー

```bash
# エラー発生時の緊急対応
1. サービス停止: docker-compose down
2. ログ確認: docker-compose logs
3. バックアップから復旧: scripts/restore-from-backup.sh
4. エラー報告: 運用担当者へ連絡
```

### 2. 性能劣化の対応

```bash
# 性能劣化時の対応
1. リソース使用量確認
2. 長時間実行クエリ確認
3. データベース再起動
4. インデックス再構築
```
