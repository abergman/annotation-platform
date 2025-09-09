"""
Redis Cache Configuration and Management

Comprehensive Redis configuration for the annotation system with support for:
- Connection pooling and clustering
- TTL management and cache strategies
- Distributed caching for scalability
- Performance monitoring and metrics
"""

import os
import json
import logging
from typing import Optional, Dict, Any, List, Union
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum

import redis
from redis.sentinel import Sentinel
from redis.cluster import RedisCluster
from redis.exceptions import (
    RedisError, 
    ConnectionError as RedisConnectionError,
    TimeoutError as RedisTimeoutError
)

from ..utils.logger import get_logger


logger = get_logger(__name__)


class CacheStrategy(Enum):
    """Cache implementation strategies"""
    CACHE_ASIDE = "cache_aside"
    WRITE_THROUGH = "write_through" 
    WRITE_BEHIND = "write_behind"
    REFRESH_AHEAD = "refresh_ahead"


class CacheMode(Enum):
    """Redis deployment modes"""
    STANDALONE = "standalone"
    SENTINEL = "sentinel"
    CLUSTER = "cluster"


@dataclass
class CacheConfig:
    """Redis cache configuration"""
    # Connection settings
    host: str = "localhost"
    port: int = 6379
    password: Optional[str] = None
    database: int = 0
    
    # Connection pooling
    max_connections: int = 50
    connection_pool_kwargs: Dict[str, Any] = None
    
    # Timeout settings
    socket_timeout: float = 5.0
    socket_connect_timeout: float = 5.0
    socket_keepalive: bool = True
    socket_keepalive_options: Dict = None
    
    # Retry settings
    retry_on_timeout: bool = True
    retry_on_error: List[type] = None
    health_check_interval: int = 30
    
    # Cache behavior
    default_ttl: int = 3600  # 1 hour
    max_ttl: int = 86400     # 24 hours
    compression_threshold: int = 1024  # bytes
    
    # Performance
    decode_responses: bool = True
    encoding: str = "utf-8"
    
    # Clustering/Sentinel
    mode: CacheMode = CacheMode.STANDALONE
    sentinel_hosts: List[tuple] = None
    sentinel_service_name: str = "mymaster"
    cluster_nodes: List[Dict[str, Union[str, int]]] = None
    
    def __post_init__(self):
        if self.connection_pool_kwargs is None:
            self.connection_pool_kwargs = {}
        
        if self.retry_on_error is None:
            self.retry_on_error = [RedisConnectionError, RedisTimeoutError]
            
        if self.socket_keepalive_options is None:
            self.socket_keepalive_options = {}


class CacheMetrics:
    """Cache performance metrics collector"""
    
    def __init__(self):
        self.hits = 0
        self.misses = 0
        self.sets = 0
        self.deletes = 0
        self.errors = 0
        self.total_time = 0.0
        self.start_time = datetime.now()
        
    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0
        
    @property
    def miss_rate(self) -> float:
        return 100.0 - self.hit_rate
        
    @property
    def avg_response_time(self) -> float:
        total_ops = self.hits + self.misses + self.sets + self.deletes
        return (self.total_time / total_ops) if total_ops > 0 else 0.0
        
    def record_hit(self, response_time: float = 0.0):
        self.hits += 1
        self.total_time += response_time
        
    def record_miss(self, response_time: float = 0.0):
        self.misses += 1
        self.total_time += response_time
        
    def record_set(self, response_time: float = 0.0):
        self.sets += 1
        self.total_time += response_time
        
    def record_delete(self, response_time: float = 0.0):
        self.deletes += 1
        self.total_time += response_time
        
    def record_error(self):
        self.errors += 1
        
    def reset(self):
        """Reset all metrics"""
        self.__init__()
        
    def to_dict(self) -> Dict[str, Any]:
        uptime = (datetime.now() - self.start_time).total_seconds()
        return {
            "hits": self.hits,
            "misses": self.misses,
            "sets": self.sets,
            "deletes": self.deletes,
            "errors": self.errors,
            "hit_rate": round(self.hit_rate, 2),
            "miss_rate": round(self.miss_rate, 2),
            "avg_response_time": round(self.avg_response_time * 1000, 2),  # ms
            "total_operations": self.hits + self.misses + self.sets + self.deletes,
            "uptime_seconds": round(uptime, 2)
        }


class CacheConfigManager:
    """Manages cache configuration from environment and settings"""
    
    @staticmethod
    def from_environment() -> CacheConfig:
        """Load cache configuration from environment variables"""
        config = CacheConfig()
        
        # Basic connection
        config.host = os.getenv("REDIS_HOST", config.host)
        config.port = int(os.getenv("REDIS_PORT", config.port))
        config.password = os.getenv("REDIS_PASSWORD")
        config.database = int(os.getenv("REDIS_DATABASE", config.database))
        
        # Connection pooling
        config.max_connections = int(os.getenv("REDIS_MAX_CONNECTIONS", config.max_connections))
        
        # Timeouts
        config.socket_timeout = float(os.getenv("REDIS_SOCKET_TIMEOUT", config.socket_timeout))
        config.socket_connect_timeout = float(os.getenv("REDIS_SOCKET_CONNECT_TIMEOUT", config.socket_connect_timeout))
        
        # TTL settings
        config.default_ttl = int(os.getenv("REDIS_DEFAULT_TTL", config.default_ttl))
        config.max_ttl = int(os.getenv("REDIS_MAX_TTL", config.max_ttl))
        
        # Performance
        config.compression_threshold = int(os.getenv("REDIS_COMPRESSION_THRESHOLD", config.compression_threshold))
        
        # Mode configuration
        mode_str = os.getenv("REDIS_MODE", "standalone").lower()
        if mode_str == "sentinel":
            config.mode = CacheMode.SENTINEL
            sentinel_hosts_str = os.getenv("REDIS_SENTINEL_HOSTS")
            if sentinel_hosts_str:
                config.sentinel_hosts = [
                    tuple(host.split(":")) for host in sentinel_hosts_str.split(",")
                ]
            config.sentinel_service_name = os.getenv("REDIS_SENTINEL_SERVICE", config.sentinel_service_name)
            
        elif mode_str == "cluster":
            config.mode = CacheMode.CLUSTER
            cluster_nodes_str = os.getenv("REDIS_CLUSTER_NODES")
            if cluster_nodes_str:
                config.cluster_nodes = [
                    {"host": parts[0], "port": int(parts[1])}
                    for node in cluster_nodes_str.split(",")
                    for parts in [node.split(":")]
                ]
        
        return config
    
    @staticmethod
    def validate_config(config: CacheConfig) -> List[str]:
        """Validate cache configuration and return list of issues"""
        issues = []
        
        if config.port < 1 or config.port > 65535:
            issues.append(f"Invalid Redis port: {config.port}")
            
        if config.database < 0 or config.database > 15:
            issues.append(f"Invalid Redis database: {config.database}")
            
        if config.max_connections < 1:
            issues.append(f"Invalid max_connections: {config.max_connections}")
            
        if config.socket_timeout <= 0:
            issues.append(f"Invalid socket_timeout: {config.socket_timeout}")
            
        if config.default_ttl <= 0:
            issues.append(f"Invalid default_ttl: {config.default_ttl}")
            
        if config.max_ttl < config.default_ttl:
            issues.append("max_ttl cannot be less than default_ttl")
            
        if config.mode == CacheMode.SENTINEL and not config.sentinel_hosts:
            issues.append("Sentinel mode requires sentinel_hosts configuration")
            
        if config.mode == CacheMode.CLUSTER and not config.cluster_nodes:
            issues.append("Cluster mode requires cluster_nodes configuration")
            
        return issues
    
    @staticmethod
    def get_redis_url(config: CacheConfig) -> str:
        """Generate Redis URL from configuration"""
        if config.mode == CacheMode.CLUSTER:
            # Cluster URLs are handled differently
            return None
            
        password_part = f":{config.password}@" if config.password else ""
        return f"redis://{password_part}{config.host}:{config.port}/{config.database}"


def load_cache_config() -> CacheConfig:
    """Load and validate cache configuration"""
    config = CacheConfigManager.from_environment()
    
    # Validate configuration
    issues = CacheConfigManager.validate_config(config)
    if issues:
        logger.warning("Cache configuration issues found:")
        for issue in issues:
            logger.warning(f"  - {issue}")
    
    logger.info(f"Cache configuration loaded: {config.mode.value} mode at {config.host}:{config.port}")
    return config