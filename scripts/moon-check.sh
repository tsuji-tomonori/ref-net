#!/bin/bash
set -e

echo "Running moon quality checks..."

# 依存関係のインストール
echo "Installing dependencies..."
moon run :install

# 全プロジェクトのチェック実行
echo "Running checks for all projects..."
moon check --all

# カバレッジレポートの統合
echo "Generating coverage report..."
moon run :coverage-report || echo "Coverage report skipped (not implemented yet)"

echo "All checks completed successfully!"
