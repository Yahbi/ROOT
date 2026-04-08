---
name: Redis Patterns
description: Caching strategies, pub/sub, streams, Lua scripting, eviction policies
version: "1.0.0"
author: ROOT
tags: [infrastructure, redis, caching, pub-sub, streams, lua]
platforms: [all]
---

# Redis Patterns

Use Redis effectively for caching, messaging, and real-time data processing.

## Caching Strategies

### Cache-Aside (Lazy Loading)
```python
async def get_user(user_id: str) -> dict:
    cached = await redis.get(f"user:{user_id}")
    if cached:
        return json.loads(cached)
    user = await db.fetch_user(user_id)
    await redis.set(f"user:{user_id}", json.dumps(user), ex=3600)  # TTL 1 hour
    return user
```

### Write-Through vs Write-Behind
| Strategy | Consistency | Latency | Use Case |
|----------|------------|---------|----------|
| Write-through | Strong | Higher (write to both) | User profiles, config |
| Write-behind | Eventual | Lower (async write to DB) | Analytics, counters |
| Cache-aside | Eventual | Lowest (lazy) | Read-heavy, tolerates stale |

### Cache Invalidation Patterns
- **TTL-based**: Set expiration on every key (simplest, eventual consistency)
- **Event-based**: Invalidate on write events via pub/sub or message queue
- **Version tag**: Append version to key (`user:42:v3`), increment on change
- **Two-key**: Store data key + metadata key, check metadata freshness first

## Pub/Sub

### Basic Pattern
```python
# Publisher
await redis.publish("notifications:user:42", json.dumps({"type": "alert", "msg": "..."}))

# Subscriber
pubsub = redis.pubsub()
await pubsub.subscribe("notifications:user:*")  # Pattern subscription
async for message in pubsub.listen():
    if message["type"] == "pmessage":
        handle_notification(message["data"])
```

### Pub/Sub Limitations
- Fire-and-forget: messages lost if no subscriber is listening (no persistence)
- No consumer groups or acknowledgment (use Streams for reliable messaging)
- Suitable for: real-time notifications, cache invalidation signals, live dashboards

## Redis Streams

### Reliable Message Queue
```bash
# Producer: add events to a stream
XADD orders * action "created" order_id "12345" amount "99.99"

# Consumer group: distribute processing across workers
XGROUP CREATE orders workers $ MKSTREAM
XREADGROUP GROUP workers worker-1 COUNT 10 BLOCK 5000 STREAMS orders >

# Acknowledge processed messages
XACK orders workers 1234567890-0
```

### Stream vs Pub/Sub vs List
| Feature | Streams | Pub/Sub | List (LPUSH/BRPOP) |
|---------|---------|---------|---------------------|
| Persistence | Yes | No | Yes |
| Consumer groups | Yes | No | No |
| Message replay | Yes (by ID) | No | No |
| Acknowledgment | Yes (XACK) | No | Implicit (pop) |
| Use case | Task queues, event log | Real-time broadcast | Simple job queue |

## Lua Scripting

### Atomic Operations
```lua
-- Rate limiter: atomic increment + expiry (no race condition)
-- KEYS[1] = rate limit key, ARGV[1] = limit, ARGV[2] = window seconds
local current = redis.call('INCR', KEYS[1])
if current == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[2])
end
if current > tonumber(ARGV[1]) then
    return 0  -- Rate limited
end
return 1  -- Allowed
```

### When to Use Lua Scripts
- Multiple Redis commands that must execute atomically (no WATCH/MULTI complexity)
- Conditional logic that depends on current Redis state
- Reducing round trips: batch reads + conditional writes in one call
- Keep scripts short (Redis is single-threaded; long scripts block everything)

## Eviction Policies

### Policy Selection
| Policy | Behavior | Best For |
|--------|----------|----------|
| `allkeys-lru` | Evict least recently used key | General-purpose cache |
| `volatile-lru` | Evict LRU among keys with TTL | Mixed cache + persistent data |
| `allkeys-lfu` | Evict least frequently used | Skewed access patterns (hot keys) |
| `volatile-ttl` | Evict keys closest to expiration | Time-sensitive data |
| `noeviction` | Return error on memory limit | Data must not be lost |

### Memory Configuration
```conf
maxmemory 2gb
maxmemory-policy allkeys-lfu
maxmemory-samples 10           # Higher = more accurate LRU/LFU, slight CPU cost
```

### Monitoring
- `INFO memory`: track `used_memory`, `mem_fragmentation_ratio` (>1.5 = fragmentation)
- `INFO stats`: `evicted_keys` (should be 0 or low for cache hits to matter)
- `OBJECT FREQ key`: check access frequency under LFU policy
