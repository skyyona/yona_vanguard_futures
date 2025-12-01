import time
import asyncio
from collections import deque
from typing import Deque


class RateLimitManager:
    """Simple async rate limit manager using a sliding window.

    Usage:
        async with rate_limit_manager:
            await do_request()

    The manager keeps timestamps of recent requests and delays when the
    configured limit would be exceeded.
    """

    def __init__(self, max_requests: int = 1200, period: float = 60.0):
        # defaults approximate Binance weight limits; adjust per needs
        self.max_requests = max_requests
        self.period = period
        self._requests: Deque[float] = deque()
        self._lock = asyncio.Lock()

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        # nothing special to do on exit
        return False

    async def acquire(self) -> None:
        """Wait until a new request can be issued under rate limits."""
        async with self._lock:
            now = time.time()
            # evict old timestamps
            while self._requests and now - self._requests[0] >= self.period:
                self._requests.popleft()

            if len(self._requests) < self.max_requests:
                self._requests.append(now)
                return

            # must wait until oldest timestamp is outside the window
            oldest = self._requests[0]
            wait_for = self.period - (now - oldest) + 0.01
            await asyncio.sleep(max(wait_for, 0))

            # after wait, evict again and append
            now = time.time()
            while self._requests and now - self._requests[0] >= self.period:
                self._requests.popleft()
            self._requests.append(now)
