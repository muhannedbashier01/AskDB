# AskDB Architecture Deep Reference

## LangGraph State Machine

### State Flow Diagram
```
                    +--------------+
                    |    START     |
                    +------+-------+
                           |
                    +------v-------+
              +---->| generate_sql |<----+
              |     +------+-------+     |
              |            |             |
              |     +------v-------+     |
              |     | validate_sql |     |
              |     +------+-------+     |
              |            |             |
              |    +-------v--------+    |
              |    | route_after_   |    |
              |    | validation     |    |
              |    +--+----+----+---+    |
              |       |    |    |        |
              |  error |   | valid  max_retry
              |       |    |    |        |
              |       |    |    +--------+----> format_error -> END
              |       |    |
              |       |    +------v-------+
              |       |    | execute_sql  |
              |       |    +------+-------+
              |       |           |
              |       |   +-------v--------+
              |       |   | route_after_   |
              |       |   | execution      |
              |       |   +--+----+----+---+
              |       |      |    |    |
              |       |  err |    | ok    max_retry
              |       |      |    |    |
              |       |      |    |    +---> format_error -> END
              |       |      |    |
              |       |      |    +----> format_response -> END
              |       |      |
              +-------+------+
              (handle_error)
```

### AgentState Fields
```python
class AgentState(TypedDict):
    trace_id: str              # UUID hex for log/trace correlation
    user_query: str            # Original NL question
    sql_query: str             # Generated/corrected SQL
    reasoning: str             # LLM's chain-of-thought
    execution_result: Any      # {columns, rows, row_count} or None
    error_message: str         # Last error description
    error_type: str            # "" | "validation" | "execution"
    attempt_count: int         # Current attempt (incremented in generate_sql)
    is_complete: bool          # True when workflow finished
    final_response: dict       # Formatted API response
```

### Retry Logic
- `max_retry_attempts` (default 3) is configured in `app/core/config.py`
- `generate_sql` increments `attempt_count` at the start
- Routing checks `attempt_count < max_retry_attempts` to decide retry vs give up
- Two error paths:
  - **Validation errors**: LLM told query was "rejected by security validator, never executed"
  - **Execution errors**: LLM told query "was executed and failed" with DB error message

## Request Lifecycle

1. **HTTP Layer** (`routes.py`): FastAPI receives POST `/api/v1/query`, validates with Pydantic
2. **Agent Entry** (`graph.py:run_agent`): Creates initial state, binds structlog trace_id, wraps in Langfuse trace
3. **SQL Generation** (`nodes.py:generate_sql`): Calls LLM with schema context and business rules
4. **Validation** (`validation.py`): Regex-based read-only enforcement
5. **Execution** (`sql_executor.py`): Runs against MSSQL, injects TOP clause, handles timeouts
6. **Summary** (`nodes.py:format_response`): LLM generates NL summary of results
7. **Response**: JSON with sql_query, columns, rows, row_count, attempts, trace_id, summary

## SQL Executor Details

### TOP Clause Injection (`inject_top_clause`)
- Skips pure aggregations: queries with COUNT/SUM/AVG/MIN/MAX but no GROUP BY
- Detects user-specified limits from NL patterns: "top N", "first N", "limit N", "last N", etc.
- Enforces `max_result_limit` (1000) even if user asks for more
- Handles `SELECT DISTINCT` → `SELECT DISTINCT TOP N`
- Default limit: `default_result_limit` (1000)

### Result Serialization
Custom JSON serialization in executor:
- `datetime`/`date` → ISO format string
- `Decimal` → `float`
- `bytes` → hex string
- `timedelta` → `str()`

## Multi-Provider LLM Architecture

```
Settings (config.py)
    |
    v
_create_chat_model(provider, base_url, model, temperature, api_key)
    |
    +-- "openai"    --> ChatOpenAI (langchain-openai)
    +-- "anthropic" --> ChatAnthropic (langchain-anthropic)
    +-- "google"    --> ChatGoogleGenerativeAI (langchain-google-genai)
    |
    v
LLMService
    |-- generate(prompt, system_prompt)        -> str
    |-- generate_sql(user_query, schema)       -> {sql, reasoning}
    |-- fix_sql(user_query, sql, error, schema) -> {sql, reasoning}
    |-- fix_validation_error(...)              -> {sql, reasoning}
    +-- _parse_structured_sql(raw)             -> {sql, reasoning}
```

## Database Schema Tables

Core tables loaded via `POLICIES_TABLES` filter:

| Table | Purpose |
|-------|---------|
| PurchasedPolicyDetail | Core aggregate - policy records, counts, dates |
| PurchasedPolicyInfo | Extended policy metadata |
| PurchasedPolicyVehicleInformation | Vehicle details per policy (IDs only, no names) |
| LeasingPurchaseTracking | Leasing flow tracking |
| LeasingContract | Leasing contract data |
| VehiclePlateTypeMaster | Plate type lookup |
| VehicleColorMaster | Color lookup |
| VehicleMakeMaster | Vehicle make lookup (Arabic names) |
| VehicleModelMaster | Vehicle model lookup (Arabic names) |
| InsuranceCompany | Insurance company lookup |

## Observability Stack

### Langfuse (Optional)
- **Root trace**: Per-request in `graph.py` via `langfuse_trace()`
- **Spans**: Per-node in `nodes.py` via `langfuse_span()`
- **Generations**: Per-LLM-call in `llm_service.py` via `langfuse_generation()`
- Context propagation via `contextvars` (`_current_root_span`, `_current_span`)
- All wrappers are no-ops when `langfuse_enabled=False`

### Seq Structured Logging
- All logs go to Seq via `seqlog`
- `structlog.contextvars` binds `trace_id` per request
- Every log line includes trace_id for correlation

## Docker Stack

```
docker-compose.yml
├── backend (FastAPI, port 8000)
├── fronnd (Nginx, port 80)
├── seq (Logging UI, ports 5341/5342)
└── langfuse stack
    ├── langfuse (Web UI, port 3000)
    ├── langfuse-worker
    ├── langfuse-postgres
    ├── langfuse-clickhouse
    ├── langfuse-redis
    └── langfuse-minio
```
