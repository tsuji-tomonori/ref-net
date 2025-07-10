# バックアップ・リストア手順書

## 概要

RefNetシステムのバックアップとリストアの手順を定義します。

## バックアップ戦略

### 1. バックアップ対象

#### データベース（PostgreSQL）
- **対象**: refnetデータベース全体
- **頻度**: 毎日自動実行（午前2時）
- **保存期間**: 7日間（自動削除）
- **形式**: SQL dump（gzip圧縮）

#### 設定ファイル
- **対象**: docker-compose.yml, .env, monitoring設定
- **頻度**: 週次（日曜日）
- **保存期間**: 4週間
- **形式**: tar.gz

#### Obsidianボルト
- **対象**: 生成されたMarkdownファイル
- **頻度**: 毎日自動実行
- **保存期間**: 30日間
- **形式**: tar.gz

### 2. バックアップ場所

```
/var/backups/refnet/
├── database/
│   ├── refnet_20231201_020000.sql.gz
│   ├── refnet_20231202_020000.sql.gz
│   └── ...
├── config/
│   ├── config_20231203.tar.gz
│   ├── config_20231210.tar.gz
│   └── ...
└── obsidian/
    ├── vault_20231201.tar.gz
    ├── vault_20231202.tar.gz
    └── ...
```

## 自動バックアップ設定

### 1. データベース自動バックアップ

#### Celery Beat設定

```python
# package/shared/src/refnet_shared/celery_config.py
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'daily-database-backup': {
        'task': 'refnet.tasks.backup_database',
        'schedule': crontab(hour=2, minute=0),  # 毎日午前2時
        'options': {'priority': 9}
    },
    'weekly-config-backup': {
        'task': 'refnet.tasks.backup_config',
        'schedule': crontab(day_of_week=0, hour=3, minute=0),  # 毎週日曜日午前3時
        'options': {'priority': 8}
    },
    'daily-obsidian-backup': {
        'task': 'refnet.tasks.backup_obsidian',
        'schedule': crontab(hour=1, minute=0),  # 毎日午前1時
        'options': {'priority': 7}
    }
}
```

#### バックアップタスク実装

```python
# package/api/src/refnet_api/tasks/backup_tasks.py
from celery import shared_task
import subprocess
import os
from pathlib import Path

@shared_task(bind=True, max_retries=3)
def backup_database(self):
    """データベースバックアップタスク"""
    try:
        script_path = Path(__file__).parent.parent.parent.parent / "scripts" / "backup-database.sh"
        result = subprocess.run([str(script_path)],
                              capture_output=True,
                              text=True,
                              check=True)
        return {"status": "success", "output": result.stdout}
    except subprocess.CalledProcessError as e:
        self.retry(countdown=300, exc=e)
    except Exception as e:
        return {"status": "error", "message": str(e)}
```

### 2. システム起動時の自動バックアップ設定

#### systemd timer設定

```ini
# /etc/systemd/system/refnet-backup.timer
[Unit]
Description=RefNet Database Backup Timer
Requires=refnet-backup.service

[Timer]
OnCalendar=daily
Persistent=true
RandomizedDelaySec=600

[Install]
WantedBy=timers.target
```

```ini
# /etc/systemd/system/refnet-backup.service
[Unit]
Description=RefNet Database Backup Service
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
WorkingDirectory=/home/user/ref-net
ExecStart=/home/user/ref-net/scripts/backup-database.sh
User=user
Group=user
```

#### 有効化

```bash
sudo systemctl enable refnet-backup.timer
sudo systemctl start refnet-backup.timer
```

## 手動バックアップ手順

### 1. データベースバックアップ

#### 標準バックアップ

```bash
# 基本的なバックアップ
./scripts/backup-database.sh

# 指定されたディレクトリにバックアップ
./scripts/backup-database.sh /custom/backup/path
```

#### 高度なバックアップ

```bash
# 1. 現在のデータベースサイズ確認
docker-compose exec postgres psql -U refnet -c "
SELECT
  pg_database.datname,
  pg_size_pretty(pg_database_size(pg_database.datname)) AS size
FROM pg_database
WHERE datname = 'refnet';
"

# 2. テーブル別サイズ確認
docker-compose exec postgres psql -U refnet -c "
SELECT
  tablename,
  pg_size_pretty(pg_total_relation_size(tablename::regclass)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(tablename::regclass) DESC;
"

# 3. 特定テーブルのバックアップ
docker-compose exec postgres pg_dump -U refnet -t papers refnet > papers_backup.sql
```

### 2. 設定ファイルバックアップ

```bash
#!/bin/bash
# scripts/backup-config.sh

DATE=$(date +%Y%m%d)
BACKUP_DIR="/var/backups/refnet/config"
BACKUP_FILE="config_${DATE}.tar.gz"

mkdir -p "$BACKUP_DIR"

# 設定ファイルのバックアップ
tar -czf "$BACKUP_DIR/$BACKUP_FILE" \
  docker-compose.yml \
  .env \
  monitoring/ \
  scripts/ \
  docs/

echo "設定ファイルをバックアップしました: $BACKUP_DIR/$BACKUP_FILE"
```

### 3. Obsidianボルトバックアップ

```bash
#!/bin/bash
# scripts/backup-obsidian.sh

DATE=$(date +%Y%m%d)
BACKUP_DIR="/var/backups/refnet/obsidian"
BACKUP_FILE="vault_${DATE}.tar.gz"
VAULT_PATH="/path/to/obsidian/vault"

mkdir -p "$BACKUP_DIR"

# Obsidianボルトのバックアップ
if [ -d "$VAULT_PATH" ]; then
  tar -czf "$BACKUP_DIR/$BACKUP_FILE" -C "$VAULT_PATH" .
  echo "Obsidianボルトをバックアップしました: $BACKUP_DIR/$BACKUP_FILE"
else
  echo "警告: Obsidianボルトが見つかりません: $VAULT_PATH"
fi
```

## リストア手順

### 1. データベースリストア

#### 基本リストア

```bash
# 最新のバックアップから復元
LATEST_BACKUP=$(ls -t /var/backups/refnet/database/refnet_*.sql.gz | head -1)
./scripts/restore-database.sh "$LATEST_BACKUP"

# 強制実行（確認なし）
./scripts/restore-database.sh "$LATEST_BACKUP" --force
```

#### 特定日時のバックアップから復元

```bash
# 利用可能なバックアップの確認
ls -la /var/backups/refnet/database/

# 特定のバックアップから復元
./scripts/restore-database.sh /var/backups/refnet/database/refnet_20231201_020000.sql.gz
```

#### 部分的なリストア

```bash
# 特定テーブルのリストア
# 1. バックアップファイルから特定テーブルを抽出
zcat /var/backups/refnet/database/refnet_20231201_020000.sql.gz | \
  sed -n '/^-- Data for Name: papers;/,/^-- Data for Name: /p' > papers_data.sql

# 2. テーブルの削除と再作成
docker-compose exec postgres psql -U refnet -c "TRUNCATE TABLE papers CASCADE;"

# 3. データの復元
docker-compose exec -T postgres psql -U refnet -d refnet < papers_data.sql
```

### 2. 設定ファイルリストア

```bash
#!/bin/bash
# scripts/restore-config.sh

BACKUP_FILE="$1"
if [ -z "$BACKUP_FILE" ]; then
    echo "使用方法: $0 <config_backup_file>"
    exit 1
fi

# 現在の設定ファイルをバックアップ
tar -czf "current_config_$(date +%Y%m%d_%H%M%S).tar.gz" \
  docker-compose.yml \
  .env \
  monitoring/ \
  scripts/ \
  docs/

# バックアップから復元
tar -xzf "$BACKUP_FILE"

echo "設定ファイルを復元しました: $BACKUP_FILE"
echo "サービスを再起動してください: docker-compose down && docker-compose up -d"
```

### 3. Obsidianボルトリストア

```bash
#!/bin/bash
# scripts/restore-obsidian.sh

BACKUP_FILE="$1"
VAULT_PATH="/path/to/obsidian/vault"

if [ -z "$BACKUP_FILE" ]; then
    echo "使用方法: $0 <vault_backup_file>"
    exit 1
fi

# 現在のボルトをバックアップ
if [ -d "$VAULT_PATH" ]; then
  tar -czf "current_vault_$(date +%Y%m%d_%H%M%S).tar.gz" -C "$VAULT_PATH" .
fi

# ボルトディレクトリの作成
mkdir -p "$VAULT_PATH"

# バックアップから復元
tar -xzf "$BACKUP_FILE" -C "$VAULT_PATH"

echo "Obsidianボルトを復元しました: $BACKUP_FILE"
```

## 災害復旧手順

### 1. 完全データ損失からの復旧

```bash
#!/bin/bash
# scripts/disaster-recovery.sh

echo "=== 災害復旧手順 ==="

# 1. システム環境の準備
echo "1. システム環境の準備"
sudo apt update && sudo apt install -y docker.io docker-compose git

# 2. リポジトリの復旧
echo "2. リポジトリの復旧"
git clone https://github.com/your-org/ref-net.git
cd ref-net

# 3. 設定ファイルの復旧
echo "3. 設定ファイルの復旧"
LATEST_CONFIG=$(ls -t /var/backups/refnet/config/config_*.tar.gz | head -1)
tar -xzf "$LATEST_CONFIG"

# 4. データベースの復旧
echo "4. データベースの復旧"
docker-compose up -d postgres
sleep 30
LATEST_DB=$(ls -t /var/backups/refnet/database/refnet_*.sql.gz | head -1)
./scripts/restore-database.sh "$LATEST_DB" --force

# 5. システム全体の起動
echo "5. システム全体の起動"
docker-compose up -d

# 6. 復旧確認
echo "6. 復旧確認"
sleep 60
curl -f http://localhost/health

echo "災害復旧が完了しました"
```

### 2. 段階的復旧

```bash
#!/bin/bash
# scripts/staged-recovery.sh

echo "=== 段階的復旧手順 ==="

# Phase 1: データストレージの復旧
echo "Phase 1: データストレージの復旧"
docker-compose up -d postgres redis
sleep 30

# Phase 2: データベースの復旧
echo "Phase 2: データベースの復旧"
LATEST_DB=$(ls -t /var/backups/refnet/database/refnet_*.sql.gz | head -1)
./scripts/restore-database.sh "$LATEST_DB" --force

# Phase 3: アプリケーションサービスの復旧
echo "Phase 3: アプリケーションサービスの復旧"
docker-compose up -d api
sleep 30

# Phase 4: バックグラウンドサービスの復旧
echo "Phase 4: バックグラウンドサービスの復旧"
docker-compose up -d crawler summarizer generator celery-beat
sleep 30

# Phase 5: 外部サービスの復旧
echo "Phase 5: 外部サービスの復旧"
docker-compose up -d nginx flower prometheus grafana
sleep 30

# Phase 6: 復旧確認
echo "Phase 6: 復旧確認"
./scripts/recovery-verification.sh

echo "段階的復旧が完了しました"
```

## バックアップ検証

### 1. 定期的なバックアップ検証

```bash
#!/bin/bash
# scripts/verify-backup.sh

BACKUP_FILE="$1"
if [ -z "$BACKUP_FILE" ]; then
    BACKUP_FILE=$(ls -t /var/backups/refnet/database/refnet_*.sql.gz | head -1)
fi

echo "=== バックアップ検証 ==="
echo "検証対象: $BACKUP_FILE"

# 1. ファイルの存在確認
if [ ! -f "$BACKUP_FILE" ]; then
    echo "エラー: バックアップファイルが見つかりません"
    exit 1
fi

# 2. ファイルサイズ確認
SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "バックアップサイズ: $SIZE"

# 3. 圧縮ファイルの整合性確認
if zcat "$BACKUP_FILE" >/dev/null 2>&1; then
    echo "✓ 圧縮ファイルの整合性: OK"
else
    echo "✗ 圧縮ファイルの整合性: NG"
    exit 1
fi

# 4. SQLファイルの形式確認
if zcat "$BACKUP_FILE" | head -1 | grep -q "PostgreSQL database dump"; then
    echo "✓ SQLファイルの形式: OK"
else
    echo "✗ SQLファイルの形式: NG"
    exit 1
fi

# 5. 主要テーブルの存在確認
TABLES=("papers" "citations" "summaries" "jobs")
for table in "${TABLES[@]}"; do
    if zcat "$BACKUP_FILE" | grep -q "CREATE TABLE.*$table"; then
        echo "✓ テーブル $table: 存在"
    else
        echo "✗ テーブル $table: 不存在"
    fi
done

echo "バックアップ検証が完了しました"
```

### 2. 月次復旧テスト

```bash
#!/bin/bash
# scripts/monthly-recovery-test.sh

echo "=== 月次復旧テスト ==="

# 1. テスト環境の準備
echo "1. テスト環境の準備"
cp docker-compose.yml docker-compose.test.yml
sed -i 's/refnet_/test_refnet_/g' docker-compose.test.yml
sed -i 's/5432:5432/5433:5432/g' docker-compose.test.yml

# 2. テスト環境の起動
echo "2. テスト環境の起動"
docker-compose -f docker-compose.test.yml up -d postgres

# 3. 最新バックアップからの復旧テスト
echo "3. 復旧テスト"
LATEST_BACKUP=$(ls -t /var/backups/refnet/database/refnet_*.sql.gz | head -1)
sleep 30
zcat "$LATEST_BACKUP" | docker-compose -f docker-compose.test.yml exec -T postgres psql -U refnet -d refnet

# 4. データ確認
echo "4. データ確認"
PAPER_COUNT=$(docker-compose -f docker-compose.test.yml exec postgres psql -U refnet -t -c "SELECT COUNT(*) FROM papers;" | xargs)
echo "復旧された論文数: $PAPER_COUNT"

# 5. テスト環境の削除
echo "5. テスト環境の削除"
docker-compose -f docker-compose.test.yml down -v
rm docker-compose.test.yml

echo "月次復旧テストが完了しました"
echo "復旧された論文数: $PAPER_COUNT"
```

## 監視とアラート

### 1. バックアップ監視

```bash
#!/bin/bash
# scripts/monitor-backup.sh

echo "=== バックアップ監視 ==="

# 1. 最新バックアップの確認
LATEST_BACKUP=$(ls -t /var/backups/refnet/database/refnet_*.sql.gz 2>/dev/null | head -1)
if [ -z "$LATEST_BACKUP" ]; then
    echo "警告: バックアップファイルが見つかりません"
    exit 1
fi

# 2. バックアップの実行時間確認
BACKUP_TIME=$(stat -c %Y "$LATEST_BACKUP")
CURRENT_TIME=$(date +%s)
TIME_DIFF=$((CURRENT_TIME - BACKUP_TIME))

if [ $TIME_DIFF -gt 86400 ]; then
    echo "警告: 最新バックアップが24時間以上古いです"
    exit 1
fi

# 3. バックアップサイズの確認
BACKUP_SIZE=$(stat -c %s "$LATEST_BACKUP")
if [ $BACKUP_SIZE -lt 1048576 ]; then
    echo "警告: バックアップサイズが異常に小さいです"
    exit 1
fi

echo "バックアップ監視: 正常"
```

### 2. Prometheus メトリクス

```python
# バックアップ関連のメトリクス
BACKUP_SUCCESS_TIME = Gauge('refnet_backup_success_timestamp', 'Last successful backup timestamp')
BACKUP_SIZE_BYTES = Gauge('refnet_backup_size_bytes', 'Backup file size in bytes')
BACKUP_DURATION_SECONDS = Histogram('refnet_backup_duration_seconds', 'Backup execution duration')

def record_backup_metrics(backup_file, duration):
    """バックアップメトリクスの記録"""
    BACKUP_SUCCESS_TIME.set(time.time())
    BACKUP_SIZE_BYTES.set(os.path.getsize(backup_file))
    BACKUP_DURATION_SECONDS.observe(duration)
```

## トラブルシューティング

### 1. バックアップ失敗

```bash
# 原因調査
docker-compose logs postgres
tail -f /var/log/refnet-backup.log

# 一般的な対処
docker-compose restart postgres
df -h  # ディスク容量確認
```

### 2. リストア失敗

```bash
# 原因調査
docker-compose logs postgres
tail -f /var/log/refnet-restore.log

# 一般的な対処
docker-compose down
docker volume rm refnet_postgres_data
docker-compose up -d postgres
```

### 3. 権限エラー

```bash
# 権限修正
sudo chown -R $(id -u):$(id -g) /var/backups/refnet
chmod +x scripts/*.sh
```
