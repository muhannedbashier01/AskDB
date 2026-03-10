"""Agent state definition for the LangGraph SQL agent."""

from __future__ import annotations

import uuid
from typing import Any, TypedDict


class AgentState(TypedDict):
    """State for the SQL agent workflow.

    Attributes:
        trace_id: Unique identifier for this request (for log/trace correlation).
        session_id: Conversation session identifier for memory.
        user_query: Original natural language query from the user.
        sql_query: Generated SQL query.
        reasoning: Optional LLM reasoning about the generated SQL.
        conversation_context: Formatted prior exchanges for LLM context.
        execution_result: Query results or None if not yet executed.
        error_message: Error message from the last failed attempt.
        error_type: Origin of the error — "" (none), "validation", or "execution".
        attempt_count: Number of SQL generation attempts (max 3).
        is_complete: Whether the workflow has completed.
        final_response: Formatted response to return to the user.
    """

    trace_id: str
    session_id: str
    user_query: str
    sql_query: str
    reasoning: str
    conversation_context: str
    execution_result: Any
    nl_summary: str | None
    error_message: str
    error_type: str
    attempt_count: int
    is_complete: bool
    final_response: dict[str, Any]


def create_initial_state(
    user_query: str,
    session_id: str = "",
    conversation_context: str = "",
) -> AgentState:
    """Create initial agent state for a new query.

    Args:
        user_query: The natural language query from the user.
        session_id: Optional conversation session ID.
        conversation_context: Optional formatted prior exchanges.

    Returns:
        Initial AgentState with default values.
    """
    return AgentState(
        trace_id=uuid.uuid4().hex,
        session_id=session_id,
        user_query=user_query,
        sql_query="",
        reasoning="",
        conversation_context=conversation_context,
        execution_result=None,
        nl_summary=None,
        error_message="",
        error_type="",
        attempt_count=0,
        is_complete=False,
        final_response={},
    )
