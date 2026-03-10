"""LLM service for interacting with language models.

Supports multiple providers (OpenAI-compatible, Anthropic, Google) via
LangChain's BaseChatModel abstraction.
"""

from __future__ import annotations

import json
from typing import Any, Callable

import structlog
from langchain_core.language_models.chat_models import BaseChatModel

from app.core.config import get_settings

# Type alias for the optional generation recording callback.
# Signature: (name, *, model, prompt_messages, response_text, usage, metadata) -> None
GenerationRecorder = Callable[..., None]

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
        generation_recorder: GenerationRecorder | None = None,
    ):
        """Initialize LLM service.

        Args:
            client: Pre-built BaseChatModel instance. If None, one is created
                    from settings using the configured provider.
            model: Model name override. If None, uses settings.
            generation_recorder: Optional callback to record LLM generations
                    for observability. Injected by the tracing layer.
        """
        settings = get_settings()
        self._model = model or settings.llm_model
        self._generation_recorder = generation_recorder
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
        content = response.content

        # Notify the generation recorder (tracing layer) if registered
        if self._generation_recorder:
            usage = self._extract_usage(response)
            self._generation_recorder(
                model=self._model,
                prompt_messages=[{"role": m[0], "content": m[1]} for m in messages],
                response_text=content,
                usage=usage,
            )

        return content

    @staticmethod
    def _extract_usage(response: Any) -> dict[str, int] | None:
        """Extract token usage from LLM response metadata.

        Handles both OpenAI-style (usage_metadata) and Anthropic-style
        (response_metadata.token_usage) response formats.
        """
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            return {
                "input": response.usage_metadata.get("input_tokens", 0),
                "output": response.usage_metadata.get("output_tokens", 0),
            }
        if hasattr(response, "response_metadata"):
            token_usage = response.response_metadata.get("token_usage", {})
            if token_usage:
                return {
                    "input": token_usage.get("prompt_tokens", 0),
                    "output": token_usage.get("completion_tokens", 0),
                }
        return None

    def generate_sql(
        self, user_query: str, schema: str, conversation_context: str = ""
    ) -> dict[str, str]:
        """Generate SQL from natural language query.

        Returns structured output with the SQL query and optional reasoning.
        Falls back to treating the raw response as SQL if JSON parsing fails.

        Args:
            user_query: Natural language query.
            schema: Database schema description.
            conversation_context: Formatted prior exchanges for follow-up resolution.

        Returns:
            Dict with 'sql' (required) and 'reasoning' (optional) keys.
        """
        from app.core.prompts.sql_agent import SQL_GENERATION_PROMPT, SYSTEM_PROMPT

        system = SYSTEM_PROMPT.format(schema=schema)
        if conversation_context:
            system = f"{system}\n\n{conversation_context}"
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

        # Attempt 1: direct JSON parse
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict) and "sql" in parsed:
                return {
                    "sql": parsed["sql"].strip(),
                    "reasoning": parsed.get("reasoning", ""),
                }
        except (json.JSONDecodeError, TypeError, AttributeError) as exc:
            logger.debug("Direct JSON parse failed, trying markdown block", error=str(exc))

        # Attempt 2: extract JSON from ```json ... ``` markdown block
        try:
            if "```json" in cleaned:
                json_block = cleaned.split("```json", 1)[1].split("```", 1)[0]
                parsed = json.loads(json_block.strip())
                if isinstance(parsed, dict) and "sql" in parsed:
                    return {
                        "sql": parsed["sql"].strip(),
                        "reasoning": parsed.get("reasoning", ""),
                    }
        except (json.JSONDecodeError, TypeError, AttributeError, IndexError) as exc:
            logger.debug("Markdown JSON block parse failed, falling back to raw SQL", error=str(exc))

        # Attempt 3: treat entire response as raw SQL (last resort)
        logger.warning("All structured parse attempts failed — using raw SQL fallback")
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
    """Get or create LLM service singleton.

    Wires the tracing service's generation recorder so that every LLM
    call is automatically observed without the LLM service knowing
    about any specific tracing provider.
    """
    global _llm_service
    if _llm_service is None:
        from app.services.tracing import get_tracing_service

        tracing = get_tracing_service()
        _llm_service = LLMService(generation_recorder=tracing.record_generation)
    return _llm_service
