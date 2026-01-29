"""LLM service for interacting with LM Studio."""

from __future__ import annotations

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

    def generate_sql(self, user_query: str, schema: str) -> str:
        """Generate SQL from natural language query.

        Args:
            user_query: Natural language query.
            schema: Database schema description.

        Returns:
            Generated SQL query.
        """
        from app.core.prompts.sql_agent import SQL_GENERATION_PROMPT, SYSTEM_PROMPT

        system = SYSTEM_PROMPT.format(schema=schema)
        prompt = SQL_GENERATION_PROMPT.format(user_query=user_query)

        sql = self.generate(prompt, system)
        return self._clean_sql(sql)

    def fix_sql(self, user_query: str, sql_query: str, error: str, schema: str) -> str:
        """Fix a failed SQL query.

        Args:
            user_query: Original natural language query.
            sql_query: The SQL query that failed.
            error: The error message.
            schema: Database schema description.

        Returns:
            Corrected SQL query.
        """
        from app.core.prompts.sql_agent import ERROR_CORRECTION_PROMPT, SYSTEM_PROMPT

        system = SYSTEM_PROMPT.format(schema=schema)
        prompt = ERROR_CORRECTION_PROMPT.format(
            user_query=user_query,
            sql_query=sql_query,
            error_message=error,
        )

        sql = self.generate(prompt, system)
        return self._clean_sql(sql)

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
