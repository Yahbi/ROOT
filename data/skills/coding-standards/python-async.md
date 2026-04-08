---
name: Python Async Patterns
description: async/await patterns, event loops, concurrency, and common async pitfalls
version: "1.0.0"
author: ROOT
tags: [coding-standards, python, async, concurrency, event-loop]
platforms: [all]
---

# Python Async Patterns

Write correct and efficient asynchronous Python code using asyncio.

## When to Use Async

### Good Use Cases
- I/O-bound operations: HTTP requests, database queries, file I/O
- Handling many concurrent connections (web servers, chat, websockets)
- Waiting for multiple external services simultaneously
- Background tasks that need to run alongside request handling

### Bad Use Cases
- CPU-bound work (use multiprocessing instead)
- Simple scripts with sequential logic (adds complexity for no benefit)
- When all your dependencies are synchronous (wrapping sync in async gains nothing)

## Core Patterns

### Basic async/await
```python
async def fetch_data(url: str) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()
```

### Concurrent Execution with gather
```python
# Run multiple coroutines concurrently
results = await asyncio.gather(
    fetch_data("https://api1.example.com"),
    fetch_data("https://api2.example.com"),
    fetch_data("https://api3.example.com"),
    return_exceptions=True  # Don't fail all if one fails
)
```

### TaskGroup (Python 3.11+, preferred over gather)
```python
async with asyncio.TaskGroup() as tg:
    task1 = tg.create_task(fetch_data(url1))
    task2 = tg.create_task(fetch_data(url2))
# Both tasks complete or all are cancelled on error
results = [task1.result(), task2.result()]
```

### Timeout Control
```python
async with asyncio.timeout(30):  # Python 3.11+
    result = await long_running_operation()
# Raises TimeoutError if exceeds 30 seconds
```

## Concurrency Control

### Semaphore (limit concurrent operations)
```python
semaphore = asyncio.Semaphore(10)  # Max 10 concurrent

async def rate_limited_fetch(url: str):
    async with semaphore:
        return await fetch_data(url)
```

### Queue (producer-consumer pattern)
```python
queue = asyncio.Queue(maxsize=100)

async def producer():
    for item in items:
        await queue.put(item)  # Blocks if queue is full

async def consumer():
    while True:
        item = await queue.get()
        await process(item)
        queue.task_done()
```

## Common Pitfalls

### Blocking the Event Loop
- Never call synchronous blocking functions in async code (time.sleep, requests.get)
- Use `await asyncio.sleep()` instead of `time.sleep()`
- Use `aiohttp` instead of `requests`
- For unavoidable sync code: `await asyncio.to_thread(sync_function)`

### Fire-and-Forget Tasks
- `asyncio.create_task(coro())` — the task runs but exceptions are silently swallowed
- Always store task references and handle exceptions
- Use background task sets: `background_tasks.add(task); task.add_done_callback(background_tasks.discard)`

### Async Context Managers
- Database connections, HTTP sessions, file handles should use `async with`
- Ensures proper cleanup even on exceptions
- Don't create connections per-request — use connection pools

## Testing Async Code

```python
import pytest

@pytest.mark.asyncio
async def test_fetch_data():
    result = await fetch_data("https://api.example.com/test")
    assert result["status"] == "ok"
```

- Use `pytest-asyncio` for async test support
- Mock external services with `aioresponses` (for aiohttp) or `respx` (for httpx)
- Test timeout behavior: verify your code handles TimeoutError gracefully
