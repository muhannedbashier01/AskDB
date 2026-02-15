"""Langfuse observability service.

Uses the Langfuse v3 programmatic API (spans, observations) to trace
the full agent lifecycle: graph execution, node steps, and LLM calls.

Trace context is propagated via ``contextvars`` so node functions and
the LLM service can create child spans without passing extra arguments.
"""

from __future__ import annotations

import contextvars
import time
from contextlib import contextmanager
from typing import Any, Generator

import structlog

from app.core.config import get_settings

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Singleton client
# ---------------------------------------------------------------------------

_langfuse_client = None
_langfuse_checked: bool = False


def _get_client():
    """Return the Langfuse client singleton, or None if disabled/unavailable."""
    global _langfuse_client, _langfuse_checked

    if _langfuse_checked:
        return _langfuse_client

    _langfuse_checked = True
    settings = get_settings()

    if not settings.langfuse_enabled:
        logger.info("Langfuse tracing is disabled")
        return None

    try:
        from langfuse import Langfuse

        _langfuse_client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            base_url=settings.langfuse_base_url,
        )

        # Verify connectivity
        if _langfuse_client.auth_check():
            logger.info(
                "Langfuse client initialized",
                base_url=settings.langfuse_base_url,
            )
        else:
            logger.warning(
                "Langfuse auth check failed — tracing disabled",
                base_url=settings.langfuse_base_url,
            )
            _langfuse_client = None

    except ImportError:
        logger.warning(
            "langfuse package is not installed — tracing disabled. "
            "pip install langfuse"
        )
    except Exception:
        logger.warning("Failed to initialize Langfuse client", exc_info=True)

    return _langfuse_client


# ---------------------------------------------------------------------------
# Context variables — carry the current trace / span across call stack
# ---------------------------------------------------------------------------

_current_root_span: contextvars.ContextVar = contextvars.ContextVar(
    "langfuse_root_span", default=None
)
_current_span: contextvars.ContextVar = contextvars.ContextVar(
    "langfuse_current_span", default=None
)


def _parent():
    """Return the nearest parent (current span or root span)."""
    return _current_span.get() or _current_root_span.get()


# ---------------------------------------------------------------------------
# Public API — used by graph.py, nodes.py, llm_service.py
# ---------------------------------------------------------------------------


@contextmanager
def langfuse_trace(
    trace_id: str,
    name: str = "askdb-agent",
    user_query: str = "",
) -> Generator:
    """Context manager that wraps an entire agent invocation in a trace.

    Usage in ``graph.py``::

        with langfuse_trace(trace_id, user_query=query) as trace:
            final_state = await graph.ainvoke(initial_state)

    Args:
        trace_id: Unique identifier for cross-referencing with Seq logs.
        name: Trace name shown in the Langfuse UI.
        user_query: The user query (stored as trace input).
    """
    client = _get_client()
    if client is None:
        yield None
        return

    root = client.start_span(
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
            client.flush()
        except Exception:
            logger.debug("Langfuse flush after trace failed (non-fatal)", exc_info=True)


@contextmanager
def langfuse_span(
    name: str,
    *,
    input: Any = None,
    metadata: Any = None,
) -> Generator:
    """Context manager for a child span (graph node step).

    Usage in ``nodes.py``::

        with langfuse_span("generate_sql", input={"attempt": 1}):
            ...

    The span is automatically nested under the current parent.
    """
    parent = _parent()
    if parent is None:
        yield None
        return

    span = parent.start_span(name=name, input=input, metadata=metadata)
    token = _current_span.set(span)
    try:
        yield span
    finally:
        span.end()
        _current_span.reset(token)


def langfuse_generation(
    name: str,
    *,
    model: str = "",
    input: Any = None,
    output: Any = None,
    usage: dict[str, int] | None = None,
    metadata: Any = None,
):
    """Record an LLM generation observation under the current span.

    Call *after* the LLM call completes so that ``output`` is available.

    Args:
        name: Observation name (e.g. ``"generate_sql"``).
        model: Model identifier.
        input: Prompt / messages sent to the LLM.
        output: Raw LLM response text.
        usage: Token usage dict, e.g. ``{"input": 150, "output": 42}``.
        metadata: Arbitrary metadata dict.
    """
    parent = _parent()
    if parent is None:
        return

    try:
        obs = parent.start_observation(
            name=name,
            as_type="generation",
            model=model,
            input=input,
            output=output,
            usage_details=usage,
            metadata=metadata,
        )
        obs.end()
    except Exception:
        logger.debug("Failed to record Langfuse generation (non-fatal)", exc_info=True)


def langfuse_update_trace(*, output: Any = None, metadata: Any = None):
    """Update the root trace span with final output / metadata."""
    root = _current_root_span.get()
    if root is None:
        return

    try:
        kwargs: dict[str, Any] = {}
        if output is not None:
            kwargs["output"] = output
        if metadata is not None:
            kwargs["metadata"] = metadata
        if kwargs:
            root.update(**kwargs)
    except Exception:
        logger.debug("Failed to update Langfuse trace (non-fatal)", exc_info=True)
