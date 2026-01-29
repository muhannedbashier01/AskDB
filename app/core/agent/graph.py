"""LangGraph workflow definition for the SQL agent."""

from typing import Any

import structlog
from langgraph.graph import END, StateGraph

from app.core.agent.nodes import (
    check_execution,
    execute_sql,
    format_error,
    format_response,
    generate_sql,
    handle_error,
    should_retry,
)
from app.core.agent.state import AgentState, create_initial_state

logger = structlog.get_logger()


def create_agent_graph() -> StateGraph:
    """Create the LangGraph state machine for the SQL agent.

    The graph follows this flow:
    START → generate_sql → execute_sql → [check_execution]
                                              ↓
                                   success? → format_response → END
                                       ↓
                                   error? → [should_retry]
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
    graph.add_node("execute_sql", execute_sql)
    graph.add_node("handle_error", handle_error)
    graph.add_node("format_response", format_response)
    graph.add_node("format_error", format_error)

    # Set entry point
    graph.set_entry_point("generate_sql")

    # Add edges
    graph.add_edge("generate_sql", "execute_sql")

    # Conditional edge after execution
    graph.add_conditional_edges(
        "execute_sql",
        check_execution,
        {
            "format_response": "format_response",
            "check_retry": "check_retry_node",
        },
    )

    # Add a dummy node for retry check (needed for conditional routing)
    graph.add_node("check_retry_node", lambda x: {})
    graph.add_conditional_edges(
        "check_retry_node",
        should_retry,
        {
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

    Args:
        user_query: Natural language query from the user.

    Returns:
        Final response dictionary with query results or error.
    """
    logger.info("Starting agent", query=user_query[:50])

    graph = get_agent_graph()
    initial_state = create_initial_state(user_query)

    # Run the graph
    final_state = await graph.ainvoke(initial_state)

    logger.info(
        "Agent completed",
        success=final_state["final_response"].get("success", False),
        attempts=final_state["attempt_count"],
    )

    return final_state["final_response"]


def run_agent_sync(user_query: str) -> dict[str, Any]:
    """Run the SQL agent synchronously.

    Args:
        user_query: Natural language query from the user.

    Returns:
        Final response dictionary with query results or error.
    """
    logger.info("Starting agent (sync)", query=user_query[:50])

    graph = get_agent_graph()
    initial_state = create_initial_state(user_query)

    # Run the graph synchronously
    final_state = graph.invoke(initial_state)

    logger.info(
        "Agent completed",
        success=final_state["final_response"].get("success", False),
        attempts=final_state["attempt_count"],
    )

    return final_state["final_response"]
