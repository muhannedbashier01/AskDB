"""Database service for schema introspection and connection management."""

from __future__ import annotations

from typing import Any, Optional

import structlog
from sqlalchemy import MetaData, create_engine, inspect, text
from sqlalchemy.engine import Engine

from app.core.config import get_settings

logger = structlog.get_logger()


class DatabaseService:
    """Service for database operations and schema introspection."""

    def __init__(self, connection_string: str | None = None):
        """Initialize database service.

        Args:
            connection_string: Database connection string. If None, uses settings.
        """
        self._connection_string = connection_string or get_settings().database_url
        self._engine: Engine | None = None
        self._schema_cache: str | None = None

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

    def get_schema(self, refresh: bool = False, max_tables: int = 100, table_filter: list[str] | None = None) -> str:
        """Get database schema as formatted string for LLM context.

        Args:
            refresh: If True, refresh the cached schema.
            max_tables: Maximum number of tables to include (default 100).
            table_filter: Specific list of table names to include. If provided,
                         only these tables are returned (overrides max_tables).

        Returns:
            Formatted schema string.
        """
        # Only use cache if no filter and not refreshing
        if self._schema_cache is not None and not refresh and table_filter is None:
            return self._schema_cache

        logger.info("Fetching database schema", table_filter_enabled=table_filter is not None)

        # Build WHERE clause for table filtering
        if table_filter:
            placeholders = ','.join([f"'{table}'" for table in table_filter])
            where_clause = f"AND t.TABLE_NAME IN ({placeholders})"
        else:
            where_clause = ""

        # Use a faster query to get table and column info
        query = text(f"""
            SELECT
                t.TABLE_NAME,
                c.COLUMN_NAME,
                c.DATA_TYPE,
                c.IS_NULLABLE,
                CASE WHEN pk.COLUMN_NAME IS NOT NULL THEN 1 ELSE 0 END as IS_PK
            FROM INFORMATION_SCHEMA.TABLES t
            JOIN INFORMATION_SCHEMA.COLUMNS c ON t.TABLE_NAME = c.TABLE_NAME AND t.TABLE_SCHEMA = c.TABLE_SCHEMA
            LEFT JOIN (
                SELECT ku.TABLE_NAME, ku.COLUMN_NAME
                FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ku ON tc.CONSTRAINT_NAME = ku.CONSTRAINT_NAME
                WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
            ) pk ON c.TABLE_NAME = pk.TABLE_NAME AND c.COLUMN_NAME = pk.COLUMN_NAME
            WHERE t.TABLE_TYPE = 'BASE TABLE'
            {where_clause}
            ORDER BY t.TABLE_NAME, c.ORDINAL_POSITION
        """)

        with self.engine.connect() as conn:
            result = conn.execute(query)
            rows = result.fetchall()

        # Group by table
        tables = {}
        for row in rows:
            table_name = row[0]
            if table_name not in tables:
                tables[table_name] = []
            tables[table_name].append({
                "name": row[1],
                "type": row[2],
                "nullable": row[3] == "YES",
                "is_pk": row[4] == 1,
            })

        # Build schema string (limit tables only if no filter)
        schema_parts = []
        table_list = list(tables.keys())

        if table_filter is None:
            table_list = table_list[:max_tables]

        for table_name in table_list:
            columns = tables[table_name]
            col_descriptions = []
            for col in columns:
                nullable = "NULL" if col["nullable"] else "NOT NULL"
                pk_marker = " [PK]" if col["is_pk"] else ""
                col_descriptions.append(f"    {col['name']} {col['type']} {nullable}{pk_marker}")

            table_schema = f"TABLE {table_name}:\n"
            table_schema += "\n".join(col_descriptions)
            schema_parts.append(table_schema)

        if table_filter is None and len(tables) > max_tables:
            schema_parts.append(f"\n... and {len(tables) - max_tables} more tables")

        schema_str = "\n\n".join(schema_parts)

        # Only cache if no filter (full schema)
        if table_filter is None:
            self._schema_cache = schema_str

        logger.info(f"Schema loaded: {len(table_list)} tables", filtered=table_filter is not None)
        return schema_str

    def get_schema_dict(self) -> dict[str, Any]:
        """Get database schema as structured dictionary.

        Returns:
            Dictionary with tables and their columns/relationships.
        """
        inspector = inspect(self.engine)
        schema = {"tables": []}

        for table_name in inspector.get_table_names():
            columns = inspector.get_columns(table_name)
            pk_columns = inspector.get_pk_constraint(table_name).get("constrained_columns", [])
            fk_constraints = inspector.get_foreign_keys(table_name)

            table_info = {
                "name": table_name,
                "columns": [
                    {
                        "name": col["name"],
                        "type": str(col["type"]),
                        "nullable": col.get("nullable", True),
                        "primary_key": col["name"] in pk_columns,
                    }
                    for col in columns
                ],
                "foreign_keys": [
                    {
                        "columns": fk["constrained_columns"],
                        "references_table": fk["referred_table"],
                        "references_columns": fk["referred_columns"],
                    }
                    for fk in fk_constraints
                ],
            }
            schema["tables"].append(table_info)

        return schema

    def test_connection(self) -> tuple[bool, str]:
        """Test database connection.

        Returns:
            Tuple of (success, message).
        """
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True, "Connection successful"
        except Exception as e:
            return False, str(e)


# In-memory query history for the session
_query_history: list[dict[str, Any]] = []


def add_to_history(
    user_query: str,
    sql_query: str,
    success: bool,
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    """Add a query to the session history.

    Args:
        user_query: The natural language query.
        sql_query: The generated SQL.
        success: Whether execution was successful.
        result: Query results if successful.
        error: Error message if failed.
    """
    from datetime import datetime

    _query_history.append({
        "timestamp": datetime.now().isoformat(),
        "user_query": user_query,
        "sql_query": sql_query,
        "success": success,
        "result_preview": _get_result_preview(result) if result else None,
        "error": error,
    })


def get_history(limit: int = 50) -> list[dict[str, Any]]:
    """Get query history.

    Args:
        limit: Maximum number of entries to return.

    Returns:
        List of history entries, most recent first.
    """
    return list(reversed(_query_history[-limit:]))


def clear_history() -> None:
    """Clear query history."""
    _query_history.clear()


def _get_result_preview(result: dict[str, Any]) -> dict[str, Any]:
    """Get a preview of results for history storage.

    Args:
        result: Full query result.

    Returns:
        Preview with limited rows.
    """
    return {
        "columns": result.get("columns", []),
        "row_count": result.get("row_count", 0),
        "rows_preview": result.get("rows", [])[:5],  # Only store first 5 rows
    }


# Module-level service instance
_db_service: DatabaseService | None = None


def get_db_service() -> DatabaseService:
    """Get or create database service singleton."""
    global _db_service
    if _db_service is None:
        _db_service = DatabaseService()
    return _db_service
