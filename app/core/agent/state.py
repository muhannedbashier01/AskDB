"""Agent state definition for the LangGraph SQL agent."""

from __future__ import annotations

import uuid
from typing import Any, TypedDict


class AgentState(TypedDict):
    """State for the SQL agent workflow.

    Attributes:
        trace_id: Unique identifier for this request (for log/trace correlation).
        user_query: Original natural language query from the user.
        sql_query: Generated SQL query.
        reasoning: Optional LLM reasoning about the generated SQL.
        execution_result: Query results or None if not yet executed.
        error_message: Error message from the last failed attempt.
        attempt_count: Number of SQL generation attempts (max 3).
        is_complete: Whether the workflow has completed.
        final_response: Formatted response to return to the user.
    """

    trace_id: str
    user_query: str
    sql_query: str
    reasoning: str
    execution_result: Any
    error_message: str
    attempt_count: int
    is_complete: bool
    final_response: dict[str, Any]


def create_initial_state(user_query: str) -> AgentState:
    """Create initial agent state for a new query.

    Args:
        user_query: The natural language query from the user.

    Returns:
        Initial AgentState with default values.
    """
    return AgentState(
        trace_id=uuid.uuid4().hex,
        user_query=user_query,
        sql_query="",
        reasoning="",
        execution_result=None,
        error_message="",
        attempt_count=0,
        is_complete=False,
        final_response={},
    )
