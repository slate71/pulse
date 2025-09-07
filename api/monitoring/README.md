# Pulse API Monitoring & Observability

This directory contains the comprehensive monitoring and observability stack for the Pulse AI Priority Engine API.

## Components

### 📊 Metrics (`metrics.py`)
- **Prometheus Integration**: Comprehensive metrics collection and exposure
- **Application Metrics**: Request counts, durations, error rates, business metrics
- **System Metrics**: Memory, CPU, database connection pool status
- **Custom Metrics**: Priority recommendations, feedback, event ingestion tracking

### 🔍 Distributed Tracing (`tracing.py`)
- **Request Correlation**: Unique trace IDs across request lifecycle
- **Span Management**: Hierarchical operation tracking with timing and metadata
- **Performance Analysis**: Detailed timing for debugging bottlenecks
- **Context Propagation**: Thread-safe context management for async operations

### ⚡ Performance Profiling (`profiling.py`)
- **cProfile Integration**: Deep function-level performance analysis
- **Request Profiling**: Automatic profiling of slow requests (>1s by default)
- **Memory Tracking**: Memory usage at different execution points
- **Selective Profiling**: Enable/disable profiling per request or globally

### 🛡️ Circuit Breakers (`circuit_breaker.py`)
- **Failure Protection**: Automatic failure detection and fast-fail behavior
- **Recovery Management**: Gradual recovery testing with half-open state
- **Service Resilience**: Protect against cascading failures from external services
- **Statistics Tracking**: Comprehensive failure/success rate monitoring

## Monitoring Endpoints

All monitoring endpoints are available under `/monitoring/` prefix:

### Metrics & Health
- `GET /monitoring/metrics` - Prometheus metrics (for Grafana/alerting)
- `GET /monitoring/health/detailed` - Comprehensive health with all dependencies
- `GET /monitoring/system/info` - System resource usage and process info

### Distributed Tracing
- `GET /monitoring/traces` - Active traces for debugging
- `GET /monitoring/traces?trace_id={id}` - Specific trace details
- `POST /monitoring/traces/cleanup` - Remove old traces

### Performance Profiling
- `GET /monitoring/profiling/stats` - Profiling statistics
- `GET /monitoring/profiling/profiles` - Recent performance profiles
- `POST /monitoring/profiling/enable` - Enable global profiling
- `POST /monitoring/profiling/disable` - Disable global profiling

### Circuit Breakers
- `GET /monitoring/circuit-breakers` - All circuit breaker states
- `POST /monitoring/circuit-breakers/{name}/reset` - Reset specific breaker
- `POST /monitoring/circuit-breakers/reset-all` - Reset all breakers

### Cache Management
- `GET /monitoring/cache/status` - Cache health and statistics
- `POST /monitoring/cache/redis/clear` - Clear Redis cache patterns
- `POST /monitoring/cache/memory/clear` - Clear in-memory cache

## Usage Examples

### Decorators for Automatic Monitoring

```python
from monitoring import trace_request, profile_operation
from monitoring.metrics import track_db_query, track_external_api
from monitoring.circuit_breaker import circuit_breaker

# Trace function execution
@trace_request("priority_generation")
async def generate_priority_recommendation(context):
    # Function automatically traced with timing and metadata
    pass

# Profile expensive operations
@profile_operation("database_analysis") 
async def analyze_large_dataset():
    # Function profiled when profiling is enabled
    pass

# Track database queries
@track_db_query("select", "events")
async def get_recent_events():
    # Query performance automatically tracked
    pass

# Protect external API calls
@circuit_breaker("github_api", failure_threshold=3, timeout=10.0)
async def fetch_github_data():
    # Automatic failure protection and fast-fail
    pass
```

### Manual Metrics Collection

```python
from monitoring.metrics import (
    REQUEST_COUNT, REQUEST_DURATION, PRIORITY_RECOMMENDATIONS_GENERATED
)

# Track custom business metrics
PRIORITY_RECOMMENDATIONS_GENERATED.labels(
    context_type="full_context",
    model_used="gpt-4"
).inc()

# Track request timing
with REQUEST_DURATION.labels(method="POST", endpoint="/priority/generate").time():
    # Code being timed
    pass
```

### Tracing with Custom Context

```python
from monitoring.tracing import get_tracer

tracer = get_tracer()
span = tracer.start_span("external_api_call")
span.add_tag("service", "github")
span.add_tag("endpoint", "/repos/user/repo/pulls")

try:
    result = await call_github_api()
    span.add_tag("result.count", len(result))
    span.finish("ok")
except Exception as e:
    span.add_tag("error.message", str(e))
    span.finish("error")
```

## Production Monitoring Setup

### 1. Prometheus Configuration

Add to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'pulse-api'
    static_configs:
      - targets: ['pulse-api:8000']
    metrics_path: '/monitoring/metrics'
    scrape_interval: 15s
```

### 2. Grafana Dashboards

Key metrics to monitor:
- `pulse_api_requests_total` - Request rates and error rates
- `pulse_api_request_duration_seconds` - Response time percentiles
- `pulse_api_db_query_duration_seconds` - Database performance
- `pulse_api_external_duration_seconds` - External API dependencies
- `pulse_api_memory_usage_bytes` - Memory consumption

### 3. Alerting Rules

Example Prometheus alerting rules:

```yaml
groups:
- name: pulse-api
  rules:
  - alert: HighErrorRate
    expr: rate(pulse_api_errors_total[5m]) > 0.1
    labels:
      severity: warning
    annotations:
      summary: High error rate detected
  
  - alert: CircuitBreakerOpen
    expr: pulse_api_circuit_breaker_state == 1
    labels:
      severity: critical
    annotations:
      summary: Circuit breaker is open
```

### 4. Log Aggregation

The monitoring system integrates with structured logging:

```json
{
  "timestamp": "2024-01-01T12:00:00Z",
  "level": "INFO",
  "request_id": "req_123456",
  "trace_id": "trace_789abc",
  "message": "Request completed",
  "duration_ms": 250,
  "status_code": 200
}
```

## Performance Considerations

- **Metrics Collection**: Minimal overhead (~0.1ms per request)
- **Tracing**: ~1-2ms overhead per request when enabled
- **Profiling**: Significant overhead, enable only for debugging
- **Circuit Breakers**: ~0.05ms overhead per protected operation

## Configuration

Environment variables for monitoring:

```bash
# Profiling
DEBUG=false                    # Enable profiling in debug mode

# Redis caching
REDIS_URL=redis://localhost:6379
REDIS_TIMEOUT=5

# Circuit breaker timeouts
GITHUB_TIMEOUT=30
LINEAR_TIMEOUT=30
OPENAI_TIMEOUT=60
```

## Troubleshooting

### High Memory Usage
1. Check `/monitoring/system/info` for process memory
2. Clear old traces: `POST /monitoring/traces/cleanup`
3. Clear old profiles: `POST /monitoring/profiling/cleanup`

### Performance Issues
1. Enable profiling: `POST /monitoring/profiling/enable`
2. Trigger slow operations
3. Check profiles: `GET /monitoring/profiling/profiles`
4. Analyze top functions and bottlenecks

### External Service Failures
1. Check circuit breaker status: `GET /monitoring/circuit-breakers`
2. Review failure patterns in metrics
3. Reset breakers after fixing: `POST /monitoring/circuit-breakers/reset-all`

This monitoring stack provides production-grade observability with minimal performance impact and comprehensive debugging capabilities.