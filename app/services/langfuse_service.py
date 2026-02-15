"""Langfuse observability service.

Owns all Langfuse concerns: client initialization, callback handler
creation, and trace flushing.  Every other module imports from here
rather than touching langfuse directly.
"""

from __future__ import annotations

import structlog

from app.core.config import get_settings

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Singleton initialisation
# ---------------------------------------------------------------------------

_langfuse_initialized: bool | None = None


def _init_langfuse_once() -> bool:
    """Initialize the Langfuse singleton client (once per process).

    The v3 Python SDK uses a singleton: we configure it here with our
    credentials so that ``CallbackHandler()`` picks them up automatically.

    Returns:
        True if initialised successfully, False otherwise.
    """
    settings = get_settings()
    if not settings.langfuse_enabled:
        return False

    try:
        from langfuse import Langfuse

        Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            base_url=settings.langfuse_base_url,
        )
        logger.info(
            "Langfuse client initialized",
            base_url=settings.langfuse_base_url,
        )
        return True
    except ImportError:
        logger.warning(
            "Langfuse is enabled but the package is not installed. pip install langfuse"
        )
        return False
    except Exception:
        logger.warning("Failed to initialize Langfuse client", exc_info=True)
        return False


def _ensure_langfuse() -> bool:
    """Lazy-initialise Langfuse. Returns True if ready."""
    global _langfuse_initialized
    if _langfuse_initialized is None:
        _langfuse_initialized = _init_langfuse_once()
    return _langfuse_initialized


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_langfuse_handler(trace_id: str, user_query: str):
    """Create a Langfuse callback handler for LangChain/LangGraph tracing.

    Args:
        trace_id: Unique trace identifier for cross-referencing with Seq logs.
        user_query: The user query (used as trace name / metadata).

    Returns:
        A Langfuse ``CallbackHandler`` instance, or ``None`` if Langfuse is
        disabled or unavailable.
    """
    if not _ensure_langfuse():
        return None

    # v3 import path
    try:
        from langfuse.langchain import CallbackHandler

        handler = CallbackHandler(
            session_id=trace_id,
            trace_name="askdb-agent",
            metadata={"trace_id": trace_id, "user_query": user_query[:200]},
        )
        logger.debug("Langfuse handler created (v3)", trace_id=trace_id)
        return handler
    except ImportError:
        pass

    # Fallback: v2 import path
    try:
        from langfuse.callback import CallbackHandler as CallbackHandlerV2

        settings = get_settings()
        handler = CallbackHandlerV2(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_base_url,
            trace_name="askdb-agent",
            session_id=trace_id,
            metadata={"trace_id": trace_id, "user_query": user_query[:200]},
        )
        logger.debug("Langfuse handler created (v2 fallback)", trace_id=trace_id)
        return handler
    except ImportError:
        logger.warning(
            "Langfuse is enabled but neither v3 nor v2 CallbackHandler could be "
            "imported. pip install langfuse"
        )
        return None
    except Exception:
        logger.warning("Failed to create Langfuse handler", exc_info=True)
        return None


def flush_langfuse() -> None:
    """Flush queued Langfuse events so they are sent before the response ends.

    Langfuse batches events in the background.  Without an explicit flush the
    HTTP response can complete before events are delivered.
    """
    try:
        from langfuse import get_client

        get_client().flush()
    except Exception as e:
        logger.debug("Langfuse flush failed (non-fatal)", error=str(e))
