#!/bin/bash

# 依存関係の安全な更新スクリプト

set -e

BACKUP_DIR="/tmp/uv_backup_$(date +%Y%m%d_%H%M%S)"
LOG_FILE="/tmp/dependency_update.log"

# パッケージリスト定義
PACKAGES=("shared" "api" "crawler" "summarizer" "generator")

echo "依存関係更新を開始します..." | tee "$LOG_FILE"

# バックアップ作成
echo "現在のuv.lockファイルをバックアップ中..." | tee -a "$LOG_FILE"
mkdir -p "$BACKUP_DIR"
for package in "${PACKAGES[@]}"; do
    if [ -f "package/$package/uv.lock" ]; then
        cp "package/$package/uv.lock" "$BACKUP_DIR/${package}_uv.lock"
    fi
done

for package in "${PACKAGES[@]}"; do
    echo "パッケージ $package を更新中..." | tee -a "$LOG_FILE"

    cd "package/$package"

    # 現在のバージョン記録
    uv export --format=requirements-txt > "$BACKUP_DIR/${package}_before.txt"

    # 依存関係更新
    if uv sync --upgrade; then
        echo "✅ $package の依存関係更新完了" | tee -a "$LOG_FILE"

        # 更新後のバージョン記録
        uv export --format=requirements-txt > "$BACKUP_DIR/${package}_after.txt"
    else
        echo "❌ $package の依存関係更新失敗" | tee -a "$LOG_FILE"
        # 失敗時はロールバック
        if [ -f "$BACKUP_DIR/${package}_uv.lock" ]; then
            cp "$BACKUP_DIR/${package}_uv.lock" "uv.lock"
        fi
    fi

    cd ../..
done

# テスト実行
echo "更新後のテスト実行中..." | tee -a "$LOG_FILE"
if moon :check; then
    echo "✅ 全テストが成功しました" | tee -a "$LOG_FILE"

    # 脆弱性スキャン実行
    echo "脆弱性スキャン実行中..." | tee -a "$LOG_FILE"
    python scripts/generate_vulnerability_report.py

    echo "依存関係更新が完了しました。バックアップ: $BACKUP_DIR" | tee -a "$LOG_FILE"
else
    echo "❌ テストが失敗しました。ロールバックを実行します..." | tee -a "$LOG_FILE"

    # ロールバック
    for package in "${PACKAGES[@]}"; do
        if [ -f "$BACKUP_DIR/${package}_uv.lock" ]; then
            cp "$BACKUP_DIR/${package}_uv.lock" "package/$package/uv.lock"
        fi
    done

    echo "ロールバック完了。詳細は $LOG_FILE を確認してください。" | tee -a "$LOG_FILE"
    exit 1
fi
