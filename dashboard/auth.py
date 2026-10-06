from __future__ import annotations

import hmac
import ipaddress
import time
from collections import defaultdict, deque
from threading import RLock

from fastapi import HTTPException, Request, status


def is_loopback_host(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class DashboardSecurity:
    def __init__(self, *, host: str, auth_token: str | None, rate_limit_per_minute: int = 120):
        self.local_only = is_loopback_host(host)
        self.auth_token = auth_token
        self.rate_limit = rate_limit_per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = RLock()

    def verify_request(self, request: Request) -> None:
        self._rate_limit(request)
        if self.local_only:
            return
        if not self.auth_token:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="remote dashboard authentication is not configured")
        supplied = request.headers.get("authorization", "")
        expected = f"Bearer {self.auth_token}"
        if not hmac.compare_digest(supplied, expected):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid dashboard credentials")

    def _rate_limit(self, request: Request) -> None:
        if self.local_only:
            return
        key = request.client.host if request.client else "unknown"
        now = time.monotonic()
        cutoff = now - 60.0
        with self._lock:
            q = self._hits[key]
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= self.rate_limit:
                raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="dashboard rate limit exceeded")
            q.append(now)
