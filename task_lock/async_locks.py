# pylint: disable=duplicate-code

from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from functools import wraps
from typing import Any, Callable, Dict, Literal, Tuple
import asyncio

import aioredis

from task_lock.utils import generate_lock_name


class AsyncLock(ABC):
    """
    Abstract base class for implementing asynchronous lock mechanisms.
    """

    @abstractmethod
    async def acquire_lock(self, lock_name: str) -> None:
        """
        Acquire a lock by name. Blocks until the lock is available.

        Args:
            lock_name (str): The name of the lock to acquire.
        """
        raise NotImplementedError

    @abstractmethod
    async def release_lock(self, lock_name: str) -> None:
        """
        Release a lock by name.

        Args:
            lock_name (str): The name of the lock to release.
        """
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        """
        Close the lock.
        """
        raise NotImplementedError

    @asynccontextmanager
    async def lock(self, lock_name: str) -> None:
        """
        Asynchronous context manager for acquiring and releasing a lock.

        Args:
            lock_name (str): The name of the lock to acquire.

        Yields:
            None
        """
        await self.acquire_lock(lock_name)
        try:
            yield
        finally:
            await self.release_lock(lock_name)

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
            async def wrapper(*args, **kwargs) -> Any:
                params = {}
                for name in param_names:
                    params[name] = kwargs.get(name, "")
                lock_name = self._generate_lock_name(func, lock_scope, params)
                async with self.lock(lock_name):
                    return await func(*args, **kwargs)

            return wrapper

        return decorator


class AsyncRedisLock(AsyncLock):
    def __init__(
        self, redis_url: str = "redis://localhost:6379", lock_timeout: int = 5
    ):
        self.client = aioredis.from_url(url=redis_url)
        self.lock_timeout = lock_timeout
        self.local_locks = {}

    async def acquire_lock(self, lock_name: str) -> None:
        """
        Acquire a lock by name. Blocks until the lock is available.

        Args:
            lock_name (str): The name of the lock to acquire.
        """
        local_lock = self.local_locks.setdefault(lock_name, asyncio.Lock())
        async with local_lock:
            backoff = 0.1
            while True:
                is_locked = await self.client.set(
                    lock_name, "1", nx=True, ex=self.lock_timeout
                )
                if is_locked:
                    return
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 2)

    async def release_lock(self, lock_name: str) -> None:
        """
        Release a lock by name.

        Args:
            lock_name (str): The name of the lock to release.
        """
        local_lock = self.local_locks.get(lock_name)
        if local_lock is None:
            raise ValueError(f"Lock {lock_name} is not acquired.")
        async with local_lock:
            lock_value = await self.client.get(lock_name)
            if lock_value == "1":
                await self.client.delete(lock_name)

    async def close(self) -> None:
        """
        Close the lock.
        """
        await self.client.close()
