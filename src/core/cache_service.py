"""
Redis Cache Service

Comprehensive caching service providing:
- Multiple cache patterns (cache-aside, write-through, etc.)
- Distributed caching with clustering support
- Intelligent TTL management and cache warming
- Performance monitoring and metrics
- Automatic serialization/deserialization
"""

import asyncio
import json
import pickle
import zlib
import time
import hashlib
from typing import Any, Optional, Dict, List, Union, Callable, TypeVar, Generic
from datetime import datetime, timedelta
from functools import wraps
from contextlib import asynccontextmanager

import redis
from redis.sentinel import Sentinel
from redis.cluster import RedisCluster
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError

from .cache_config import CacheConfig, CacheStrategy, CacheMode, CacheMetrics, load_cache_config
from ..utils.logger import get_logger


logger = get_logger(__name__)
T = TypeVar('T')


class SerializationError(Exception):
    """Raised when serialization/deserialization fails"""
    pass


class CacheConnectionError(Exception):
    """Raised when cache connection fails"""
    pass


class Serializer:
    """Handles serialization/deserialization with compression"""
    
    @staticmethod
    def serialize(data: Any, compress_threshold: int = 1024) -> bytes:
        """Serialize data with optional compression"""
        try:
            if isinstance(data, (str, int, float, bool)):
                # Simple types - use JSON for readability
                serialized = json.dumps(data).encode('utf-8')
            else:
                # Complex types - use pickle
                serialized = pickle.dumps(data)
            
            # Compress if data is large enough
            if len(serialized) > compress_threshold:
                compressed = zlib.compress(serialized)
                # Only use compression if it actually reduces size
                if len(compressed) < len(serialized):
                    return b'compressed:' + compressed
            
            return b'raw:' + serialized
            
        except Exception as e:
            raise SerializationError(f"Failed to serialize data: {str(e)}")
    
    @staticmethod
    def deserialize(data: bytes) -> Any:
        """Deserialize data with automatic decompression"""
        try:
            if data.startswith(b'compressed:'):
                # Decompress first
                compressed_data = data[11:]  # Remove 'compressed:' prefix
                decompressed = zlib.decompress(compressed_data)
                data = b'raw:' + decompressed
            
            if data.startswith(b'raw:'):
                serialized_data = data[4:]  # Remove 'raw:' prefix
                try:
                    # Try JSON first (for simple types)
                    return json.loads(serialized_data.decode('utf-8'))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    # Fall back to pickle
                    return pickle.loads(serialized_data)
            
            # Fallback - assume raw pickle data (backward compatibility)
            return pickle.loads(data)
            
        except Exception as e:
            raise SerializationError(f"Failed to deserialize data: {str(e)}")


class CacheKey:
    """Utility for generating consistent cache keys"""
    
    @staticmethod
    def generate(prefix: str, *args, **kwargs) -> str:
        """Generate a cache key from prefix and arguments"""
        key_parts = [prefix]
        
        # Add positional arguments
        for arg in args:
            key_parts.append(str(arg))
        
        # Add keyword arguments (sorted for consistency)
        for key, value in sorted(kwargs.items()):
            key_parts.append(f"{key}:{value}")
        
        key = ":".join(key_parts)
        
        # Hash if key is too long
        if len(key) > 250:  # Redis key limit is 512MB but keep it reasonable
            key_hash = hashlib.sha256(key.encode()).hexdigest()
            return f"{prefix}:hash:{key_hash}"
        
        return key
    
    @staticmethod
    def pattern(prefix: str, pattern: str = "*") -> str:
        """Generate a pattern for key matching"""
        return f"{prefix}:{pattern}"


class CacheService:
    """Redis cache service with advanced features"""
    
    def __init__(self, config: Optional[CacheConfig] = None):
        self.config = config or load_cache_config()
        self.redis_client: Optional[Union[redis.Redis, RedisCluster]] = None
        self.serializer = Serializer()
        self.metrics = CacheMetrics()
        self._connection_lock = asyncio.Lock()
        
    async def connect(self) -> bool:
        """Establish Redis connection"""
        if self.redis_client:
            return True
            
        async with self._connection_lock:
            if self.redis_client:
                return True
                
            try:
                if self.config.mode == CacheMode.CLUSTER:
                    self.redis_client = RedisCluster(
                        startup_nodes=self.config.cluster_nodes,
                        password=self.config.password,
                        socket_timeout=self.config.socket_timeout,
                        socket_connect_timeout=self.config.socket_connect_timeout,
                        decode_responses=False,  # We handle serialization ourselves
                        skip_full_coverage_check=True
                    )
                elif self.config.mode == CacheMode.SENTINEL:
                    sentinel = Sentinel(self.config.sentinel_hosts)
                    self.redis_client = sentinel.master_for(
                        self.config.sentinel_service_name,
                        password=self.config.password,
                        socket_timeout=self.config.socket_timeout,
                        socket_connect_timeout=self.config.socket_connect_timeout,
                        decode_responses=False
                    )
                else:
                    # Standalone mode
                    connection_pool = redis.ConnectionPool(
                        host=self.config.host,
                        port=self.config.port,
                        password=self.config.password,
                        db=self.config.database,
                        max_connections=self.config.max_connections,
                        socket_timeout=self.config.socket_timeout,
                        socket_connect_timeout=self.config.socket_connect_timeout,
                        socket_keepalive=self.config.socket_keepalive,
                        socket_keepalive_options=self.config.socket_keepalive_options,
                        **self.config.connection_pool_kwargs
                    )
                    
                    self.redis_client = redis.Redis(
                        connection_pool=connection_pool,
                        decode_responses=False
                    )
                
                # Test connection
                await self._ping()
                logger.info(f"Connected to Redis in {self.config.mode.value} mode")
                return True
                
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {str(e)}")
                self.metrics.record_error()
                raise CacheConnectionError(f"Redis connection failed: {str(e)}")
    
    async def _ping(self) -> bool:
        """Test Redis connection"""
        try:
            if asyncio.iscoroutinefunction(self.redis_client.ping):
                result = await self.redis_client.ping()
            else:
                result = self.redis_client.ping()
            return bool(result)
        except Exception as e:
            logger.error(f"Redis ping failed: {str(e)}")
            return False
    
    async def disconnect(self):
        """Close Redis connection"""
        if self.redis_client:
            try:
                if hasattr(self.redis_client, 'close'):
                    await self.redis_client.close()
                elif hasattr(self.redis_client, 'connection_pool'):
                    self.redis_client.connection_pool.disconnect()
                logger.info("Disconnected from Redis")
            except Exception as e:
                logger.warning(f"Error during Redis disconnect: {str(e)}")
            finally:
                self.redis_client = None
    
    async def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache"""
        start_time = time.time()
        
        try:
            if not await self.connect():
                return default
            
            if asyncio.iscoroutinefunction(self.redis_client.get):
                data = await self.redis_client.get(key)
            else:
                data = self.redis_client.get(key)
            
            response_time = time.time() - start_time
            
            if data is None:
                self.metrics.record_miss(response_time)
                return default
            
            try:
                value = self.serializer.deserialize(data)
                self.metrics.record_hit(response_time)
                return value
            except SerializationError as e:
                logger.warning(f"Failed to deserialize cached data for key '{key}': {str(e)}")
                self.metrics.record_error()
                return default
                
        except Exception as e:
            logger.error(f"Cache get error for key '{key}': {str(e)}")
            self.metrics.record_error()
            return default
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None, 
        nx: bool = False, 
        xx: bool = False
    ) -> bool:
        """Set value in cache"""
        start_time = time.time()
        
        try:
            if not await self.connect():
                return False
            
            # Use default TTL if not specified
            if ttl is None:
                ttl = self.config.default_ttl
            elif ttl > self.config.max_ttl:
                ttl = self.config.max_ttl
            
            # Serialize the data
            try:
                data = self.serializer.serialize(value, self.config.compression_threshold)
            except SerializationError as e:
                logger.error(f"Failed to serialize data for key '{key}': {str(e)}")
                self.metrics.record_error()
                return False
            
            # Set with TTL and conditions
            if asyncio.iscoroutinefunction(self.redis_client.set):
                result = await self.redis_client.set(
                    key, data, ex=ttl, nx=nx, xx=xx
                )
            else:
                result = self.redis_client.set(
                    key, data, ex=ttl, nx=nx, xx=xx
                )
            
            response_time = time.time() - start_time
            self.metrics.record_set(response_time)
            
            return bool(result)
            
        except Exception as e:
            logger.error(f"Cache set error for key '{key}': {str(e)}")
            self.metrics.record_error()
            return False
    
    async def delete(self, *keys: str) -> int:
        """Delete keys from cache"""
        start_time = time.time()
        
        try:
            if not await self.connect() or not keys:
                return 0
            
            if asyncio.iscoroutinefunction(self.redis_client.delete):
                count = await self.redis_client.delete(*keys)
            else:
                count = self.redis_client.delete(*keys)
            
            response_time = time.time() - start_time
            self.metrics.record_delete(response_time)
            
            return int(count)
            
        except Exception as e:
            logger.error(f"Cache delete error for keys {keys}: {str(e)}")
            self.metrics.record_error()
            return 0
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        try:
            if not await self.connect():
                return False
            
            if asyncio.iscoroutinefunction(self.redis_client.exists):
                result = await self.redis_client.exists(key)
            else:
                result = self.redis_client.exists(key)
            
            return bool(result)
            
        except Exception as e:
            logger.error(f"Cache exists error for key '{key}': {str(e)}")
            return False
    
    async def ttl(self, key: str) -> int:
        """Get TTL for key (-1 = no expire, -2 = doesn't exist)"""
        try:
            if not await self.connect():
                return -2
            
            if asyncio.iscoroutinefunction(self.redis_client.ttl):
                result = await self.redis_client.ttl(key)
            else:
                result = self.redis_client.ttl(key)
            
            return int(result)
            
        except Exception as e:
            logger.error(f"Cache TTL error for key '{key}': {str(e)}")
            return -2
    
    async def expire(self, key: str, ttl: int) -> bool:
        """Set TTL for existing key"""
        try:
            if not await self.connect():
                return False
            
            if asyncio.iscoroutinefunction(self.redis_client.expire):
                result = await self.redis_client.expire(key, ttl)
            else:
                result = self.redis_client.expire(key, ttl)
            
            return bool(result)
            
        except Exception as e:
            logger.error(f"Cache expire error for key '{key}': {str(e)}")
            return False
    
    async def keys(self, pattern: str = "*") -> List[str]:
        """Get keys matching pattern"""
        try:
            if not await self.connect():
                return []
            
            if asyncio.iscoroutinefunction(self.redis_client.keys):
                keys = await self.redis_client.keys(pattern)
            else:
                keys = self.redis_client.keys(pattern)
            
            # Decode keys if needed
            if keys and isinstance(keys[0], bytes):
                return [key.decode('utf-8') for key in keys]
            return list(keys)
            
        except Exception as e:
            logger.error(f"Cache keys error for pattern '{pattern}': {str(e)}")
            return []
    
    async def flush_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern"""
        keys = await self.keys(pattern)
        if keys:
            return await self.delete(*keys)
        return 0
    
    async def flush_all(self) -> bool:
        """Clear entire cache"""
        try:
            if not await self.connect():
                return False
            
            if asyncio.iscoroutinefunction(self.redis_client.flushall):
                result = await self.redis_client.flushall()
            else:
                result = self.redis_client.flushall()
            
            return bool(result)
            
        except Exception as e:
            logger.error(f"Cache flush all error: {str(e)}")
            return False
    
    async def get_info(self) -> Dict[str, Any]:
        """Get Redis server information"""
        try:
            if not await self.connect():
                return {}
            
            if asyncio.iscoroutinefunction(self.redis_client.info):
                info = await self.redis_client.info()
            else:
                info = self.redis_client.info()
            
            return dict(info)
            
        except Exception as e:
            logger.error(f"Cache info error: {str(e)}")
            return {}
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get cache performance metrics"""
        return self.metrics.to_dict()
    
    def reset_metrics(self):
        """Reset performance metrics"""
        self.metrics.reset()


# Global cache service instance
_cache_service: Optional[CacheService] = None


def get_cache_service() -> CacheService:
    """Get global cache service instance"""
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service


@asynccontextmanager
async def cache_transaction():
    """Context manager for cache operations"""
    cache = get_cache_service()
    try:
        yield cache
    except Exception as e:
        logger.error(f"Cache transaction error: {str(e)}")
        raise