"""Pydantic schemas for API request/response models."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Request model for submitting a natural language query."""

    query: str = Field(..., min_length=1, description="Natural language query")


class QueryResponse(BaseModel):
    """Response model for query results."""

    success: bool = Field(..., description="Whether the query was successful")
    sql_query: str = Field(..., description="Generated SQL query")
    columns: List[str] = Field(default_factory=list, description="Column names")
    rows: List[Dict[str, Any]] = Field(default_factory=list, description="Query results")
    row_count: int = Field(default=0, description="Number of rows returned")
    attempts: int = Field(default=1, description="Number of generation attempts")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    message: Optional[str] = Field(default=None, description="Additional message")


class ColumnInfo(BaseModel):
    """Column information."""

    name: str
    type: str
    nullable: bool
    primary_key: bool


class ForeignKeyInfo(BaseModel):
    """Foreign key information."""

    columns: List[str]
    references_table: str
    references_columns: List[str]


class TableInfo(BaseModel):
    """Table schema information."""

    name: str
    columns: List[ColumnInfo]
    foreign_keys: List[ForeignKeyInfo]


class SchemaResponse(BaseModel):
    """Response model for database schema."""

    tables: List[TableInfo]


class HistoryEntry(BaseModel):
    """A single query history entry."""

    timestamp: str
    user_query: str
    sql_query: str
    success: bool
    result_preview: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class HistoryResponse(BaseModel):
    """Response model for query history."""

    entries: List[HistoryEntry]
    total: int


class HealthResponse(BaseModel):
    """Response model for health check."""

    status: str
    database: str
    llm_endpoint: str
