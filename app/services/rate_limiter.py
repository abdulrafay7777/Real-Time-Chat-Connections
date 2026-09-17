import time
from collections import defaultdict


class RateLimiter:
    """
    Token bucket rate limiter — in-memory, no external dependencies.
    Tracks request counts per key (user_id or IP) within a time window.
    """

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests   = max_requests
        self.window_seconds = window_seconds
        # key -> list of timestamps when requests were made
        self._store: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str) -> bool:
        """
        Returns True if the request is allowed, False if rate limited.
        Automatically cleans up timestamps outside the current window.
        """
        now    = time.monotonic()
        window_start = now - self.window_seconds

        # drop timestamps that are outside the window
        self._store[key] = [
            ts for ts in self._store[key]
            if ts > window_start
        ]

        if len(self._store[key]) >= self.max_requests:
            return False

        # record this request
        self._store[key].append(now)
        return True

    def remaining(self, key: str) -> int:
        """How many requests the key has left in the current window."""
        now          = time.monotonic()
        window_start = now - self.window_seconds
        recent = [ts for ts in self._store[key] if ts > window_start]
        return max(0, self.max_requests - len(recent))

    def retry_after(self, key: str) -> int:
        """Seconds until the oldest request falls outside the window."""
        now          = time.monotonic()
        window_start = now - self.window_seconds
        recent = sorted(ts for ts in self._store[key] if ts > window_start)
        if not recent:
            return 0
        return int(self.window_seconds - (now - recent[0])) + 1


# ── Singletons — one per limit type ──────────────────────────
# 20 messages per 60 seconds per user (WebSocket)
message_limiter = RateLimiter(max_requests=20, window_seconds=60)

# 5 login/register attempts per 60 seconds per IP
auth_limiter = RateLimiter(max_requests=5, window_seconds=60)
