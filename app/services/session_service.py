"""Redis-backed session service for conversational memory.

Stores recent successful exchanges per session so the LLM can resolve
follow-up references like "filter that by last week".  Redis is treated
as non-critical — if unavailable, queries still work without context.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

import structlog

from app.core.config import get_settings

logger = structlog.get_logger()


@dataclass
class Exchange:
    """A single successful query exchange in a conversation."""

    user_query: str
    sql_query: str
    row_count: int
    summary: str | None = None


class SessionService:
    """Redis-backed session store for conversation history."""

    _KEY_PREFIX = "askdb:session:"

    def __init__(self) -> None:
        settings = get_settings()
        self._ttl_seconds = settings.session_ttl_minutes * 60
        self._connected = False

        try:
            import redis

            self._redis = redis.Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=3,
            )
            self._redis.ping()
            self._connected = True
            logger.info("Redis session store connected", url=settings.redis_url)
        except Exception:
            self._redis = None
            logger.warning("Redis unavailable, sessions disabled", exc_info=True)

    @property
    def is_connected(self) -> bool:
        return self._connected

    def _key(self, session_id: str) -> str:
        return f"{self._KEY_PREFIX}{session_id}"

    def add_exchange(self, session_id: str, exchange: Exchange) -> None:
        """Append an exchange to the session and refresh TTL."""
        if not self._redis:
            return
        try:
            key = self._key(session_id)
            raw = self._redis.get(key)
            exchanges = json.loads(raw) if raw else []
            exchanges.append(asdict(exchange))
            self._redis.set(key, json.dumps(exchanges), ex=self._ttl_seconds)
        except Exception:
            logger.warning("Failed to save exchange to Redis", exc_info=True)

    def get_recent_exchanges(self, session_id: str, limit: int | None = None) -> list[Exchange]:
        """Get recent exchanges for a session."""
        if not self._redis:
            return []
        try:
            settings = get_settings()
            limit = limit or settings.conversation_memory_limit
            key = self._key(session_id)
            raw = self._redis.get(key)
            if not raw:
                return []
            exchanges = json.loads(raw)
            return [Exchange(**e) for e in exchanges[-limit:]]
        except Exception:
            logger.warning("Failed to read exchanges from Redis", exc_info=True)
            return []

    def delete_session(self, session_id: str) -> bool:
        """Delete a session. Returns True if session existed."""
        if not self._redis:
            return False
        try:
            return bool(self._redis.delete(self._key(session_id)))
        except Exception:
            logger.warning("Failed to delete session from Redis", exc_info=True)
            return False


# Module-level singleton
_session_service: SessionService | None = None


def get_session_service() -> SessionService:
    """Get or create session service singleton."""
    global _session_service
    if _session_service is None:
        _session_service = SessionService()
    return _session_service
