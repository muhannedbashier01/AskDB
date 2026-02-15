# Backend Dockerfile for AskDB
FROM python:3.11-slim-bookworm

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies for pyodbc and pymssql
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg2 \
    unixodbc \
    unixodbc-dev \
    freetds-dev \
    freetds-bin \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && echo "deb [arch=arm64,amd64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir \
    "langgraph>=0.2.0" \
    "langchain-openai>=0.1.0" \
    "langchain-core>=0.2.0" \
    "fastapi>=0.109.0" \
    "uvicorn[standard]>=0.27.0" \
    "sqlalchemy>=2.0.0" \
    "pyodbc>=5.0.0" \
    "pydantic>=2.0.0" \
    "pydantic-settings>=2.0.0" \
    "structlog>=24.0.0" \
    "python-dotenv>=1.0.0" \
    "seqlog>=0.3.0" \
    "pymssql>=2.2.0" \
    "langfuse>=2.0.0"

# Copy application code
COPY app/ ./app/

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
