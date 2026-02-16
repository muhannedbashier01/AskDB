"""LLM service for interacting with language models.

Supports multiple providers (OpenAI-compatible, Anthropic, Google) via
LangChain's BaseChatModel abstraction.
"""

from __future__ import annotations

import json

import structlog
from langchain_core.language_models.chat_models import BaseChatModel

from app.core.config import get_settings

logger = structlog.get_logger()


def _create_chat_model(
    provider: str,
    base_url: str,
    model: str,
    temperature: float,
    api_key: str,
) -> BaseChatModel:
    """Factory function that creates the appropriate LangChain chat model.

    Args:
        provider: Provider name ("openai", "anthropic", "google").
        base_url: API base URL.
        model: Model name.
        temperature: Temperature for generation.
        api_key: API key.

    Returns:
        A concrete BaseChatModel instance.

    Raises:
        ValueError: If the provider is not supported.
    """
    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            base_url=base_url,
            model=model,
            temperature=temperature,
            api_key=api_key or "not-needed",
        )

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model_name=model,
            temperature=temperature,
            api_key=api_key,
        )

    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=model,
            temperature=temperature,
            google_api_key=api_key,
        )

    raise ValueError(
        f"Unsupported LLM provider: '{provider}'. "
        f"Supported providers: openai, anthropic, google"
    )


class LLMService:
    """Service for LLM interactions via any LangChain-supported provider."""

    def __init__(
        self,
        client: BaseChatModel | None = None,
        model: str | None = None,
    ):
        """Initialize LLM service.

        Args:
            client: Pre-built BaseChatModel instance. If None, one is created
                    from settings using the configured provider.
            model: Model name override (used for Langfuse logging). If None,
                   uses settings.
        """
        settings = get_settings()
        self._model = model or settings.llm_model
        self._client = client or _create_chat_model(
            provider=settings.llm_provider,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            api_key=settings.llm_api_key,
        )

    @property
    def client(self) -> BaseChatModel:
        """Get the LangChain chat model client."""
        return self._client

    def generate(self, prompt: str, system_prompt: str | None = None, *, generation_name: str = "llm-generate") -> str:
        """Generate text from the LLM.

        Args:
            prompt: The user prompt.
            system_prompt: Optional system prompt.
            generation_name: Name for the Langfuse generation observation.

        Returns:
            Generated text response.
        """
        from app.services.langfuse_service import langfuse_generation

        messages = []
        if system_prompt:
            messages.append(("system", system_prompt))
        messages.append(("human", prompt))

        logger.debug("Generating LLM response", prompt_length=len(prompt))

        response = self.client.invoke(messages)
        content = response.content

        # Record the LLM call in Langfuse
        usage = {}
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            usage = {
                "input": response.usage_metadata.get("input_tokens", 0),
                "output": response.usage_metadata.get("output_tokens", 0),
            }
        elif hasattr(response, "response_metadata"):
            token_usage = response.response_metadata.get("token_usage", {})
            if token_usage:
                usage = {
                    "input": token_usage.get("prompt_tokens", 0),
                    "output": token_usage.get("completion_tokens", 0),
                }

        langfuse_generation(
            name=generation_name,
            model=self._model,
            input={"messages": [{"role": m[0], "content": m[1][:500]} for m in messages]},
            output=content[:1000] if content else "",
            usage=usage if usage else None,
        )

        return content

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

        raw = self.generate(prompt, system, generation_name="generate-sql")
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

        raw = self.generate(prompt, system, generation_name="fix-sql")
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

        raw = self.generate(prompt, system, generation_name="fix-validation-error")
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

    def generate_visualizations(
        self,
        user_query: str,
        columns: list[str],
        rows: list[dict],
        row_count: int,
    ) -> list[dict]:
        """Generate Vega-Lite chart specs for query results.

        Calls the LLM with a sample of the data and expects a JSON response
        containing visualization specifications. Returns an empty list on any
        failure so the main response is never broken.
        """
        from app.core.prompts.sql_agent import VISUALIZATION_PROMPT

        try:
            sample_rows = rows[:30]
            sample_text = json.dumps(sample_rows, default=str, indent=2)

            prompt = VISUALIZATION_PROMPT.format(
                user_query=user_query,
                columns=columns,
                row_count=row_count,
                sample_count=len(sample_rows),
                sample_rows=sample_text,
            )

            raw = self.generate(prompt, generation_name="generate-visualizations")
            cleaned = raw.strip()

            # Try direct JSON parse
            try:
                parsed = json.loads(cleaned)
                if isinstance(parsed, dict) and "visualizations" in parsed:
                    return parsed["visualizations"]
            except (json.JSONDecodeError, TypeError):
                pass

            # Try extracting from markdown code block
            if "```" in cleaned:
                for marker in ("```json", "```"):
                    if marker in cleaned:
                        block = cleaned.split(marker, 1)[1].split("```", 1)[0]
                        try:
                            parsed = json.loads(block.strip())
                            if isinstance(parsed, dict) and "visualizations" in parsed:
                                return parsed["visualizations"]
                        except (json.JSONDecodeError, TypeError):
                            continue

            logger.warning("Failed to parse visualization response")
            return []

        except Exception:
            logger.warning("Failed to generate visualizations", exc_info=True)
            return []


# Module-level service instance
_llm_service: LLMService | None = None


def get_llm_service() -> LLMService:
    """Get or create LLM service singleton."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
