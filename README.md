# TaskLock
TaskLock is a Python library designed for efficient distributed locking in asynchronous and synchronous systems. It provides seamless integration with Redis (and other lock mechanisms), allowing you to synchronize tasks and prevent race conditions across processes, threads, or distributed nodes.

With TaskLock, you can:

- Lock by Parameters: Dynamically create locks based on function parameters (e.g., teamspace names, resource IDs).
- Support Multiple Backends: Extendable to support Redis, RabbitMQ, and more.
- Fine-Grained Locks: Create locks scoped by module, method, or parameters to suit your use case.
- Asynchronous Compatibility: Fully supports async workflows for modern Python applications.
- Exponential Backoff: Retry lock acquisition with smart exponential backoff to avoid server overloads.

## Features

- Dynamic lock generation based on custom parameters or Pydantic models.
- Easy-to-use decorator for synchronizing critical sections.
- Automatic lock expiration to avoid deadlocks.
- Pluggable architecture for supporting custom lock providers.
- Lightweight and highly scalable for distributed systems.

## Use Cases

- Synchronize access to shared resources across multiple processes.
- Manage task queues in distributed systems.
- Prevent duplicate execution of tasks in serverless environments or microservices.

## Supported Locks
TaskLock is designed to be extensible and supports various locking backends out of the box. Here's the list of currently supported locks:

### Redis Lock
A robust and high-performance lock implementation using Redis. Ideal for distributed systems where tasks need synchronized access to shared resources.

### In-Memory Lock (Coming Soon)
A lightweight lock for single-machine setups, perfect for testing and local development environments.

### RabbitMQ Lock (Coming Soon)
Distributed locking using RabbitMQ message queues, suitable for task-based systems.

### Custom Locks
TaskLock provides a flexible base class (BaseLock) to easily implement your own lock mechanism. Whether it's a database-backed lock, file-based lock, or a custom queue, you can extend TaskLock to meet your specific needs.

## Getting Started

### Install TaskLock

```bash
pip install tasklock
```

### Example Usage

```
from tasklock import RedisLock # Import other types of Locks as required

lock = RedisLock(lock_timeout=10)

@lock.synchronized("teamspace_name")
def critical_section(teamspace_name):
    print(f"Processing {teamspace_name}")
```

## Why TaskLock?
TaskLock is built for modern distributed systems, offering a robust and developer-friendly methods to ensure reliable task execution with minimal overhead.

Contribute, star, and follow the project for updates! 🚀
