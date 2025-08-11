"""Centralized Cache Manager for Performance Optimization.

This module provides a unified caching system to eliminate scattered cache implementations
and improve memory efficiency across the application.
"""

import time
import threading
from typing import Any, Optional, Dict, List, Callable
from functools import wraps
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger


class CacheStrategy(Enum):
    """Cache strategy enumeration"""
    LRU = "lru"
    TTL = "ttl"
    FIFO = "fifo"


@dataclass
class CacheEntry:
    """Cache entry with metadata"""
    key: str
    value: Any
    created_at: float
    accessed_at: float
    access_count: int = 0
    ttl: Optional[float] = None
    
    def is_expired(self) -> bool:
        """Check if entry is expired based on TTL"""
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl
    
    def update_access(self):
        """Update access metadata"""
        self.accessed_at = time.time()
        self.access_count += 1


class CacheManager:
    """Centralized cache manager with multiple strategies and memory management"""
    
    def __init__(self, max_size: int = 1000, default_ttl: Optional[float] = None):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        self._stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'sets': 0
        }
        
        # Start cleanup thread
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()
        
        logger.info(f"Cache manager initialized with max_size={max_size}, default_ttl={default_ttl}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache"""
        with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self._stats['misses'] += 1
                return default
            
            if entry.is_expired():
                del self._cache[key]
                self._stats['misses'] += 1
                return default
            
            entry.update_access()
            self._stats['hits'] += 1
            return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Set value in cache"""
        with self._lock:
            # Remove expired entries first
            self._remove_expired_entries()
            
            # Check if we need to evict entries
            if len(self._cache) >= self.max_size:
                self._evict_entries()
            
            # Create new entry
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=time.time(),
                accessed_at=time.time(),
                ttl=ttl or self.default_ttl
            )
            
            self._cache[key] = entry
            self._stats['sets'] += 1
    
    def delete(self, key: str) -> bool:
        """Delete entry from cache"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def clear(self) -> None:
        """Clear all cache entries"""
        with self._lock:
            self._cache.clear()
            logger.info("Cache cleared")
    
    def _remove_expired_entries(self) -> None:
        """Remove expired entries from cache"""
        expired_keys = [
            key for key, entry in self._cache.items()
            if entry.is_expired()
        ]
        
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            logger.debug(f"Removed {len(expired_keys)} expired entries")
    
    def _evict_entries(self) -> None:
        """Evict entries based on LRU strategy"""
        if not self._cache:
            return
        
        # Sort by access time (LRU)
        sorted_entries = sorted(
            self._cache.items(),
            key=lambda x: x[1].accessed_at
        )
        
        # Remove oldest entries
        entries_to_remove = len(self._cache) - self.max_size + 1
        for i in range(entries_to_remove):
            key, _ = sorted_entries[i]
            del self._cache[key]
        
        self._stats['evictions'] += entries_to_remove
        logger.debug(f"Evicted {entries_to_remove} entries")
    
    def _cleanup_loop(self) -> None:
        """Background cleanup loop"""
        while True:
            try:
                time.sleep(60)  # Cleanup every minute
                with self._lock:
                    self._remove_expired_entries()
            except Exception as e:
                logger.error(f"Cache cleanup error: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            total_requests = self._stats['hits'] + self._stats['misses']
            hit_rate = (self._stats['hits'] / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'size': len(self._cache),
                'max_size': self.max_size,
                'hits': self._stats['hits'],
                'misses': self._stats['misses'],
                'hit_rate': f"{hit_rate:.2f}%",
                'evictions': self._stats['evictions'],
                'sets': self._stats['sets']
            }
    
    def cache_function(self, ttl: Optional[float] = None, key_prefix: str = ""):
        """Decorator to cache function results"""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Create cache key from function name and arguments
                cache_key = f"{key_prefix}:{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"
                
                # Try to get from cache
                result = self.get(cache_key)
                if result is not None:
                    return result
                
                # Execute function and cache result
                result = func(*args, **kwargs)
                self.set(cache_key, result, ttl)
                return result
            
            return wrapper
        return decorator


# Global cache manager instance
cache_manager = CacheManager(max_size=2000, default_ttl=3600)  # 1 hour default TTL


def cached(ttl: Optional[float] = None, key_prefix: str = ""):
    """Convenience decorator for caching function results"""
    return cache_manager.cache_function(ttl, key_prefix)


def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics"""
    return cache_manager.get_stats() 