# AskDB Troubleshooting Guide

## Common Issues & Fixes

### LLM Not Generating Valid JSON
**Symptom**: `_parse_structured_sql` falls through to raw SQL fallback
**Cause**: Model not following JSON format instructions
**Fix**:
- Check `LLM_TEMPERATURE` is 0.0 (deterministic)
- Strengthen JSON instruction in `SYSTEM_PROMPT` in `app/core/prompts/sql_agent.py`
- Try a more capable model
- Check Langfuse generation output to see what the LLM actually returned

### SQL Validation Rejecting Valid Queries
**Symptom**: Valid SELECT query rejected, `error_type: "validation"`
**Cause**: Forbidden pattern regex matching inside column names or string literals
**Example**: Column named `CreatedBy` triggers `CREATE` pattern
**Fix**: Make regex patterns more precise in `app/core/agent/validation.py`, e.g. use `\bCREATE\s+(TABLE|DATABASE|INDEX|VIEW|PROCEDURE)\b` instead of bare `\bCREATE\b`

### Query Timeout
**Symptom**: SQL execution fails after `QUERY_TIMEOUT_SECONDS`
**Cause**: Query too complex or missing indexes, large result set
**Fix**:
- Check `inject_top_clause` is adding TOP limit correctly
- Increase `QUERY_TIMEOUT_SECONDS` in `.env`
- Add index hints in prompts for known slow patterns
- Review the generated SQL in Langfuse/Seq for missing JOINs or full scans

### Database Connection Failures
**Symptom**: `/health` returns `"degraded"`, connection errors
**Fix**:
- Verify `DATABASE_URL` format: `mssql+pyodbc://user:pass@host:port/db?driver=ODBC+Driver+17+for+SQL+Server`
- Check ODBC driver installed: `odbcinst -j` and `odbcinst -q -d`
- Test with `pymssql` as alternative: `mssql+pymssql://user:pass@host:port/db`
- Verify network connectivity to SQL Server from container/host
- Check `pool_pre_ping=True` is set in `db_service.py`

### Vehicle Names Showing NULL
**Symptom**: Vehicle make/model columns are NULL in results
**Cause**: Using English columns (`VehicleModelNameEnglish`) which are ALL NULL
**Fix**: Ensure prompts enforce Arabic columns. Check `SYSTEM_PROMPT` vehicle rules.

### Max Retries Exhausted
**Symptom**: `"Failed to execute query after 3 attempts"` response
**Debug**:
1. Check Langfuse trace for all 3 attempts
2. Look at `error_type` per attempt (validation vs execution)
3. If validation errors: the LLM keeps generating forbidden patterns
4. If execution errors: the LLM can't fix the SQL syntax/semantics
5. Consider increasing `MAX_RETRY_ATTEMPTS` or improving prompts

### Langfuse Not Capturing Traces
**Fix**:
- Verify `LANGFUSE_ENABLED=true` (not "True" — Pydantic parses bool)
- Check `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` set correctly
- Verify `LANGFUSE_BASE_URL` is reachable from the backend
- Check `langfuse_service.py` — all functions silently no-op on errors

### Frontend Not Connecting to Backend
**Fix**:
- In dev: Vite proxies `/api` to `http://localhost:8000` — check `vite.config.ts`
- In Docker: Check `CORS_ORIGINS` includes frontend URL
- Verify backend is running: `curl http://localhost:8000/api/v1/health`

### IsCancelled Filter Missing
**Symptom**: Results include cancelled policies, inflating counts
**Cause**: LLM forgot to add `ISNULL(IsCancelled, 0) = 0`
**Fix**: This is the #1 business rule — if it keeps being missed, add it as a post-processing step in `execute_sql` node or as a SQL transformation before execution.

## Debugging Workflow

1. **Get the trace_id** from the API response
2. **Check Seq** (http://localhost:5341): Filter by `trace_id` to see full request lifecycle
3. **Check Langfuse** (http://localhost:3000): Find trace, inspect:
   - `generate_sql` span: See LLM input/output, token usage
   - `validate_sql` span: See if validation passed
   - `execute_sql` span: See SQL sent to DB and result
   - `format_response` span: See summary generation
4. **Check attempt count**: Multiple attempts mean errors occurred — look at each attempt's error

## Performance Tuning

- **Schema caching**: `db_service.get_schema()` caches results. Call `get_schema(refresh=True)` to bust cache
- **Connection pooling**: `pool_pre_ping=True`, `pool_recycle=3600` in `db_service.py`
- **Result limits**: `DEFAULT_RESULT_LIMIT=1000`, `MAX_RESULT_LIMIT=1000` prevent runaway queries
- **Frontend pagination**: 20 rows/page, only renders visible page
- **LLM temperature**: 0.0 for deterministic, reproducible SQL generation
