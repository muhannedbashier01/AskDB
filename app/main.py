"""FastAPI application entry point."""

import logging

import seqlog
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.routes import router as v1_router
from app.core.config import get_settings

# Get settings for Seq configuration
_settings = get_settings()

# Configure seqlog to send logs to Seq server
seqlog.log_to_seq(
    server_url=_settings.seq_server_url,
    api_key=_settings.seq_api_key or None,
    level=logging.INFO,
    batch_size=10,
    auto_flush_timeout=2,
    override_root_logger=True,
)

# Configure structlog to use standard logging (which seqlog hooks into)
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

# Also configure a formatter for the standard logging to output structured logs
formatter = structlog.stdlib.ProcessorFormatter(
    processor=structlog.dev.ConsoleRenderer(colors=True),
)

# Apply formatter to root logger handlers for console output
for handler in logging.root.handlers:
    if isinstance(handler, logging.StreamHandler):
        handler.setFormatter(formatter)

logger = structlog.get_logger()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application.
    """
    settings = get_settings()

    app = FastAPI(
        title="AskDB",
        description="Natural Language SQL Agent with self-correction",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(v1_router)

    @app.on_event("startup")
    async def startup_event():
        """Log startup information."""
        logger.info(
            "Starting AskDB",
            llm_endpoint=settings.llm_base_url,
            cors_origins=settings.cors_origins_list,
        )

    @app.on_event("shutdown")
    async def shutdown_event():
        """Clean up on shutdown."""
        logger.info("Shutting down AskDB")

    return app


# Create the app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )
