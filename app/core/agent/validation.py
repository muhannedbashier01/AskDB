"""SQL query validation for read-only enforcement.

Ensures that only safe, read-only SELECT statements are executed.
Rejects any query containing dangerous patterns such as DDL, DML,
or multiple statements.
"""

from __future__ import annotations

import re

# Forbidden SQL keywords/patterns that indicate non-read-only operations.
# Each entry is (compiled regex, human-readable description).
_FORBIDDEN_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bDROP\b", re.IGNORECASE), "DROP statements are not allowed"),
    (re.compile(r"\bDELETE\b", re.IGNORECASE), "DELETE statements are not allowed"),
    (re.compile(r"\bUPDATE\b", re.IGNORECASE), "UPDATE statements are not allowed"),
    (re.compile(r"\bINSERT\b", re.IGNORECASE), "INSERT statements are not allowed"),
    (re.compile(r"\bTRUNCATE\b", re.IGNORECASE), "TRUNCATE statements are not allowed"),
    (re.compile(r"\bALTER\b", re.IGNORECASE), "ALTER statements are not allowed"),
    (re.compile(r"\bCREATE\b", re.IGNORECASE), "CREATE statements are not allowed"),
    (re.compile(r"\bEXEC(?:UTE)?\b", re.IGNORECASE), "EXEC/EXECUTE statements are not allowed"),
    (re.compile(r"\bGRANT\b", re.IGNORECASE), "GRANT statements are not allowed"),
    (re.compile(r"\bREVOKE\b", re.IGNORECASE), "REVOKE statements are not allowed"),
    (re.compile(r"\bMERGE\b", re.IGNORECASE), "MERGE statements are not allowed"),
    (re.compile(r"\bxp_", re.IGNORECASE), "Extended stored procedures are not allowed"),
    (re.compile(r"\bsp_", re.IGNORECASE), "System stored procedures are not allowed"),
    (re.compile(r"\bOPENROWSET\b", re.IGNORECASE), "OPENROWSET is not allowed"),
    (re.compile(r"\bOPENDATASOURCE\b", re.IGNORECASE), "OPENDATASOURCE is not allowed"),
    (re.compile(r"\bBULK\b", re.IGNORECASE), "BULK operations are not allowed"),
]


def _strip_sql_comments(sql: str) -> str:
    """Remove SQL comments (single-line and block) from a query.

    Args:
        sql: The raw SQL string.

    Returns:
        SQL with comments removed.
    """
    # Remove block comments (non-greedy to handle nested-ish patterns)
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    # Remove single-line comments
    sql = re.sub(r"--[^\n]*", " ", sql)
    return sql


def validate_sql_query(sql: str) -> tuple[bool, str]:
    """Validate a SQL query for read-only safety.

    Checks that the query:
    - Is non-empty
    - Starts with SELECT (after stripping comments and whitespace)
    - Contains no forbidden keywords (DROP, DELETE, UPDATE, etc.)
    - Contains no multiple statements (semicolons splitting statements)

    Args:
        sql: The SQL query to validate.

    Returns:
        A tuple of (is_valid, error_reason). If is_valid is True,
        error_reason is an empty string.
    """
    if not sql or not sql.strip():
        return False, "Empty SQL query"

    # Strip comments to prevent comment-based bypass
    cleaned = _strip_sql_comments(sql)
    # Collapse whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if not cleaned:
        return False, "SQL query is empty after removing comments"

    # Must start with SELECT
    if not re.match(r"^SELECT\b", cleaned, re.IGNORECASE):
        return False, "Only SELECT statements are allowed"

    # Check for multiple statements (semicolons that aren't inside string literals)
    # Simple heuristic: split on semicolons and check for non-empty trailing statements
    parts = [p.strip() for p in cleaned.split(";") if p.strip()]
    if len(parts) > 1:
        return False, "Multiple SQL statements are not allowed"

    # Check for forbidden patterns
    for pattern, description in _FORBIDDEN_PATTERNS:
        if pattern.search(cleaned):
            return False, description

    return True, ""
