"""
Tests for WatchTower health monitor.
Run: pytest tests/ -v
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from monitor import EndpointConfig, HealthCheckResult, TrendAnalyzer
from datetime import datetime, timedelta


class TestEndpointConfig:
    """Test endpoint configuration defaults and validation."""

    def test_default_values(self):
        config = EndpointConfig(url="https://example.com")
        assert config.method == "GET"
        assert config.expected_status == 200
        assert config.timeout_seconds == 30
        assert config.check_ssl is True
        assert config.ssl_expiry_warning_days == 30
        assert config.response_time_threshold_ms == 2000

    def test_custom_timeout(self):
        config = EndpointConfig(url="https://example.com", timeout_seconds=5)
        assert config.timeout_seconds == 5

    def test_custom_headers(self):
        headers = {"Authorization": "Bearer token"}
        config = EndpointConfig(url="https://example.com", headers=headers)
        assert config.headers["Authorization"] == "Bearer token"


class TestHealthCheckResult:
    """Test health check result object."""

    def test_healthy_result(self):
        result = HealthCheckResult(
            url="https://example.com",
            timestamp=datetime.now(),
            status_code=200,
            response_time_ms=150,
            is_healthy=True,
            error_message=None
        )
        assert result.is_healthy is True
        assert result.status_code == 200

    def test_unhealthy_result_with_error(self):
        result = HealthCheckResult(
            url="https://example.com",
            timestamp=datetime.now(),
            status_code=None,
            response_time_ms=0,
            is_healthy=False,
            error_message="Connection refused"
        )
        assert result.is_healthy is False
        assert "Connection refused" in result.error_message

    def test_ssl_expiry_tracking(self):
        expiry = datetime.now() + timedelta(days=15)
        result = HealthCheckResult(
            url="https://example.com",
            timestamp=datetime.now(),
            status_code=200,
            response_time_ms=100,
            is_healthy=True,
            error_message=None,
            ssl_expiry_date=expiry,
            ssl_issuer="Test CA"
        )
        assert result.ssl_expiry_date == expiry
        assert result.ssl_issuer == "Test CA"


class TestTrendAnalyzer:
    """Test degradation detection logic."""

    def setup_method(self):
        self.analyzer = TrendAnalyzer(db_path=":memory:")

    def test_insufficient_data_returns_no_degradation(self):
        result = self.analyzer.detect_degradation(
            "https://example.com", window_hours=24
        )
        assert result["degradation_detected"] is False
        assert result["reason"] == "insufficient_data"


class TestEndpointConfigEdgeCases:
    """Test edge cases for endpoint configuration."""

    def test_very_short_timeout(self):
        config = EndpointConfig(url="https://example.com", timeout_seconds=1)
        assert config.timeout_seconds == 1

    def test_non_standard_status(self):
        config = EndpointConfig(
            url="https://example.com", expected_status=302
        )
        assert config.expected_status == 302

    def test_custom_method(self):
        config = EndpointConfig(url="https://example.com", method="POST")
        assert config.method == "POST"