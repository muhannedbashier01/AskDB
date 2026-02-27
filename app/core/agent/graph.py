"""LangGraph workflow definition for the SQL agent."""

from __future__ import annotations

from typing import Any, Callable

import structlog
from langgraph.graph import END, StateGraph

from app.core.agent.nodes import (
    execute_sql,
    format_error,
    format_response,
    generate_sql,
    handle_error,
    route_after_execution,
    validate_sql,
    route_after_validation,
)
from app.core.agent.state import AgentState, create_initial_state
from app.core.prompts.sql_agent import CONVERSATION_CONTEXT_BLOCK
from app.services.session_service import Exchange, get_session_service
from app.services.tracing import get_tracing_service

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Traced node wrapper — applies observability at graph construction time
# ---------------------------------------------------------------------------


def _traced_node(
    node_fn: Callable[[AgentState], dict[str, Any]],
    *,
    input_extractor: Callable[[AgentState], dict[str, Any]] | None = None,
    output_extractor: Callable[[dict[str, Any], AgentState], dict[str, Any]] | None = None,
) -> Callable[[AgentState], dict[str, Any]]:
    """Wrap a node function with tracing.

    The node itself remains pure — no tracing imports or awareness.
    Tracing metadata (what to capture as input/output) is defined here,
    co-located with the graph wiring.

    Args:
        node_fn: The original node function ``(state) -> dict``.
        input_extractor: Optional ``(state) -> dict`` for span input.
        output_extractor: Optional ``(result, state) -> dict`` for span output.
    """
    node_name = node_fn.__name__

    def wrapper(state: AgentState) -> dict[str, Any]:
        tracing = get_tracing_service()
        span_input = input_extractor(state) if input_extractor else None

        with tracing.span(node_name, span_input=span_input) as span:
            result = node_fn(state)
            if output_extractor:
                span.update(output=output_extractor(result, state))
            return result

    wrapper.__name__ = node_name
    wrapper.__qualname__ = node_fn.__qualname__
    return wrapper


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------


def create_agent_graph() -> StateGraph:
    """Create the LangGraph state machine for the SQL agent.

    The graph follows this flow:
    START → generate_sql → validate_sql → [route_after_validation]
                                              ↓
                                   valid? → execute_sql → [route_after_execution]
                                              ↓                    ↓
                                   invalid? → handle_error    success? → format_response → END
                                                                   ↓
                                                        attempts < max? → handle_error → generate_sql
                                                                   ↓
                                                        attempts >= max? → format_error → END

    Returns:
        Compiled LangGraph state machine.
    """
    graph = StateGraph(AgentState)

    # Add nodes — traced nodes get observability applied externally
    graph.add_node("generate_sql", _traced_node(
        generate_sql,
        input_extractor=lambda s: {
            "user_query": s["user_query"],
            "attempt": s["attempt_count"] + 1,
            "previous_error": s["error_message"] or None,
        },
        output_extractor=lambda r, _s: {
            "sql": r.get("sql_query", ""),
            "reasoning": r.get("reasoning", ""),
        },
    ))
    graph.add_node("validate_sql", _traced_node(
        validate_sql,
        input_extractor=lambda s: {"sql_preview": s["sql_query"][:200]},
        output_extractor=lambda r, _s: {
            "valid": not r.get("error_message"),
            "reason": r.get("error_message", ""),
        },
    ))
    graph.add_node("execute_sql", _traced_node(
        execute_sql,
        input_extractor=lambda s: {"sql": s["sql_query"][:500]},
        output_extractor=lambda r, _s: {
            "row_count": (r.get("execution_result") or {}).get("row_count", 0),
            "error": r.get("error_message", ""),
        },
    ))
    graph.add_node("handle_error", handle_error)
    graph.add_node("format_response", _traced_node(
        format_response,
        input_extractor=lambda s: {
            "row_count": (s.get("execution_result") or {}).get("row_count", 0),
        },
        output_extractor=lambda r, _s: {
            "has_summary": r.get("final_response", {}).get("summary") is not None,
            "row_count": r.get("final_response", {}).get("row_count", 0),
        },
    ))
    graph.add_node("format_error", format_error)

    # Set entry point
    graph.set_entry_point("generate_sql")

    # Edges
    graph.add_edge("generate_sql", "validate_sql")

    graph.add_conditional_edges(
        "validate_sql",
        route_after_validation,
        {
            "execute_sql": "execute_sql",
            "handle_error": "handle_error",
            "format_error": "format_error",
        },
    )

    graph.add_conditional_edges(
        "execute_sql",
        route_after_execution,
        {
            "format_response": "format_response",
            "handle_error": "handle_error",
            "format_error": "format_error",
        },
    )

    graph.add_edge("handle_error", "generate_sql")
    graph.add_edge("format_response", END)
    graph.add_edge("format_error", END)

    return graph.compile()


# Compiled graph instance
_agent_graph = None


def get_agent_graph():
    """Get or create the agent graph singleton."""
    global _agent_graph
    if _agent_graph is None:
        _agent_graph = create_agent_graph()
    return _agent_graph


# ---------------------------------------------------------------------------
# Conversation context helpers
# ---------------------------------------------------------------------------


def _build_conversation_context(session_id: str) -> str:
    """Build formatted conversation context from session history."""
    if not session_id:
        return ""

    session_svc = get_session_service()
    exchanges = session_svc.get_recent_exchanges(session_id)
    if not exchanges:
        return ""

    lines = []
    for i, ex in enumerate(exchanges, 1):
        entry = f'{i}. Q: "{ex.user_query}"\n   SQL: {ex.sql_query}\n   Result: {ex.row_count} row(s) returned'
        if ex.summary:
            entry += f"\n   Summary: {ex.summary}"
        lines.append(entry)

    return CONVERSATION_CONTEXT_BLOCK.format(exchanges="\n\n".join(lines))


def _save_exchange(session_id: str, final_state: dict[str, Any]) -> None:
    """Save a successful exchange to the session store."""
    if not session_id:
        return

    response = final_state.get("final_response", {})
    if not response.get("success"):
        return

    session_svc = get_session_service()
    session_svc.add_exchange(
        session_id,
        Exchange(
            user_query=final_state["user_query"],
            sql_query=final_state["sql_query"],
            row_count=response.get("row_count", 0),
            summary=response.get("summary"),
        ),
    )


# ---------------------------------------------------------------------------
# Agent run helpers — shared logic between async and sync entry points
# ---------------------------------------------------------------------------


def _prepare_agent_run(
    user_query: str, session_id: str
) -> tuple[Any, AgentState, str]:
    """Prepare graph, initial state, and conversation context."""
    graph = get_agent_graph()
    conversation_context = _build_conversation_context(session_id)
    initial_state = create_initial_state(
        user_query,
        session_id=session_id,
        conversation_context=conversation_context,
    )
    return graph, initial_state, conversation_context


def _finalize_agent_run(
    final_state: dict[str, Any],
    session_id: str,
    conversation_context: str,
    trace_id: str,
) -> dict[str, Any]:
    """Update trace, save exchange, and return the response."""
    tracing = get_tracing_service()

    tracing.update_trace(
        output=final_state["final_response"],
        metadata={
            "attempts": final_state["attempt_count"],
            "success": final_state["final_response"].get("success", False),
            "session_id": session_id or "stateless",
            "has_context": bool(conversation_context),
        },
    )

    _save_exchange(session_id, final_state)

    logger.info(
        "Agent completed",
        success=final_state["final_response"].get("success", False),
        attempts=final_state["attempt_count"],
        trace_id=trace_id,
    )

    response = final_state["final_response"]
    if session_id:
        response["session_id"] = session_id
    return response


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


async def run_agent(user_query: str, session_id: str = "") -> dict[str, Any]:
    """Run the SQL agent asynchronously with tracing.

    Args:
        user_query: Natural language query from the user.
        session_id: Optional session ID for conversational memory.

    Returns:
        Final response dictionary with query results or error.
    """
    graph, initial_state, conversation_context = _prepare_agent_run(user_query, session_id)
    trace_id = initial_state["trace_id"]
    tracing = get_tracing_service()

    structlog.contextvars.bind_contextvars(trace_id=trace_id)
    logger.info(
        "Starting agent",
        query=user_query[:50],
        trace_id=trace_id,
        session_id=session_id or "stateless",
        has_context=bool(conversation_context),
    )

    try:
        with tracing.trace(trace_id, user_query=user_query):
            final_state = await graph.ainvoke(initial_state)
            return _finalize_agent_run(final_state, session_id, conversation_context, trace_id)
    finally:
        structlog.contextvars.unbind_contextvars("trace_id")


def run_agent_sync(user_query: str, session_id: str = "") -> dict[str, Any]:
    """Run the SQL agent synchronously with tracing.

    Args:
        user_query: Natural language query from the user.
        session_id: Optional session ID for conversational memory.

    Returns:
        Final response dictionary with query results or error.
    """
    graph, initial_state, conversation_context = _prepare_agent_run(user_query, session_id)
    trace_id = initial_state["trace_id"]
    tracing = get_tracing_service()

    structlog.contextvars.bind_contextvars(trace_id=trace_id)
    logger.info(
        "Starting agent (sync)",
        query=user_query[:50],
        trace_id=trace_id,
        session_id=session_id or "stateless",
    )

    try:
        with tracing.trace(trace_id, user_query=user_query):
            final_state = graph.invoke(initial_state)
            return _finalize_agent_run(final_state, session_id, conversation_context, trace_id)
    finally:
        structlog.contextvars.unbind_contextvars("trace_id")