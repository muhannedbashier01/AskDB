# AskDB

A natural-language-to-SQL agent that converts plain English questions into executable SQL queries and returns results — powered by LangGraph, FastAPI, and React.

---

## What It Does

Type a question like *"How many active policies were created last month?"* and AskDB:
1. Generates SQL using an LLM (with your database schema as context)
2. Validates the query (read-only enforcement)
3. Executes it against your MSSQL database
4. Returns results with a natural language summary

Supports **conversational memory** (follow-up questions), **self-correction** (retries on SQL errors), and full **observability** via Langfuse and Seq.

---

## Architecture

```
User Query
    │
    ▼
FastAPI (/api/v1/query)
    │
    ▼
LangGraph Agent
    ├── generate_sql   → LLM generates SQL from NL + schema
    ├── validate_sql   → Read-only regex enforcement
    ├── execute_sql    → Runs on MSSQL
    │       └── on error: retry up to 3x with error context
    └── format_response → Results + summary returned
```

**Stack:**
- **Backend**: Python 3.11, FastAPI, LangGraph, LangChain, SQLAlchemy
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS
- **Database**: Microsoft SQL Server (MSSQL via pymssql/pyodbc)
- **Memory**: Redis (conversational session history)
- **Tracing**: Langfuse (LLM observability)
- **Logging**: Seq (structured logs via structlog)

---

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Access to your MSSQL database
- An LLM endpoint (local via LM Studio, or OpenAI/Anthropic/Google API key)

### 1. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```env
# LLM (example: local LM Studio)
LLM_PROVIDER=openai
LLM_BASE_URL=http://host.docker.internal:1234/v1
LLM_MODEL=qwen2.5-coder-7b-instruct-mlx
LLM_API_KEY=lm-studio

# Database
DATABASE_URL=mssql+pymssql://user:password@host:port/YourDatabase
```

### 2. Start all services

```bash
docker-compose up -d
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| Langfuse | http://localhost:3000 |
| Seq Logging | http://localhost:5342 |

### 3. Local development

```bash
# Backend (terminal 1)
pip install -e ".[dev]"
uvicorn app.main:app --reload

# Frontend (terminal 2)
cd frontend && npm install && npm run dev
```

Or use the provided scripts:

```bash
./scripts/start-all.sh   # Start everything
./scripts/stop-all.sh    # Stop everything
```

---

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/query` | POST | Submit a natural language query |
| `/api/v1/schema` | GET | Get database schema |
| `/api/v1/history` | GET | Query history (paginated) |
| `/api/v1/health` | GET | Health check |
| `/api/v1/session/{id}` | DELETE | Clear conversation session |

**Example request:**

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "How many policies were created this year?", "session_id": "my-session"}'
```

**Example response:**

```json
{
  "success": true,
  "sql_query": "SELECT COUNT(*) AS PolicyCount FROM PurchasedPolicyDetail WHERE YEAR(Createdon) = YEAR(GETDATE()) AND ISNULL(IsCancelled, 0) = 0",
  "columns": ["PolicyCount"],
  "rows": [[1423]],
  "row_count": 1,
  "attempts": 1,
  "summary": "There are 1,423 active policies created this year.",
  "session_id": "my-session"
}
```

---

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `openai` | LLM provider: `openai`, `anthropic`, `google` |
| `LLM_BASE_URL` | — | Custom base URL (for local models) |
| `LLM_MODEL` | — | Model name |
| `LLM_TEMPERATURE` | `0` | Generation temperature (0 = deterministic) |
| `DATABASE_URL` | — | SQLAlchemy connection string |
| `MAX_RETRY_ATTEMPTS` | `3` | SQL generation retries on failure |
| `QUERY_TIMEOUT_SECONDS` | `30` | Query execution timeout |
| `DEFAULT_RESULT_LIMIT` | `10` | Default TOP N rows |
| `MAX_RESULT_LIMIT` | `50` | Maximum rows returned |
| `CONVERSATION_MEMORY_LIMIT` | `5` | Prior exchanges passed to LLM |
| `SESSION_TTL_MINUTES` | `60` | Redis session TTL |
| `REDIS_URL` | — | Redis connection URL |
| `LANGFUSE_ENABLED` | `true` | Enable LLM tracing |
| `SEQ_SERVER_URL` | — | Seq log ingestion URL |

---

## Project Structure

```
AskDB/
├── app/
│   ├── api/v1/          # REST endpoints & schemas
│   ├── core/
│   │   ├── agent/       # LangGraph nodes, graph, state, validation
│   │   ├── prompts/     # LLM prompt templates
│   │   └── config.py    # Pydantic settings
│   └── services/
│       ├── db_service.py        # Database + schema introspection
│       ├── llm_service.py       # Multi-provider LLM wrapper
│       ├── session_service.py   # Redis-backed memory
│       └── tracing/             # Langfuse observability
├── frontend/
│   └── src/
│       ├── components/  # ChatInterface, ResultsTable, SqlPreview, ...
│       ├── hooks/       # useQuery, useAutoScroll
│       └── services/    # API client
├── tests/
├── evals/
├── docker-compose.yml
└── .env.example
```

---

## License

MIT
