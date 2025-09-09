"""
Cache Decorators for Performance Optimization

Provides decorators for caching function results with:
- Automatic cache key generation
- TTL management and invalidation
- Error handling and fallback
- Performance monitoring
"""

import asyncio
import functools
import hashlib
import json
import time
from typing import Any, Optional, Dict, List, Callable, Union
from datetime import datetime, timedelta

from ..core.cache_service import get_cache_service, CacheKey
from ..services.cache_manager import get_cache_manager
from ..utils.logger import get_logger


logger = get_logger(__name__)


def cached(
    ttl: Optional[int] = None,
    key_prefix: Optional[str] = None,
    key_func: Optional[Callable] = None,
    invalidate_patterns: Optional[List[str]] = None,
    ignore_errors: bool = True,
    cache_none: bool = False
):
    """
    Cache decorator for async functions with advanced features
    
    Args:
        ttl: Time to live in seconds (uses default if None)
        key_prefix: Prefix for cache key (uses function name if None)
        key_func: Custom function to generate cache key
        invalidate_patterns: Patterns to invalidate when function is called with write operations
        ignore_errors: Continue execution if cache fails
        cache_none: Whether to cache None results
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            cache_manager = get_cache_manager()
            
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                prefix = key_prefix or f"{func.__module__}.{func.__name__}"
                cache_key = CacheKey.generate(prefix, *args, **kwargs)
            
            try:
                # Try to get from cache first
                cached_result = await cache_manager.cache.get(cache_key)
                if cached_result is not None or (cached_result is None and cache_none):
                    logger.debug(f"Cache hit for {cache_key}")
                    return cached_result
                
                # Cache miss - execute function
                logger.debug(f"Cache miss for {cache_key}, executing function")
                start_time = time.time()
                result = await func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                # Cache the result
                if result is not None or cache_none:
                    success = await cache_manager.cache.set(cache_key, result, ttl=ttl)
                    if success:
                        logger.debug(f"Cached result for {cache_key} (execution: {execution_time:.3f}s)")
                    else:
                        logger.warning(f"Failed to cache result for {cache_key}")
                
                # Invalidate related patterns if specified
                if invalidate_patterns and result is not None:
                    for pattern in invalidate_patterns:
                        try:
                            await cache_manager.invalidate_query_cache(pattern)
                        except Exception as e:
                            logger.warning(f"Failed to invalidate pattern {pattern}: {str(e)}")
                
                return result
                
            except Exception as e:
                if ignore_errors:
                    logger.warning(f"Cache error for {cache_key}, executing function anyway: {str(e)}")
                    return await func(*args, **kwargs)
                else:
                    raise
        
        # Add cache invalidation method to the function
        wrapper.invalidate_cache = lambda *args, **kwargs: _invalidate_cache(func, key_func, key_prefix, *args, **kwargs)
        wrapper.warm_cache = lambda *args, **kwargs: _warm_cache(func, key_func, key_prefix, *args, **kwargs)
        
        return wrapper
    return decorator


async def _invalidate_cache(func, key_func, key_prefix, *args, **kwargs):
    """Invalidate cache for specific function call"""
    cache_manager = get_cache_manager()
    
    if key_func:
        cache_key = key_func(*args, **kwargs)
    else:
        prefix = key_prefix or f"{func.__module__}.{func.__name__}"
        cache_key = CacheKey.generate(prefix, *args, **kwargs)
    
    success = await cache_manager.cache.delete(cache_key) > 0
    if success:
        logger.info(f"Invalidated cache for {cache_key}")
    return success


async def _warm_cache(func, key_func, key_prefix, *args, **kwargs):
    """Pre-warm cache for specific function call"""
    cache_manager = get_cache_manager()
    
    if key_func:
        cache_key = key_func(*args, **kwargs)
    else:
        prefix = key_prefix or f"{func.__module__}.{func.__name__}"
        cache_key = CacheKey.generate(prefix, *args, **kwargs)
    
    # Check if already cached
    if await cache_manager.cache.exists(cache_key):
        logger.debug(f"Cache already warmed for {cache_key}")
        return True
    
    # Execute and cache
    result = await func(*args, **kwargs)
    if result is not None:
        success = await cache_manager.cache.set(cache_key, result)
        if success:
            logger.info(f"Warmed cache for {cache_key}")
        return success
    
    return False


def cache_invalidate(*patterns: str):
    """
    Decorator to invalidate cache patterns after function execution
    
    Args:
        patterns: Cache patterns to invalidate
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            
            # Invalidate cache patterns
            cache_manager = get_cache_manager()
            for pattern in patterns:
                try:
                    await cache_manager.invalidate_query_cache(pattern)
                    logger.debug(f"Invalidated cache pattern: {pattern}")
                except Exception as e:
                    logger.warning(f"Failed to invalidate pattern {pattern}: {str(e)}")
            
            return result
        return wrapper
    return decorator


def cache_warm(key_patterns: List[str], loader_func: Callable):
    """
    Decorator to warm cache after function execution
    
    Args:
        key_patterns: Patterns to warm
        loader_func: Function to load data for warming
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            
            # Warm cache in background
            asyncio.create_task(_warm_cache_patterns(key_patterns, loader_func, result))
            
            return result
        return wrapper
    return decorator


async def _warm_cache_patterns(patterns: List[str], loader_func: Callable, context_data: Any):
    """Warm cache patterns in background"""
    try:
        await loader_func(patterns, context_data)
        logger.debug(f"Warmed cache patterns: {patterns}")
    except Exception as e:
        logger.warning(f"Failed to warm cache patterns {patterns}: {str(e)}")


class CacheContext:
    """Context manager for cache operations with automatic cleanup"""
    
    def __init__(self, keys_to_invalidate: Optional[List[str]] = None):
        self.keys_to_invalidate = keys_to_invalidate or []
        self.temp_keys = []
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:  # Success
            # Invalidate specified keys
            if self.keys_to_invalidate:
                cache_manager = get_cache_manager()
                for key in self.keys_to_invalidate:
                    try:
                        await cache_manager.cache.delete(key)
                        logger.debug(f"Invalidated cache key: {key}")
                    except Exception as e:
                        logger.warning(f"Failed to invalidate key {key}: {str(e)}")
        
        # Clean up temporary keys
        if self.temp_keys:
            cache_manager = get_cache_manager()
            try:
                await cache_manager.cache.delete(*self.temp_keys)
                logger.debug(f"Cleaned up {len(self.temp_keys)} temporary cache keys")
            except Exception as e:
                logger.warning(f"Failed to clean up temporary keys: {str(e)}")
    
    def add_temp_key(self, key: str):
        """Add a key to be cleaned up at context exit"""
        self.temp_keys.append(key)
    
    def add_invalidation_key(self, key: str):
        """Add a key to be invalidated on successful completion"""
        self.keys_to_invalidate.append(key)


# Specialized decorators for domain objects


def cache_user(ttl: int = 3600, include_projects: bool = False):
    """Cache decorator specifically for user-related functions"""
    def key_func(*args, **kwargs):
        user_id = args[0] if args else kwargs.get('user_id')
        suffix = "with_projects" if include_projects else "basic"
        return CacheKey.generate("user", user_id, suffix)
    
    invalidate_patterns = ["user:*"] if include_projects else []
    
    return cached(
        ttl=ttl,
        key_func=key_func,
        invalidate_patterns=invalidate_patterns
    )


def cache_project(ttl: int = 1800, include_stats: bool = False):
    """Cache decorator specifically for project-related functions"""
    def key_func(*args, **kwargs):
        project_id = args[0] if args else kwargs.get('project_id')
        suffix = "with_stats" if include_stats else "basic"
        return CacheKey.generate("project", project_id, suffix)
    
    return cached(ttl=ttl, key_func=key_func)


def cache_annotations(ttl: int = 900):
    """Cache decorator for annotation queries"""
    def key_func(*args, **kwargs):
        text_id = kwargs.get('text_id') or (args[0] if args else None)
        user_id = kwargs.get('user_id')
        filters = kwargs.get('filters', {})
        
        key_parts = ["annotations", "text", text_id]
        if user_id:
            key_parts.extend(["user", user_id])
        if filters:
            # Sort filters for consistent keys
            for k, v in sorted(filters.items()):
                key_parts.extend([k, str(v)])
        
        return CacheKey.generate(*key_parts)
    
    return cached(ttl=ttl, key_func=key_func)


def cache_labels(ttl: int = 7200):
    """Cache decorator for label queries"""
    def key_func(*args, **kwargs):
        project_id = kwargs.get('project_id') or (args[0] if args else None)
        return CacheKey.generate("labels", "project", project_id)
    
    return cached(ttl=ttl, key_func=key_func)


def cache_query_result(query_name: str, ttl: int = 600):
    """Cache decorator for expensive database queries"""
    def key_func(*args, **kwargs):
        return CacheKey.generate("query", query_name, **kwargs)
    
    return cached(ttl=ttl, key_func=key_func)


# Performance monitoring decorator
def monitor_cache_performance(func):
    """Decorator to monitor and log cache performance"""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        
        try:
            result = await func(*args, **kwargs)
            execution_time = time.time() - start_time
            
            logger.info(
                f"Cache operation completed",
                extra={
                    "function": f"{func.__module__}.{func.__name__}",
                    "execution_time": execution_time,
                    "success": True,
                    "args_count": len(args),
                    "kwargs_count": len(kwargs)
                }
            )
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            
            logger.error(
                f"Cache operation failed",
                extra={
                    "function": f"{func.__module__}.{func.__name__}",
                    "execution_time": execution_time,
                    "success": False,
                    "error": str(e),
                    "args_count": len(args),
                    "kwargs_count": len(kwargs)
                }
            )
            
            raise
    
    return wrapper


# Batch operations for cache warming
class CacheWarmer:
    """Utility class for batch cache warming operations"""
    
    def __init__(self, cache_manager=None):
        self.cache_manager = cache_manager or get_cache_manager()
    
    async def warm_user_caches(self, user_ids: List[int], db_session) -> Dict[str, int]:
        """Warm caches for multiple users"""
        from ..services.user_service import get_users_by_ids
        
        results = {"success": 0, "failed": 0}
        
        # Warm basic user data
        try:
            users = await get_users_by_ids(user_ids, db_session)
            success_count = await self.cache_manager.warm_user_cache(user_ids, lambda ids: users)
            results["success"] += success_count
        except Exception as e:
            logger.error(f"Failed to warm user caches: {str(e)}")
            results["failed"] += len(user_ids)
        
        return results
    
    async def warm_project_caches(self, project_ids: List[int], db_session) -> Dict[str, int]:
        """Warm caches for multiple projects"""
        from ..services.project_service import get_projects_by_ids
        
        results = {"success": 0, "failed": 0}
        
        try:
            # Load projects function
            async def load_projects(ids):
                return await get_projects_by_ids(ids, db_session)
            
            success_count = await self.cache_manager.warm_project_cache(project_ids, load_projects)
            results["success"] += success_count
        except Exception as e:
            logger.error(f"Failed to warm project caches: {str(e)}")
            results["failed"] += len(project_ids)
        
        return results
    
    async def warm_annotation_caches(self, text_ids: List[int], db_session) -> Dict[str, int]:
        """Warm annotation caches for multiple texts"""
        from ..services.annotation_service import get_text_annotations
        
        results = {"success": 0, "failed": 0}
        
        for text_id in text_ids:
            try:
                annotations = await get_text_annotations(text_id, db_session)
                key = CacheKey.generate("text", text_id, "annotations")
                success = await self.cache_manager.cache.set(key, annotations, ttl=900)
                
                if success:
                    results["success"] += 1
                else:
                    results["failed"] += 1
                    
            except Exception as e:
                logger.warning(f"Failed to warm annotations cache for text {text_id}: {str(e)}")
                results["failed"] += 1
        
        return results