"""
Monitoring and Health Check API Endpoints

This module provides comprehensive monitoring, health check, and system status
endpoints for the academic text annotation platform.
"""

import os
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..core.database import get_db
from ..utils.logger import get_logger
from ..utils.monitoring import (
    get_metrics_collector, get_alert_manager, export_metrics_to_file,
    AlertThreshold
)
from ..models.user import User


# Pydantic models for API responses
class SystemHealthResponse(BaseModel):
    """System health status response."""
    status: str
    timestamp: str
    version: str
    uptime_seconds: float
    components: Dict[str, Dict[str, Any]]


class MetricsSummaryResponse(BaseModel):
    """Metrics summary response."""
    period_hours: int
    system_metrics: Dict[str, Any]
    request_metrics: Dict[str, Any]
    database_metrics: Dict[str, Any]
    custom_metrics: Dict[str, Any]


class AlertResponse(BaseModel):
    """Alert information response."""
    id: str
    timestamp: str
    metric_name: str
    current_value: float
    threshold_value: float
    severity: str
    description: str
    status: str


class LogAnalysisResponse(BaseModel):
    """Log analysis response."""
    period_hours: int
    total_entries: int
    error_count: int
    warning_count: int
    top_endpoints: List[Dict[str, Any]]
    error_patterns: List[Dict[str, Any]]
    performance_issues: List[Dict[str, Any]]


# Router setup
router = APIRouter(prefix="/api/monitoring", tags=["Monitoring"])

# Application start time for uptime calculation
APP_START_TIME = datetime.now(timezone.utc)

logger = get_logger('main')


@router.get("/health", response_model=SystemHealthResponse)
async def comprehensive_health_check(db: Session = Depends(get_db)):
    """
    Comprehensive system health check endpoint.
    
    Checks database connectivity, system resources, monitoring components,
    and returns detailed health status for all system components.
    """
    start_time = datetime.now(timezone.utc)
    health_status = {
        "status": "healthy",
        "timestamp": start_time.isoformat(),
        "version": "1.0.0",
        "uptime_seconds": (start_time - APP_START_TIME).total_seconds(),
        "components": {}
    }
    
    # Database health check
    try:
        # Test basic connectivity
        db.execute("SELECT 1")
        
        # Check database version and stats
        version_result = db.execute("SELECT version()").fetchone()
        db_version = version_result[0] if version_result else "Unknown"
        
        # Check connection count (PostgreSQL specific)
        try:
            conn_result = db.execute(
                "SELECT count(*) FROM pg_stat_activity WHERE state = 'active'"
            ).fetchone()
            active_connections = conn_result[0] if conn_result else 0
        except Exception:
            active_connections = None
        
        health_status["components"]["database"] = {
            "status": "healthy",
            "version": db_version,
            "active_connections": active_connections,
            "response_time_ms": (datetime.now(timezone.utc) - start_time).total_seconds() * 1000,
            "message": "Database connection successful"
        }
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["components"]["database"] = {
            "status": "unhealthy",
            "error": str(e),
            "message": "Database connection failed"
        }
    
    # System resources check
    try:
        collector = get_metrics_collector()
        latest_metrics = collector.collect_system_metrics()
        
        if latest_metrics:
            # Determine resource status based on usage
            cpu_status = "healthy"
            if latest_metrics.cpu_percent > 90:
                cpu_status = "critical"
            elif latest_metrics.cpu_percent > 75:
                cpu_status = "warning"
            
            memory_status = "healthy"
            if latest_metrics.memory_percent > 95:
                memory_status = "critical"
            elif latest_metrics.memory_percent > 85:
                memory_status = "warning"
            
            disk_status = "healthy"
            if latest_metrics.disk_usage_percent > 95:
                disk_status = "critical"
            elif latest_metrics.disk_usage_percent > 85:
                disk_status = "warning"
            
            overall_resources_status = "healthy"
            if any(status == "critical" for status in [cpu_status, memory_status, disk_status]):
                overall_resources_status = "critical"
                health_status["status"] = "degraded"
            elif any(status == "warning" for status in [cpu_status, memory_status, disk_status]):
                overall_resources_status = "warning"
                if health_status["status"] == "healthy":
                    health_status["status"] = "degraded"
            
            health_status["components"]["system_resources"] = {
                "status": overall_resources_status,
                "cpu": {
                    "status": cpu_status,
                    "usage_percent": latest_metrics.cpu_percent
                },
                "memory": {
                    "status": memory_status,
                    "usage_percent": latest_metrics.memory_percent,
                    "used_mb": latest_metrics.memory_used_mb,
                    "available_mb": latest_metrics.memory_available_mb
                },
                "disk": {
                    "status": disk_status,
                    "usage_percent": latest_metrics.disk_usage_percent,
                    "free_gb": latest_metrics.disk_free_gb
                },
                "load_average": latest_metrics.load_average,
                "process_count": latest_metrics.process_count
            }
        else:
            health_status["components"]["system_resources"] = {
                "status": "unknown",
                "message": "Unable to collect system metrics"
            }
    except Exception as e:
        health_status["components"]["system_resources"] = {
            "status": "degraded",
            "error": str(e),
            "message": "System resource monitoring failed"
        }
    
    # Monitoring system health
    try:
        collector = get_metrics_collector()
        alert_manager = get_alert_manager()
        
        # Get recent metrics
        system_summary = collector.get_system_metrics_summary(hours=0.5)
        request_summary = collector.get_request_metrics_summary(hours=0.5)
        
        # Get active alerts
        active_alerts = alert_manager.get_active_alerts()
        
        monitoring_status = "healthy"
        if len(active_alerts) > 0:
            critical_alerts = [a for a in active_alerts if a['severity'] == 'critical']
            if critical_alerts:
                monitoring_status = "critical"
                if health_status["status"] != "unhealthy":
                    health_status["status"] = "degraded"
            else:
                monitoring_status = "warning"
        
        health_status["components"]["monitoring"] = {
            "status": monitoring_status,
            "metrics_collected": bool(system_summary and request_summary),
            "active_alerts": len(active_alerts),
            "critical_alerts": len([a for a in active_alerts if a['severity'] == 'critical']),
            "message": "Monitoring system operational"
        }
    except Exception as e:
        health_status["components"]["monitoring"] = {
            "status": "degraded",
            "error": str(e),
            "message": "Monitoring system check failed"
        }
    
    # Log files health check
    try:
        log_dir = Path("logs")
        if log_dir.exists():
            log_files = list(log_dir.glob("*.log"))
            total_log_size = sum(f.stat().st_size for f in log_files)
            
            # Check if logs are being written recently
            recent_logs = [
                f for f in log_files
                if (datetime.now() - datetime.fromtimestamp(f.stat().st_mtime)).seconds < 300
            ]
            
            logs_status = "healthy" if recent_logs else "warning"
            
            health_status["components"]["logging"] = {
                "status": logs_status,
                "log_files_count": len(log_files),
                "total_size_mb": round(total_log_size / 1024 / 1024, 2),
                "recent_activity": len(recent_logs) > 0,
                "message": "Logging system operational"
            }
        else:
            health_status["components"]["logging"] = {
                "status": "warning",
                "message": "Log directory not found"
            }
    except Exception as e:
        health_status["components"]["logging"] = {
            "status": "degraded",
            "error": str(e),
            "message": "Logging system check failed"
        }
    
    # Overall status check
    total_check_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
    health_status["health_check_duration_ms"] = total_check_time
    
    # Log health check
    logger.info(f"Health check completed: {health_status['status']} in {total_check_time:.2f}ms")
    
    return health_status


@router.get("/metrics/system", response_model=MetricsSummaryResponse)
async def get_system_metrics(
    hours: int = Query(1, description="Hours of metrics to retrieve", ge=1, le=72)
):
    """
    Get system performance metrics for the specified time period.
    
    Returns CPU, memory, disk usage, and network statistics.
    """
    try:
        collector = get_metrics_collector()
        
        system_metrics = collector.get_system_metrics_summary(hours)
        request_metrics = collector.get_request_metrics_summary(hours)
        database_metrics = collector.get_database_metrics_summary()
        
        # Get custom metrics
        custom_metrics = {}
        for metric_name, metrics_deque in collector.custom_metrics.items():
            if metrics_deque:
                cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
                recent_metrics = [
                    m for m in metrics_deque
                    if m['timestamp'] >= cutoff_time
                ]
                if recent_metrics:
                    values = [m['value'] for m in recent_metrics]
                    custom_metrics[metric_name] = {
                        'count': len(values),
                        'avg': sum(values) / len(values),
                        'max': max(values),
                        'min': min(values),
                        'latest': values[-1] if values else None
                    }
        
        return {
            "period_hours": hours,
            "system_metrics": system_metrics or {},
            "request_metrics": request_metrics or {},
            "database_metrics": database_metrics or {},
            "custom_metrics": custom_metrics
        }
        
    except Exception as e:
        logger.error(f"Failed to get system metrics: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve system metrics")


@router.get("/alerts/active")
async def get_active_alerts():
    """Get all currently active alerts."""
    try:
        alert_manager = get_alert_manager()
        active_alerts = alert_manager.get_active_alerts()
        
        # Convert to response format
        alerts_response = [
            AlertResponse(
                id=alert['id'],
                timestamp=alert['timestamp'].isoformat(),
                metric_name=alert['metric_name'],
                current_value=alert['current_value'],
                threshold_value=alert['threshold_value'],
                severity=alert['severity'],
                description=alert['description'],
                status=alert['status']
            )
            for alert in active_alerts
        ]
        
        return {
            "active_alerts_count": len(alerts_response),
            "alerts": alerts_response
        }
        
    except Exception as e:
        logger.error(f"Failed to get active alerts: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve active alerts")


@router.get("/alerts/history")
async def get_alert_history(
    hours: int = Query(24, description="Hours of alert history to retrieve", ge=1, le=168)
):
    """Get alert history for the specified time period."""
    try:
        alert_manager = get_alert_manager()
        alert_history = alert_manager.get_alert_history(hours)
        
        return {
            "period_hours": hours,
            "total_alerts": len(alert_history),
            "alerts": alert_history
        }
        
    except Exception as e:
        logger.error(f"Failed to get alert history: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve alert history")


@router.post("/alerts/threshold")
async def add_alert_threshold(threshold_data: dict):
    """Add a new alert threshold."""
    try:
        threshold = AlertThreshold(
            metric_name=threshold_data['metric_name'],
            threshold_value=float(threshold_data['threshold_value']),
            comparison=threshold_data['comparison'],
            severity=threshold_data['severity'],
            description=threshold_data.get('description', ''),
            enabled=threshold_data.get('enabled', True)
        )
        
        alert_manager = get_alert_manager()
        alert_manager.add_threshold(threshold)
        
        return {"message": "Alert threshold added successfully", "threshold": threshold_data}
        
    except Exception as e:
        logger.error(f"Failed to add alert threshold: {str(e)}")
        raise HTTPException(status_code=400, detail="Failed to add alert threshold")


@router.delete("/alerts/threshold/{metric_name}")
async def remove_alert_threshold(metric_name: str):
    """Remove an alert threshold."""
    try:
        alert_manager = get_alert_manager()
        alert_manager.remove_threshold(metric_name)
        
        return {"message": f"Alert threshold for {metric_name} removed successfully"}
        
    except Exception as e:
        logger.error(f"Failed to remove alert threshold: {str(e)}")
        raise HTTPException(status_code=400, detail="Failed to remove alert threshold")


@router.get("/logs/analysis")
async def analyze_logs(
    hours: int = Query(24, description="Hours of logs to analyze", ge=1, le=168),
    log_type: str = Query("all", description="Type of logs to analyze")
):
    """
    Analyze log files for errors, patterns, and performance issues.
    
    Returns summary statistics and identifies common issues.
    """
    try:
        log_dir = Path("logs")
        if not log_dir.exists():
            raise HTTPException(status_code=404, detail="Log directory not found")
        
        # Determine which log files to analyze
        log_files = []
        if log_type == "all":
            log_files = list(log_dir.glob("*.log"))
        else:
            log_files = list(log_dir.glob(f"{log_type}*.log"))
        
        if not log_files:
            return {
                "period_hours": hours,
                "total_entries": 0,
                "error_count": 0,
                "warning_count": 0,
                "top_endpoints": [],
                "error_patterns": [],
                "performance_issues": []
            }
        
        # Analyze logs
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        total_entries = 0
        error_count = 0
        warning_count = 0
        endpoint_counts = {}
        error_patterns = {}
        slow_requests = []
        
        for log_file in log_files:
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            log_entry = json.loads(line.strip())
                            entry_time_str = log_entry.get('timestamp')
                            if not entry_time_str:
                                continue
                            
                            # Parse timestamp
                            entry_time = datetime.fromisoformat(entry_time_str.replace('Z', '+00:00'))
                            if entry_time < cutoff_time:
                                continue
                            
                            total_entries += 1
                            
                            # Count log levels
                            if 'error' in log_entry.get('event', '').lower():
                                error_count += 1
                            elif 'warning' in log_entry.get('event', '').lower():
                                warning_count += 1
                            
                            # Track endpoints
                            endpoint = log_entry.get('endpoint') or log_entry.get('request', {}).get('endpoint')
                            if endpoint:
                                endpoint_counts[endpoint] = endpoint_counts.get(endpoint, 0) + 1
                            
                            # Track error patterns
                            if log_entry.get('exception_type'):
                                error_type = log_entry['exception_type']
                                error_patterns[error_type] = error_patterns.get(error_type, 0) + 1
                            
                            # Track slow requests
                            response_time = log_entry.get('response_time_ms')
                            if response_time and response_time > 5000:
                                slow_requests.append({
                                    'timestamp': entry_time_str,
                                    'endpoint': endpoint,
                                    'response_time_ms': response_time
                                })
                        
                        except (json.JSONDecodeError, ValueError, KeyError):
                            continue  # Skip malformed log entries
            
            except Exception as e:
                logger.warning(f"Failed to analyze log file {log_file}: {str(e)}")
                continue
        
        # Sort and limit results
        top_endpoints = sorted(endpoint_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        top_error_patterns = sorted(error_patterns.items(), key=lambda x: x[1], reverse=True)[:10]
        recent_slow_requests = sorted(slow_requests, key=lambda x: x['response_time_ms'], reverse=True)[:10]
        
        return LogAnalysisResponse(
            period_hours=hours,
            total_entries=total_entries,
            error_count=error_count,
            warning_count=warning_count,
            top_endpoints=[{"endpoint": ep, "count": count} for ep, count in top_endpoints],
            error_patterns=[{"error_type": err, "count": count} for err, count in top_error_patterns],
            performance_issues=recent_slow_requests
        )
        
    except Exception as e:
        logger.error(f"Failed to analyze logs: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to analyze logs")


@router.get("/export/metrics")
async def export_metrics(
    background_tasks: BackgroundTasks,
    hours: int = Query(24, description="Hours of metrics to export", ge=1, le=168),
    format: str = Query("json", description="Export format (json)")
):
    """
    Export system metrics to a file for external analysis.
    
    Returns a downloadable file with comprehensive metrics data.
    """
    try:
        if format.lower() != "json":
            raise HTTPException(status_code=400, detail="Only JSON format is currently supported")
        
        # Create export directory
        export_dir = Path("exports")
        export_dir.mkdir(exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"metrics_export_{timestamp}.json"
        filepath = export_dir / filename
        
        # Export metrics in background
        background_tasks.add_task(export_metrics_to_file, str(filepath), hours)
        
        return {
            "message": "Metrics export initiated",
            "filename": filename,
            "download_url": f"/api/monitoring/export/download/{filename}",
            "note": "Export will be available for download shortly"
        }
        
    except Exception as e:
        logger.error(f"Failed to initiate metrics export: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to initiate metrics export")


@router.get("/export/download/{filename}")
async def download_exported_metrics(filename: str):
    """Download exported metrics file."""
    try:
        export_dir = Path("exports")
        filepath = export_dir / filename
        
        if not filepath.exists():
            raise HTTPException(status_code=404, detail="Export file not found")
        
        return FileResponse(
            path=str(filepath),
            filename=filename,
            media_type="application/json"
        )
        
    except Exception as e:
        logger.error(f"Failed to download export file: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to download export file")


@router.get("/dashboard")
async def get_monitoring_dashboard():
    """
    Get comprehensive monitoring dashboard data.
    
    Returns all key metrics, alerts, and system status for a monitoring dashboard.
    """
    try:
        # Get current system status
        collector = get_metrics_collector()
        alert_manager = get_alert_manager()
        
        # Collect current metrics
        current_system = collector.collect_system_metrics()
        
        # Get summaries for different time periods
        last_hour = collector.get_system_metrics_summary(1)
        last_day = collector.get_system_metrics_summary(24)
        
        # Get request metrics
        request_metrics_hour = collector.get_request_metrics_summary(1)
        request_metrics_day = collector.get_request_metrics_summary(24)
        
        # Get database metrics
        db_metrics = collector.get_database_metrics_summary()
        
        # Get alerts
        active_alerts = alert_manager.get_active_alerts()
        recent_alerts = alert_manager.get_alert_history(24)
        
        # Calculate trends
        cpu_trend = "stable"
        memory_trend = "stable"
        if last_hour and last_day:
            cpu_change = last_hour.get('cpu', {}).get('avg', 0) - last_day.get('cpu', {}).get('avg', 0)
            memory_change = last_hour.get('memory', {}).get('avg', 0) - last_day.get('memory', {}).get('avg', 0)
            
            cpu_trend = "increasing" if cpu_change > 5 else "decreasing" if cpu_change < -5 else "stable"
            memory_trend = "increasing" if memory_change > 5 else "decreasing" if memory_change < -5 else "stable"
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "uptime_seconds": (datetime.now(timezone.utc) - APP_START_TIME).total_seconds(),
            "current_status": {
                "cpu_percent": current_system.cpu_percent if current_system else 0,
                "memory_percent": current_system.memory_percent if current_system else 0,
                "disk_percent": current_system.disk_usage_percent if current_system else 0,
                "cpu_trend": cpu_trend,
                "memory_trend": memory_trend
            },
            "metrics_summary": {
                "last_hour": last_hour or {},
                "last_day": last_day or {}
            },
            "request_metrics": {
                "last_hour": request_metrics_hour or {},
                "last_day": request_metrics_day or {}
            },
            "database_metrics": db_metrics or {},
            "alerts": {
                "active_count": len(active_alerts),
                "critical_count": len([a for a in active_alerts if a['severity'] == 'critical']),
                "active_alerts": active_alerts[:5],  # Limit to 5 most recent
                "recent_alerts_count": len(recent_alerts)
            },
            "system_health": "healthy" if not active_alerts else 
                           "critical" if any(a['severity'] == 'critical' for a in active_alerts) else "warning"
        }
        
    except Exception as e:
        logger.error(f"Failed to get dashboard data: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get dashboard data")