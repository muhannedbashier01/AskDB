# AskDB Feature Backlog

## High Impact — Low Effort

- [x] **1. Conversational Memory** — Follow-up queries referencing previous context ("now filter that by last week"). Redis-backed sessions with context injection into LLM prompts. *(IN PROGRESS)*

- [ ] **2. Export Results** — CSV/Excel download button. Users get results but can't use them outside the UI. Backend: `csv.writer` endpoint. Frontend: download link.

- [ ] **3. Saved/Bookmarked Queries** — Save frequently asked questions ("daily policy count") and re-run with one click. Persist to Redis or DB.

- [ ] **4. Query Suggestions** — Show 4-5 example questions on empty chat based on schema. Removes "what can I ask?" friction for new users.

## High Impact — Medium Effort

- [ ] **5. Auto-Visualization** — Detect when results suit a chart (time series → line, categories → bar, single number → stat card). Render automatically with `recharts`.

- [ ] **6. Streaming Response** — Stream stages to UI: "Generating SQL..." → show SQL → "Executing..." → show results → "Summarizing..." → show summary. SSE or WebSocket.

- [ ] **7. User Feedback Loop** — Thumbs up/down per response. Store (query, SQL, feedback) tuples. Use negatives as few-shot corrections in prompts. Agent improves over time.

- [ ] **8. Scheduled Reports** — "Send me policy count every morning at 9am." Cron + agent pipeline + email/Slack webhook. Turns Q&A into reporting.

## Medium Impact — Production-Ready

- [ ] **9. Multi-Tenant / Role-Based Access** — Different users see different tables. Filter `POLICIES_TABLES` per role. Sales user shouldn't query leasing internals.

- [ ] **10. Query Cost Estimation** — Before executing, estimate if query is expensive (full scan, no WHERE, huge JOINs). Warn user or auto-add filters.

- [ ] **11. Read Replica Routing** — Point agent at read replica instead of production. One config change for safety.

- [ ] **12. Caching Layer** — Same NL question asked twice returns cached results (with TTL). Redis LRU. Saves LLM calls and DB load.

## Nice-to-Have — Differentiators

- [ ] **13. Voice Input** — Web Speech API → text → existing pipeline. Low effort, high demo impact.

- [ ] **14. SQL Explanation Mode** — "Explain this query" button. LLM breaks down generated SQL in plain language. Builds trust with non-technical users.

- [ ] **15. Schema Explorer UI** — Visual ERD or interactive table browser. Already have `/api/v1/schema` — just render it.

- [ ] **16. Slack/Teams Bot** — Wrap `/api/v1/query` in a bot. Users ask questions in chat without opening another tool.
