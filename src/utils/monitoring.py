"""
System Monitoring and Metrics Collection

This module provides comprehensive system monitoring including performance metrics,
resource usage tracking, database monitoring, and alerting capabilities.
"""

import os
import sys
import time
import psutil
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict
from threading import Lock
import json
import aiofiles
from pathlib import Path
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from .logger import get_logger, log_performance_metric, log_exception, log_security_event


@dataclass
class SystemMetrics:
    """System performance metrics."""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_available_mb: float
    disk_usage_percent: float
    disk_free_gb: float
    network_bytes_sent: int
    network_bytes_recv: int
    process_count: int
    load_average: Optional[float] = None


@dataclass
class RequestMetrics:
    """HTTP request metrics."""
    timestamp: datetime
    method: str
    endpoint: str
    status_code: int
    response_time_ms: float
    request_size_bytes: int
    response_size_bytes: int
    user_id: Optional[str] = None
    project_id: Optional[str] = None


@dataclass
class DatabaseMetrics:
    """Database performance metrics."""
    timestamp: datetime
    query_count: int
    slow_query_count: int
    avg_query_time_ms: float
    max_query_time_ms: float
    connection_count: int
    active_connections: int
    idle_connections: int
    failed_queries: int


@dataclass
class AlertThreshold:
    """Alert threshold configuration."""
    metric_name: str
    threshold_value: float
    comparison: str  # 'greater_than', 'less_than', 'equals'
    severity: str  # 'low', 'medium', 'high', 'critical'
    description: str
    enabled: bool = True


class MetricsCollector:
    """Collects and stores system metrics."""
    
    def __init__(self, retention_hours: int = 72):
        """Initialize metrics collector."""
        self.retention_hours = retention_hours
        self.system_metrics: deque = deque(maxlen=10000)
        self.request_metrics: deque = deque(maxlen=50000)
        self.database_metrics: deque = deque(maxlen=10000)
        self.custom_metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))
        
        self.lock = Lock()
        self.logger = get_logger('performance')
        
        # Request tracking
        self.active_requests = {}
        self.request_counters = defaultdict(int)
        
        # Database query tracking
        self.query_times = deque(maxlen=1000)
        self.slow_queries = deque(maxlen=100)
        
        # Process info cache
        self.process = psutil.Process()
        self._last_network_stats = None
    
    def collect_system_metrics(self) -> SystemMetrics:
        """Collect current system metrics."""
        try:
            # CPU and memory
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            
            # Disk usage for the application directory
            disk = psutil.disk_usage('/')
            
            # Network stats
            network = psutil.net_io_counters()
            
            # Load average (Unix-like systems only)
            load_avg = None
            if hasattr(os, 'getloadavg'):
                load_avg = os.getloadavg()[0]
            
            metrics = SystemMetrics(
                timestamp=datetime.now(timezone.utc),
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_used_mb=memory.used / 1024 / 1024,
                memory_available_mb=memory.available / 1024 / 1024,
                disk_usage_percent=disk.percent,
                disk_free_gb=disk.free / 1024 / 1024 / 1024,
                network_bytes_sent=network.bytes_sent,
                network_bytes_recv=network.bytes_recv,
                process_count=len(psutil.pids()),
                load_average=load_avg
            )
            
            with self.lock:
                self.system_metrics.append(metrics)
            
            # Log performance metrics
            log_performance_metric('cpu_usage', cpu_percent, 'percent')
            log_performance_metric('memory_usage', memory.percent, 'percent')
            log_performance_metric('disk_usage', disk.percent, 'percent')
            
            return metrics
            
        except Exception as e:
            log_exception(self.logger, e, {'context': 'system_metrics_collection'})
            return None
    
    def start_request_tracking(self, request_id: str, method: str, endpoint: str,
                              user_id: str = None, project_id: str = None) -> float:
        """Start tracking a request."""
        start_time = time.time()
        with self.lock:
            self.active_requests[request_id] = {
                'start_time': start_time,
                'method': method,
                'endpoint': endpoint,
                'user_id': user_id,
                'project_id': project_id
            }
            self.request_counters[f"{method}:{endpoint}"] += 1
        return start_time
    
    def end_request_tracking(self, request_id: str, status_code: int,
                           request_size: int = 0, response_size: int = 0):
        """End tracking a request and record metrics."""
        end_time = time.time()
        
        with self.lock:
            if request_id not in self.active_requests:
                return
            
            req_info = self.active_requests.pop(request_id)
            response_time_ms = (end_time - req_info['start_time']) * 1000
            
            metrics = RequestMetrics(
                timestamp=datetime.now(timezone.utc),
                method=req_info['method'],
                endpoint=req_info['endpoint'],
                status_code=status_code,
                response_time_ms=response_time_ms,
                request_size_bytes=request_size,
                response_size_bytes=response_size,
                user_id=req_info['user_id'],
                project_id=req_info['project_id']
            )
            
            self.request_metrics.append(metrics)
        
        # Log performance metrics
        log_performance_metric(
            'response_time',
            response_time_ms,
            'ms',
            {
                'endpoint': req_info['endpoint'],
                'method': req_info['method'],
                'status_code': status_code
            }
        )
        
        # Check for slow requests
        if response_time_ms > 5000:  # 5 seconds
            self.logger.warning(
                json.dumps({
                    'event': 'slow_request',
                    'endpoint': req_info['endpoint'],
                    'method': req_info['method'],
                    'response_time_ms': response_time_ms,
                    'user_id': req_info['user_id']
                })
            )
    
    def record_database_query(self, query_time_ms: float, query_sql: str = None,
                            failed: bool = False):
        """Record database query metrics."""
        with self.lock:
            self.query_times.append(query_time_ms)
            
            # Track slow queries
            if query_time_ms > 1000:  # 1 second
                slow_query_info = {
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'query_time_ms': query_time_ms,
                    'query_sql': query_sql[:500] if query_sql else None,  # Truncate long queries
                    'failed': failed
                }
                self.slow_queries.append(slow_query_info)
                
                # Log slow query
                self.logger.warning(
                    json.dumps({
                        'event': 'slow_query',
                        'query_time_ms': query_time_ms,
                        'query': query_sql[:200] if query_sql else None
                    })
                )
        
        # Log query performance
        log_performance_metric('query_time', query_time_ms, 'ms')
        
        if failed:
            log_performance_metric('failed_query', 1, 'count')
    
    def record_custom_metric(self, metric_name: str, value: float, 
                           tags: Dict[str, Any] = None):
        """Record a custom metric."""
        timestamp = datetime.now(timezone.utc)
        metric_data = {
            'timestamp': timestamp,
            'value': value,
            'tags': tags or {}
        }
        
        with self.lock:
            self.custom_metrics[metric_name].append(metric_data)
        
        log_performance_metric(metric_name, value, context=tags)
    
    def get_system_metrics_summary(self, hours: int = 1) -> Dict[str, Any]:
        """Get summary of system metrics for the last N hours."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        with self.lock:
            recent_metrics = [
                m for m in self.system_metrics
                if m.timestamp >= cutoff_time
            ]
        
        if not recent_metrics:
            return {}
        
        # Calculate statistics
        cpu_values = [m.cpu_percent for m in recent_metrics]
        memory_values = [m.memory_percent for m in recent_metrics]
        
        return {
            'period_hours': hours,
            'sample_count': len(recent_metrics),
            'cpu': {
                'avg': sum(cpu_values) / len(cpu_values),
                'max': max(cpu_values),
                'min': min(cpu_values)
            },
            'memory': {
                'avg': sum(memory_values) / len(memory_values),
                'max': max(memory_values),
                'min': min(memory_values)
            },
            'latest': recent_metrics[-1] if recent_metrics else None
        }
    
    def get_request_metrics_summary(self, hours: int = 1) -> Dict[str, Any]:
        """Get summary of request metrics for the last N hours."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        with self.lock:
            recent_requests = [
                r for r in self.request_metrics
                if r.timestamp >= cutoff_time
            ]
        
        if not recent_requests:
            return {}
        
        # Calculate statistics
        response_times = [r.response_time_ms for r in recent_requests]
        status_codes = defaultdict(int)
        endpoints = defaultdict(int)
        
        for req in recent_requests:
            status_codes[req.status_code] += 1
            endpoints[req.endpoint] += 1
        
        return {
            'period_hours': hours,
            'total_requests': len(recent_requests),
            'requests_per_minute': len(recent_requests) / (hours * 60),
            'response_time': {
                'avg': sum(response_times) / len(response_times),
                'max': max(response_times),
                'min': min(response_times),
                'p95': sorted(response_times)[int(len(response_times) * 0.95)] if response_times else 0
            },
            'status_codes': dict(status_codes),
            'top_endpoints': dict(sorted(endpoints.items(), key=lambda x: x[1], reverse=True)[:10])
        }
    
    def get_database_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of database metrics."""
        with self.lock:
            query_times_list = list(self.query_times)
            slow_queries_list = list(self.slow_queries)
        
        if not query_times_list:
            return {}
        
        return {
            'total_queries': len(query_times_list),
            'slow_queries': len(slow_queries_list),
            'avg_query_time_ms': sum(query_times_list) / len(query_times_list),
            'max_query_time_ms': max(query_times_list),
            'recent_slow_queries': slow_queries_list[-5:] if slow_queries_list else []
        }
    
    def cleanup_old_metrics(self, hours: int = None):
        """Clean up old metrics to free memory."""
        if hours is None:
            hours = self.retention_hours
        
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        with self.lock:
            # Clean up system metrics
            self.system_metrics = deque(
                [m for m in self.system_metrics if m.timestamp >= cutoff_time],
                maxlen=self.system_metrics.maxlen
            )
            
            # Clean up request metrics
            self.request_metrics = deque(
                [r for r in self.request_metrics if r.timestamp >= cutoff_time],
                maxlen=self.request_metrics.maxlen
            )
            
            # Clean up custom metrics
            for metric_name, metrics in self.custom_metrics.items():
                self.custom_metrics[metric_name] = deque(
                    [m for m in metrics if m['timestamp'] >= cutoff_time],
                    maxlen=metrics.maxlen
                )


class AlertManager:
    """Manages system alerts and notifications."""
    
    def __init__(self, metrics_collector: MetricsCollector):
        """Initialize alert manager."""
        self.metrics_collector = metrics_collector
        self.thresholds: List[AlertThreshold] = []
        self.active_alerts: Dict[str, Dict] = {}
        self.alert_history: deque = deque(maxlen=1000)
        self.lock = Lock()
        self.logger = get_logger('security')
        
        # Load default thresholds
        self._setup_default_thresholds()
    
    def _setup_default_thresholds(self):
        """Setup default alert thresholds."""
        default_thresholds = [
            AlertThreshold(
                'cpu_usage', 85.0, 'greater_than', 'high',
                'CPU usage is critically high'
            ),
            AlertThreshold(
                'memory_usage', 90.0, 'greater_than', 'critical',
                'Memory usage is critically high'
            ),
            AlertThreshold(
                'disk_usage', 95.0, 'greater_than', 'critical',
                'Disk usage is critically high'
            ),
            AlertThreshold(
                'response_time', 10000.0, 'greater_than', 'high',
                'Response time is too high'
            ),
            AlertThreshold(
                'error_rate', 5.0, 'greater_than', 'medium',
                'Error rate is above acceptable threshold'
            ),
            AlertThreshold(
                'slow_query_count', 10, 'greater_than', 'medium',
                'Too many slow database queries'
            )
        ]
        
        self.thresholds.extend(default_thresholds)
    
    def add_threshold(self, threshold: AlertThreshold):
        """Add a new alert threshold."""
        with self.lock:
            self.thresholds.append(threshold)
    
    def remove_threshold(self, metric_name: str):
        """Remove alert threshold for a metric."""
        with self.lock:
            self.thresholds = [
                t for t in self.thresholds
                if t.metric_name != metric_name
            ]
    
    def check_alerts(self):
        """Check all alert thresholds and trigger alerts if needed."""
        current_metrics = self.metrics_collector.get_system_metrics_summary(hours=0.1)
        request_metrics = self.metrics_collector.get_request_metrics_summary(hours=0.1)
        db_metrics = self.metrics_collector.get_database_metrics_summary()
        
        # Combine all metrics for checking
        all_metrics = {}
        
        if current_metrics and 'latest' in current_metrics and current_metrics['latest']:
            latest = current_metrics['latest']
            all_metrics.update({
                'cpu_usage': latest.cpu_percent,
                'memory_usage': latest.memory_percent,
                'disk_usage': latest.disk_usage_percent
            })
        
        if request_metrics:
            all_metrics.update({
                'response_time': request_metrics.get('response_time', {}).get('avg', 0),
                'error_rate': self._calculate_error_rate(request_metrics)
            })
        
        if db_metrics:
            all_metrics.update({
                'slow_query_count': db_metrics.get('slow_queries', 0)
            })
        
        # Check thresholds
        for threshold in self.thresholds:
            if not threshold.enabled:
                continue
            
            metric_value = all_metrics.get(threshold.metric_name)
            if metric_value is None:
                continue
            
            should_alert = self._should_trigger_alert(metric_value, threshold)
            
            if should_alert:
                self._trigger_alert(threshold, metric_value)
            else:
                self._resolve_alert(threshold.metric_name)
    
    def _should_trigger_alert(self, value: float, threshold: AlertThreshold) -> bool:
        """Check if a threshold should trigger an alert."""
        if threshold.comparison == 'greater_than':
            return value > threshold.threshold_value
        elif threshold.comparison == 'less_than':
            return value < threshold.threshold_value
        elif threshold.comparison == 'equals':
            return abs(value - threshold.threshold_value) < 0.001
        return False
    
    def _trigger_alert(self, threshold: AlertThreshold, current_value: float):
        """Trigger an alert."""
        alert_id = f"{threshold.metric_name}_{threshold.comparison}_{threshold.threshold_value}"
        
        with self.lock:
            # Don't spam the same alert
            if alert_id in self.active_alerts:
                return
            
            alert_data = {
                'id': alert_id,
                'timestamp': datetime.now(timezone.utc),
                'metric_name': threshold.metric_name,
                'current_value': current_value,
                'threshold_value': threshold.threshold_value,
                'severity': threshold.severity,
                'description': threshold.description,
                'status': 'active'
            }
            
            self.active_alerts[alert_id] = alert_data
            self.alert_history.append(alert_data.copy())
        
        # Log security event for alerts
        log_security_event(
            event_type='system_alert',
            severity=threshold.severity,
            details={
                'metric_name': threshold.metric_name,
                'current_value': current_value,
                'threshold_value': threshold.threshold_value,
                'description': threshold.description
            }
        )
        
        # Log the alert
        self.logger.error(
            json.dumps({
                'event': 'alert_triggered',
                'alert_id': alert_id,
                'metric_name': threshold.metric_name,
                'current_value': current_value,
                'threshold_value': threshold.threshold_value,
                'severity': threshold.severity,
                'description': threshold.description
            })
        )
    
    def _resolve_alert(self, metric_name: str):
        """Resolve an active alert."""
        with self.lock:
            resolved_alerts = []
            for alert_id, alert_data in list(self.active_alerts.items()):
                if alert_data['metric_name'] == metric_name:
                    alert_data['status'] = 'resolved'
                    alert_data['resolved_timestamp'] = datetime.now(timezone.utc)
                    resolved_alerts.append(alert_id)
            
            for alert_id in resolved_alerts:
                del self.active_alerts[alert_id]
                
                # Log resolution
                self.logger.info(
                    json.dumps({
                        'event': 'alert_resolved',
                        'alert_id': alert_id,
                        'metric_name': metric_name
                    })
                )
    
    def _calculate_error_rate(self, request_metrics: Dict) -> float:
        """Calculate error rate from request metrics."""
        if not request_metrics or 'status_codes' not in request_metrics:
            return 0.0
        
        total_requests = request_metrics['total_requests']
        if total_requests == 0:
            return 0.0
        
        error_codes = [code for code in request_metrics['status_codes'].keys() if code >= 400]
        error_count = sum(request_metrics['status_codes'][code] for code in error_codes)
        
        return (error_count / total_requests) * 100
    
    def get_active_alerts(self) -> List[Dict]:
        """Get list of active alerts."""
        with self.lock:
            return list(self.active_alerts.values())
    
    def get_alert_history(self, hours: int = 24) -> List[Dict]:
        """Get alert history for the last N hours."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        with self.lock:
            return [
                alert for alert in self.alert_history
                if alert['timestamp'] >= cutoff_time
            ]


# Global instances
_metrics_collector = None
_alert_manager = None


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def get_alert_manager() -> AlertManager:
    """Get the global alert manager instance."""
    global _alert_manager
    if _alert_manager is None:
        collector = get_metrics_collector()
        _alert_manager = AlertManager(collector)
    return _alert_manager


@asynccontextmanager
async def monitor_request(request_id: str, method: str, endpoint: str,
                         user_id: str = None, project_id: str = None):
    """Context manager for monitoring request performance."""
    collector = get_metrics_collector()
    start_time = collector.start_request_tracking(
        request_id, method, endpoint, user_id, project_id
    )
    
    try:
        yield start_time
    except Exception as e:
        # End tracking with error status
        collector.end_request_tracking(request_id, 500)
        raise
    else:
        # Will be ended by middleware with actual status code
        pass


async def start_background_monitoring():
    """Start background monitoring tasks."""
    collector = get_metrics_collector()
    alert_manager = get_alert_manager()
    
    async def collect_metrics_loop():
        """Background task to collect system metrics."""
        while True:
            try:
                collector.collect_system_metrics()
                await asyncio.sleep(30)  # Collect every 30 seconds
            except Exception as e:
                logger = get_logger('errors')
                log_exception(logger, e, {'context': 'background_metrics_collection'})
                await asyncio.sleep(60)  # Wait longer on error
    
    async def check_alerts_loop():
        """Background task to check alerts."""
        while True:
            try:
                alert_manager.check_alerts()
                await asyncio.sleep(60)  # Check every minute
            except Exception as e:
                logger = get_logger('errors')
                log_exception(logger, e, {'context': 'background_alert_checking'})
                await asyncio.sleep(120)  # Wait longer on error
    
    async def cleanup_loop():
        """Background task to clean up old metrics."""
        while True:
            try:
                collector.cleanup_old_metrics()
                await asyncio.sleep(3600)  # Cleanup every hour
            except Exception as e:
                logger = get_logger('errors')
                log_exception(logger, e, {'context': 'background_cleanup'})
                await asyncio.sleep(3600)
    
    # Start background tasks
    asyncio.create_task(collect_metrics_loop())
    asyncio.create_task(check_alerts_loop())
    asyncio.create_task(cleanup_loop())


def export_metrics_to_file(filepath: str, hours: int = 24):
    """Export metrics to JSON file for external analysis."""
    collector = get_metrics_collector()
    
    export_data = {
        'export_timestamp': datetime.now(timezone.utc).isoformat(),
        'period_hours': hours,
        'system_metrics': collector.get_system_metrics_summary(hours),
        'request_metrics': collector.get_request_metrics_summary(hours),
        'database_metrics': collector.get_database_metrics_summary(),
        'active_alerts': get_alert_manager().get_active_alerts(),
        'alert_history': get_alert_manager().get_alert_history(hours)
    }
    
    with open(filepath, 'w') as f:
        json.dump(export_data, f, indent=2, default=str)