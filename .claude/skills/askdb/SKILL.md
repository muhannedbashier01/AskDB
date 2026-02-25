---
name: askdb
description: Expert assistant for developing, debugging, and extending the AskDB natural-language-to-SQL agent. Use when working on agent logic, LLM prompts, SQL generation, validation, database connectivity, API routes, frontend components, observability, or configuration. Covers architecture decisions, coding patterns, domain rules, and troubleshooting.
argument-hint: [task-description]
allowed-tools: Read, Grep, Glob, Bash(python *), Bash(npm *), Bash(docker *), Bash(docker-compose *), Bash(uv *), Bash(pip *), Bash(git *)
---

# AskDB Agent Development Skill

You are an expert on the **AskDB** agent — a production natural-language-to-T-SQL system built with **FastAPI + LangGraph + React**. Use this knowledge to help develop, debug, and extend the agent.

## Architecture Overview

```
User (React Chat UI)
  |
  v
FastAPI  POST /api/v1/query
  |
  v
LangGraph State Machine (AgentState):
  generate_sql -> validate_sql -> [route]
                                   |
                          valid -> execute_sql -> [route]
                                   |                |
                        invalid -> handle_error   success -> format_response -> END
                                                    |
                                           retry -> handle_error -> generate_sql
                                                    |
                                           max   -> format_error -> END
```

## Key Files

| Purpose | Path |
|---------|------|
| FastAPI entry | `app/main.py` |
| Config & settings | `app/core/config.py` |
| LangGraph graph | `app/core/agent/graph.py` |
| Agent nodes | `app/core/agent/nodes.py` |
| Agent state | `app/core/agent/state.py` |
| SQL validation | `app/core/agent/validation.py` |
| LLM prompts | `app/core/prompts/sql_agent.py` |
| SQL executor | `app/core/tools/sql_executor.py` |
| LLM service | `app/services/llm_service.py` |
| DB service | `app/services/db_service.py` |
| Langfuse service | `app/services/langfuse_service.py` |
| API routes | `app/api/v1/routes.py` |
| API schemas | `app/api/v1/schemas.py` |
| Frontend app | `frontend/src/App.tsx` |
| Chat interface | `frontend/src/components/ChatInterface.tsx` |
| Message bubble | `frontend/src/components/MessageBubble.tsx` |
| Results table | `frontend/src/components/ResultsTable.tsx` |
| Query hook | `frontend/src/hooks/useQuery.ts` |
| API service | `frontend/src/services/api.ts` |
| CLI tool | `cli.py` |

## Coding Patterns

### Singletons
All services use module-level singletons with `get_*()` factory functions:
```python
_llm_service: LLMService | None = None
def get_llm_service() -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
```
Follow this pattern for any new service.

### LangGraph Nodes
Every node function takes `AgentState` and returns `dict[str, Any]` (partial state update):
```python
def my_node(state: AgentState) -> dict[str, Any]:
    with langfuse_span("my_node", input={...}) as span:
        # logic
        if span is not None:
            span.update(output={...})
    return {"field": value}
```

### Routing Functions
Conditional edges use router functions that return the next node name as a string:
```python
def route_after_something(state: AgentState) -> str:
    if state["some_condition"]:
        return "next_node"
    return "fallback_node"
```

### LLM Output Parsing
The LLM is prompted to return JSON `{"sql": "...", "reasoning": "..."}`. Parsing has 3 fallback tiers:
1. Direct `json.loads()`
2. Extract from ` ```json ``` ` markdown blocks
3. Raw SQL cleanup (strip markdown fences)

### Langfuse Integration
Always wrap observable logic in context managers:
- `langfuse_trace(trace_id, user_query=...)` for top-level request
- `langfuse_span("name", input={...})` for sub-operations
- `langfuse_generation(name=..., model=..., input=..., output=..., usage=...)` for LLM calls
These are no-ops when Langfuse is disabled — safe to use unconditionally.

### Structured Logging
Use `structlog` everywhere. Bind trace_id at request scope:
```python
structlog.contextvars.bind_contextvars(trace_id=trace_id)
```

## Domain-Specific Business Rules (CRITICAL)

These rules are baked into `app/core/prompts/sql_agent.py` and must be maintained:

1. **Cancellation filter**: ALWAYS `ISNULL(IsCancelled, 0) = 0` (not just `IsCancelled = 0` — misses NULLs)
2. **Policy counting**: `COUNT(*)` from `PurchasedPolicyDetail` (never count PolicyNumber — has duplicates/NULLs)
3. **Date filtering**: Use `Createdon` column (NOT `PolicyIssuedDate`)
4. **Vehicle names**: MUST use Arabic columns (`VehicleModelNameArabic`, `VehicleMakeNameArabic`) — English columns are ALL NULL
5. **Vehicle joins**: Names are NOT in `PurchasedPolicyVehicleInformation` — must JOIN through `VehicleModelMaster` and `VehicleMakeMaster`
6. **Policyholder identity**: Use `PolicyHolderUniqueId` (national ID/iqama), NOT `PolicyHolderId`
7. **Renewals**: `COUNT(*) WHERE IsRenew = 1` from `PurchasedPolicyDetail`, NOT from `LeasingPurchaseTracking`
8. **Leasing tracking**: Only use `LeasingPurchaseTracking` for actual leasing tracking queries

## SQL Validation Rules

File: `app/core/agent/validation.py`

- Query MUST start with `SELECT`
- No semicolons (blocks multi-statement)
- Comments are stripped before validation
- Forbidden: DROP, DELETE, UPDATE, INSERT, TRUNCATE, ALTER, CREATE, EXEC/EXECUTE, GRANT, REVOKE, MERGE, xp_*, sp_*, OPENROWSET, OPENDATASOURCE, BULK

When adding new validation rules, add to `_FORBIDDEN_PATTERNS` list as `(re.compile(...), "description")`.

## Multi-Provider LLM Configuration

Supported in `app/services/llm_service.py` via `_create_chat_model()`:

| Provider | Class | Key Config |
|----------|-------|------------|
| `openai` | `ChatOpenAI` | `base_url`, `model`, `api_key` (covers LM Studio, OpenAI, any OpenAI-compatible) |
| `anthropic` | `ChatAnthropic` | `model_name`, `api_key` |
| `google` | `ChatGoogleGenerativeAI` | `model`, `google_api_key` |

To add a new provider: add a new `if provider == "name"` branch in `_create_chat_model()`.

## Configuration (.env)

All settings in `app/core/config.py` via `pydantic-settings`:
- `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_MODEL`, `LLM_TEMPERATURE`, `LLM_API_KEY`
- `DATABASE_URL` (MSSQL connection string)
- `MAX_RETRY_ATTEMPTS` (default: 3), `QUERY_TIMEOUT_SECONDS` (default: 30)
- `DEFAULT_RESULT_LIMIT` / `MAX_RESULT_LIMIT` (default: 1000)
- `API_HOST`, `API_PORT`, `CORS_ORIGINS`
- `SEQ_SERVER_URL`, `SEQ_API_KEY`
- `LANGFUSE_ENABLED`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL`

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v1/query` | Submit NL query, get SQL + results |
| GET | `/api/v1/schema` | Get database schema |
| GET | `/api/v1/history?limit=50` | Get query history |
| GET | `/api/v1/health` | Health check (DB + LLM status) |

## Database

- **Target**: Microsoft SQL Server (T-SQL)
- **Driver**: `pyodbc` (primary) or `pymssql` (alternative)
- **ORM**: SQLAlchemy with `create_engine()`, connection pooling (`pool_pre_ping=True`, `pool_recycle=3600`)
- **Schema introspection**: Via `INFORMATION_SCHEMA` queries in `db_service.py`
- **Table filter**: Only loads tables listed in `POLICIES_TABLES` (config.py)

## Frontend

- React 18 + TypeScript + Vite + Tailwind CSS
- Dark theme (gray-900 base)
- Chat-style interface with `ChatInterface` > `MessageBubble` > `SqlPreview` / `ResultsTable` / `SummaryPreview`
- `useQuery` hook manages messages, loading state, API calls
- Vite proxies `/api` to `localhost:8000`
- Results table: sortable columns, 20 rows/page pagination, truncated values with tooltips

## Common Development Tasks

### Adding a new agent node
1. Define function in `app/core/agent/nodes.py` following the pattern
2. Add node to graph in `app/core/agent/graph.py` via `graph.add_node()`
3. Wire edges with `graph.add_edge()` or `graph.add_conditional_edges()`
4. Update `AgentState` in `state.py` if new fields needed

### Modifying prompts
Edit `app/core/prompts/sql_agent.py`. The system prompt includes `{schema}` placeholder that gets filled with live DB schema. Business rules are in the system prompt — keep them accurate.

### Adding a new API endpoint
1. Add Pydantic models in `app/api/v1/schemas.py`
2. Add route in `app/api/v1/routes.py`
3. Router is auto-included via `app/main.py`

### Adding a new LLM provider
Add branch in `_create_chat_model()` in `app/services/llm_service.py`. Install the corresponding `langchain-*` package.

### Debugging SQL generation
1. Check Langfuse traces (if enabled) for full LLM input/output
2. Check Seq logs for structured trace_id correlation
3. Look at `attempt_count` and `error_type` in response to understand retry behavior
4. The `reasoning` field in responses shows LLM's chain of thought

Now use this knowledge to help with: $ARGUMENTS
