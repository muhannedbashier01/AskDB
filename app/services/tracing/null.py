"""Null (no-op) tracing service for when observability is disabled."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Generator


@dataclass
class NullSpan:
    """A span that silently accepts any update."""

    def update(self, **kwargs: Any) -> None:
        pass

    def end(self) -> None:
        pass


class NullTracingService:
    """No-op tracing service — all operations are safe no-ops."""

    @contextmanager
    def trace(
        self,
        trace_id: str,
        name: str = "askdb-agent",
        user_query: str = "",
    ) -> Generator[NullSpan, None, None]:
        yield NullSpan()

    @contextmanager
    def span(
        self,
        name: str,
        *,
        span_input: Any = None,
        metadata: Any = None,
    ) -> Generator[NullSpan, None, None]:
        yield NullSpan()

    def record_generation(self, name: str, **kwargs: Any) -> None:
        pass

    def update_trace(self, **kwargs: Any) -> None:
        pass