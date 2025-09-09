"""
Comprehensive Logging System for Academic Text Annotation Platform

This module provides structured logging with JSON formatting, multiple log levels,
and specialized loggers for different components of the system.
"""

import os
import sys
import json
import logging
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union
from pathlib import Path
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
import structlog
from structlog import stdlib
from structlog.processors import JSONRenderer
import contextvars


class AcademicJSONRenderer:
    """Custom JSON renderer optimized for academic research environments."""
    
    def __call__(self, logger, method_name, event_dict):
        """Render log entry as JSON with academic-specific fields."""
        # Add common fields for academic tracking
        event_dict.update({
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'environment': os.getenv('ENVIRONMENT', 'development'),
            'service': 'text-annotation-system',
            'version': '1.0.0'
        })
        
        # Add request context if available
        request_context = get_request_context()
        if request_context:
            event_dict['request'] = request_context
            
        # Add user context if available
        user_context = get_user_context()
        if user_context:
            event_dict['user'] = user_context
            
        return json.dumps(event_dict, ensure_ascii=False, default=str)


class RequestContextFilter(logging.Filter):
    """Filter to add request context to log records."""
    
    def filter(self, record):
        """Add request context to log record."""
        context = get_request_context()
        if context:
            record.request_id = context.get('request_id')
            record.user_id = context.get('user_id')
            record.endpoint = context.get('endpoint')
            record.method = context.get('method')
        return True


class PerformanceFilter(logging.Filter):
    """Filter for performance-related logs."""
    
    def filter(self, record):
        """Only pass through performance-related log records."""
        performance_keywords = [
            'response_time', 'query_time', 'processing_time',
            'memory_usage', 'cpu_usage', 'slow_query'
        ]
        return any(keyword in record.getMessage().lower() for keyword in performance_keywords)


class SecurityFilter(logging.Filter):
    """Filter for security-related logs."""
    
    def filter(self, record):
        """Only pass through security-related log records."""
        security_keywords = [
            'authentication', 'authorization', 'login', 'logout',
            'access_denied', 'invalid_token', 'security_violation',
            'suspicious_activity', 'rate_limit', 'csrf'
        ]
        return any(keyword in record.getMessage().lower() for keyword in security_keywords)


class AuditFilter(logging.Filter):
    """Filter for audit trail logs."""
    
    def filter(self, record):
        """Only pass through audit-related log records."""
        audit_keywords = [
            'created', 'updated', 'deleted', 'modified',
            'annotation_added', 'annotation_removed', 'project_created',
            'user_action', 'data_change', 'permission_change'
        ]
        return any(keyword in record.getMessage().lower() for keyword in audit_keywords)


# Context variables for tracking request and user information
_request_context = contextvars.ContextVar('request_context', default=None)
_user_context = contextvars.ContextVar('user_context', default=None)


def set_request_context(request_id: str, endpoint: str, method: str, user_id: Optional[str] = None):
    """Set request context for logging."""
    context = {
        'request_id': request_id,
        'endpoint': endpoint,
        'method': method,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }
    if user_id:
        context['user_id'] = user_id
    _request_context.set(context)


def get_request_context() -> Optional[Dict[str, Any]]:
    """Get current request context."""
    return _request_context.get(None)


def set_user_context(user_id: str, username: str, role: str, project_id: Optional[str] = None):
    """Set user context for logging."""
    context = {
        'user_id': user_id,
        'username': username,
        'role': role,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }
    if project_id:
        context['project_id'] = project_id
    _user_context.set(context)


def get_user_context() -> Optional[Dict[str, Any]]:
    """Get current user context."""
    return _user_context.get(None)


def clear_context():
    """Clear all context variables."""
    _request_context.set(None)
    _user_context.set(None)


class LoggerSetup:
    """Centralized logger setup for the academic annotation system."""
    
    def __init__(self, log_level: str = "INFO", log_dir: str = "logs"):
        """Initialize logger setup."""
        self.log_level = getattr(logging, log_level.upper(), logging.INFO)
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # Configure structlog
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                AcademicJSONRenderer(),
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
    
    def setup_main_logger(self) -> logging.Logger:
        """Setup main application logger."""
        logger = logging.getLogger("academic_annotation")
        logger.setLevel(self.log_level)
        logger.handlers.clear()
        
        # Console handler with colored output for development
        if os.getenv('ENVIRONMENT', 'development') == 'development':
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(self.log_level)
            console_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)
        
        # Rotating file handler for all logs
        main_file_handler = RotatingFileHandler(
            filename=self.log_dir / "application.log",
            maxBytes=100 * 1024 * 1024,  # 100MB
            backupCount=10,
            encoding='utf-8'
        )
        main_file_handler.setLevel(self.log_level)
        main_file_handler.addFilter(RequestContextFilter())
        
        # JSON formatter for file logs
        json_formatter = logging.Formatter('%(message)s')
        main_file_handler.setFormatter(json_formatter)
        logger.addHandler(main_file_handler)
        
        return logger
    
    def setup_api_logger(self) -> logging.Logger:
        """Setup API request/response logger."""
        logger = logging.getLogger("api_requests")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        
        # Daily rotating file handler for API logs
        api_handler = TimedRotatingFileHandler(
            filename=self.log_dir / "api_requests.log",
            when='midnight',
            interval=1,
            backupCount=30,
            encoding='utf-8'
        )
        api_handler.setLevel(logging.INFO)
        api_handler.addFilter(RequestContextFilter())
        
        json_formatter = logging.Formatter('%(message)s')
        api_handler.setFormatter(json_formatter)
        logger.addHandler(api_handler)
        
        return logger
    
    def setup_performance_logger(self) -> logging.Logger:
        """Setup performance monitoring logger."""
        logger = logging.getLogger("performance")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        
        # Performance logs with daily rotation
        perf_handler = TimedRotatingFileHandler(
            filename=self.log_dir / "performance.log",
            when='midnight',
            interval=1,
            backupCount=30,
            encoding='utf-8'
        )
        perf_handler.setLevel(logging.INFO)
        perf_handler.addFilter(PerformanceFilter())
        perf_handler.addFilter(RequestContextFilter())
        
        json_formatter = logging.Formatter('%(message)s')
        perf_handler.setFormatter(json_formatter)
        logger.addHandler(perf_handler)
        
        return logger
    
    def setup_security_logger(self) -> logging.Logger:
        """Setup security event logger."""
        logger = logging.getLogger("security")
        logger.setLevel(logging.WARNING)
        logger.handlers.clear()
        
        # Security logs with immediate flush and longer retention
        security_handler = TimedRotatingFileHandler(
            filename=self.log_dir / "security.log",
            when='midnight',
            interval=1,
            backupCount=90,  # Keep security logs for 3 months
            encoding='utf-8'
        )
        security_handler.setLevel(logging.WARNING)
        security_handler.addFilter(SecurityFilter())
        security_handler.addFilter(RequestContextFilter())
        
        json_formatter = logging.Formatter('%(message)s')
        security_handler.setFormatter(json_formatter)
        logger.addHandler(security_handler)
        
        return logger
    
    def setup_audit_logger(self) -> logging.Logger:
        """Setup audit trail logger."""
        logger = logging.getLogger("audit_trail")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        
        # Audit logs with long retention for compliance
        audit_handler = TimedRotatingFileHandler(
            filename=self.log_dir / "audit_trail.log",
            when='midnight',
            interval=1,
            backupCount=365,  # Keep audit logs for 1 year
            encoding='utf-8'
        )
        audit_handler.setLevel(logging.INFO)
        audit_handler.addFilter(AuditFilter())
        audit_handler.addFilter(RequestContextFilter())
        
        json_formatter = logging.Formatter('%(message)s')
        audit_handler.setFormatter(json_formatter)
        logger.addHandler(audit_handler)
        
        return logger
    
    def setup_error_logger(self) -> logging.Logger:
        """Setup error and exception logger."""
        logger = logging.getLogger("errors")
        logger.setLevel(logging.ERROR)
        logger.handlers.clear()
        
        # Error logs with immediate writing and long retention
        error_handler = TimedRotatingFileHandler(
            filename=self.log_dir / "errors.log",
            when='midnight',
            interval=1,
            backupCount=90,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.addFilter(RequestContextFilter())
        
        json_formatter = logging.Formatter('%(message)s')
        error_handler.setFormatter(json_formatter)
        logger.addHandler(error_handler)
        
        return logger


# Global logger instances
_logger_setup = None
_loggers = {}


def setup_logging(log_level: str = None, log_dir: str = "logs") -> Dict[str, logging.Logger]:
    """Setup all loggers and return dictionary of configured loggers."""
    global _logger_setup, _loggers
    
    if not log_level:
        log_level = os.getenv('LOG_LEVEL', 'INFO')
    
    _logger_setup = LoggerSetup(log_level=log_level, log_dir=log_dir)
    
    _loggers = {
        'main': _logger_setup.setup_main_logger(),
        'api': _logger_setup.setup_api_logger(),
        'performance': _logger_setup.setup_performance_logger(),
        'security': _logger_setup.setup_security_logger(),
        'audit': _logger_setup.setup_audit_logger(),
        'errors': _logger_setup.setup_error_logger(),
    }
    
    return _loggers


def get_logger(name: str = 'main') -> logging.Logger:
    """Get a configured logger by name."""
    if not _loggers:
        setup_logging()
    
    return _loggers.get(name, _loggers['main'])


def log_exception(logger: logging.Logger, exception: Exception, context: Dict[str, Any] = None):
    """Log an exception with full context and stack trace."""
    error_data = {
        'event': 'exception_occurred',
        'exception_type': type(exception).__name__,
        'exception_message': str(exception),
        'stack_trace': traceback.format_exc(),
        'timestamp': datetime.now(timezone.utc).isoformat()
    }
    
    if context:
        error_data['context'] = context
    
    # Add request context if available
    request_context = get_request_context()
    if request_context:
        error_data['request'] = request_context
    
    # Add user context if available
    user_context = get_user_context()
    if user_context:
        error_data['user'] = user_context
    
    logger.error(json.dumps(error_data, default=str))


def log_user_action(user_id: str, action: str, resource_type: str, 
                   resource_id: str = None, details: Dict[str, Any] = None):
    """Log user action for audit trail."""
    audit_logger = get_logger('audit')
    
    audit_data = {
        'event': 'user_action',
        'user_id': user_id,
        'action': action,
        'resource_type': resource_type,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }
    
    if resource_id:
        audit_data['resource_id'] = resource_id
    
    if details:
        audit_data['details'] = details
    
    # Add request context if available
    request_context = get_request_context()
    if request_context:
        audit_data['request'] = request_context
    
    audit_logger.info(json.dumps(audit_data, default=str))


def log_performance_metric(metric_name: str, value: Union[int, float], 
                          unit: str = None, context: Dict[str, Any] = None):
    """Log performance metric."""
    perf_logger = get_logger('performance')
    
    metric_data = {
        'event': 'performance_metric',
        'metric_name': metric_name,
        'value': value,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }
    
    if unit:
        metric_data['unit'] = unit
    
    if context:
        metric_data['context'] = context
    
    # Add request context if available
    request_context = get_request_context()
    if request_context:
        metric_data['request'] = request_context
    
    perf_logger.info(json.dumps(metric_data, default=str))


def log_security_event(event_type: str, severity: str, details: Dict[str, Any] = None):
    """Log security event."""
    security_logger = get_logger('security')
    
    security_data = {
        'event': 'security_event',
        'event_type': event_type,
        'severity': severity,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }
    
    if details:
        security_data['details'] = details
    
    # Add request context if available
    request_context = get_request_context()
    if request_context:
        security_data['request'] = request_context
    
    # Add user context if available
    user_context = get_user_context()
    if user_context:
        security_data['user'] = user_context
    
    # Log at appropriate level based on severity
    if severity.lower() in ['critical', 'high']:
        security_logger.error(json.dumps(security_data, default=str))
    elif severity.lower() == 'medium':
        security_logger.warning(json.dumps(security_data, default=str))
    else:
        security_logger.info(json.dumps(security_data, default=str))


# Convenience functions for common logging patterns
def info(message: str, **kwargs):
    """Log info message with structured data."""
    logger = get_logger('main')
    data = {'event': 'info', 'message': message, **kwargs}
    logger.info(json.dumps(data, default=str))


def warning(message: str, **kwargs):
    """Log warning message with structured data."""
    logger = get_logger('main')
    data = {'event': 'warning', 'message': message, **kwargs}
    logger.warning(json.dumps(data, default=str))


def error(message: str, **kwargs):
    """Log error message with structured data."""
    logger = get_logger('errors')
    data = {'event': 'error', 'message': message, **kwargs}
    logger.error(json.dumps(data, default=str))


def debug(message: str, **kwargs):
    """Log debug message with structured data."""
    logger = get_logger('main')
    data = {'event': 'debug', 'message': message, **kwargs}
    logger.debug(json.dumps(data, default=str))