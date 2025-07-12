"""セキュリティ監視スクリプトのテスト."""

import json
from unittest.mock import mock_open, patch

import pytest

from scripts.security_monitoring import SecurityMonitor


class TestSecurityMonitor:
    """SecurityMonitorクラスのテスト."""

    def test_init(self):
        """初期化テスト."""
        monitor = SecurityMonitor()
        assert monitor.thresholds["auth_failures_per_minute"] == 5
        assert monitor.thresholds["rate_limit_threshold"] == 10
        assert monitor.thresholds["response_time_threshold"] == 5.0
        assert monitor.thresholds["cpu_threshold"] == 70.0
        assert monitor.thresholds["memory_threshold"] == 80.0

    def test_check_authentication_failures(self):
        """認証失敗監視のテスト."""
        monitor = SecurityMonitor()
        result = monitor.check_authentication_failures()
        assert result["status"] == "ok"
        assert "failures" in result
        assert "threshold" in result
        assert "alert" in result
        assert result["threshold"] == 5

    def test_check_rate_limiting(self):
        """レート制限監視のテスト."""
        monitor = SecurityMonitor()
        result = monitor.check_rate_limiting()
        assert result["status"] == "ok"
        assert "rate_limit_events" in result
        assert "threshold" in result
        assert "alert" in result
        assert result["threshold"] == 10

    def test_check_ssl_certificates(self):
        """SSL証明書確認のテスト."""
        monitor = SecurityMonitor()
        result = monitor.check_ssl_certificates()
        assert result["status"] == "ok"
        assert "days_until_expiry" in result
        assert "certificate_path" in result
        assert "alert" in result

    def test_check_system_resources(self):
        """システムリソース確認のテスト."""
        monitor = SecurityMonitor()
        result = monitor.check_system_resources()
        assert result["status"] == "ok"
        assert "cpu_usage" in result
        assert "memory_usage" in result
        assert "alert" in result

    def test_daily_security_check(self):
        """日次セキュリティチェックのテスト."""
        monitor = SecurityMonitor()
        result = monitor.daily_security_check()
        assert "timestamp" in result
        assert result["check_type"] == "daily"
        assert "checks" in result
        assert "authentication" in result["checks"]
        assert "rate_limiting" in result["checks"]
        assert "ssl_certificates" in result["checks"]
        assert "system_resources" in result["checks"]
        assert "alerts_count" in result
        assert "status" in result

    def test_generate_report(self):
        """レポート生成のテスト."""
        monitor = SecurityMonitor()
        results = {
            "timestamp": "2024-01-01T10:00:00",
            "check_type": "daily",
            "status": "ok",
            "alerts_count": 0,
            "checks": {
                "authentication": {"status": "ok", "alert": False},
                "rate_limiting": {"status": "ok", "alert": False}
            }
        }
        report = monitor.generate_report(results)
        assert "セキュリティ監査レポート" in report
        assert "2024-01-01T10:00:00" in report
        assert "daily" in report
        assert "✅ authentication: ok" in report
        assert "✅ rate_limiting: ok" in report

    def test_generate_report_with_alerts(self):
        """アラート付きレポート生成のテスト."""
        monitor = SecurityMonitor()
        results = {
            "timestamp": "2024-01-01T10:00:00",
            "check_type": "daily",
            "status": "alert",
            "alerts_count": 1,
            "checks": {
                "authentication": {"status": "alert", "alert": True},
                "rate_limiting": {"status": "ok", "alert": False}
            }
        }
        report = monitor.generate_report(results)
        assert "🚨 authentication: alert" in report
        assert "✅ rate_limiting: ok" in report
