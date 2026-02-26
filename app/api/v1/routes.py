"""API routes for the SQL agent."""

import structlog
from fastapi import APIRouter, HTTPException

from app.api.v1.schemas import (
    HealthResponse,
    HistoryResponse,
    QueryRequest,
    QueryResponse,
    SchemaResponse,
)
from app.core.agent.graph import run_agent
from app.core.config import get_settings
from app.services.db_service import get_db_service, get_history
from app.services.session_service import get_session_service

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1", tags=["v1"])


@router.post("/query", response_model=QueryResponse)
async def submit_query(request: QueryRequest) -> QueryResponse:
    """Submit a natural language query and get SQL results.

    Args:
        request: Query request with natural language query.

    Returns:
        Query response with SQL and results.
    """
    logger.info("Received query", query=request.query[:50])

    try:
        result = await run_agent(request.query, session_id=request.session_id or "")
        return QueryResponse(**result)
    except Exception as e:
        logger.exception("Query processing failed")
        raise HTTPException(
            status_code=500,
            detail=f"Query processing failed: {str(e)}",
        ) from e


@router.get("/schema", response_model=SchemaResponse)
async def get_schema() -> SchemaResponse:
    """Get database schema.

    Returns:
        Database schema with tables, columns, and relationships.
    """
    logger.info("Fetching schema")

    try:
        db = get_db_service()
        schema_dict = db.get_schema_dict()
        return SchemaResponse(**schema_dict)
    except Exception as e:
        logger.exception("Failed to fetch schema")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch schema: {str(e)}",
        ) from e


@router.get("/history", response_model=HistoryResponse)
async def get_query_history(limit: int = 50) -> HistoryResponse:
    """Get query history.

    Args:
        limit: Maximum number of entries to return.

    Returns:
        Query history entries.
    """
    logger.info("Fetching history", limit=limit)

    history = get_history(limit=limit)
    return HistoryResponse(
        entries=history,
        total=len(history),
    )


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint.

    Returns:
        Health status of the service.
    """
    settings = get_settings()
    db = get_db_service()

    db_success, db_msg = db.test_connection()

    return HealthResponse(
        status="healthy" if db_success else "degraded",
        database="connected" if db_success else f"error: {db_msg}",
        llm_endpoint=settings.llm_base_url,
    )


@router.delete("/session/{session_id}")
async def clear_session(session_id: str) -> dict[str, str]:
    """Clear a conversation session.

    Args:
        session_id: The session ID to clear.

    Returns:
        Status of the operation.
    """
    logger.info("Clearing session", session_id=session_id)
    session_svc = get_session_service()
    deleted = session_svc.delete_session(session_id)
    return {"status": "deleted" if deleted else "not_found"}
