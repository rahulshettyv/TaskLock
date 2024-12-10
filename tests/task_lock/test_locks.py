# pylint: disable=unused-argument,too-few-public-methods,redefined-outer-name,unused-variable

from unittest.mock import MagicMock, patch
import threading
import time

import pytest

from task_lock.locks import Lock, RedisLock, InMemoryLock
from task_lock.utils import generate_lock_name


class MockLock(Lock):
    """Mock implementation of Lock for testing the abstract base class"""

    def __init__(self):
        self.locks = set()

    def acquire_lock(self, lock_name: str) -> None:
        self.locks.add(lock_name)

    def release_lock(self, lock_name: str) -> None:
        self.locks.remove(lock_name)

    def close(self) -> None:
        self.locks.clear()


@pytest.fixture
def mock_lock():
    return MockLock()


@pytest.fixture
def redis_lock():
    with patch("redis.from_url") as mock_redis:
        mock_client = MagicMock()
        mock_redis.return_value = mock_client
        lock = RedisLock(redis_url="redis://localhost:6379", lock_timeout=5)
        yield lock, mock_client


@pytest.fixture
def in_memory_lock():
    return InMemoryLock()


def test_lock_context_manager(mock_lock):
    lock_name = "test_lock"

    with mock_lock.lock(lock_name):
        assert lock_name in mock_lock.locks

    assert lock_name not in mock_lock.locks


def test_lock_synchronize_decorator(mock_lock):
    @mock_lock.synchronize("method")
    def test_func(x, y):
        return x + y

    result = test_func(1, 2)
    assert result == 3
    assert len(mock_lock.locks) == 0  # Lock should be released after function execution


def test_lock_synchronize_with_parameters(mock_lock):
    @mock_lock.synchronize("parameters", "x", "y")
    def test_func(x, y):
        return x + y

    result = test_func(1, 2)
    assert result == 3
    assert len(mock_lock.locks) == 0


def test_redis_lock_acquire_release(redis_lock):
    lock, mock_client = redis_lock
    lock_name = "test_lock"

    # Test acquire
    mock_client.set.return_value = True
    lock.acquire_lock(lock_name)
    mock_client.set.assert_called_once_with(lock_name, "1", nx=True, ex=5)

    # Test release
    lock.release_lock(lock_name)
    mock_client.delete.assert_called_once_with(lock_name)


def test_redis_lock_acquire_with_retry(redis_lock):
    lock, mock_client = redis_lock
    lock_name = "test_lock"

    # Mock set to fail first, then succeed
    mock_client.set.side_effect = [False, True]

    lock.acquire_lock(lock_name)
    assert mock_client.set.call_count == 2
    mock_client.set.assert_called_with(lock_name, "1", nx=True, ex=5)


def test_redis_lock_close(redis_lock):
    lock, mock_client = redis_lock
    lock.close()
    mock_client.close.assert_called_once()


def test_generate_lock_name_different_scopes():
    def test_func(x, y):
        return x + y

    params = {"x": 1, "y": 2}

    # Test module scope
    module_lock = generate_lock_name(test_func, "module", params)
    assert isinstance(module_lock, str)

    # Test method scope
    method_lock = generate_lock_name(test_func, "method", params)
    assert isinstance(method_lock, str)
    assert module_lock != method_lock

    # Test parameters scope
    params_lock = generate_lock_name(test_func, "parameters", params)
    assert isinstance(params_lock, str)
    assert params_lock != method_lock


def test_invalid_lock_scope():
    def test_func(x, y):
        return x + y

    with pytest.raises(ValueError):
        generate_lock_name(test_func, "invalid_scope", {})


def test_in_memory_lock_acquire_release(in_memory_lock):
    lock_name = "test_lock"

    # Test acquire
    in_memory_lock.acquire_lock(lock_name)
    assert lock_name in in_memory_lock.locks

    # Test release
    in_memory_lock.release_lock(lock_name)
    assert lock_name not in in_memory_lock.locks


def test_in_memory_lock_context_manager(in_memory_lock):
    lock_name = "test_lock"

    with in_memory_lock.lock(lock_name):
        assert lock_name in in_memory_lock.locks

    assert lock_name not in in_memory_lock.locks


def test_in_memory_lock_multiple_locks(in_memory_lock):
    lock1 = "test_lock_1"
    lock2 = "test_lock_2"

    in_memory_lock.acquire_lock(lock1)
    in_memory_lock.acquire_lock(lock2)

    assert lock1 in in_memory_lock.locks
    assert lock2 in in_memory_lock.locks

    in_memory_lock.release_lock(lock1)
    assert lock1 not in in_memory_lock.locks
    assert lock2 in in_memory_lock.locks

    in_memory_lock.release_lock(lock2)
    assert lock2 not in in_memory_lock.locks


def test_in_memory_lock_release_nonexistent(in_memory_lock):
    # Should not raise any exception when releasing nonexistent lock
    in_memory_lock.release_lock("nonexistent_lock")


def test_in_memory_lock_close(in_memory_lock):
    lock1 = "test_lock_1"
    lock2 = "test_lock_2"

    in_memory_lock.acquire_lock(lock1)
    in_memory_lock.acquire_lock(lock2)

    in_memory_lock.close()
    # After close(), locks should be None
    assert in_memory_lock.locks is None


def test_in_memory_lock_synchronize(in_memory_lock):
    @in_memory_lock.synchronize("method")
    def test_func(x, y):
        return x + y

    result = test_func(1, 2)
    assert result == 3
    assert len(in_memory_lock.locks) == 0


def test_in_memory_lock_concurrent_access(in_memory_lock):
    lock_name = "test_lock"
    release_time = None
    acquire_time = None
    thread_started = threading.Event()

    def acquire_lock_with_delay():
        nonlocal acquire_time
        thread_started.set()
        in_memory_lock.acquire_lock(lock_name)
        acquire_time = time.time()

    # First thread acquires the lock
    in_memory_lock.acquire_lock(lock_name)

    # Start second thread that will wait for lock
    thread = threading.Thread(target=acquire_lock_with_delay)
    thread.start()

    # Wait for second thread to actually start and attempt lock acquisition
    thread_started.wait()
    # Give enough time for the second thread to hit the backoff
    time.sleep(0.2)

    # Release the lock and record the time
    release_time = time.time()
    in_memory_lock.release_lock(lock_name)

    # Wait for second thread to complete
    thread.join()

    # Verify that second thread acquired lock after first thread released it
    assert release_time <= acquire_time

    # Verify backoff behavior - acquire_time should be at least 0.1s after release
    # due to initial backoff
    assert acquire_time - release_time >= 0.1


def test_in_memory_lock_backoff_limit(in_memory_lock):
    lock_name = "test_lock"
    backoff_times = []

    def record_backoff_attempts():
        start_time = time.time()
        in_memory_lock.acquire_lock(lock_name)
        total_time = time.time() - start_time
        backoff_times.append(total_time)

    # First thread acquires the lock
    in_memory_lock.acquire_lock(lock_name)

    # Start second thread that will experience backoff
    thread = threading.Thread(target=record_backoff_attempts)
    thread.start()

    # Hold lock for enough time to see multiple backoff attempts
    time.sleep(1)
    in_memory_lock.release_lock(lock_name)

    thread.join()

    # Verify that backoff occurred and was limited
    assert len(backoff_times) == 1
    # Total wait time should be less than max backoff (2 seconds)
    assert backoff_times[0] <= 2
