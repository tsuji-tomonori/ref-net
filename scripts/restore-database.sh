#!/bin/bash

# データベースリストアスクリプト
# 使用方法: ./restore-database.sh <backup_file> [--force]

set -e

# 引数チェック
if [ $# -eq 0 ]; then
    echo "使用方法: $0 <backup_file> [--force]"
    echo "例: $0 /var/backups/refnet/refnet_20231201_120000.sql.gz"
    echo "例: $0 /var/backups/refnet/refnet_20231201_120000.sql.gz --force"
    exit 1
fi

# 設定
BACKUP_FILE="$1"
FORCE_MODE="$2"
LOG_FILE="/var/log/refnet-restore.log"

# ログ出力関数
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# エラーハンドリング
trap 'log "ERROR: リストアが失敗しました"; exit 1' ERR

log "INFO: データベースリストアを開始します"
log "INFO: バックアップファイル: $BACKUP_FILE"

# 1. バックアップファイルの存在確認
if [ ! -f "$BACKUP_FILE" ]; then
    log "ERROR: バックアップファイルが見つかりません: $BACKUP_FILE"
    exit 1
fi

# 2. バックアップファイルの整合性確認
log "INFO: バックアップファイルの整合性を確認します"
if [[ "$BACKUP_FILE" == *.gz ]]; then
    if ! zcat "$BACKUP_FILE" | head -1 | grep -q "PostgreSQL database dump"; then
        log "ERROR: バックアップファイルの整合性確認に失敗しました"
        exit 1
    fi
else
    if ! head -1 "$BACKUP_FILE" | grep -q "PostgreSQL database dump"; then
        log "ERROR: バックアップファイルの整合性確認に失敗しました"
        exit 1
    fi
fi

# 3. 現在のデータベース状態確認
log "INFO: 現在のデータベース状態を確認します"
if docker-compose exec postgres pg_isready -U refnet >/dev/null 2>&1; then
    CURRENT_TABLES=$(docker-compose exec postgres psql -U refnet -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" | xargs)
    CURRENT_PAPERS=$(docker-compose exec postgres psql -U refnet -t -c "SELECT COUNT(*) FROM papers;" 2>/dev/null | xargs || echo "0")
    log "INFO: 現在のテーブル数: $CURRENT_TABLES"
    log "INFO: 現在の論文数: $CURRENT_PAPERS"
else
    log "ERROR: PostgreSQLに接続できません"
    exit 1
fi

# 4. 強制モードでない場合の確認
if [ "$FORCE_MODE" != "--force" ]; then
    echo "警告: この操作により現在のデータベースの内容が上書きされます"
    echo "現在のテーブル数: $CURRENT_TABLES"
    echo "現在の論文数: $CURRENT_PAPERS"
    echo "続行しますか？ (y/N): "
    read -r confirmation
    if [ "$confirmation" != "y" ] && [ "$confirmation" != "Y" ]; then
        log "INFO: ユーザーによりリストアがキャンセルされました"
        exit 0
    fi
fi

# 5. 依存サービスの停止
log "INFO: 依存サービスを停止します"
services_to_stop=("api" "crawler" "summarizer" "generator" "celery-beat")
for service in "${services_to_stop[@]}"; do
    if docker-compose ps -q "$service" >/dev/null 2>&1; then
        docker-compose stop "$service"
        log "INFO: $service を停止しました"
    fi
done

# 6. 現在のデータベースのバックアップ（安全のため）
log "INFO: 現在のデータベースをバックアップします"
CURRENT_BACKUP_FILE="/tmp/current_backup_$(date +%Y%m%d_%H%M%S).sql"
docker-compose exec postgres pg_dump -U refnet refnet > "$CURRENT_BACKUP_FILE"
log "INFO: 現在のデータベースを一時バックアップしました: $CURRENT_BACKUP_FILE"

# 7. データベースの初期化
log "INFO: データベースを初期化します"
docker-compose exec postgres psql -U refnet -c "DROP SCHEMA public CASCADE;" 2>/dev/null || true
docker-compose exec postgres psql -U refnet -c "CREATE SCHEMA public;"
docker-compose exec postgres psql -U refnet -c "GRANT ALL ON SCHEMA public TO refnet;"
docker-compose exec postgres psql -U refnet -c "GRANT ALL ON SCHEMA public TO public;"

# 8. バックアップからの復元
log "INFO: バックアップからデータベースを復元します"
if [[ "$BACKUP_FILE" == *.gz ]]; then
    zcat "$BACKUP_FILE" | docker-compose exec -T postgres psql -U refnet -d refnet
else
    docker-compose exec -T postgres psql -U refnet -d refnet < "$BACKUP_FILE"
fi

# 9. 復元後の確認
log "INFO: 復元後の状態を確認します"
RESTORED_TABLES=$(docker-compose exec postgres psql -U refnet -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" | xargs)
RESTORED_PAPERS=$(docker-compose exec postgres psql -U refnet -t -c "SELECT COUNT(*) FROM papers;" 2>/dev/null | xargs || echo "0")
log "INFO: 復元後のテーブル数: $RESTORED_TABLES"
log "INFO: 復元後の論文数: $RESTORED_PAPERS"

# 10. データベース統計の更新
log "INFO: データベース統計を更新します"
docker-compose exec postgres psql -U refnet -c "ANALYZE;"

# 11. 依存サービスの再開
log "INFO: 依存サービスを再開します"
for service in "${services_to_stop[@]}"; do
    docker-compose start "$service"
    log "INFO: $service を再開しました"
done

# 12. サービスの起動確認
log "INFO: サービスの起動を確認します"
sleep 30
for service in "${services_to_stop[@]}"; do
    if docker-compose ps "$service" | grep -q "Up"; then
        log "INFO: $service は正常に起動しています"
    else
        log "WARNING: $service の起動に問題があります"
    fi
done

# 13. API機能確認
log "INFO: API機能確認"
sleep 10
if curl -s -f http://localhost/health >/dev/null 2>&1; then
    log "INFO: API機能は正常です"
else
    log "WARNING: API機能の確認に失敗しました"
fi

# 14. 一時バックアップファイルの削除
log "INFO: 一時バックアップファイルを削除します"
rm -f "$CURRENT_BACKUP_FILE"

# 15. 結果の記録
log "INFO: データベースリストアが完了しました"
log "INFO: 使用したバックアップファイル: $BACKUP_FILE"
log "INFO: 復元されたテーブル数: $RESTORED_TABLES"
log "INFO: 復元された論文数: $RESTORED_PAPERS"

# 16. システム通知（オプション）
if command -v notify-send >/dev/null 2>&1; then
    notify-send "RefNet Restore" "データベースリストアが完了しました (テーブル: $RESTORED_TABLES, 論文: $RESTORED_PAPERS)"
fi

log "INFO: リストア処理が正常に完了しました"

# 17. 重要な注意事項
log "IMPORTANT: リストア後は以下を確認してください:"
log "IMPORTANT: 1. データの整合性"
log "IMPORTANT: 2. 外部API接続"
log "IMPORTANT: 3. Celeryタスクの動作"
log "IMPORTANT: 4. 監視システムの状態"
