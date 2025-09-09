"""
Logging Middleware for FastAPI

This middleware provides comprehensive request/response logging, performance monitoring,
and security event logging for all API endpoints.
"""

import time
import uuid
import json
import asyncio
from typing import Callable, Dict, Any, Optional
from datetime import datetime, timezone

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ..utils.logger import (
    get_logger, set_request_context, set_user_context, clear_context,
    log_performance_metric, log_security_event, log_user_action, log_exception
)
from ..utils.monitoring import get_metrics_collector, monitor_request


class LoggingMiddleware(BaseHTTPMiddleware):
    """Comprehensive logging middleware for API requests and responses."""
    
    def __init__(self, app: ASGIApp, config: Dict[str, Any] = None):
        """Initialize logging middleware."""
        super().__init__(app)
        self.config = config or {}
        
        # Logger instances
        self.api_logger = get_logger('api')
        self.performance_logger = get_logger('performance')
        self.security_logger = get_logger('security')
        self.error_logger = get_logger('errors')
        
        # Metrics collector
        self.metrics_collector = get_metrics_collector()
        
        # Configuration
        self.log_request_body = self.config.get('log_request_body', True)
        self.log_response_body = self.config.get('log_response_body', False)
        self.max_body_size = self.config.get('max_body_size', 10000)  # 10KB
        self.exclude_paths = set(self.config.get('exclude_paths', []))
        self.sensitive_headers = set(self.config.get('sensitive_headers', [
            'authorization', 'cookie', 'x-api-key', 'x-auth-token'
        ]))
        
        # Performance thresholds
        self.slow_request_threshold = self.config.get('slow_request_threshold', 5000)  # 5 seconds
        self.very_slow_threshold = self.config.get('very_slow_threshold', 10000)  # 10 seconds
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and response with comprehensive logging."""
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        
        # Skip excluded paths
        if request.url.path in self.exclude_paths:
            return await call_next(request)
        
        # Record start time
        start_time = time.time()
        
        # Extract basic request info
        method = request.method
        endpoint = request.url.path
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get('user-agent', 'Unknown')
        
        # Extract user information if available
        user_id = self._extract_user_id(request)
        project_id = self._extract_project_id(request)
        
        # Set logging context
        set_request_context(request_id, endpoint, method, user_id)
        if user_id:
            # Try to get more user info from request
            username = self._extract_username(request)
            role = self._extract_user_role(request)
            set_user_context(user_id, username or f"user_{user_id}", role or "unknown", project_id)
        
        # Start metrics tracking
        async with monitor_request(request_id, method, endpoint, user_id, project_id):
            # Read request body if configured
            request_body = None
            request_size = 0
            if self.log_request_body and method in ['POST', 'PUT', 'PATCH']:
                try:
                    body_bytes = await request.body()
                    request_size = len(body_bytes)
                    
                    if request_size <= self.max_body_size:
                        # Try to decode as JSON, fallback to string
                        try:
                            request_body = json.loads(body_bytes.decode('utf-8'))
                            # Remove sensitive fields
                            request_body = self._sanitize_data(request_body)
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            request_body = f"<binary_data_size_{request_size}>"
                    else:
                        request_body = f"<large_request_body_size_{request_size}>"
                        
                except Exception as e:
                    request_body = f"<error_reading_body: {str(e)}>"
            
            # Log incoming request
            request_log_data = {
                'event': 'request_started',
                'request_id': request_id,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'method': method,
                'endpoint': endpoint,
                'full_url': str(request.url),
                'client_ip': client_ip,
                'user_agent': user_agent,
                'user_id': user_id,
                'project_id': project_id,
                'headers': self._sanitize_headers(dict(request.headers)),
                'query_params': dict(request.query_params),
                'request_size_bytes': request_size
            }
            
            if request_body is not None:
                request_log_data['request_body'] = request_body
            
            self.api_logger.info(json.dumps(request_log_data, default=str))
            
            # Security logging for authentication attempts
            if endpoint.startswith('/api/auth/'):
                log_security_event(
                    event_type='authentication_attempt',
                    severity='low',
                    details={
                        'endpoint': endpoint,
                        'client_ip': client_ip,
                        'user_agent': user_agent
                    }
                )
            
            # Process request
            response = None
            response_body = None
            exception_info = None
            
            try:
                response = await call_next(request)
                
                # Read response body if configured and status indicates error
                if (self.log_response_body or response.status_code >= 400) and hasattr(response, 'body'):
                    try:
                        # For StreamingResponse, we can't easily read the body
                        if hasattr(response, 'body_iterator'):
                            response_body = "<streaming_response>"
                        else:
                            body_bytes = getattr(response, 'body', b'')
                            if len(body_bytes) <= self.max_body_size:
                                try:
                                    response_body = json.loads(body_bytes.decode('utf-8'))
                                except (json.JSONDecodeError, UnicodeDecodeError):
                                    response_body = body_bytes.decode('utf-8', errors='ignore')[:1000]
                            else:
                                response_body = f"<large_response_body_size_{len(body_bytes)}>"
                    except Exception as e:
                        response_body = f"<error_reading_response: {str(e)}>"
                
            except Exception as e:
                # Log exception details
                exception_info = {
                    'exception_type': type(e).__name__,
                    'exception_message': str(e),
                    'exception_details': str(e)
                }
                
                log_exception(self.error_logger, e, {
                    'request_id': request_id,
                    'endpoint': endpoint,
                    'method': method,
                    'user_id': user_id
                })
                
                # Create error response
                response = JSONResponse(
                    status_code=500,
                    content={
                        'error': 'Internal server error',
                        'request_id': request_id,
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    }
                )
            
            # Calculate timing
            end_time = time.time()
            response_time_ms = (end_time - start_time) * 1000
            response_size = 0
            
            if response and hasattr(response, 'body'):
                body_bytes = getattr(response, 'body', b'')
                response_size = len(body_bytes)
            
            # End metrics tracking
            self.metrics_collector.end_request_tracking(
                request_id, 
                response.status_code if response else 500,
                request_size,
                response_size
            )
            
            # Log response
            response_log_data = {
                'event': 'request_completed',
                'request_id': request_id,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'method': method,
                'endpoint': endpoint,
                'status_code': response.status_code if response else 500,
                'response_time_ms': response_time_ms,
                'response_size_bytes': response_size,
                'user_id': user_id,
                'project_id': project_id
            }
            
            if response_body is not None:
                response_log_data['response_body'] = response_body
            
            if exception_info:
                response_log_data['exception'] = exception_info
            
            # Log at appropriate level
            if response and response.status_code >= 500:
                self.api_logger.error(json.dumps(response_log_data, default=str))
            elif response and response.status_code >= 400:
                self.api_logger.warning(json.dumps(response_log_data, default=str))
            else:
                self.api_logger.info(json.dumps(response_log_data, default=str))
            
            # Performance logging
            if response_time_ms > self.very_slow_threshold:
                self.performance_logger.error(
                    json.dumps({
                        'event': 'very_slow_request',
                        'request_id': request_id,
                        'endpoint': endpoint,
                        'method': method,
                        'response_time_ms': response_time_ms,
                        'user_id': user_id
                    }, default=str)
                )
            elif response_time_ms > self.slow_request_threshold:
                self.performance_logger.warning(
                    json.dumps({
                        'event': 'slow_request',
                        'request_id': request_id,
                        'endpoint': endpoint,
                        'method': method,
                        'response_time_ms': response_time_ms,
                        'user_id': user_id
                    }, default=str)
                )
            
            # Security logging for authentication results
            if endpoint.startswith('/api/auth/'):
                if response and response.status_code == 200:
                    log_security_event(
                        event_type='authentication_success',
                        severity='low',
                        details={
                            'endpoint': endpoint,
                            'user_id': user_id,
                            'client_ip': client_ip
                        }
                    )
                elif response and response.status_code == 401:
                    log_security_event(
                        event_type='authentication_failed',
                        severity='medium',
                        details={
                            'endpoint': endpoint,
                            'client_ip': client_ip,
                            'user_agent': user_agent
                        }
                    )
            
            # Log user actions for audit trail
            if user_id and method in ['POST', 'PUT', 'DELETE', 'PATCH']:
                action_type = self._determine_action_type(method, endpoint, response.status_code if response else 500)
                resource_type = self._extract_resource_type(endpoint)
                resource_id = self._extract_resource_id(endpoint, request)
                
                if action_type and resource_type:
                    log_user_action(
                        user_id=user_id,
                        action=action_type,
                        resource_type=resource_type,
                        resource_id=resource_id,
                        details={
                            'endpoint': endpoint,
                            'method': method,
                            'status_code': response.status_code if response else 500,
                            'response_time_ms': response_time_ms
                        }
                    )
        
        # Clear context
        clear_context()
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        # Check for forwarded headers (when behind proxy)
        forwarded_for = request.headers.get('x-forwarded-for')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        real_ip = request.headers.get('x-real-ip')
        if real_ip:
            return real_ip
        
        # Fallback to direct connection
        if request.client:
            return request.client.host
        
        return 'unknown'
    
    def _extract_user_id(self, request: Request) -> Optional[str]:
        """Extract user ID from request (JWT token, session, etc.)."""
        # Try to get from JWT token
        auth_header = request.headers.get('authorization', '')
        if auth_header.startswith('Bearer '):
            try:
                # This would need to be implemented with your JWT decoding logic
                # For now, return None to avoid import errors
                return None
            except Exception:
                pass
        
        # Try to get from session or other sources
        # This would be implemented based on your authentication system
        return None
    
    def _extract_username(self, request: Request) -> Optional[str]:
        """Extract username from request."""
        # This would be implemented based on your authentication system
        return None
    
    def _extract_user_role(self, request: Request) -> Optional[str]:
        """Extract user role from request."""
        # This would be implemented based on your authentication system
        return None
    
    def _extract_project_id(self, request: Request) -> Optional[str]:
        """Extract project ID from request path or headers."""
        # Try to extract from path parameters
        path_parts = request.url.path.split('/')
        try:
            if 'projects' in path_parts:
                project_index = path_parts.index('projects')
                if len(path_parts) > project_index + 1:
                    return path_parts[project_index + 1]
        except (ValueError, IndexError):
            pass
        
        # Try to extract from headers
        project_id = request.headers.get('x-project-id')
        if project_id:
            return project_id
        
        return None
    
    def _sanitize_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Remove sensitive information from headers."""
        sanitized = {}
        for key, value in headers.items():
            if key.lower() in self.sensitive_headers:
                sanitized[key] = '<redacted>'
            else:
                sanitized[key] = value
        return sanitized
    
    def _sanitize_data(self, data: Any) -> Any:
        """Remove sensitive information from request/response data."""
        if isinstance(data, dict):
            sanitized = {}
            sensitive_fields = {
                'password', 'token', 'secret', 'key', 'authorization',
                'credit_card', 'ssn', 'social_security'
            }
            
            for key, value in data.items():
                if any(sensitive_field in key.lower() for sensitive_field in sensitive_fields):
                    sanitized[key] = '<redacted>'
                elif isinstance(value, (dict, list)):
                    sanitized[key] = self._sanitize_data(value)
                else:
                    sanitized[key] = value
            return sanitized
        elif isinstance(data, list):
            return [self._sanitize_data(item) for item in data]
        else:
            return data
    
    def _determine_action_type(self, method: str, endpoint: str, status_code: int) -> Optional[str]:
        """Determine action type from HTTP method and endpoint."""
        if status_code >= 400:
            return None  # Don't log failed actions
        
        action_mapping = {
            'POST': 'created',
            'PUT': 'updated',
            'PATCH': 'updated',
            'DELETE': 'deleted'
        }
        
        return action_mapping.get(method.upper())
    
    def _extract_resource_type(self, endpoint: str) -> Optional[str]:
        """Extract resource type from endpoint."""
        path_parts = [part for part in endpoint.split('/') if part]
        
        # Skip 'api' prefix
        if path_parts and path_parts[0] == 'api':
            path_parts = path_parts[1:]
        
        # Return the resource type (pluralized form)
        resource_mapping = {
            'projects': 'project',
            'texts': 'text',
            'annotations': 'annotation',
            'labels': 'label',
            'users': 'user',
            'auth': 'authentication'
        }
        
        if path_parts:
            resource_type = path_parts[0]
            return resource_mapping.get(resource_type, resource_type.rstrip('s'))
        
        return None
    
    def _extract_resource_id(self, endpoint: str, request: Request) -> Optional[str]:
        """Extract resource ID from endpoint or request."""
        path_parts = [part for part in endpoint.split('/') if part]
        
        # Try to find ID in path (usually after resource type)
        for i, part in enumerate(path_parts):
            # Check if this looks like an ID (numeric or UUID-like)
            if part.isdigit() or (len(part) > 10 and '-' in part):
                return part
        
        # Try to get from query parameters
        resource_id = request.query_params.get('id')
        if resource_id:
            return resource_id
        
        return None


class DatabaseLoggingMiddleware:
    """Middleware for database query logging."""
    
    def __init__(self):
        """Initialize database logging middleware."""
        self.logger = get_logger('performance')
        self.metrics_collector = get_metrics_collector()
        self.slow_query_threshold = 1000  # 1 second
    
    def log_query(self, query: str, params: tuple = None, execution_time_ms: float = None, 
                  error: Exception = None):
        """Log database query execution."""
        query_data = {
            'event': 'database_query',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'query': query[:500] if query else None,  # Truncate long queries
            'execution_time_ms': execution_time_ms,
            'error': str(error) if error else None
        }
        
        # Add parameter count (but not values for security)
        if params:
            query_data['parameter_count'] = len(params)
        
        # Log at appropriate level
        if error:
            self.logger.error(json.dumps(query_data, default=str))
        elif execution_time_ms and execution_time_ms > self.slow_query_threshold:
            self.logger.warning(json.dumps(query_data, default=str))
        else:
            self.logger.info(json.dumps(query_data, default=str))
        
        # Record metrics
        if execution_time_ms:
            self.metrics_collector.record_database_query(
                execution_time_ms, 
                query,
                failed=error is not None
            )


# Global database logging instance
_db_logger = None


def get_database_logger() -> DatabaseLoggingMiddleware:
    """Get the global database logging middleware instance."""
    global _db_logger
    if _db_logger is None:
        _db_logger = DatabaseLoggingMiddleware()
    return _db_logger