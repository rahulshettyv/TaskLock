# pylint: disable=unused-argument,too-few-public-methods,redefined-outer-name,unused-variable

from unittest.mock import MagicMock, patch

import pytest

from task_lock.locks import Lock, RedisLock
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
