"""SQL execution tool for running queries against MSSQL."""

from __future__ import annotations

import decimal
import re
from datetime import date, datetime
from typing import Any

import structlog
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings

logger = structlog.get_logger()


def inject_top_clause(sql_query: str, user_query: str) -> str:
    """Inject TOP clause into SELECT queries if not already present.

    Args:
        sql_query: The SQL query to modify.
        user_query: The original user query to detect explicit limit requests.

    Returns:
        Modified SQL query with TOP clause if applicable.
    """
    settings = get_settings()

    # Check if query already has TOP clause
    if re.search(r'\bTOP\s+\d+\b', sql_query, re.IGNORECASE):
        # Extract existing TOP value
        match = re.search(r'\bTOP\s+(\d+)\b', sql_query, re.IGNORECASE)
        if match:
            top_value = int(match.group(1))
            # Enforce max limit
            if top_value > settings.max_result_limit:
                sql_query = re.sub(
                    r'\bTOP\s+\d+\b',
                    f'TOP {settings.max_result_limit}',
                    sql_query,
                    flags=re.IGNORECASE
                )
                logger.info(
                    f"Limiting TOP clause from {top_value} to {settings.max_result_limit}"
                )
        return sql_query

    # Skip TOP injection for aggregation queries
    # Check if query uses aggregate functions without GROUP BY at row level
    has_aggregate = re.search(
        r'\b(COUNT|SUM|AVG|MIN|MAX)\s*\(',
        sql_query,
        re.IGNORECASE
    )

    # Check if there's a GROUP BY clause (these might need limits)
    has_group_by = re.search(r'\bGROUP\s+BY\b', sql_query, re.IGNORECASE)

    if has_aggregate and not has_group_by:
        # Pure aggregation query (e.g., SELECT COUNT(*), SELECT AVG(price))
        # These return a single row, no need for TOP
        logger.info("Skipping TOP injection for aggregation query without GROUP BY")
        return sql_query

    # Check if user explicitly requested a specific number
    number_match = re.search(r'\b(\d+)\b', user_query)
    if number_match:
        requested_limit = int(number_match.group(1))
        # Cap at max limit
        limit = min(requested_limit, settings.max_result_limit)
    else:
        limit = settings.default_result_limit

    # Only inject TOP for SELECT queries
    if re.match(r'^\s*SELECT\s+', sql_query, re.IGNORECASE):
        # Check if it's SELECT DISTINCT
        if re.match(r'^\s*SELECT\s+DISTINCT\s+', sql_query, re.IGNORECASE):
            sql_query = re.sub(
                r'^(\s*SELECT\s+DISTINCT\s+)',
                rf'\1TOP {limit} ',
                sql_query,
                count=1,
                flags=re.IGNORECASE
            )
        else:
            sql_query = re.sub(
                r'^(\s*SELECT\s+)',
                rf'\1TOP {limit} ',
                sql_query,
                count=1,
                flags=re.IGNORECASE
            )

        if has_group_by:
            logger.info(f"Injected TOP {limit} clause into GROUP BY query (limiting groups)")
        else:
            logger.info(f"Injected TOP {limit} clause into SELECT query")

    return sql_query


class SQLExecutionError(Exception):
    """Exception raised when SQL execution fails."""

    def __init__(self, message: str, original_error: str | None = None):
        self.message = message
        self.original_error = original_error
        super().__init__(self.message)


class SQLExecutor:
    """Executes SQL queries against MSSQL database."""

    def __init__(self, connection_string: str | None = None):
        """Initialize SQL executor.

        Args:
            connection_string: Database connection string. If None, uses settings.
        """
        self._connection_string = connection_string or get_settings().database_url
        self._engine: Engine | None = None

    @property
    def engine(self) -> Engine:
        """Get or create SQLAlchemy engine."""
        if self._engine is None:
            self._engine = create_engine(
                self._connection_string,
                pool_pre_ping=True,
                pool_recycle=3600,
            )
        return self._engine

    def execute(self, sql_query: str, timeout: int | None = None) -> dict[str, Any]:
        """Execute SQL query and return results.

        Args:
            sql_query: The SQL query to execute.
            timeout: Query timeout in seconds. If None, uses default from settings.

        Returns:
            Dictionary with 'columns' and 'rows' keys.

        Raises:
            SQLExecutionError: If query execution fails.
        """
        timeout = timeout or get_settings().query_timeout_seconds

        logger.info("Executing SQL query", query=sql_query[:100])

        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(sql_query))

                if result.returns_rows:
                    columns = list(result.keys())
                    rows = [
                        self._serialize_row(dict(zip(columns, row)))
                        for row in result.fetchall()
                    ]
                    return {
                        "columns": columns,
                        "rows": rows,
                        "row_count": len(rows),
                    }
                else:
                    return {
                        "columns": [],
                        "rows": [],
                        "row_count": result.rowcount,
                        "message": f"Query executed successfully. {result.rowcount} rows affected.",
                    }

        except SQLAlchemyError as e:
            error_msg = str(e)
            logger.error("SQL execution failed", error=error_msg)
            raise SQLExecutionError(
                message=f"SQL execution failed: {self._clean_error(error_msg)}",
                original_error=error_msg,
            ) from e

    def _serialize_row(self, row: dict[str, Any]) -> dict[str, Any]:
        """Serialize row values to JSON-compatible types.

        Args:
            row: Row dictionary with potentially non-serializable values.

        Returns:
            Row with all values converted to JSON-compatible types.
        """
        serialized = {}
        for key, value in row.items():
            if isinstance(value, datetime):
                serialized[key] = value.isoformat()
            elif isinstance(value, date):
                serialized[key] = value.isoformat()
            elif isinstance(value, decimal.Decimal):
                serialized[key] = float(value)
            elif isinstance(value, bytes):
                serialized[key] = value.hex()
            else:
                serialized[key] = value
        return serialized

    def _clean_error(self, error: str) -> str:
        """Clean up error message for user display.

        Args:
            error: Raw error message.

        Returns:
            Cleaned error message.
        """
        # Remove connection details and sensitive info
        lines = error.split("\n")
        cleaned_lines = []
        for line in lines:
            # Skip lines with connection info
            if "connection" in line.lower() and "@" in line:
                continue
            cleaned_lines.append(line)
        return "\n".join(cleaned_lines[:5])  # Limit to first 5 lines

    def test_connection(self) -> bool:
        """Test database connection.

        Returns:
            True if connection is successful, False otherwise.
        """
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except SQLAlchemyError:
            return False


# Module-level executor instance
_executor: SQLExecutor | None = None


def get_sql_executor() -> SQLExecutor:
    """Get or create SQL executor singleton."""
    global _executor
    if _executor is None:
        _executor = SQLExecutor()
    return _executor
