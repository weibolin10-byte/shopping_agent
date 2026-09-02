"""A tiny in-memory token-bucket rate limiter, keyed per client. Good enough for the demo;
swap for Redis behind the same interface at scale."""
from __future__ import annotations

import os
import time

_UNITS = {"second": 1.0, "minute": 60.0, "hour": 3600.0}


def parse_rate(spec: str) -> tuple[int, float]:
    """'30/minute' -> (30, 60.0)."""
    count, _, unit = spec.partition("/")
    return int(count), _UNITS.get(unit.strip().lower(), 60.0)


class RateLimiter:
    # Above this many tracked clients, drop the idle ones so a wide botnet cannot grow the dict
    # without bound. A bucket refilled to full capacity is identical to a fresh one, so evicting it
    # changes no decision.
    _MAX_BUCKETS = 20_000

    def __init__(self, spec: str = "30/minute") -> None:
        self.capacity, window = parse_rate(spec)
        self.refill_per_sec = self.capacity / window if window else float(self.capacity)
        self._buckets: dict[str, tuple[float, float]] = {}

    def _current_tokens(self, tokens: float, last: float, now: float) -> float:
        return min(self.capacity, tokens + (now - last) * self.refill_per_sec)

    def _prune(self, now: float) -> None:
        # Iterate over a snapshot: FastAPI serves requests on a threadpool, so another request could
        # insert a bucket mid-iteration and raise "dict changed size during iteration".
        self._buckets = {
            k: (t, ts) for k, (t, ts) in list(self._buckets.items())
            if self._current_tokens(t, ts, now) < self.capacity}

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        if len(self._buckets) > self._MAX_BUCKETS:
            self._prune(now)
        tokens, last = self._buckets.get(key, (float(self.capacity), now))
        tokens = self._current_tokens(tokens, last, now)
        if tokens < 1.0:
            self._buckets[key] = (tokens, now)
            return False
        self._buckets[key] = (tokens - 1.0, now)
        return True


class RedisRateLimiter:
    """Shared fixed-window limiter using one atomic Redis script."""
    _ALLOW = """
local n = redis.call('INCR', KEYS[1])
if n == 1 then redis.call('EXPIRE', KEYS[1], tonumber(ARGV[1])) end
if n > tonumber(ARGV[2]) then return 0 else return 1 end
"""

    def __init__(self, client, spec: str, *, namespace: str = "shopping:rate") -> None:
        self.capacity, self.window = parse_rate(spec)
        self.client = client
        self.namespace = namespace

    def allow(self, key: str, now: float | None = None) -> bool:
        timestamp = time.time() if now is None else now
        bucket = int(timestamp // self.window) if self.window else int(timestamp)
        redis_key = f"{self.namespace}:{key}:{bucket}"
        return bool(self.client.eval(self._ALLOW, 1, redis_key, int(self.window) + 1,
                                     self.capacity))


def make_rate_limiter(spec: str, *, namespace: str = "shopping:rate"):
    backend = os.getenv("RATE_LIMIT_BACKEND", "memory").strip().lower()
    if backend == "memory":
        return RateLimiter(spec)
    if backend == "redis":
        try:
            import redis
        except ImportError as exc:
            raise RuntimeError("RATE_LIMIT_BACKEND=redis requires the production extra") from exc
        client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        return RedisRateLimiter(client, spec, namespace=namespace)
    raise ValueError(f"unknown rate-limit backend: {backend}")
