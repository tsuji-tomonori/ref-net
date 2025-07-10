#!/bin/bash

# データベースバックアップスクリプト
# 使用方法: ./backup-database.sh [backup_directory]

set -e

# 設定
BACKUP_DIR="${1:-/var/backups/refnet}"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="refnet_${DATE}.sql"
COMPRESSED_FILE="${BACKUP_FILE}.gz"
RETENTION_DAYS=7

# ログ設定
LOG_FILE="/var/log/refnet-backup.log"

# ログ出力関数
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# エラーハンドリング
trap 'log "ERROR: バックアップが失敗しました"; exit 1' ERR

log "INFO: データベースバックアップを開始します"

# 1. バックアップディレクトリの作成
log "INFO: バックアップディレクトリを作成します: $BACKUP_DIR"
mkdir -p "$BACKUP_DIR"

# 2. PostgreSQL接続確認
log "INFO: PostgreSQL接続確認"
if ! docker-compose exec postgres pg_isready -U refnet >/dev/null 2>&1; then
    log "ERROR: PostgreSQLに接続できません"
    exit 1
fi

# 3. データベースバックアップの実行
log "INFO: データベースバックアップを実行します"
docker-compose exec postgres pg_dump -U refnet -h localhost refnet > "$BACKUP_DIR/$BACKUP_FILE"

# 4. バックアップファイルの圧縮
log "INFO: バックアップファイルを圧縮します"
gzip "$BACKUP_DIR/$BACKUP_FILE"

# 5. バックアップファイルサイズの確認
BACKUP_SIZE=$(du -h "$BACKUP_DIR/$COMPRESSED_FILE" | cut -f1)
log "INFO: バックアップファイルサイズ: $BACKUP_SIZE"

# 6. 古いバックアップファイルの削除
log "INFO: $RETENTION_DAYS 日より古いバックアップファイルを削除します"
find "$BACKUP_DIR" -name "refnet_*.sql.gz" -mtime +$RETENTION_DAYS -delete

# 7. バックアップの整合性確認
log "INFO: バックアップの整合性を確認します"
if zcat "$BACKUP_DIR/$COMPRESSED_FILE" | head -1 | grep -q "PostgreSQL database dump"; then
    log "INFO: バックアップの整合性確認OK"
else
    log "ERROR: バックアップの整合性確認に失敗しました"
    exit 1
fi

# 8. 結果の記録
log "INFO: バックアップが完了しました"
log "INFO: バックアップファイル: $BACKUP_DIR/$COMPRESSED_FILE"
log "INFO: バックアップサイズ: $BACKUP_SIZE"

# 9. 現在のバックアップ一覧
log "INFO: 現在のバックアップ一覧:"
ls -lh "$BACKUP_DIR"/refnet_*.sql.gz | while read line; do
    log "INFO: $line"
done

# 10. システム通知（オプション）
if command -v notify-send >/dev/null 2>&1; then
    notify-send "RefNet Backup" "データベースバックアップが完了しました ($BACKUP_SIZE)"
fi

log "INFO: バックアップ処理が正常に完了しました"
