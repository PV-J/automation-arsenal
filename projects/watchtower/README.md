## 2. WatchTower — `projects/watchtower/README.md`

```markdown
# WatchTower — Intelligent Website Health Monitor

**Problem:** Teams rely on basic uptime checks that miss slow degradation, SSL certificate expirations, and intermittent failures until users report them.

**Solution:** An async health monitor that checks multiple endpoints concurrently, tracks response time trends in SQLite, detects performance degradation before outages occur, and alerts via webhooks before your customers notice.

## What It Does

- Concurrent health checks across unlimited endpoints
- Response time trend analysis with moving averages
- SSL certificate expiry monitoring (alerts 30, 14, and 7 days before expiry)
- Degradation detection: alerts if response times drift 50% above baseline
- Circuit breaker pattern: suppresses alerts for flapping endpoints
- Slack/Discord webhook integration with customizable alert severity

## Architecture Decision: Why async instead of multithreading

Health checks are I/O-bound, not CPU-bound. asyncio with aiohttp handles thousands of concurrent checks in a single thread with near-zero overhead. Multithreading would add context-switching costs without benefit. When an endpoint times out, other checks continue unaffected.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run once with config file
python monitor.py --config config.yaml

# Run continuously (checks every 60 seconds)
python monitor.py --config config.yaml --daemon --interval 60

# Generate trend report for last 24 hours
python monitor.py --report --hours 24

Expected Output
✓ https://api.example.com/health     → 200 OK (142ms)
✓ https://dashboard.example.com      → 200 OK (389ms)
⚠ https://auth.example.com/token     → 200 OK (2450ms) — Above threshold
✗ https://legacy.example.com/api     → Timeout after 10s

SSL WARNING: dashboard.example.com — Certificate expires in 21 days
DEGRADATION ALERT: api.example.com — Response time increased 62% over baseline

Edge Cases Handled

    DNS failures: Graceful error with retry after TTL expires

    Self-signed certificates: Configurable to ignore or alert

    Rate limiting: Built-in cooldown prevents alert storms

    Empty responses: Treated as unhealthy with specific error message

Limits

    Does not perform JavaScript-rendered page checks (use Playwright for SPA monitoring)

    SQLite is sufficient for single-instance; use PostgreSQL for distributed monitoring

    Network-level monitoring (packet loss) requires additional tooling

Dependencies

See requirements.txt.

License

MIT