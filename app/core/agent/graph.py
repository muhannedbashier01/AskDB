"""LangGraph workflow definition for the SQL agent."""

from __future__ import annotations

from typing import Any

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
from app.services.langfuse_service import langfuse_trace, langfuse_update_trace

logger = structlog.get_logger()


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
    # Create the graph with AgentState
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("generate_sql", generate_sql)
    graph.add_node("validate_sql", validate_sql)
    graph.add_node("execute_sql", execute_sql)
    graph.add_node("handle_error", handle_error)
    graph.add_node("format_response", format_response)
    graph.add_node("format_error", format_error)

    # Set entry point
    graph.set_entry_point("generate_sql")

    # Add edges: generate → validate → (conditional) → execute or handle_error
    graph.add_edge("generate_sql", "validate_sql")

    # Conditional edge after validation: pass or reject
    graph.add_conditional_edges(
        "validate_sql",
        route_after_validation,
        {
            "execute_sql": "execute_sql",
            "handle_error": "handle_error",
            "format_error": "format_error",
        },
    )

    # Conditional edge after execution: success, retry, or give up
    graph.add_conditional_edges(
        "execute_sql",
        route_after_execution,
        {
            "format_response": "format_response",
            "handle_error": "handle_error",
            "format_error": "format_error",
        },
    )

    # Retry loop
    graph.add_edge("handle_error", "generate_sql")

    # Terminal edges
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


async def run_agent(user_query: str) -> dict[str, Any]:
    """Run the SQL agent for a user query.

    Integrates Langfuse tracing (if enabled) via LangChain callbacks so that
    every LLM call and graph step is automatically captured.

    Args:
        user_query: Natural language query from the user.

    Returns:
        Final response dictionary with query results or error.
    """
    graph = get_agent_graph()
    initial_state = create_initial_state(user_query)
    trace_id = initial_state["trace_id"]

    # Bind trace_id to structured logging context for all downstream calls
    structlog.contextvars.bind_contextvars(trace_id=trace_id)

    logger.info("Starting agent", query=user_query[:50], trace_id=trace_id)

    try:
        # Wrap entire graph execution in a Langfuse trace
        with langfuse_trace(trace_id, user_query=user_query):
            final_state = await graph.ainvoke(initial_state)

            # Attach final output to the Langfuse trace
            langfuse_update_trace(
                output=final_state["final_response"],
                metadata={
                    "attempts": final_state["attempt_count"],
                    "success": final_state["final_response"].get("success", False),
                },
            )

        logger.info(
            "Agent completed",
            success=final_state["final_response"].get("success", False),
            attempts=final_state["attempt_count"],
            trace_id=trace_id,
        )

        return final_state["final_response"]
    finally:
        structlog.contextvars.unbind_contextvars("trace_id")


def run_agent_sync(user_query: str) -> dict[str, Any]:
    """Run the SQL agent synchronously.

    Integrates Langfuse tracing (if enabled) via LangChain callbacks so that
    every LLM call and graph step is automatically captured.

    Args:
        user_query: Natural language query from the user.

    Returns:
        Final response dictionary with query results or error.
    """
    graph = get_agent_graph()
    initial_state = create_initial_state(user_query)
    trace_id = initial_state["trace_id"]

    # Bind trace_id to structured logging context for all downstream calls
    structlog.contextvars.bind_contextvars(trace_id=trace_id)

    logger.info("Starting agent (sync)", query=user_query[:50], trace_id=trace_id)

    try:
        # Wrap entire graph execution in a Langfuse trace
        with langfuse_trace(trace_id, user_query=user_query):
            final_state = graph.invoke(initial_state)

            # Attach final output to the Langfuse trace
            langfuse_update_trace(
                output=final_state["final_response"],
                metadata={
                    "attempts": final_state["attempt_count"],
                    "success": final_state["final_response"].get("success", False),
                },
            )

        logger.info(
            "Agent completed",
            success=final_state["final_response"].get("success", False),
            attempts=final_state["attempt_count"],
            trace_id=trace_id,
        )

        return final_state["final_response"]
    finally:
        structlog.contextvars.unbind_contextvars("trace_id")
