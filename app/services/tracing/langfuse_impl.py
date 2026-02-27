"""Langfuse implementation of the TracingService protocol.

Uses the Langfuse v3 SDK (v3.14.5) programmatic API.  The SDK auto-creates
a trace when ``client.start_span()`` is called without an existing context.
Child spans nest via ``parent.start_span()``, and LLM generations are recorded
via ``parent.start_observation(as_type="generation")``.

Context propagation via ``contextvars`` for async safety.
"""

from __future__ import annotations

import contextvars
from contextlib import contextmanager
from typing import Any, Generator

import structlog

from app.core.config import get_settings

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROMPT_TRUNCATE_LIMIT = 500
RESPONSE_TRUNCATE_LIMIT = 1000

# ---------------------------------------------------------------------------
# Context variables — propagate trace/span across the async call stack
# ---------------------------------------------------------------------------

_current_root_span: contextvars.ContextVar = contextvars.ContextVar(
    "langfuse_root_span", default=None
)
_current_span: contextvars.ContextVar = contextvars.ContextVar(
    "langfuse_current_span", default=None
)


def _parent():
    """Return the nearest parent (current span, falling back to root)."""
    return _current_span.get() or _current_root_span.get()


# ---------------------------------------------------------------------------
# Concrete service
# ---------------------------------------------------------------------------


class LangfuseTracingService:
    """Langfuse-backed tracing service.

    In v3, ``client.start_span()`` auto-creates an underlying trace.
    Child spans are created with ``parent.start_span()``, and LLM
    generations with ``parent.start_observation(as_type="generation")``.
    """

    def __init__(self) -> None:
        self._client = None
        self._available = False
        self._init_client()

    def _init_client(self) -> None:
        settings = get_settings()

        if not settings.langfuse_enabled:
            logger.info("Langfuse tracing is disabled")
            return

        try:
            from langfuse import Langfuse

            client = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                base_url=settings.langfuse_base_url,
            )

            if client.auth_check():
                self._client = client
                self._available = True
                logger.info(
                    "Langfuse client initialized",
                    base_url=settings.langfuse_base_url,
                )
            else:
                logger.warning(
                    "Langfuse auth check failed — tracing disabled",
                    base_url=settings.langfuse_base_url,
                )

        except ImportError:
            logger.warning(
                "langfuse package not installed — tracing disabled. "
                "pip install langfuse"
            )
        except Exception:
            logger.warning("Failed to initialize Langfuse client", exc_info=True)

    @property
    def is_available(self) -> bool:
        return self._available

    # -- Root trace --------------------------------------------------------

    @contextmanager
    def trace(
        self,
        trace_id: str,
        name: str = "askdb-agent",
        user_query: str = "",
    ) -> Generator:
        """Create a root span (auto-creates a Langfuse trace underneath).

        In Langfuse v3, ``client.start_span()`` automatically creates a
        parent trace.  We store the root span in a context variable so
        child spans can nest under it.
        """
        if not self._available:
            yield None
            return

        root = self._client.start_span(
            name=name,
            input={"user_query": user_query},
            metadata={"trace_id": trace_id},
        )
        token = _current_root_span.set(root)
        try:
            yield root
        finally:
            root.end()
            _current_root_span.reset(token)
            try:
                self._client.flush()
            except Exception:
                logger.debug("Langfuse flush failed (non-fatal)", exc_info=True)

    # -- Child span --------------------------------------------------------

    @contextmanager
    def span(
        self,
        name: str,
        *,
        span_input: Any = None,
        metadata: Any = None,
    ) -> Generator:
        """Create a child span under the current parent."""
        parent = _parent()
        if parent is None:
            yield None
            return

        child = parent.start_span(name=name, input=span_input, metadata=metadata)
        token = _current_span.set(child)
        try:
            yield child
        finally:
            child.end()
            _current_span.reset(token)

    # -- LLM generation observation ----------------------------------------

    def record_generation(
        self,
        name: str = "llm-generation",
        *,
        model: str = "",
        prompt_messages: Any = None,
        response_text: Any = None,
        usage: dict[str, int] | None = None,
        metadata: Any = None,
    ) -> None:
        """Record an LLM generation under the current span/trace."""
        parent = _parent()
        if parent is None:
            return

        try:
            truncated_input = None
            if prompt_messages and isinstance(prompt_messages, list):
                truncated_input = [
                    {"role": m.get("role", ""), "content": str(m.get("content", ""))[:PROMPT_TRUNCATE_LIMIT]}
                    for m in prompt_messages
                ]
            elif prompt_messages is not None:
                truncated_input = prompt_messages

            truncated_output = (
                response_text[:RESPONSE_TRUNCATE_LIMIT]
                if isinstance(response_text, str)
                else response_text
            )

            gen = parent.start_observation(
                name=name,
                as_type="generation",
                model=model,
                input=truncated_input,
                output=truncated_output,
                usage_details=usage,
                metadata=metadata,
            )
            gen.end()
        except Exception:
            logger.debug(
                "Failed to record Langfuse generation (non-fatal)", exc_info=True
            )

    # -- Trace update ------------------------------------------------------

    def update_trace(self, *, output: Any = None, metadata: Any = None) -> None:
        """Update the root trace with final output/metadata.

        Uses ``update_trace()`` on the root span, which propagates the
        update to the underlying Langfuse trace object.
        """
        root = _current_root_span.get()
        if root is None:
            return

        try:
            root.update_trace(output=output, metadata=metadata)
        except Exception:
            logger.debug("Failed to update Langfuse trace (non-fatal)", exc_info=True)
