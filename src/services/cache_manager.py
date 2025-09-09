"""
Cache Manager - High-level caching with patterns and strategies

Provides domain-specific caching for:
- Projects, Users, Annotations, Labels
- Query result caching
- Cache warming and preloading
- Distributed invalidation strategies
"""

import asyncio
import json
from typing import Any, Optional, Dict, List, Callable, Union, Type
from datetime import datetime, timedelta
from functools import wraps
from dataclasses import dataclass, asdict

from ..core.cache_service import get_cache_service, CacheKey, cache_transaction
from ..core.cache_config import CacheStrategy
from ..utils.logger import get_logger


logger = get_logger(__name__)


@dataclass
class CacheEntry:
    """Cache entry metadata"""
    key: str
    value: Any
    ttl: int
    created_at: datetime
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "ttl": self.ttl,
            "created_at": self.created_at.isoformat(),
            "access_count": self.access_count,
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None
        }


class CacheManager:
    """High-level cache management with domain-specific patterns"""
    
    def __init__(self, cache_service=None):
        self.cache = cache_service or get_cache_service()
        self.default_ttls = {
            "user": 3600,        # 1 hour
            "project": 1800,     # 30 minutes  
            "annotation": 900,   # 15 minutes
            "label": 7200,       # 2 hours
            "query": 600,        # 10 minutes
            "static": 86400,     # 24 hours
        }
        
    # =============================================================================
    # User Caching
    # =============================================================================
    
    async def get_user(self, user_id: int, loader: Optional[Callable] = None) -> Optional[Any]:
        """Get user with cache-aside pattern"""
        key = CacheKey.generate("user", user_id)
        
        # Try cache first
        user = await self.cache.get(key)
        if user is not None:
            logger.debug(f"Cache hit for user {user_id}")
            return user
        
        # Cache miss - load from database
        if loader:
            logger.debug(f"Cache miss for user {user_id}, loading from database")
            user = await loader(user_id)
            if user:
                await self.cache.set(key, user, ttl=self.default_ttls["user"])
                logger.debug(f"Cached user {user_id}")
            return user
        
        return None
    
    async def set_user(self, user_id: int, user_data: Any, ttl: Optional[int] = None) -> bool:
        """Cache user data"""
        key = CacheKey.generate("user", user_id)
        return await self.cache.set(key, user_data, ttl=ttl or self.default_ttls["user"])
    
    async def invalidate_user(self, user_id: int) -> bool:
        """Invalidate user cache"""
        key = CacheKey.generate("user", user_id)
        count = await self.cache.delete(key)
        if count > 0:
            logger.info(f"Invalidated cache for user {user_id}")
        return count > 0
    
    async def get_users_batch(self, user_ids: List[int], loader: Optional[Callable] = None) -> Dict[int, Any]:
        """Get multiple users with batch loading"""
        results = {}
        missing_ids = []
        
        # Check cache for all users
        for user_id in user_ids:
            key = CacheKey.generate("user", user_id)
            user = await self.cache.get(key)
            if user is not None:
                results[user_id] = user
            else:
                missing_ids.append(user_id)
        
        # Load missing users from database
        if missing_ids and loader:
            logger.debug(f"Batch loading {len(missing_ids)} users from database")
            loaded_users = await loader(missing_ids)
            
            # Cache loaded users
            for user_id, user_data in loaded_users.items():
                key = CacheKey.generate("user", user_id)
                await self.cache.set(key, user_data, ttl=self.default_ttls["user"])
                results[user_id] = user_data
        
        return results
    
    # =============================================================================
    # Project Caching
    # =============================================================================
    
    async def get_project(self, project_id: int, loader: Optional[Callable] = None) -> Optional[Any]:
        """Get project with cache-aside pattern"""
        key = CacheKey.generate("project", project_id)
        
        project = await self.cache.get(key)
        if project is not None:
            return project
        
        if loader:
            project = await loader(project_id)
            if project:
                await self.cache.set(key, project, ttl=self.default_ttls["project"])
            return project
        
        return None
    
    async def set_project(self, project_id: int, project_data: Any, ttl: Optional[int] = None) -> bool:
        """Cache project data with write-through pattern"""
        key = CacheKey.generate("project", project_id)
        success = await self.cache.set(key, project_data, ttl=ttl or self.default_ttls["project"])
        
        # Also cache project list entries
        await self._update_project_lists(project_id, project_data)
        
        return success
    
    async def invalidate_project(self, project_id: int, cascade: bool = True) -> bool:
        """Invalidate project cache with optional cascade to related data"""
        keys_to_delete = [CacheKey.generate("project", project_id)]
        
        if cascade:
            # Invalidate related caches
            keys_to_delete.extend([
                CacheKey.generate("project", project_id, "stats"),
                CacheKey.generate("project", project_id, "users"),
                CacheKey.generate("project", project_id, "annotations"),
                CacheKey.pattern("annotation", f"project:{project_id}:*")
            ])
            
            # Clear query caches that might include this project
            await self.cache.flush_pattern(CacheKey.pattern("query", "projects:*"))
        
        count = await self.cache.delete(*keys_to_delete)
        if count > 0:
            logger.info(f"Invalidated cache for project {project_id} (cascade={cascade})")
        
        return count > 0
    
    async def get_user_projects(self, user_id: int, loader: Optional[Callable] = None) -> Optional[List[Any]]:
        """Get user's projects list with caching"""
        key = CacheKey.generate("user", user_id, "projects")
        
        projects = await self.cache.get(key)
        if projects is not None:
            return projects
        
        if loader:
            projects = await loader(user_id)
            if projects is not None:
                await self.cache.set(key, projects, ttl=self.default_ttls["project"])
            return projects
        
        return None
    
    async def _update_project_lists(self, project_id: int, project_data: Any):
        """Update cached project lists when project changes"""
        # This would typically invalidate user project lists
        # or update them if we have the necessary information
        pass
    
    # =============================================================================
    # Annotation Caching
    # =============================================================================
    
    async def get_annotation(self, annotation_id: int, loader: Optional[Callable] = None) -> Optional[Any]:
        """Get annotation with cache-aside pattern"""
        key = CacheKey.generate("annotation", annotation_id)
        
        annotation = await self.cache.get(key)
        if annotation is not None:
            return annotation
        
        if loader:
            annotation = await loader(annotation_id)
            if annotation:
                await self.cache.set(key, annotation, ttl=self.default_ttls["annotation"])
            return annotation
        
        return None
    
    async def get_text_annotations(
        self, 
        text_id: int, 
        user_id: Optional[int] = None,
        loader: Optional[Callable] = None
    ) -> Optional[List[Any]]:
        """Get annotations for a text with optional user filtering"""
        key_parts = ["text", text_id, "annotations"]
        if user_id:
            key_parts.extend(["user", user_id])
        
        key = CacheKey.generate(*key_parts)
        
        annotations = await self.cache.get(key)
        if annotations is not None:
            return annotations
        
        if loader:
            annotations = await loader(text_id, user_id)
            if annotations is not None:
                await self.cache.set(key, annotations, ttl=self.default_ttls["annotation"])
            return annotations
        
        return None
    
    async def invalidate_annotation(self, annotation_id: int, text_id: Optional[int] = None) -> bool:
        """Invalidate annotation cache and related caches"""
        keys_to_delete = [CacheKey.generate("annotation", annotation_id)]
        
        if text_id:
            # Invalidate text annotation lists
            keys_to_delete.append(CacheKey.pattern("text", text_id, "annotations:*"))
            
        count = await self.cache.delete(*keys_to_delete)
        if count > 0:
            logger.info(f"Invalidated cache for annotation {annotation_id}")
        
        return count > 0
    
    # =============================================================================
    # Label Caching
    # =============================================================================
    
    async def get_label(self, label_id: int, loader: Optional[Callable] = None) -> Optional[Any]:
        """Get label with cache-aside pattern"""
        key = CacheKey.generate("label", label_id)
        
        label = await self.cache.get(key)
        if label is not None:
            return label
        
        if loader:
            label = await loader(label_id)
            if label:
                # Labels are relatively static, longer TTL
                await self.cache.set(key, label, ttl=self.default_ttls["label"])
            return label
        
        return None
    
    async def get_project_labels(self, project_id: int, loader: Optional[Callable] = None) -> Optional[List[Any]]:
        """Get all labels for a project"""
        key = CacheKey.generate("project", project_id, "labels")
        
        labels = await self.cache.get(key)
        if labels is not None:
            return labels
        
        if loader:
            labels = await loader(project_id)
            if labels is not None:
                await self.cache.set(key, labels, ttl=self.default_ttls["label"])
            return labels
        
        return None
    
    async def invalidate_project_labels(self, project_id: int) -> bool:
        """Invalidate label cache for a project"""
        pattern = CacheKey.pattern("project", project_id, "labels")
        count = await self.cache.flush_pattern(pattern)
        
        # Also invalidate individual labels from this project
        pattern = CacheKey.pattern("label", f"project:{project_id}:*")
        count += await self.cache.flush_pattern(pattern)
        
        if count > 0:
            logger.info(f"Invalidated label cache for project {project_id}")
        
        return count > 0
    
    # =============================================================================
    # Query Result Caching
    # =============================================================================
    
    async def get_query_result(
        self, 
        query_name: str, 
        params: Dict[str, Any],
        loader: Optional[Callable] = None,
        ttl: Optional[int] = None
    ) -> Optional[Any]:
        """Cache expensive query results"""
        # Generate cache key from query name and parameters
        key = CacheKey.generate("query", query_name, **params)
        
        result = await self.cache.get(key)
        if result is not None:
            logger.debug(f"Query cache hit for {query_name}")
            return result
        
        if loader:
            logger.debug(f"Query cache miss for {query_name}, executing query")
            result = await loader(**params)
            if result is not None:
                await self.cache.set(key, result, ttl=ttl or self.default_ttls["query"])
            return result
        
        return None
    
    async def invalidate_query_cache(self, pattern: str) -> int:
        """Invalidate query cache by pattern"""
        cache_pattern = CacheKey.pattern("query", pattern)
        count = await self.cache.flush_pattern(cache_pattern)
        if count > 0:
            logger.info(f"Invalidated {count} query cache entries matching {pattern}")
        return count
    
    # =============================================================================
    # Cache Warming and Preloading
    # =============================================================================
    
    async def warm_user_cache(self, user_ids: List[int], loader: Callable) -> int:
        """Preload user data into cache"""
        warmed_count = 0
        
        logger.info(f"Warming cache for {len(user_ids)} users")
        
        # Load users in batches to avoid overwhelming the database
        batch_size = 50
        for i in range(0, len(user_ids), batch_size):
            batch_ids = user_ids[i:i + batch_size]
            
            try:
                users = await loader(batch_ids)
                
                # Cache each user
                for user_id, user_data in users.items():
                    key = CacheKey.generate("user", user_id)
                    success = await self.cache.set(key, user_data, ttl=self.default_ttls["user"])
                    if success:
                        warmed_count += 1
                
                # Small delay to avoid overwhelming Redis
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.warning(f"Error warming user cache batch {i//batch_size + 1}: {str(e)}")
        
        logger.info(f"Warmed cache for {warmed_count} users")
        return warmed_count
    
    async def warm_project_cache(self, project_ids: List[int], loader: Callable) -> int:
        """Preload project data into cache"""
        warmed_count = 0
        
        logger.info(f"Warming cache for {len(project_ids)} projects")
        
        for project_id in project_ids:
            try:
                project_data = await loader(project_id)
                if project_data:
                    success = await self.set_project(project_id, project_data)
                    if success:
                        warmed_count += 1
                
                # Small delay between requests
                await asyncio.sleep(0.05)
                
            except Exception as e:
                logger.warning(f"Error warming cache for project {project_id}: {str(e)}")
        
        logger.info(f"Warmed cache for {warmed_count} projects")
        return warmed_count
    
    # =============================================================================
    # Cache Statistics and Monitoring
    # =============================================================================
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        stats = {
            "service_metrics": self.cache.get_metrics(),
            "redis_info": await self.cache.get_info(),
            "key_distribution": await self._get_key_distribution()
        }
        
        return stats
    
    async def _get_key_distribution(self) -> Dict[str, int]:
        """Get distribution of cache keys by type"""
        distribution = {}
        
        for key_type in ["user", "project", "annotation", "label", "query"]:
            pattern = CacheKey.pattern(key_type)
            keys = await self.cache.keys(pattern)
            distribution[key_type] = len(keys)
        
        return distribution
    
    async def cleanup_expired_entries(self) -> int:
        """Clean up expired cache entries (if not handled automatically by Redis)"""
        # This is primarily handled by Redis TTL, but we can do manual cleanup for patterns
        cleaned = 0
        
        # Get all keys and check their TTL
        all_keys = await self.cache.keys("*")
        
        for key in all_keys:
            ttl = await self.cache.ttl(key)
            if ttl == -2:  # Key doesn't exist (expired)
                cleaned += 1
        
        return cleaned
    
    # =============================================================================
    # Utility Methods
    # =============================================================================
    
    async def health_check(self) -> Dict[str, Any]:
        """Check cache health"""
        try:
            # Test basic operations
            test_key = "health_check_test"
            test_value = {"test": True, "timestamp": datetime.now().isoformat()}
            
            # Test set
            set_success = await self.cache.set(test_key, test_value, ttl=60)
            
            # Test get
            get_result = await self.cache.get(test_key)
            get_success = get_result == test_value
            
            # Test delete
            delete_success = await self.cache.delete(test_key) > 0
            
            return {
                "status": "healthy" if (set_success and get_success and delete_success) else "unhealthy",
                "operations": {
                    "set": set_success,
                    "get": get_success,
                    "delete": delete_success
                },
                "metrics": self.cache.get_metrics()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "metrics": self.cache.get_metrics()
            }


# Global cache manager instance
_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """Get global cache manager instance"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager


# Decorator for caching function results
def cache_result(key_prefix: str, ttl: Optional[int] = None, key_func: Optional[Callable] = None):
    """Decorator to cache function results"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_manager = get_cache_manager()
            
            # Generate cache key
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                key = CacheKey.generate(key_prefix, *args, **kwargs)
            
            # Try to get from cache
            result = await cache_manager.cache.get(key)
            if result is not None:
                return result
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            if result is not None:
                await cache_manager.cache.set(key, result, ttl=ttl)
            
            return result
        
        return wrapper
    return decorator