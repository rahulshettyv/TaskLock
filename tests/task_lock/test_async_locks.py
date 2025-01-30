from unittest.mock import AsyncMock, patch
from typing import Any, Callable, Dict, Literal
import asyncio

import pytest

from task_lock.async_locks import AsyncLock, AsyncRedisLock

pytestmark = pytest.mark.asyncio


class MockAsyncLock(AsyncLock):
    """Mock implementation of AsyncLock for testing the abstract base class"""

    def __init__(self):
        self.locks = set()

    async def acquire_lock(self, lock_name: str) -> None:
        self.locks.add(lock_name)

    async def release_lock(self, lock_name: str) -> None:
        self.locks.remove(lock_name)

    async def force_release_lock(
        self,
        func: Callable | None,
        lock_scope: Literal["module", "method", "parameters"],
        params: Dict[str, Any],
    ) -> None:
        self.locks.discard(lock_name)

    async def close(self) -> None:
        self.locks.clear()


@pytest.fixture
def mock_async_lock():
    return MockAsyncLock()


class MockRedisClient:
    def __init__(self):
        self.client = AsyncMock()
        self.client.set.return_value = True
        self.client.get.return_value = b"1"

    async def from_url(self, *args, **kwargs):
        return self.client


@pytest.fixture
def redis_client():
    return MockRedisClient().client


@pytest.fixture
async def redis_lock_fixture(redis_client):
    with patch("redis.asyncio.from_url", return_value=redis_client):
        lock = AsyncRedisLock(redis_url="redis://localhost:6379", lock_timeout=5)
        return lock, redis_client


async def test_async_lock_context_manager(mock_async_lock):
    lock_name = "test_lock"

    async with mock_async_lock.lock(lock_name):
        assert lock_name in mock_async_lock.locks

    assert lock_name not in mock_async_lock.locks


async def test_async_lock_synchronize_decorator(mock_async_lock):
    @mock_async_lock.synchronize("method")
    async def test_func(x, y):
        return x + y

    result = await test_func(1, 2)
    assert result == 3
    assert (
        len(mock_async_lock.locks) == 0
    )  # Lock should be released after function execution


async def test_async_lock_synchronize_with_parameters(mock_async_lock):
    @mock_async_lock.synchronize("parameters", "x", "y")
    async def test_func(x, y):
        return x + y

    result = await test_func(1, 2)
    assert result == 3
    assert len(mock_async_lock.locks) == 0


async def test_redis_lock_acquire_release(redis_lock_fixture):
    lock, mock_client = await redis_lock_fixture
    lock_name = "test_lock"

    # Test acquire
    await lock.acquire_lock(lock_name)
    mock_client.set.assert_called_once_with(lock_name, "1", nx=True, ex=5)

    # Test release
    await lock.release_lock(lock_name)
    mock_client.delete.assert_called_once_with(lock_name)
    await lock.close()


async def test_redis_lock_acquire_with_retry(redis_lock_fixture):
    lock, mock_client = await redis_lock_fixture
    lock_name = "test_lock"

    # Mock set to fail first, then succeed
    mock_client.set.side_effect = [False, True]

    await lock.acquire_lock(lock_name)
    assert mock_client.set.call_count == 2
    mock_client.set.assert_called_with(lock_name, "1", nx=True, ex=5)
    await lock.close()


async def test_redis_lock_release_expired(redis_lock_fixture):
    lock, mock_client = await redis_lock_fixture
    lock_name = "test_lock"

    # Acquire the lock first
    await lock.acquire_lock(lock_name)

    # Simulate lock expiration (get returns None)
    mock_client.get.return_value = None
    await lock.release_lock(lock_name)

    # Delete should not be called if lock is expired
    mock_client.delete.assert_not_called()
    await lock.close()


async def test_redis_lock_close(redis_lock_fixture):
    lock, mock_client = await redis_lock_fixture
    await lock.close()
    mock_client.close.assert_called_once()


async def test_concurrent_locks(redis_lock_fixture):
    """Test that multiple coroutines can acquire different locks concurrently"""
    lock, mock_client = await redis_lock_fixture

    async def task(lock_name: str, sleep_time: float):
        async with lock.lock(lock_name):
            await asyncio.sleep(sleep_time)
            return lock_name

    # Create two tasks with different lock names
    task1 = asyncio.create_task(task("lock1", 0.1))
    task2 = asyncio.create_task(task("lock2", 0.1))

    # Both tasks should complete without blocking each other
    results = await asyncio.gather(task1, task2)
    assert set(results) == {"lock1", "lock2"}
    await lock.close()


async def test_lock_contention(redis_lock_fixture):
    """Test that multiple coroutines properly contend for the same lock"""
    lock, mock_client = await redis_lock_fixture
    mock_client.set.side_effect = [True] * 10  # Allow all lock attempts
    execution_order = []

    async def task(task_id: int):
        async with lock.lock("shared_lock"):
            execution_order.append(task_id)
            await asyncio.sleep(0.1)  # Simulate some work

    # Create multiple tasks trying to acquire the same lock
    tasks = [asyncio.create_task(task(i)) for i in range(10)]
    await asyncio.gather(*tasks)

    # Tasks should execute sequentially
    assert len(execution_order) == 10
    assert execution_order == sorted(execution_order)
    await lock.close()
