"""Abstract tracing protocol for observability providers."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator, Protocol, runtime_checkable


@runtime_checkable
class Span(Protocol):
    """Minimal span interface for updating trace data."""

    def update(
        self,
        *,
        output: Any = None,
        metadata: Any = None,
        level: str | None = None,
        status_message: str | None = None,
    ) -> None: ...

    def end(self) -> None: ...


@runtime_checkable
class TracingService(Protocol):
    """Protocol for distributed tracing providers.

    Implementations must provide context-manager-based trace and span
    creation, plus a generation recorder for LLM calls.  All methods
    must be safe to call even when the provider is unavailable.
    """

    @contextmanager
    def trace(
        self,
        trace_id: str,
        name: str = "askdb-agent",
        user_query: str = "",
    ) -> Generator[Span, None, None]: ...

    @contextmanager
    def span(
        self,
        name: str,
        *,
        span_input: Any = None,
        metadata: Any = None,
    ) -> Generator[Span, None, None]: ...

    def record_generation(
        self,
        name: str,
        *,
        model: str = "",
        prompt_messages: Any = None,
        response_text: Any = None,
        usage: dict[str, int] | None = None,
        metadata: Any = None,
    ) -> None: ...

    def update_trace(self, *, output: Any = None, metadata: Any = None) -> None: ...
