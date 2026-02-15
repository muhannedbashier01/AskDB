"""LLM service for interacting with LM Studio."""

from __future__ import annotations

import json

import structlog
from langchain_openai import ChatOpenAI

from app.core.config import get_settings

logger = structlog.get_logger()


class LLMService:
    """Service for LLM interactions via LM Studio."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
    ):
        """Initialize LLM service.

        Args:
            base_url: LM Studio API URL. If None, uses settings.
            model: Model name. If None, uses settings.
            temperature: Temperature for generation. If None, uses settings.
        """
        settings = get_settings()
        self._base_url = base_url or settings.llm_base_url
        self._model = model or settings.llm_model
        self._temperature = temperature if temperature is not None else settings.llm_temperature
        self._client: ChatOpenAI | None = None

    @property
    def client(self) -> ChatOpenAI:
        """Get or create LangChain ChatOpenAI client."""
        if self._client is None:
            self._client = ChatOpenAI(
                base_url=self._base_url,
                model=self._model,
                temperature=self._temperature,
                api_key="not-needed",  # LM Studio doesn't require API key
            )
        return self._client

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        """Generate text from the LLM.

        Args:
            prompt: The user prompt.
            system_prompt: Optional system prompt.

        Returns:
            Generated text response.
        """
        messages = []
        if system_prompt:
            messages.append(("system", system_prompt))
        messages.append(("human", prompt))

        logger.debug("Generating LLM response", prompt_length=len(prompt))

        response = self.client.invoke(messages)
        return response.content

    def generate_sql(self, user_query: str, schema: str) -> dict[str, str]:
        """Generate SQL from natural language query.

        Returns structured output with the SQL query and optional reasoning.
        Falls back to treating the raw response as SQL if JSON parsing fails.

        Args:
            user_query: Natural language query.
            schema: Database schema description.

        Returns:
            Dict with 'sql' (required) and 'reasoning' (optional) keys.
        """
        from app.core.prompts.sql_agent import SQL_GENERATION_PROMPT, SYSTEM_PROMPT

        system = SYSTEM_PROMPT.format(schema=schema)
        prompt = SQL_GENERATION_PROMPT.format(user_query=user_query)

        raw = self.generate(prompt, system)
        return self._parse_structured_sql(raw)

    def fix_sql(self, user_query: str, sql_query: str, error: str, schema: str) -> dict[str, str]:
        """Fix a failed SQL query.

        Returns structured output with the corrected SQL and optional reasoning.
        Falls back to treating the raw response as SQL if JSON parsing fails.

        Args:
            user_query: Original natural language query.
            sql_query: The SQL query that failed.
            error: The error message.
            schema: Database schema description.

        Returns:
            Dict with 'sql' (required) and 'reasoning' (optional) keys.
        """
        from app.core.prompts.sql_agent import ERROR_CORRECTION_PROMPT, SYSTEM_PROMPT

        system = SYSTEM_PROMPT.format(schema=schema)
        prompt = ERROR_CORRECTION_PROMPT.format(
            user_query=user_query,
            sql_query=sql_query,
            error_message=error,
        )

        raw = self.generate(prompt, system)
        return self._parse_structured_sql(raw)

    def fix_validation_error(
        self, user_query: str, sql_query: str, error: str, schema: str
    ) -> dict[str, str]:
        """Regenerate SQL after a security validation rejection.

        Unlike fix_sql (which handles database execution errors), this method
        tells the LLM that the query was rejected by the validator and was
        never executed, prompting it to produce a compliant SELECT statement.

        Args:
            user_query: Original natural language query.
            sql_query: The SQL query that was rejected.
            error: The validation rejection reason.
            schema: Database schema description.

        Returns:
            Dict with 'sql' (required) and 'reasoning' (optional) keys.
        """
        from app.core.prompts.sql_agent import SYSTEM_PROMPT, VALIDATION_CORRECTION_PROMPT

        system = SYSTEM_PROMPT.format(schema=schema)
        prompt = VALIDATION_CORRECTION_PROMPT.format(
            user_query=user_query,
            sql_query=sql_query,
            error_message=error,
        )

        raw = self.generate(prompt, system)
        return self._parse_structured_sql(raw)

    def _parse_structured_sql(self, raw: str) -> dict[str, str]:
        """Parse structured JSON output from the LLM.

        Expected format: {"sql": "<query>", "reasoning": "<explanation>"}
        Falls back to treating the entire response as raw SQL if parsing fails.

        Args:
            raw: Raw LLM response text.

        Returns:
            Dict with 'sql' (required) and 'reasoning' (optional) keys.
        """
        cleaned = raw.strip()

        # Try JSON parse first
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict) and "sql" in parsed:
                return {
                    "sql": parsed["sql"].strip(),
                    "reasoning": parsed.get("reasoning", ""),
                }
        except (json.JSONDecodeError, TypeError, AttributeError):
            pass

        # Try extracting JSON from markdown code blocks (```json ... ```)
        try:
            if "```json" in cleaned:
                json_block = cleaned.split("```json", 1)[1].split("```", 1)[0]
                parsed = json.loads(json_block.strip())
                if isinstance(parsed, dict) and "sql" in parsed:
                    return {
                        "sql": parsed["sql"].strip(),
                        "reasoning": parsed.get("reasoning", ""),
                    }
        except (json.JSONDecodeError, TypeError, AttributeError, IndexError):
            pass

        # Fallback: treat entire response as raw SQL
        logger.warning("Failed to parse structured SQL output, falling back to raw SQL")
        return {
            "sql": self._clean_sql(cleaned),
            "reasoning": "",
        }

    def _clean_sql(self, sql: str) -> str:
        """Clean generated SQL by removing markdown formatting.

        Args:
            sql: Raw SQL from LLM.

        Returns:
            Cleaned SQL query.
        """
        sql = sql.strip()

        # Remove markdown code blocks
        if sql.startswith("```sql"):
            sql = sql[6:]
        elif sql.startswith("```"):
            sql = sql[3:]

        if sql.endswith("```"):
            sql = sql[:-3]

        return sql.strip()


# Module-level service instance
_llm_service: LLMService | None = None


def get_llm_service() -> LLMService:
    """Get or create LLM service singleton."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
