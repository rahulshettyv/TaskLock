# pylint: disable=duplicate-code

from abc import ABC, abstractmethod
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Dict, Literal, Tuple
import time

import redis

from task_lock.utils import generate_lock_name


class Lock(ABC):
    """
    Abstract base class for implementing lock mechanisms.
    """

    @abstractmethod
    def acquire_lock(self, lock_name: str) -> None:
        """
        Acquire a lock by name. Blocks until the lock is available.

        Args:
            lock_name (str): The name of the lock to acquire.
        """
        raise NotImplementedError

    @abstractmethod
    def release_lock(self, lock_name: str) -> None:
        """
        Release a lock by name.

        Args:
            lock_name (str): The name of the lock to release.
        """
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """
        Close the lock.
        """
        raise NotImplementedError

    @contextmanager
    def lock(self, lock_name: str) -> None:
        """
        Context manager for acquiring and releasing a lock.

        Args:
            lock_name (str): The name of the lock to acquire.

        Yields:
            None
        """
        self.acquire_lock(lock_name)
        try:
            yield
        finally:
            self.release_lock(lock_name)

    def _generate_lock_name(
        self,
        func: Callable,
        lock_scope: Literal["module", "method", "parameters"],
        params: Dict[str, Any],
    ) -> str:
        """
        Generate a lock name based on the function and lock scope.

        Args:
            func (Callable): The function to generate a lock name for.
            lock_scope (Literal['module', 'method', 'parameters']): The scope of the lock.
            params (Dict[str, Any]): The parameters of the function.

        Returns:
            str: The generated lock name.
        """
        return generate_lock_name(func, lock_scope, params)

    def synchronize(
        self,
        lock_scope: Literal["module", "method", "parameters"],
        *param_names: Tuple[str],
    ) -> Callable:
        """
        Decorator for synchronizing function with lock optionally on multiple parameter values.

        Args:
            *param_names (Tuple[str]): Variable-length tuple of parameter names to synchronize on.

        Returns:
            Callable: The decorated function.
        """

        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs) -> Any:
                params = {}
                for name in param_names:
                    params[name] = kwargs.get(name, "")
                lock_name = self._generate_lock_name(func, lock_scope, params)
                with self.lock(lock_name):
                    return func(*args, **kwargs)

            return wrapper

        return decorator


class RedisLock(Lock):
    """
    Redis-based lock implementation using the redis-py library.
    """

    def __init__(
        self, redis_url: str = "redis://localhost:6379", lock_timeout: int = 5
    ) -> None:
        self.client = redis.from_url(redis_url)
        self.lock_timeout = lock_timeout

    def acquire_lock(self, lock_name: str) -> None:
        """
        Acquire a lock by name. Blocks until the lock is available.

        Args:
            lock_name (str): The name of the lock to acquire.
        """
        backoff = 0.1
        while True:
            if self.client.set(lock_name, "1", nx=True, ex=self.lock_timeout):
                return
            time.sleep(backoff)
            backoff = min(backoff * 2, 2)

    def release_lock(self, lock_name: str) -> None:
        """
        Release a lock by name.

        Args:
            lock_name (str): The name of the lock to release.
        """
        self.client.delete(lock_name)

    def close(self) -> None:
        """
        Close the lock.
        """
        self.client.close()


class InMemoryLock(Lock):
    def __init__(self):
        self.locks = set()

    def acquire_lock(self, lock_name: str) -> None:
        """
        Acquire a lock by name. Blocks until the lock is available.

        Args:
            lock_name (str): The name of the lock to acquire.
        """
        backoff = 0.1
        while lock_name in self.locks:
            time.sleep(backoff)
            backoff = min(backoff * 2, 2)
        self.locks.add(lock_name)

    def release_lock(self, lock_name: str) -> None:
        """
        Release a lock by name.

        Args:
            lock_name (str): The name of the lock to release.
        """
        self.locks.discard(lock_name)

    def close(self) -> None:
        """
        Close the lock.
        """
        self.locks.clear()
        self.locks = None
