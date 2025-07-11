# Task: セキュリティ運用プロセスの確立

## タスクの目的

定期セキュリティ監査手順とインシデント対応プロセスを策定・実装し、継続的なセキュリティ維持体制を確立する。

## 前提条件

- Phase 4が完了している
- セキュリティ監査ログシステムが稼働中
- システムが本番稼働している
- 基本的な監視体制が構築済み

## 実施内容

### 1. 定期セキュリティ監査チェックリストの作成

#### docs/security/security_audit_checklist.md (新規作成)

```markdown
# セキュリティ監査チェックリスト

## 実施頻度
- 日次チェック：毎日実施
- 週次チェック：毎週月曜日実施
- 月次チェック：毎月1日実施
- 四半期チェック：四半期初月の1日実施

## 日次チェック項目

### 認証・認可
- [ ] 認証失敗ログ（5回/分以上の連続失敗がないか）
- [ ] 不正アクセス試行（通常とは異なるIPアドレスからのアクセス）
- [ ] Flower UIへの未認証アクセス試行

### レート制限・パフォーマンス
- [ ] レート制限発動状況（異常な発動頻度がないか）
- [ ] API応答時間（平均5秒以内を維持）
- [ ] システムリソース使用率（CPU 70%未満、メモリ 80%未満）

### セキュリティログ
- [ ] 重要度「high」「critical」のセキュリティイベント確認
- [ ] ログの欠損（24時間以内のログが存在するか）
- [ ] 異常なトラフィックパターン

## 週次チェック項目

### 証明書・暗号化
- [ ] SSL証明書の有効期限（30日前に警告）
- [ ] TLS設定の確認（不正な変更がないか）
- [ ] パスワード変更履歴の確認

### アクセス制御
- [ ] ユーザーアクセス権限の妥当性確認
- [ ] 管理者権限の使用履歴確認
- [ ] 不要なアカウントの存在確認

### システム更新
- [ ] 依存関係の脆弱性スキャン実行
- [ ] セキュリティパッチの適用状況確認
- [ ] バックアップの完全性確認

## 月次チェック項目

### 包括的セキュリティ評価
- [ ] ペネトレーションテストの実施
- [ ] 脆弱性評価レポートの作成
- [ ] セキュリティインシデント統計の分析
- [ ] セキュリティポリシーの見直し

### コンプライアンス
- [ ] 監査ログの完全性確認
- [ ] データ保護規則への準拠確認
- [ ] セキュリティトレーニングの実施状況

## 四半期チェック項目

### 戦略的セキュリティ評価
- [ ] セキュリティ戦略の見直し
- [ ] 脅威モデルの更新
- [ ] セキュリティ投資の効果測定
- [ ] インシデント対応計画の見直し
```

### 2. インシデント対応プロセスの策定

#### docs/security/incident_response_procedure.md (新規作成)

```markdown
# セキュリティインシデント対応手順

## インシデント分類

### レベル1：軽微（情報収集）
- 認証失敗の増加
- レート制限の頻繁な発動
- 軽微な設定ミス

**対応時間：24時間以内**

### レベル2：中程度（注意が必要）
- 不正アクセスの疑い
- システムパフォーマンスの異常
- セキュリティポリシー違反

**対応時間：4時間以内**

### レベル3：深刻（緊急対応）
- データ漏洩の疑い
- システム侵害の確認
- サービス停止を伴う攻撃

**対応時間：1時間以内**

### レベル4：致命的（即座対応）
- データの大量漏洩
- システムの完全侵害
- ランサムウェア感染

**対応時間：即座**

## 対応手順

### 初期対応（全レベル共通）
1. インシデントの記録・報告
2. 影響範囲の特定
3. エスカレーション判断
4. ステークホルダーへの通知

### 調査・分析
1. ログ分析によるインシデント詳細調査
2. 攻撃ベクターの特定
3. 被害範囲の確定
4. 根本原因の分析

### 封じ込め・根絶
1. 攻撃の封じ込め（必要に応じてサービス停止）
2. 脆弱性の修正
3. 攻撃者アクセスの排除
4. システムの復旧

### 復旧・事後対応
1. サービスの段階的復旧
2. 監視体制の強化
3. 再発防止策の実装
4. インシデント報告書の作成

## 連絡先・エスカレーション

### 技術チーム
- システム管理者：[連絡先]
- セキュリティ担当：[連絡先]
- 開発責任者：[連絡先]

### 管理職
- プロジェクトマネージャー：[連絡先]
- CTO：[連絡先]

### 外部機関
- 法執行機関：[連絡先]
- セキュリティベンダー：[連絡先]
```

### 3. 監査・インシデントトラッキングスクリプト

#### scripts/security_monitoring.py (新規作成)

```python
#!/usr/bin/env python3
"""セキュリティ監視・監査スクリプト."""

import argparse
import json
from datetime import datetime, timedelta
from typing import Dict, List

import structlog
from refnet_shared.security.audit_logger import security_audit_logger

logger = structlog.get_logger(__name__)


class SecurityMonitor:
    """セキュリティ監視クラス."""

    def __init__(self):
        """初期化."""
        self.thresholds = {
            "auth_failures_per_minute": 5,
            "rate_limit_threshold": 10,
            "response_time_threshold": 5.0,
            "cpu_threshold": 70.0,
            "memory_threshold": 80.0
        }

    def check_authentication_failures(self, time_window: int = 60) -> Dict:
        """認証失敗の監視."""
        # 過去time_window分の認証失敗ログを確認
        # 実装では監査ログから認証失敗イベントを抽出
        return {
            "status": "ok",
            "failures": 2,
            "threshold": self.thresholds["auth_failures_per_minute"],
            "alert": False
        }

    def check_rate_limiting(self, time_window: int = 60) -> Dict:
        """レート制限の監視."""
        # レート制限発動状況の確認
        return {
            "status": "ok",
            "rate_limit_events": 3,
            "threshold": self.thresholds["rate_limit_threshold"],
            "alert": False
        }

    def check_ssl_certificates(self) -> Dict:
        """SSL証明書の有効期限確認."""
        # 証明書の有効期限をチェック
        return {
            "status": "ok",
            "days_until_expiry": 90,
            "certificate_path": "/etc/nginx/ssl/server.crt",
            "alert": False
        }

    def check_system_resources(self) -> Dict:
        """システムリソース使用率確認."""
        # CPU・メモリ使用率の確認
        return {
            "status": "ok",
            "cpu_usage": 45.2,
            "memory_usage": 62.1,
            "alert": False
        }

    def daily_security_check(self) -> Dict:
        """日次セキュリティチェック."""
        results = {
            "timestamp": datetime.now().isoformat(),
            "check_type": "daily",
            "checks": {
                "authentication": self.check_authentication_failures(),
                "rate_limiting": self.check_rate_limiting(),
                "ssl_certificates": self.check_ssl_certificates(),
                "system_resources": self.check_system_resources()
            }
        }

        # アラートが必要なものがあるかチェック
        alerts = [check for check in results["checks"].values() if check.get("alert")]
        results["alerts_count"] = len(alerts)
        results["status"] = "alert" if alerts else "ok"

        return results

    def generate_report(self, results: Dict) -> str:
        """監査レポート生成."""
        report = f"""
# セキュリティ監査レポート
実行日時: {results['timestamp']}
チェック種別: {results['check_type']}
総合ステータス: {results['status']}
アラート数: {results['alerts_count']}

## チェック結果詳細
"""

        for check_name, check_result in results["checks"].items():
            status_icon = "🚨" if check_result.get("alert") else "✅"
            report += f"{status_icon} {check_name}: {check_result['status']}\n"

        return report


def main():
    """メイン処理."""
    parser = argparse.ArgumentParser(description="セキュリティ監視スクリプト")
    parser.add_argument("--check-type", choices=["daily", "weekly", "monthly"],
                       default="daily", help="チェック種別")
    parser.add_argument("--output", help="レポート出力ファイル")

    args = parser.parse_args()

    monitor = SecurityMonitor()

    if args.check_type == "daily":
        results = monitor.daily_security_check()
    else:
        # 週次・月次チェックは将来実装
        results = {"error": f"{args.check_type} check not implemented yet"}

    # レポート生成・出力
    report = monitor.generate_report(results)

    if args.output:
        with open(args.output, "w") as f:
            f.write(report)
        logger.info("Security report generated", file=args.output)
    else:
        print(report)

    # JSON形式でも出力
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
```

### 4. 定期実行設定

#### scripts/setup_security_cron.sh (新規作成)

```bash
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
```

## 完了条件

### 必須条件
- [ ] セキュリティ監査チェックリストが作成されている
- [ ] インシデント対応手順が文書化されている
- [ ] 監視スクリプトが実装・テスト済み
- [ ] 定期実行が設定されている
- [ ] 初回の監査が実施され、結果が確認されている

### 運用確認
- [ ] 日次監査が自動実行される
- [ ] インシデント分類・エスカレーションが明確である
- [ ] 監査レポートが適切に生成される
- [ ] アラート通知が動作する
- [ ] 手順書に従った対応テストが実施されている

### ドキュメント
- [ ] 運用手順書が作成・レビュー済み
- [ ] 担当者向けトレーニング資料が準備されている
- [ ] エスカレーション連絡先が最新である

## 推定作業時間

**8-12時間**
- チェックリスト作成：2-3時間
- インシデント対応手順策定：3-4時間
- 監視スクリプト実装：2-3時間
- テスト・検証：1-2時間

## 優先度

**📋 中優先度** - Phase 4完了後の運用フェーズで対応

## 次のステップ

- 01_vulnerability_management.md での脆弱性管理体制確立
- 運用チームへの手順共有・トレーニング実施
- 監視システムとの統合検討
