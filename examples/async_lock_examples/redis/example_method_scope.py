# pylint: disable=duplicate-code

import asyncio
from task_lock.async_locks import AsyncRedisLock


lock = AsyncRedisLock(lock_timeout=600)


@lock.synchronize("method")
async def func1(resource):
    print("Running task for resource_id:", resource)
    await asyncio.sleep(3)
    print("Task completed for resource_id:", resource)


@lock.synchronize("method")
async def func2(resource):
    print("Running task for resource_id:", resource)
    await asyncio.sleep(2)
    print("Task completed for resource_id:", resource)


async def main():
    await asyncio.gather(
        func1(resource="resource1"),
        func2(resource="resource1"),
        func1(resource="resource2"),
    )
    await lock.close()


if __name__ == "__main__":
    asyncio.run(main())
