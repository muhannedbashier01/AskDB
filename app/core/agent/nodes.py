"""Agent node functions for the LangGraph SQL agent."""

from __future__ import annotations

from typing import Any

import structlog

from app.core.agent.state import AgentState
from app.core.agent.validation import validate_sql_query
from app.core.config import POLICIES_TABLES, get_settings
from app.core.tools.sql_executor import SQLExecutionError, get_sql_executor, inject_top_clause
from app.services.db_service import add_to_history, get_db_service
from app.services.langfuse_service import langfuse_span
from app.services.llm_service import get_llm_service

logger = structlog.get_logger()


def generate_sql(state: AgentState) -> dict[str, Any]:
    """Generate SQL query from natural language.

    Uses structured JSON output from the LLM to extract both the SQL query
    and optional reasoning for better observability.

    Args:
        state: Current agent state.

    Returns:
        State updates with generated SQL and optional reasoning.
    """
    attempt = state["attempt_count"] + 1

    with langfuse_span(
        "generate_sql",
        input={
            "user_query": state["user_query"],
            "attempt": attempt,
            "previous_error": state["error_message"] or None,
        },
    ) as span:
        llm = get_llm_service()
        db = get_db_service()
        schema = db.get_schema(table_filter=POLICIES_TABLES)  # Policies context only

        logger.info("Generating SQL", attempt=attempt, user_query=state["user_query"][:50])

        if state["error_message"] and state["sql_query"]:
            if state["error_type"] == "validation":
                result = llm.fix_validation_error(
                    user_query=state["user_query"],
                    sql_query=state["sql_query"],
                    error=state["error_message"],
                    schema=schema,
                )
            else:
                result = llm.fix_sql(
                    user_query=state["user_query"],
                    sql_query=state["sql_query"],
                    error=state["error_message"],
                    schema=schema,
                )
        else:
            result = llm.generate_sql(
                user_query=state["user_query"],
                schema=schema,
            )

        sql = result["sql"]
        reasoning = result.get("reasoning", "")

        logger.info(
            "SQL generated",
            sql_query=sql,
            reasoning=reasoning,
            user_query=state["user_query"],
            attempt=attempt,
            sql_preview=sql[:100] if sql else "",
        )

        # Attach output to Langfuse span
        if span is not None:
            span.update(output={"sql": sql, "reasoning": reasoning})

    return {
        "sql_query": sql,
        "reasoning": reasoning,
        "attempt_count": attempt,
        "error_message": "",
        "error_type": "",
    }


def validate_sql(state: AgentState) -> dict[str, Any]:
    """Validate the generated SQL query before execution.

    Ensures only read-only SELECT statements are allowed and rejects
    dangerous patterns (DROP, DELETE, UPDATE, INSERT, TRUNCATE, EXEC, etc.).

    Args:
        state: Current agent state.

    Returns:
        State updates with validation error if invalid, or empty if valid.
    """
    sql = state["sql_query"]

    with langfuse_span("validate_sql", input={"sql_preview": sql[:200]}) as span:
        is_valid, error_reason = validate_sql_query(sql)

        if is_valid:
            logger.info("SQL validation passed", sql_preview=sql[:100])
            if span is not None:
                span.update(output={"valid": True})
            return {"error_message": "", "error_type": ""}

        logger.warning("SQL validation failed", reason=error_reason, sql_preview=sql[:100])
        if span is not None:
            span.update(output={"valid": False, "reason": error_reason})

    return {
        "error_message": f"SQL validation failed: {error_reason}",
        "error_type": "validation",
    }


def route_after_validation(state: AgentState) -> str:
    """Route after SQL validation: execute, retry, or give up.

    Args:
        state: Current agent state.

    Returns:
        Next node name:
            - 'execute_sql' if validation passed
            - 'handle_error' to retry on validation failure
            - 'format_error' when max retries exhausted
    """
    if not state["error_message"]:
        return "execute_sql"

    settings = get_settings()

    if state["attempt_count"] < settings.max_retry_attempts:
        logger.info(
            "Retrying after validation failure",
            attempt=state["attempt_count"],
            max=settings.max_retry_attempts,
        )
        return "handle_error"

    logger.info("Max retries reached after validation failure", attempts=state["attempt_count"])
    return "format_error"


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

    with langfuse_span("execute_sql", input={"sql": sql_with_limit[:500]}) as span:
        logger.info("Executing SQL", query=sql_with_limit[:100])

        try:
            result = executor.execute(sql_with_limit)
            logger.info("SQL executed successfully", row_count=result.get("row_count", 0))

            # Add to history
            add_to_history(
                user_query=state["user_query"],
                sql_query=sql_with_limit,
                success=True,
                result=result,
            )

            if span is not None:
                span.update(output={
                    "row_count": result.get("row_count", 0),
                    "columns": result.get("columns", []),
                })

            return {
                "execution_result": result,
                "error_message": "",
                "error_type": "",
                "sql_query": sql_with_limit,
            }
        except SQLExecutionError as e:
            logger.warning("SQL execution failed", error=e.message)
            if span is not None:
                span.update(
                    output={"error": e.message},
                    level="ERROR",
                    status_message=e.message,
                )

            return {
                "execution_result": None,
                "error_message": e.message,
                "error_type": "execution",
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


def _generate_nl_summary(user_query: str, result: dict[str, Any]) -> str | None:
    """Generate a natural language summary of query results.

    Calls the LLM to produce a concise 1-2 sentence summary. Falls back to
    None on any error so the response is still returned without a summary.

    Args:
        user_query: The original user question.
        result: The SQL execution result dict (columns, rows, row_count).

    Returns:
        A short summary string, or None if generation fails.
    """
    from app.core.prompts.sql_agent import RESPONSE_FORMAT_PROMPT

    try:
        llm = get_llm_service()

        # Build a concise results preview for the LLM (first 5 rows max)
        columns = result.get("columns", [])
        rows = result.get("rows", [])
        row_count = result.get("row_count", 0)

        preview_rows = rows[:5]
        results_text = (
            f"Columns: {columns}\n"
            f"Row count: {row_count}\n"
            f"Sample rows: {preview_rows}"
        )
        if row_count > 5:
            results_text += f"\n(showing 5 of {row_count} rows)"

        prompt = RESPONSE_FORMAT_PROMPT.format(
            user_query=user_query,
            results=results_text,
        )
        summary = llm.generate(prompt, generation_name="generate-summary")
        return summary.strip() if summary else None
    except Exception:
        logger.warning("Failed to generate NL summary, skipping", exc_info=True)
        return None


def format_response(state: AgentState) -> dict[str, Any]:
    """Format successful response for the user.

    Includes a natural language summary generated by the LLM.

    Args:
        state: Current agent state.

    Returns:
        State updates with final formatted response.
    """
    result = state["execution_result"]

    with langfuse_span("format_response", input={"row_count": result.get("row_count", 0)}) as span:
        # Generate natural language summary
        summary = _generate_nl_summary(state["user_query"], result)

        response = {
            "success": True,
            "sql_query": state["sql_query"],
            "columns": result.get("columns", []),
            "rows": result.get("rows", []),
            "row_count": result.get("row_count", 0),
            "attempts": state["attempt_count"],
            "message": result.get("message"),
            "trace_id": state["trace_id"],
            "summary": summary,
        }

        logger.info("Response formatted", row_count=response["row_count"], has_summary=summary is not None)

        if span is not None:
            span.update(output={"has_summary": summary is not None, "row_count": response["row_count"]})

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
        "trace_id": state["trace_id"],
    }

    logger.info("Error response formatted", attempts=state["attempt_count"])

    return {
        "final_response": response,
        "is_complete": True,
    }


def route_after_execution(state: AgentState) -> str:
    """Route after SQL execution: success, retry, or give up.

    Combines execution check and retry logic into a single router
    to eliminate the need for a dummy intermediate node.

    Args:
        state: Current agent state.

    Returns:
        Next node name:
            - 'format_response' on success
            - 'handle_error' to retry on failure
            - 'format_error' when max retries exhausted
    """
    if state["execution_result"] is not None:
        return "format_response"

    settings = get_settings()

    if state["attempt_count"] < settings.max_retry_attempts:
        logger.info(
            "Retrying", attempt=state["attempt_count"], max=settings.max_retry_attempts
        )
        return "handle_error"

    logger.info("Max retries reached", attempts=state["attempt_count"])
    return "format_error"
