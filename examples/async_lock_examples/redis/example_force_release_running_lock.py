# pylint: disable=duplicate-code

import asyncio
from task_lock.async_locks import AsyncRedisLock


lock = AsyncRedisLock(lock_timeout=600)


@lock.synchronize("parameters", "resource", "resource_name")
async def func(resource, resource_name):
    print(
        "Running task for resource_id:", resource, "and resource_name:", resource_name
    )
    await asyncio.sleep(10)
    print(
        "Task completed for resource_id:", resource, "and resource_name:", resource_name
    )


async def force_release_task():
    await lock.force_release_lock(
        None, "parameters", {"resource": "resource1", "resource_name": "resource1"}
    )


async def main():
    await asyncio.gather(
        func(resource="resource1", resource_name="resource1"),
        force_release_task(),
        func(resource="resource1", resource_name="resource1"),
        force_release_task(),
        func(resource="resource1", resource_name="resource1"),
        force_release_task(),
    )
    await lock.close()


if __name__ == "__main__":
    asyncio.run(main())
