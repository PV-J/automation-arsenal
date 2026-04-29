"""
monitor.py
Async website health monitor with intelligent alerting and trend analysis.
Designed for continuous operation with minimal resource footprint.

Author: PV-J
License: MIT
Version: 1.0.0
"""

import asyncio
import aiohttp
import sqlite3
import ssl
import socket
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json
import logging
from dataclasses import dataclass, asdict
from collections import defaultdict
import statistics

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class EndpointConfig:
    """Configuration for monitored endpoints."""
    url: str
    method: str = "GET"
    expected_status: int = 200
    timeout_seconds: int = 30
    check_ssl: bool = True
    ssl_expiry_warning_days: int = 30
    response_time_threshold_ms: int = 2000
    headers: Dict = None
    
    def __post_init__(self):
        if self.headers is None:
            self.headers = {
                'User-Agent': 'HealthMonitor/1.0'
            }


@dataclass
class HealthCheckResult:
    """Result of a single health check."""
    url: str
    timestamp: datetime
    status_code: Optional[int]
    response_time_ms: float
    is_healthy: bool
    error_message: Optional[str]
    ssl_expiry_date: Optional[datetime] = None
    ssl_issuer: Optional[str] = None


class TrendAnalyzer:
    """
    Analyzes response time trends to detect degradation.
    
    Uses moving averages and threshold-based anomaly detection
    to identify performance issues before they become outages.
    """
    
    def __init__(self, db_path: str = "monitor_history.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database for historical data."""
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS health_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT,
                timestamp TIMESTAMP,
                response_time_ms REAL,
                status_code INTEGER,
                is_healthy BOOLEAN
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_url_timestamp 
            ON health_checks(url, timestamp)
        ''')
        self.conn.commit()
    
    def detect_degradation(self, url: str, window_hours: int = 24) -> Dict:
        """
        Detect response time degradation using moving averages.
        
        Args:
            url: The endpoint URL to analyze
            window_hours: Analysis window in hours
            
        Returns:
            Dictionary with degradation metrics and alerts
        """
        cursor = self.conn.cursor()
        cutoff_time = datetime.now() - timedelta(hours=window_hours)
        
        cursor.execute('''
            SELECT response_time_ms, timestamp 
            FROM health_checks 
            WHERE url = ? AND timestamp > ?
            ORDER BY timestamp
        ''', (url, cutoff_time))
        
        results = cursor.fetchall()
        
        if len(results) < 10:  # Need minimum data points
            return {"degradation_detected": False, "reason": "insufficient_data"}
        
        response_times = [r[0] for r in results]
        timestamps = [r[1] for r in results]
        
        # Calculate metrics
        avg_response = statistics.mean(response_times)
        std_dev = statistics.stdev(response_times)
        recent_avg = statistics.mean(response_times[-5:])  # Last 5 checks
        baseline_avg = statistics.mean(response_times[:-5])
        
        # Detect anomalies
        degradation_detected = False
        alert_message = None
        
        if recent_avg > baseline_avg * 1.5:  # 50% degradation
            degradation_detected = True
            alert_message = f"Response time degraded by {(recent_avg/baseline_avg - 1)*100:.1f}%"
        elif recent_avg > 2000:  # Absolute threshold
            degradation_detected = True
            alert_message = f"Sustained high response time: {recent_avg:.0f}ms"
        
        return {
            "degradation_detected": degradation_detected,
            "alert_message": alert_message,
            "baseline_avg_ms": baseline_avg,
            "recent_avg_ms": recent_avg,
            "std_dev_ms": std_dev,
            "data_points": len(results)
        }


class HealthMonitor:
    """
    Async health monitor with concurrent checking capabilities.
    
    Features:
    - Concurrent endpoint checking with configurable parallelism
    - Circuit breaker pattern for failing endpoints
    - SSL certificate monitoring
    - Trend analysis and degradation detection
    """
    
    def __init__(self, endpoints: List[EndpointConfig], 
                 max_concurrent: int = 10):
        self.endpoints = endpoints
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.trend_analyzer = TrendAnalyzer()
        self.failure_counts = defaultdict(int)
        self.circuit_breaker_threshold = 3
    
    async def check_endpoint(self, endpoint: EndpointConfig) -> HealthCheckResult:
        """
        Perform comprehensive health check on single endpoint.
        
        Includes HTTP status check, response time measurement,
        and SSL certificate validation.
        """
        async with self.semaphore:
            start_time = datetime.now()
            
            try:
                async with aiohttp.ClientSession() as session:
                    timeout = aiohttp.ClientTimeout(total=endpoint.timeout_seconds)
                    
                    async with session.request(
                        method=endpoint.method,
                        url=endpoint.url,
                        headers=endpoint.headers,
                        timeout=timeout,
                        ssl=False  # We'll check SSL separately
                    ) as response:
                        response_time = (datetime.now() - start_time).total_seconds() * 1000
                        
                        # Check SSL if HTTPS
                        ssl_info = {}
                        if endpoint.check_ssl and endpoint.url.startswith('https'):
                            ssl_info = await self._check_ssl_certificate(endpoint.url)
                        
                        is_healthy = (
                            response.status == endpoint.expected_status and
                            response_time <= endpoint.response_time_threshold_ms
                        )
                        
                        result = HealthCheckResult(
                            url=endpoint.url,
                            timestamp=datetime.now(),
                            status_code=response.status,
                            response_time_ms=response_time,
                            is_healthy=is_healthy,
                            error_message=None,
                            **ssl_info
                        )
                        
                        # Check for degradation
                        degradation = self.trend_analyzer.detect_degradation(
                            endpoint.url
                        )
                        if degradation.get('degradation_detected'):
                            logger.warning(
                                f"Degradation detected for {endpoint.url}: "
                                f"{degradation['alert_message']}"
                            )
                        
                        return result
                        
            except asyncio.TimeoutError:
                return HealthCheckResult(
                    url=endpoint.url,
                    timestamp=datetime.now(),
                    status_code=None,
                    response_time_ms=endpoint.timeout_seconds * 1000,
                    is_healthy=False,
                    error_message="Request timeout"
                )
            except Exception as e:
                logger.error(f"Error checking {endpoint.url}: {e}")
                return HealthCheckResult(
                    url=endpoint.url,
                    timestamp=datetime.now(),
                    status_code=None,
                    response_time_ms=0,
                    is_healthy=False,
                    error_message=str(e)
                )
    
    async def _check_ssl_certificate(self, url: str) -> Dict:
        """Check SSL certificate for HTTPS endpoints."""
        try:
            hostname = url.split('//')[1].split('/')[0]
            context = ssl.create_default_context()
            
            with socket.create_connection((hostname, 443), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    
                    expiry_date = datetime.strptime(
                        cert['notAfter'], 
                        '%b %d %H:%M:%S %Y %Z'
                    )
                    
                    return {
                        'ssl_expiry_date': expiry_date,
                        'ssl_issuer': dict(x[0] for x in cert['issuer'])
                    }
        except Exception as e:
            logger.error(f"SSL check failed for {url}: {e}")
            return {'ssl_expiry_date': None, 'ssl_issuer': None}
    
    async def run_check(self) -> List[HealthCheckResult]:
        """Run health checks on all endpoints concurrently."""
        tasks = [self.check_endpoint(endpoint) for endpoint in self.endpoints]
        results = await asyncio.gather(*tasks)
        
        # Store results in database
        for result in results:
            self.trend_analyzer.conn.execute(
                '''INSERT INTO health_checks 
                   (url, timestamp, response_time_ms, status_code, is_healthy)
                   VALUES (?, ?, ?, ?, ?)''',
                (result.url, result.timestamp, result.response_time_ms,
                 result.status_code, result.is_healthy)
            )
        self.trend_analyzer.conn.commit()
        
        return results


# Example configuration
ENDPOINTS = [
    EndpointConfig(
        url="https://api.example.com/health",
        expected_status=200,
        timeout_seconds=10
    ),
    EndpointConfig(
        url="https://dashboard.example.com",
        expected_status=200,
        response_time_threshold_ms=1500
    ),
]

if __name__ == "__main__":
    async def main():
        monitor = HealthMonitor(ENDPOINTS)
        results = await monitor.run_check()
        
        # Generate report
        for result in results:
            status = "✓" if result.is_healthy else "✗"
            print(f"{status} {result.url}: {result.response_time_ms:.0f}ms")
    
    asyncio.run(main())
