#!/bin/bash

# セキュリティ監視の定期実行設定

SCRIPT_DIR="/app/scripts"
LOG_DIR="/app/logs/security"
REPORT_DIR="/app/reports/security"

# ディレクトリ作成
mkdir -p "$LOG_DIR"
mkdir -p "$REPORT_DIR"

# crontab設定
cat << EOF > /tmp/security_cron
# セキュリティ監視の定期実行
# 日次チェック（毎日9:00）
0 9 * * * cd /app && python scripts/security_monitoring.py --check-type daily --output "$REPORT_DIR/daily_$(date +\%Y\%m\%d).txt" >> "$LOG_DIR/security_monitoring.log" 2>&1

# 週次チェック（毎週月曜日10:00）
0 10 * * 1 cd /app && python scripts/security_monitoring.py --check-type weekly --output "$REPORT_DIR/weekly_$(date +\%Y\%m\%d).txt" >> "$LOG_DIR/security_monitoring.log" 2>&1

# 月次チェック（毎月1日11:00）
0 11 1 * * cd /app && python scripts/security_monitoring.py --check-type monthly --output "$REPORT_DIR/monthly_$(date +\%Y\%m\%d).txt" >> "$LOG_DIR/security_monitoring.log" 2>&1
EOF

# crontab登録
crontab /tmp/security_cron
rm /tmp/security_cron

echo "セキュリティ監視の定期実行が設定されました。"
echo "ログディレクトリ: $LOG_DIR"
echo "レポートディレクトリ: $REPORT_DIR"
