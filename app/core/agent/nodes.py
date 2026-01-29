"""Agent node functions for the LangGraph SQL agent."""

from __future__ import annotations

from typing import Any

import structlog

from app.core.agent.state import AgentState
from app.core.config import POLICIES_TABLES, get_settings
from app.core.tools.sql_executor import SQLExecutionError, get_sql_executor, inject_top_clause
from app.services.db_service import add_to_history, get_db_service
from app.services.llm_service import get_llm_service

logger = structlog.get_logger()


def generate_sql(state: AgentState) -> dict[str, Any]:
    """Generate SQL query from natural language.

    Args:
        state: Current agent state.

    Returns:
        State updates with generated SQL.
    """
    llm = get_llm_service()
    db = get_db_service()
    schema = db.get_schema(table_filter=POLICIES_TABLES)  # Policies context only

    attempt = state["attempt_count"] + 1
    logger.info("Generating SQL", attempt=attempt, user_query=state["user_query"][:50])

    if state["error_message"] and state["sql_query"]:
        # Retry with error context
        sql = llm.fix_sql(
            user_query=state["user_query"],
            sql_query=state["sql_query"],
            error=state["error_message"],
            schema=schema,
        )
    else:
        # Initial generation
        sql = llm.generate_sql(
            user_query=state["user_query"],
            schema=schema,
        )

    # Log full SQL query to Seq
    logger.info(
        "SQL generated",
        sql_query=sql,
        user_query=state["user_query"],
        attempt=attempt,
        sql_preview=sql[:100] if sql else ""
    )

    return {
        "sql_query": sql,
        "attempt_count": attempt,
        "error_message": "",  # Clear previous error
    }


def execute_sql(state: AgentState) -> dict[str, Any]:
    """Execute the generated SQL query.

    Args:
        state: Current agent state.

    Returns:
        State updates with execution result or error.
    """
    executor = get_sql_executor()

    # Inject TOP clause to limit results
    sql_with_limit = inject_top_clause(state["sql_query"], state["user_query"])

    logger.info("Executing SQL", query=sql_with_limit[:100])

    try:
        result = executor.execute(sql_with_limit)
        logger.info("SQL executed successfully", row_count=result.get("row_count", 0))

        # Add to history
        add_to_history(
            user_query=state["user_query"],
            sql_query=sql_with_limit,  # Use modified SQL with TOP clause
            success=True,
            result=result,
        )

        return {
            "execution_result": result,
            "error_message": "",
            "sql_query": sql_with_limit,  # Update state with modified SQL
        }
    except SQLExecutionError as e:
        logger.warning("SQL execution failed", error=e.message)

        return {
            "execution_result": None,
            "error_message": e.message,
        }


def handle_error(state: AgentState) -> dict[str, Any]:
    """Handle SQL execution error and prepare for retry.

    Args:
        state: Current agent state.

    Returns:
        State updates (error message is already set).
    """
    logger.info(
        "Handling error for retry",
        attempt=state["attempt_count"],
        error=state["error_message"][:100],
    )

    # The error_message is already set by execute_sql
    # This node exists for the graph structure and potential future logic
    return {}


def format_response(state: AgentState) -> dict[str, Any]:
    """Format successful response for the user.

    Args:
        state: Current agent state.

    Returns:
        State updates with final formatted response.
    """
    result = state["execution_result"]

    response = {
        "success": True,
        "sql_query": state["sql_query"],
        "columns": result.get("columns", []),
        "rows": result.get("rows", []),
        "row_count": result.get("row_count", 0),
        "attempts": state["attempt_count"],
        "message": result.get("message"),
    }

    logger.info("Response formatted", row_count=response["row_count"])

    return {
        "final_response": response,
        "is_complete": True,
    }


def format_error(state: AgentState) -> dict[str, Any]:
    """Format error response after max retries.

    Args:
        state: Current agent state.

    Returns:
        State updates with error response.
    """
    # Add to history as failed
    add_to_history(
        user_query=state["user_query"],
        sql_query=state["sql_query"],
        success=False,
        error=state["error_message"],
    )

    response = {
        "success": False,
        "sql_query": state["sql_query"],
        "error": state["error_message"],
        "attempts": state["attempt_count"],
        "message": f"Failed to execute query after {state['attempt_count']} attempts.",
    }

    logger.info("Error response formatted", attempts=state["attempt_count"])

    return {
        "final_response": response,
        "is_complete": True,
    }


def should_retry(state: AgentState) -> str:
    """Determine if we should retry or give up.

    Args:
        state: Current agent state.

    Returns:
        Next node name: 'handle_error' to retry, 'format_error' to give up.
    """
    settings = get_settings()

    if state["attempt_count"] < settings.max_retry_attempts:
        logger.info("Retrying", attempt=state["attempt_count"], max=settings.max_retry_attempts)
        return "handle_error"
    else:
        logger.info("Max retries reached", attempts=state["attempt_count"])
        return "format_error"


def check_execution(state: AgentState) -> str:
    """Check if execution was successful.

    Args:
        state: Current agent state.

    Returns:
        Next node name: 'format_response' on success, conditional on error.
    """
    if state["execution_result"] is not None:
        return "format_response"
    else:
        return "check_retry"
