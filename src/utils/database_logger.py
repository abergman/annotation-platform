"""
Database Query Logging and Monitoring

This module provides comprehensive database query logging, slow query detection,
and database performance monitoring for the academic annotation system.
"""

import time
import json
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Callable
from contextlib import contextmanager, asynccontextmanager
from functools import wraps

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import Pool
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from .logger import get_logger, log_performance_metric, log_exception
from .monitoring import get_metrics_collector


class DatabaseQueryLogger:
    """Comprehensive database query logging and monitoring."""
    
    def __init__(self, slow_query_threshold_ms: int = 1000):
        """Initialize database query logger."""
        self.slow_query_threshold_ms = slow_query_threshold_ms
        self.logger = get_logger('performance')
        self.error_logger = get_logger('errors')
        self.metrics_collector = get_metrics_collector()
        
        # Query statistics
        self.query_count = 0
        self.slow_query_count = 0
        self.failed_query_count = 0
        
        # Connection pool monitoring
        self.connection_stats = {
            'total_connections': 0,
            'active_connections': 0,
            'checked_out': 0,
            'checked_in': 0,
            'invalidated': 0
        }
    
    def log_query_start(self, query: str, parameters: Any = None, context: Dict[str, Any] = None):
        """Log the start of a database query."""
        start_time = time.time()
        
        query_data = {
            'event': 'query_started',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'query_hash': str(hash(query)),
            'query': self._sanitize_query(query),
            'parameter_count': len(parameters) if parameters else 0,
            'start_time': start_time
        }
        
        if context:
            query_data['context'] = context
        
        # Log query start (debug level)
        self.logger.debug(json.dumps(query_data, default=str))
        
        return start_time
    
    def log_query_completion(self, query: str, start_time: float, 
                           parameters: Any = None, result_count: int = None,
                           context: Dict[str, Any] = None):
        """Log successful query completion."""
        end_time = time.time()
        execution_time_ms = (end_time - start_time) * 1000
        
        self.query_count += 1
        
        query_data = {
            'event': 'query_completed',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'query_hash': str(hash(query)),
            'query': self._sanitize_query(query),
            'execution_time_ms': execution_time_ms,
            'result_count': result_count,
            'parameter_count': len(parameters) if parameters else 0
        }
        
        if context:
            query_data['context'] = context
        
        # Determine log level based on execution time
        if execution_time_ms > self.slow_query_threshold_ms:
            self.slow_query_count += 1
            self.logger.warning(json.dumps(query_data, default=str))
        else:
            self.logger.info(json.dumps(query_data, default=str))
        
        # Record metrics
        self.metrics_collector.record_database_query(execution_time_ms, query, failed=False)
        log_performance_metric('db_query_time', execution_time_ms, 'ms', context)
    
    def log_query_error(self, query: str, start_time: float, error: Exception,
                       parameters: Any = None, context: Dict[str, Any] = None):
        """Log query execution error."""
        end_time = time.time()
        execution_time_ms = (end_time - start_time) * 1000
        
        self.failed_query_count += 1
        
        error_data = {
            'event': 'query_failed',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'query_hash': str(hash(query)),
            'query': self._sanitize_query(query),
            'execution_time_ms': execution_time_ms,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'parameter_count': len(parameters) if parameters else 0
        }
        
        if context:
            error_data['context'] = context
        
        self.error_logger.error(json.dumps(error_data, default=str))
        
        # Record metrics
        self.metrics_collector.record_database_query(execution_time_ms, query, failed=True)
        log_performance_metric('db_query_failed', 1, 'count', context)
    
    def _sanitize_query(self, query: str) -> str:
        """Sanitize query for logging (truncate and clean)."""
        # Remove extra whitespace and newlines
        cleaned_query = ' '.join(query.split())
        
        # Truncate very long queries
        if len(cleaned_query) > 500:
            cleaned_query = cleaned_query[:500] + "..."
        
        return cleaned_query
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get query statistics."""
        return {
            'total_queries': self.query_count,
            'slow_queries': self.slow_query_count,
            'failed_queries': self.failed_query_count,
            'slow_query_rate': (self.slow_query_count / max(self.query_count, 1)) * 100,
            'failure_rate': (self.failed_query_count / max(self.query_count, 1)) * 100,
            'connection_stats': self.connection_stats.copy()
        }


# Global logger instance
_db_query_logger = None


def get_database_query_logger() -> DatabaseQueryLogger:
    """Get the global database query logger instance."""
    global _db_query_logger
    if _db_query_logger is None:
        _db_query_logger = DatabaseQueryLogger()
    return _db_query_logger


@contextmanager
def log_database_query(query: str, parameters: Any = None, context: Dict[str, Any] = None):
    """Context manager for logging database queries."""
    logger = get_database_query_logger()
    start_time = logger.log_query_start(query, parameters, context)
    
    try:
        yield
        logger.log_query_completion(query, start_time, parameters, context=context)
    except Exception as e:
        logger.log_query_error(query, start_time, e, parameters, context)
        raise


def setup_sqlalchemy_logging(engine: Engine):
    """Setup SQLAlchemy event listeners for comprehensive query logging."""
    query_logger = get_database_query_logger()
    
    # Track query execution
    @event.listens_for(engine, "before_cursor_execute")
    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        """Log query start."""
        conn.info.setdefault('query_start_time', []).append(time.time())
        
        # Extract additional context
        query_context = {
            'connection_id': id(conn),
            'executemany': executemany,
            'autocommit': conn.get_autocommit() if hasattr(conn, 'get_autocommit') else None
        }
        
        query_logger.log_query_start(statement, parameters, query_context)
    
    @event.listens_for(engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        """Log successful query completion."""
        total_time = time.time() - conn.info['query_start_time'].pop(-1)
        
        # Get result count if available
        result_count = None
        if hasattr(cursor, 'rowcount') and cursor.rowcount >= 0:
            result_count = cursor.rowcount
        
        # Extract additional context
        query_context = {
            'connection_id': id(conn),
            'executemany': executemany,
            'result_count': result_count
        }
        
        query_logger.log_query_completion(
            statement, 
            time.time() - total_time, 
            parameters, 
            result_count,
            query_context
        )
    
    @event.listens_for(engine, "handle_error")
    def handle_error(exception_context):
        """Log query errors."""
        conn = exception_context.connection
        if conn and 'query_start_time' in conn.info and conn.info['query_start_time']:
            total_time = time.time() - conn.info['query_start_time'].pop(-1)
            
            query_context = {
                'connection_id': id(conn) if conn else None,
                'is_disconnect': exception_context.is_disconnect
            }
            
            query_logger.log_query_error(
                exception_context.statement or "Unknown",
                time.time() - total_time,
                exception_context.original_exception,
                exception_context.parameters,
                query_context
            )
    
    # Track connection pool events
    @event.listens_for(Pool, "connect")
    def pool_connect(dbapi_conn, connection_record):
        """Log new database connections."""
        query_logger.connection_stats['total_connections'] += 1
        
        connection_data = {
            'event': 'database_connection_created',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'connection_id': id(connection_record),
            'total_connections': query_logger.connection_stats['total_connections']
        }
        
        query_logger.logger.info(json.dumps(connection_data, default=str))
    
    @event.listens_for(Pool, "checkout")
    def pool_checkout(dbapi_conn, connection_record, connection_proxy):
        """Log connection checkout from pool."""
        query_logger.connection_stats['checked_out'] += 1
        query_logger.connection_stats['active_connections'] += 1
    
    @event.listens_for(Pool, "checkin")
    def pool_checkin(dbapi_conn, connection_record):
        """Log connection checkin to pool."""
        query_logger.connection_stats['checked_in'] += 1
        query_logger.connection_stats['active_connections'] = max(
            0, query_logger.connection_stats['active_connections'] - 1
        )
    
    @event.listens_for(Pool, "invalidate")
    def pool_invalidate(dbapi_conn, connection_record, exception):
        """Log connection invalidation."""
        query_logger.connection_stats['invalidated'] += 1
        
        invalidation_data = {
            'event': 'database_connection_invalidated',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'connection_id': id(connection_record),
            'exception': str(exception) if exception else None,
            'total_invalidated': query_logger.connection_stats['invalidated']
        }
        
        query_logger.logger.warning(json.dumps(invalidation_data, default=str))


class QueryPerformanceAnalyzer:
    """Analyze database query performance patterns."""
    
    def __init__(self):
        """Initialize query performance analyzer."""
        self.query_patterns = {}
        self.slow_query_patterns = {}
        self.logger = get_logger('performance')
    
    def analyze_query(self, query: str, execution_time_ms: float, result_count: int = None):
        """Analyze individual query performance."""
        # Extract query pattern (remove specific values)
        query_pattern = self._extract_query_pattern(query)
        
        if query_pattern not in self.query_patterns:
            self.query_patterns[query_pattern] = {
                'count': 0,
                'total_time': 0,
                'max_time': 0,
                'min_time': float('inf'),
                'slow_count': 0,
                'avg_result_count': 0,
                'total_results': 0
            }
        
        pattern_stats = self.query_patterns[query_pattern]
        pattern_stats['count'] += 1
        pattern_stats['total_time'] += execution_time_ms
        pattern_stats['max_time'] = max(pattern_stats['max_time'], execution_time_ms)
        pattern_stats['min_time'] = min(pattern_stats['min_time'], execution_time_ms)
        
        if result_count is not None:
            pattern_stats['total_results'] += result_count
            pattern_stats['avg_result_count'] = pattern_stats['total_results'] / pattern_stats['count']
        
        if execution_time_ms > 1000:  # Slow query threshold
            pattern_stats['slow_count'] += 1
            
            if query_pattern not in self.slow_query_patterns:
                self.slow_query_patterns[query_pattern] = []
            
            self.slow_query_patterns[query_pattern].append({
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'execution_time_ms': execution_time_ms,
                'result_count': result_count
            })
            
            # Keep only recent slow queries (last 100)
            if len(self.slow_query_patterns[query_pattern]) > 100:
                self.slow_query_patterns[query_pattern] = self.slow_query_patterns[query_pattern][-100:]
    
    def _extract_query_pattern(self, query: str) -> str:
        """Extract query pattern by removing specific values."""
        import re
        
        # Convert to lowercase and remove extra whitespace
        pattern = re.sub(r'\s+', ' ', query.lower().strip())
        
        # Replace string literals with placeholder
        pattern = re.sub(r"'[^']*'", "'?'", pattern)
        pattern = re.sub(r'"[^"]*"', '"?"', pattern)
        
        # Replace numeric literals with placeholder
        pattern = re.sub(r'\b\d+\b', '?', pattern)
        
        # Replace IN clauses with placeholder
        pattern = re.sub(r'in\s*\([^)]+\)', 'in (?)', pattern)
        
        # Replace specific table names with pattern if they contain IDs
        pattern = re.sub(r'\b\w+_\d+\b', 'table_?', pattern)
        
        return pattern
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report."""
        if not self.query_patterns:
            return {'message': 'No query data available'}
        
        # Calculate overall statistics
        total_queries = sum(stats['count'] for stats in self.query_patterns.values())
        total_time = sum(stats['total_time'] for stats in self.query_patterns.values())
        total_slow = sum(stats['slow_count'] for stats in self.query_patterns.values())
        
        # Find top slow queries
        slow_patterns = []
        for pattern, stats in self.query_patterns.items():
            if stats['slow_count'] > 0:
                slow_patterns.append({
                    'pattern': pattern,
                    'slow_count': stats['slow_count'],
                    'slow_percentage': (stats['slow_count'] / stats['count']) * 100,
                    'avg_time': stats['total_time'] / stats['count'],
                    'max_time': stats['max_time'],
                    'total_executions': stats['count']
                })
        
        slow_patterns.sort(key=lambda x: x['slow_count'], reverse=True)
        
        # Find most frequently executed queries
        frequent_patterns = sorted(
            [
                {
                    'pattern': pattern,
                    'count': stats['count'],
                    'avg_time': stats['total_time'] / stats['count'],
                    'total_time': stats['total_time']
                }
                for pattern, stats in self.query_patterns.items()
            ],
            key=lambda x: x['count'],
            reverse=True
        )
        
        return {
            'summary': {
                'total_queries': total_queries,
                'total_execution_time_ms': total_time,
                'avg_query_time_ms': total_time / total_queries if total_queries > 0 else 0,
                'slow_queries': total_slow,
                'slow_query_percentage': (total_slow / total_queries) * 100 if total_queries > 0 else 0,
                'unique_patterns': len(self.query_patterns)
            },
            'top_slow_patterns': slow_patterns[:10],
            'most_frequent_patterns': frequent_patterns[:10],
            'recommendations': self._generate_recommendations(slow_patterns, frequent_patterns)
        }
    
    def _generate_recommendations(self, slow_patterns: List[Dict], frequent_patterns: List[Dict]) -> List[str]:
        """Generate performance optimization recommendations."""
        recommendations = []
        
        if slow_patterns:
            recommendations.append(
                f"Consider optimizing the {len(slow_patterns)} query patterns with slow execution times"
            )
            
            # Check for specific patterns
            for pattern_info in slow_patterns[:3]:
                pattern = pattern_info['pattern']
                if 'select * from' in pattern:
                    recommendations.append("Avoid SELECT * queries; select only needed columns")
                if 'like' in pattern and pattern.count('%') > 1:
                    recommendations.append("Consider full-text search instead of LIKE with multiple wildcards")
                if 'order by' in pattern and 'limit' not in pattern:
                    recommendations.append("Consider adding LIMIT to ORDER BY queries")
        
        if frequent_patterns:
            top_frequent = frequent_patterns[0]
            if top_frequent['count'] > 1000:
                recommendations.append(
                    f"Most frequent query pattern executed {top_frequent['count']} times - consider caching"
                )
        
        if not recommendations:
            recommendations.append("Query performance looks good!")
        
        return recommendations


# Global performance analyzer
_query_analyzer = None


def get_query_performance_analyzer() -> QueryPerformanceAnalyzer:
    """Get the global query performance analyzer."""
    global _query_analyzer
    if _query_analyzer is None:
        _query_analyzer = QueryPerformanceAnalyzer()
    return _query_analyzer


def log_slow_query_analysis():
    """Log periodic query performance analysis."""
    analyzer = get_query_performance_analyzer()
    report = analyzer.get_performance_report()
    
    if 'summary' in report:
        performance_logger = get_logger('performance')
        performance_logger.info(
            json.dumps({
                'event': 'query_performance_analysis',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'analysis': report
            }, default=str)
        )