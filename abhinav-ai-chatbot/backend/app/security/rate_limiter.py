"""
Abhinav Group AI Chatbot — Sliding-Window Rate Limiter
In-memory, high-performance, zero-dependency rate limiter to protect against
DDoS, API flooding, chat token exhaustion, and credential brute-force.
"""
from __future__ import annotations

import os
import time
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import structlog

logger = structlog.get_logger(__name__)


class SlidingWindowRateLimiter:
    """
    Sliding window rate limiter that tracks request timestamps per client IP & endpoint category.
    """

    def __init__(self):
        # Maps key -> list of monotonic timestamps
        self._history: Dict[str, List[float]] = defaultdict(list)
        self._last_cleanup = time.monotonic()
        self._cleanup_interval = 60.0  # seconds

        # Rate limits: (max_requests, window_seconds)
        self.routes: Dict[str, Tuple[int, int]] = {
            "login": (10, 60),    # Max 10 login attempts per min (anti-brute-force)
            "chat": (30, 60),     # Max 30 messages per min (protect LLM token quota)
            "leads": (15, 60),    # Max 15 lead submissions per min (anti-CRM-spam)
            "general": (120, 60), # Max 120 requests per min for other API endpoints
        }

    def _resolve_category(self, path: str) -> Optional[str]:
        """Categorize incoming URL path into rate limiting buckets."""
        p = path.lower()
        if "/api/v1/auth/login" in p:
            return "login"
        elif "/api/v1/chat/message" in p:
            return "chat"
        elif "/api/v1/leads" in p:
            return "leads"
        elif p.startswith("/api/"):
            return "general"
        return None  # Static files, root, health check are not rate-limited

    def is_allowed(self, client_ip: str, path: str) -> Tuple[bool, int]:
        """
        Check if request from client_ip to path is permitted.
        Returns: (allowed: bool, retry_after_seconds: int)
        """
        # Global bypass check (e.g. in test suite or dev override)
        if os.environ.get("RATE_LIMIT_ENABLED", "true").lower() in ("false", "0", "no"):
            return True, 0

        category = self._resolve_category(path)
        if not category:
            return True, 0

        max_requests, window = self.routes[category]
        key = f"{client_ip}:{category}"
        now = time.monotonic()

        # Housekeeping: prune old timestamps for this key
        timestamps = self._history[key]
        cutoff = now - window
        timestamps = [t for t in timestamps if t > cutoff]
        self._history[key] = timestamps

        # Periodic global purge of empty keys every 60s
        if now - self._last_cleanup > self._cleanup_interval:
            self._purge_stale_keys(now)
            self._last_cleanup = now

        if len(timestamps) >= max_requests:
            # Exceeded limit
            oldest = timestamps[0]
            retry_after = max(1, int(oldest + window - now + 1))
            logger.warning(
                "rate_limit_exceeded",
                client_ip=client_ip,
                category=category,
                path=path,
                retry_after=retry_after,
            )
            return False, retry_after

        # Permit and record request
        timestamps.append(now)
        return True, 0

    def _purge_stale_keys(self, now: float) -> None:
        """Remove keys with no active timestamps in the longest window."""
        max_window = 120.0
        keys_to_delete = []
        for key, times in self._history.items():
            if not times or (now - times[-1] > max_window):
                keys_to_delete.append(key)
        for k in keys_to_delete:
            del self._history[k]

    def reset(self) -> None:
        """Reset all rate limiter tracking history (used in test fixtures)."""
        self._history.clear()


# Global singleton instance
rate_limiter = SlidingWindowRateLimiter()
