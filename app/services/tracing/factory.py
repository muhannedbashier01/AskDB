"""Factory for the tracing service singleton."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from app.core.config import get_settings

if TYPE_CHECKING:
    from app.services.tracing.protocol import TracingService

logger = structlog.get_logger()

_tracing_service: TracingService | None = None


def get_tracing_service() -> TracingService:
    """Get or create the tracing service singleton.

    Returns ``LangfuseTracingService`` when enabled and available,
    otherwise ``NullTracingService``.
    """
    global _tracing_service
    if _tracing_service is not None:
        return _tracing_service

    settings = get_settings()

    if settings.langfuse_enabled:
        from app.services.tracing.langfuse_impl import LangfuseTracingService

        service = LangfuseTracingService()
        if service.is_available:
            _tracing_service = service
            return _tracing_service

    from app.services.tracing.null import NullTracingService

    _tracing_service = NullTracingService()
    return _tracing_service
