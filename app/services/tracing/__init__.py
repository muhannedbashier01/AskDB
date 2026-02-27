"""Tracing service package — provider-agnostic observability."""

from app.services.tracing.factory import get_tracing_service
from app.services.tracing.protocol import Span, TracingService

__all__ = ["Span", "TracingService", "get_tracing_service"]
