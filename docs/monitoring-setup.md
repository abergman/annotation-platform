# Academic Annotation Platform - Monitoring & Alerting Setup

## Monitoring Architecture Overview

The Academic Annotation Platform requires comprehensive monitoring across multiple layers to ensure optimal performance, security, and user experience. The monitoring stack consists of application metrics, infrastructure monitoring, business intelligence, and real-time alerting.

### Monitoring Stack Components
- **Metrics Collection**: Prometheus + custom application metrics
- **Visualization**: Grafana dashboards
- **Log Aggregation**: ELK Stack (Elasticsearch, Logstash, Kibana)
- **APM**: Application Performance Monitoring
- **Alerting**: PagerDuty/Slack integration
- **Health Checks**: Multi-layer health monitoring

## Application-Level Monitoring

### FastAPI Backend Metrics

#### Core Application Metrics ✅
```python
# Current metrics implemented in src/main.py
- Request/Response times per endpoint
- Error rates (4xx/5xx) with categorization
- Active user sessions and authentication events  
- Database query performance and connection pool status
- Batch operation progress and completion rates
- File upload/processing success rates
- Cache hit/miss ratios and performance
```

#### Custom Business Metrics 📊
```python
# Annotation-specific metrics to implement
- Annotations created/updated/deleted per minute
- Concurrent annotation sessions per project
- Annotation conflict resolution rates
- User collaboration activity (simultaneous editors)
- Export format usage statistics
- Project activity levels and user engagement
```

#### Health Check Endpoints ✅
The application already implements comprehensive health checks:
```python
# /health endpoint returns
{
  "status": "healthy|degraded|unhealthy",
  "components": {
    "database": {"status": "healthy", "response_time": "5ms"},
    "cache": {"status": "healthy", "hit_ratio": "0.85"},
    "batch_processing": {"active_operations": 3},
    "websockets": {"active_connections": 45}
  }
}
```

### WebSocket Server Monitoring

#### Real-time Collaboration Metrics ✅
```javascript
// Current WebSocket metrics in websocket-server.js
- Active WebSocket connections by room
- Message throughput (messages/second)
- Connection establishment/termination rates
- Operational transform operations per second
- Conflict resolution events and success rates
- User presence tracking accuracy
- Message queue depth and processing latency
```

#### WebSocket Health Monitoring 📊
```javascript
// Additional metrics to implement
- Connection stability (reconnection rates)
- Message delivery success rates  
- Room scaling efficiency (users per room)
- Cursor tracking accuracy and latency
- Collaborative editing convergence time
```

### Database Performance Monitoring

#### PostgreSQL Metrics 📊
```sql
-- Key database metrics to monitor
- Connection pool utilization
- Query execution times by operation type
- Lock contention and deadlock events
- Index usage efficiency
- Table scan ratios
- Replication lag (if using streaming replication)
- Backup success rates and recovery time objectives
```

#### Database Health Checks ✅
```python
# Implemented in health check endpoint
- Connection validation
- Basic query execution test
- Transaction rollback capability
- Connection pool status
```

### Redis Cache Monitoring

#### Cache Performance Metrics 📊
```bash
# Redis metrics to track
redis_connected_clients
redis_blocked_clients  
redis_used_memory
redis_used_memory_peak
redis_keyspace_hits
redis_keyspace_misses
redis_expired_keys
redis_evicted_keys
redis_commands_processed_per_sec
```

## Infrastructure Monitoring

### Container & Host Metrics

#### Docker Container Monitoring 🐳
```yaml
# Key container metrics
- CPU usage per container (target: <70%)
- Memory usage per container (target: <80%)
- Network I/O per container
- Disk I/O and storage usage
- Container restart events
- Image vulnerability scan results
```

#### Host-Level Metrics 🖥️
```bash
# System metrics to monitor
- CPU utilization (user, system, iowait)
- Memory usage (available, cached, buffers)  
- Disk usage and I/O statistics
- Network interface statistics
- Load averages (1, 5, 15 minute)
- File descriptor usage
- Process counts and zombie processes
```

### Kubernetes Monitoring (if applicable)

#### Cluster Health Metrics ☸️
```yaml
# Kubernetes-specific metrics
- Pod restart rates
- Node resource availability
- Persistent volume usage
- Service mesh performance (if using Istio)
- Ingress controller performance
- Horizontal Pod Autoscaler effectiveness
```

## Prometheus Configuration

### Prometheus Setup 📊
```yaml
# prometheus.yml configuration
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "alert_rules.yml"

scrape_configs:
  - job_name: 'annotation-backend'
    static_configs:
      - targets: ['app:8000']
    metrics_path: '/api/monitoring/metrics'
    scrape_interval: 10s
    
  - job_name: 'websocket-server'
    static_configs:
      - targets: ['websocket:8001']
    metrics_path: '/metrics'
    scrape_interval: 10s
    
  - job_name: 'postgres-exporter'
    static_configs:
      - targets: ['postgres-exporter:9187']
      
  - job_name: 'redis-exporter'
    static_configs:
      - targets: ['redis-exporter:9121']
      
  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093
```

### Custom Application Metrics Export 📈
```python
# FastAPI metrics endpoint implementation
from prometheus_client import Counter, Histogram, Gauge, generate_latest

# Metrics to expose
annotation_operations = Counter(
    'annotation_operations_total',
    'Total annotation operations',
    ['operation_type', 'project_id']
)

request_duration = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint', 'status']
)

active_websocket_connections = Gauge(
    'websocket_connections_active',
    'Active WebSocket connections',
    ['room_type']
)
```

## Grafana Dashboard Configuration

### Application Performance Dashboard 📊

#### Panel 1: Request Overview
```json
{
  "title": "API Request Overview",
  "targets": [
    {
      "expr": "rate(http_requests_total[5m])",
      "legendFormat": "{{method}} {{endpoint}}"
    }
  ],
  "yAxis": {"unit": "reqps"}
}
```

#### Panel 2: Error Rates
```json
{
  "title": "Error Rates",
  "targets": [
    {
      "expr": "rate(http_requests_total{status=~\"4..|5..\"}[5m])",
      "legendFormat": "{{status}} errors"
    }
  ],
  "alert": {
    "conditions": [
      {"query": "A", "reducer": {"type": "avg"}, "threshold": 0.05}
    ]
  }
}
```

#### Panel 3: WebSocket Activity
```json
{
  "title": "Real-time Collaboration Activity",
  "targets": [
    {
      "expr": "websocket_connections_active",
      "legendFormat": "{{room_type}} connections"
    },
    {
      "expr": "rate(websocket_messages_total[1m])",
      "legendFormat": "Messages per second"
    }
  ]
}
```

### Infrastructure Dashboard 🖥️

#### System Resources Panel
```json
{
  "title": "System Resources",
  "panels": [
    {
      "title": "CPU Usage",
      "targets": [{"expr": "100 - (avg(rate(node_cpu_seconds_total{mode=\"idle\"}[5m])) * 100)"}]
    },
    {
      "title": "Memory Usage", 
      "targets": [{"expr": "(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100"}]
    },
    {
      "title": "Disk Usage",
      "targets": [{"expr": "100 - ((node_filesystem_avail_bytes / node_filesystem_size_bytes) * 100)"}]
    }
  ]
}
```

### Business Intelligence Dashboard 📈

#### User Activity Metrics
```json
{
  "title": "User Engagement",
  "panels": [
    {
      "title": "Active Users",
      "targets": [{"expr": "authenticated_users_active"}]
    },
    {
      "title": "Annotation Activity",
      "targets": [{"expr": "rate(annotation_operations_total[1h])"}]
    },
    {
      "title": "Project Usage",
      "targets": [{"expr": "active_projects_total"}]
    }
  ]
}
```

## Alerting Rules & Thresholds

### Critical Alerts 🚨

#### Application Health Alerts
```yaml
# alert_rules.yml
groups:
  - name: application_health
    rules:
      - alert: ApplicationDown
        expr: up{job=~"annotation-backend|websocket-server"} == 0
        for: 30s
        labels:
          severity: critical
        annotations:
          summary: "{{ $labels.instance }} is down"
          
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.1
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "High 5xx error rate: {{ $value }}"
          
      - alert: DatabaseConnectionFailure
        expr: postgres_up == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "PostgreSQL database is unreachable"
```

#### Performance Alerts ⚠️
```yaml
  - name: performance_alerts
    rules:
      - alert: HighResponseTime
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "95th percentile response time is {{ $value }}s"
          
      - alert: HighMemoryUsage
        expr: (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100 > 85
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage: {{ $value }}%"
          
      - alert: WebSocketConnectionDrop
        expr: rate(websocket_disconnections_total[5m]) > 0.5
        for: 3m  
        labels:
          severity: warning
        annotations:
          summary: "High WebSocket disconnection rate"
```

#### Business Logic Alerts 📊
```yaml
  - name: business_alerts
    rules:
      - alert: AnnotationConflictSpike
        expr: rate(annotation_conflicts_total[10m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High annotation conflict rate detected"
          
      - alert: BatchProcessingFailure
        expr: batch_operations_failed_total / batch_operations_total > 0.2
        for: 5m
        labels:
          severity: warning  
        annotations:
          summary: "High batch processing failure rate"
```

### Alert Routing & Escalation 📞

#### AlertManager Configuration
```yaml
# alertmanager.yml
global:
  smtp_smarthost: 'localhost:587'
  smtp_from: 'alerts@annotation-platform.com'

route:
  group_by: ['alertname']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 1h
  receiver: 'web.hook'
  routes:
    - match:
        severity: critical
      receiver: 'critical-alerts'
      group_wait: 0s
      repeat_interval: 5m
    - match:
        severity: warning
      receiver: 'warning-alerts'

receivers:
  - name: 'critical-alerts'
    slack_configs:
      - api_url: 'YOUR_SLACK_WEBHOOK'
        channel: '#critical-alerts'
        title: 'CRITICAL: {{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.summary }}{{ end }}'
    pagerduty_configs:
      - routing_key: 'YOUR_PAGERDUTY_KEY'
        
  - name: 'warning-alerts'
    slack_configs:
      - api_url: 'YOUR_SLACK_WEBHOOK'
        channel: '#warnings'
```

## Log Management & Analysis

### Centralized Logging Setup 📝

#### ELK Stack Configuration
```yaml
# docker-compose.yml additions for logging
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.10.0
    environment:
      - discovery.type=single-node
      - "ES_JAVA_OPTS=-Xms1g -Xmx1g"
    volumes:
      - elasticsearch_data:/usr/share/elasticsearch/data
      
  kibana:
    image: docker.elastic.co/kibana/kibana:8.10.0
    ports:
      - "5601:5601"
    depends_on:
      - elasticsearch
      
  logstash:
    image: docker.elastic.co/logstash/logstash:8.10.0
    volumes:
      - ./logstash/pipeline:/usr/share/logstash/pipeline
    depends_on:
      - elasticsearch
```

#### Application Log Configuration ✅
```python
# Current logging setup in src/utils/logger.py
- Structured logging with JSON format
- Multiple log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Request/response logging with correlation IDs
- Security event logging (auth failures, access attempts)
- Performance logging (slow queries, high memory usage)
```

### Log Analysis Queries 🔍

#### Common Log Analysis Patterns
```json
{
  "security_events": {
    "query": "level:ERROR AND (auth OR login OR permission)",
    "description": "Authentication and authorization failures"
  },
  "performance_issues": {
    "query": "response_time:>2000 OR level:WARNING",
    "description": "Slow responses and performance warnings"
  },
  "websocket_issues": {
    "query": "service:websocket-server AND (disconnect OR error)",
    "description": "WebSocket connection problems"
  }
}
```

## Backup & Recovery Monitoring

### Backup Monitoring 💾

#### Database Backup Verification
```bash
#!/bin/bash
# backup-monitor.sh
BACKUP_STATUS=$(pg_dump --version && echo "SUCCESS" || echo "FAILED")
BACKUP_SIZE=$(du -sh /backups/latest.sql | cut -f1)
BACKUP_AGE=$(find /backups -name "latest.sql" -mmin +1440 | wc -l)

# Send metrics to monitoring
curl -X POST http://prometheus-gateway:9091/metrics/job/backup-monitor \
     -d "backup_status{status=\"$BACKUP_STATUS\"} 1"
```

#### Recovery Testing Metrics
```yaml
# Monthly recovery test tracking
- Recovery Time Objective (RTO) achievement
- Recovery Point Objective (RPO) validation  
- Data integrity verification results
- Recovery procedure compliance scoring
```

## Monitoring Deployment Guide

### Quick Setup Commands 🚀

#### 1. Deploy Monitoring Stack
```bash
# Clone monitoring configuration
git clone https://github.com/your-org/annotation-monitoring.git monitoring/

# Deploy with Docker Compose
cd monitoring/
docker-compose up -d prometheus grafana alertmanager

# Verify deployment
curl http://localhost:9090/targets  # Prometheus targets
curl http://localhost:3000          # Grafana UI
```

#### 2. Configure Application Metrics
```bash
# Enable metrics endpoints in application
export ENABLE_METRICS=true
export METRICS_PORT=8080

# Restart application services
docker-compose restart app websocket
```

#### 3. Import Grafana Dashboards
```bash
# Import preconfigured dashboards
curl -X POST \
  http://admin:admin@localhost:3000/api/dashboards/db \
  -H 'Content-Type: application/json' \
  -d @grafana/dashboards/application-overview.json
```

### Monitoring Maintenance Schedule 🗓️

#### Daily Tasks
- [ ] Review critical alerts and resolution status
- [ ] Check dashboard for anomalies or performance degradation
- [ ] Verify backup completion and integrity
- [ ] Monitor resource utilization trends

#### Weekly Tasks  
- [ ] Analyze performance trends and capacity planning
- [ ] Review and tune alert thresholds based on false positives
- [ ] Test alert escalation procedures
- [ ] Update monitoring documentation

#### Monthly Tasks
- [ ] Conduct disaster recovery monitoring tests
- [ ] Review and optimize dashboard configurations
- [ ] Analyze business metrics and user behavior patterns
- [ ] Security monitoring review and threat assessment

#### Quarterly Tasks
- [ ] Full monitoring stack security review
- [ ] Performance benchmarking and capacity planning
- [ ] Monitoring tool updates and maintenance
- [ ] Training sessions for operations team

## Monitoring Team Responsibilities

### On-Call Rotation 📞
- **Primary On-Call**: Immediate response to critical alerts (< 15 minutes)
- **Secondary On-Call**: Escalation support and backup coverage  
- **Escalation Manager**: Complex incident coordination and management
- **Subject Matter Expert**: Deep technical expertise for complex issues

### Contact Information
- **Monitoring Team Lead**: monitoring-lead@organization.com
- **DevOps Engineer**: devops@organization.com  
- **Platform Architect**: architecture@organization.com
- **Security Operations**: security-ops@organization.com

---

This monitoring setup provides comprehensive observability across the entire Academic Annotation Platform stack, ensuring optimal performance, security, and user experience through proactive monitoring and alerting.