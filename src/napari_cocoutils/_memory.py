"""
Memory management utilities for napari-cocoutils plugin.

This module provides utilities for efficient memory usage,
cache management, and resource cleanup.
"""

import gc
import weakref
from typing import Dict, Any, Optional, Set, Callable, TypeVar, Generic
import threading
import time
import logging
from dataclasses import dataclass
from collections import OrderedDict

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class MemoryStats:
    cache_entries: int
    cache_size_bytes: int
    last_gc_time: float
    gc_count: int


class LRUCache(Generic[T]):
    
    def __init__(self, max_size: int = 100, max_memory_mb: int = 100):
        self.max_size = max_size
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self._cache: OrderedDict[Any, T] = OrderedDict()
        self._lock = threading.RLock()
        self._memory_usage = 0
    
    def get(self, key: Any, default: Optional[T] = None) -> Optional[T]:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
            return default
    
    def put(self, key: Any, value: T, size_bytes: int = 0) -> None:
        with self._lock:
            if key in self._cache:
                self._cache.pop(key)
            
            self._cache[key] = value
            self._memory_usage += size_bytes
            
            self._enforce_limits()
    
    def _enforce_limits(self) -> None:
        # Remove oldest items to stay within limits
        while (len(self._cache) > self.max_size or 
               self._memory_usage > self.max_memory_bytes):
            if not self._cache:
                break
            
            oldest_key, oldest_value = self._cache.popitem(last=False)
            # Rough estimate for memory reduction since exact tracking is expensive
            self._memory_usage -= max(1024, self._memory_usage // len(self._cache) if self._cache else 0)
    
    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._memory_usage = 0
    
    def size(self) -> int:
        return len(self._cache)
    
    def memory_usage(self) -> int:
        return self._memory_usage


class WeakRefRegistry:
    
    def __init__(self):
        self._registry: Set[weakref.ref] = set()
        self._callbacks: Dict[weakref.ref, Callable[[], None]] = {}
        self._lock = threading.RLock()
    
    def register(self, obj: Any, cleanup_callback: Optional[Callable[[], None]] = None) -> None:
        with self._lock:
            def cleanup_wrapper(ref):
                self._registry.discard(ref)
                if ref in self._callbacks:
                    callback = self._callbacks.pop(ref)
                    try:
                        callback()
                    except Exception as e:
                        logger.warning(f"Error in cleanup callback: {e}")
            
            ref = weakref.ref(obj, cleanup_wrapper)
            self._registry.add(ref)
            
            if cleanup_callback:
                self._callbacks[ref] = cleanup_callback
    
    def cleanup_dead_refs(self) -> int:
        with self._lock:
            dead_refs = {ref for ref in self._registry if ref() is None}
            self._registry -= dead_refs
            
            for ref in dead_refs:
                self._callbacks.pop(ref, None)
            
            return len(dead_refs)
    
    def active_count(self) -> int:
        with self._lock:
            return sum(1 for ref in self._registry if ref() is not None)


class MemoryManager:
    
    def __init__(self):
        self._caches: Dict[str, LRUCache] = {}
        self._registry = WeakRefRegistry()
        self._gc_threshold = 50
        self._operation_count = 0
        self._last_gc_time = time.time()
        self._gc_count = 0
        self._lock = threading.RLock()
        
    def get_cache(self, name: str, max_size: int = 100, max_memory_mb: int = 50) -> LRUCache:
        with self._lock:
            if name not in self._caches:
                self._caches[name] = LRUCache(max_size, max_memory_mb)
            return self._caches[name]
    
    def register_object(self, obj: Any, cleanup_callback: Optional[Callable[[], None]] = None) -> None:
        self._registry.register(obj, cleanup_callback)
    
    def trigger_operation(self) -> None:
        with self._lock:
            self._operation_count += 1
            
            if self._operation_count >= self._gc_threshold:
                self._maybe_garbage_collect()
                self._operation_count = 0
    
    def _maybe_garbage_collect(self) -> None:
        dead_refs = self._registry.cleanup_dead_refs()
        
        # Only run expensive GC if we have dead refs or it's been 5+ minutes
        current_time = time.time()
        time_since_last_gc = current_time - self._last_gc_time
        
        if dead_refs > 0 or time_since_last_gc > 300:
            collected = gc.collect()
            self._last_gc_time = current_time
            self._gc_count += 1
            
            if collected > 0 or dead_refs > 0:
                logger.debug(f"GC: collected {collected} objects, {dead_refs} dead refs")
    
    def force_cleanup(self) -> None:
        with self._lock:
            for cache in self._caches.values():
                cache.clear()
            
            self._registry.cleanup_dead_refs()
            
            gc.collect()
            self._gc_count += 1
            self._last_gc_time = time.time()
            
            logger.info("Forced memory cleanup completed")
    
    def get_stats(self) -> MemoryStats:
        total_entries = sum(cache.size() for cache in self._caches.values())
        total_memory = sum(cache.memory_usage() for cache in self._caches.values())
        
        return MemoryStats(
            cache_entries=total_entries,
            cache_size_bytes=total_memory,
            last_gc_time=self._last_gc_time,
            gc_count=self._gc_count
        )
    
    def configure(self, gc_threshold: int = 50) -> None:
        self._gc_threshold = max(1, gc_threshold)
    
    def clear_cache(self, cache_name: Optional[str] = None) -> None:
        with self._lock:
            if cache_name and cache_name in self._caches:
                self._caches[cache_name].clear()
            else:
                for cache in self._caches.values():
                    cache.clear()


# Global memory manager instance
_memory_manager: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager


def memory_efficient_operation(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator to track operations for memory management."""
    def wrapper(*args, **kwargs):
        manager = get_memory_manager()
        try:
            result = func(*args, **kwargs)
            manager.trigger_operation()
            return result
        except Exception:
            # Still trigger tracking even on failure for consistent behavior
            manager.trigger_operation()
            raise
    
    return wrapper


class ResourceTracker:
    
    def __init__(self, operation_name: str = "unknown"):
        self.operation_name = operation_name
        self.start_time = 0
        
    def __enter__(self):
        self.start_time = time.time()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        manager = get_memory_manager()
        manager.trigger_operation()
        
        if duration > 1.0:
            logger.info(f"Operation '{self.operation_name}' took {duration:.2f}s")


def clear_all_caches() -> None:
    get_memory_manager().clear_cache()


def force_cleanup() -> None:
    get_memory_manager().force_cleanup()


def get_memory_stats() -> MemoryStats:
    return get_memory_manager().get_stats()


def configure_memory_management(gc_threshold: int = 50) -> None:
    get_memory_manager().configure(gc_threshold)