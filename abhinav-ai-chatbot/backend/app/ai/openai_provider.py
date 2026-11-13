"""
OpenAI AI provider — uses openai SDK v1.x.

Model selection:
  chat  → gpt-4o-mini       (fast, affordable)
  embed → text-embedding-3-small  (1536-dim, projected to 768 for compatibility)

Environment variables required:
  OPENAI_API_KEY   — from platform.openai.com
  OPENAI_MODEL     — optional override (default: gpt-4o-mini)
"""
from __future__ import annotations

import hashlib
import logging
import time
from typing import List, Optional

from app.ai.provider import AIMessage, AIResponse, BaseAIProvider

logger = logging.getLogger(__name__)

EMBED_DIM = 768
DEFAULT_CHAT_MODEL = "gpt-4o-mini"
EMBED_MODEL = "text-embedding-3-small"
# Dimension we request from text-embedding-3-small (supports custom dims ≤ 1536)
EMBED_DIMENSIONS = 768


class OpenAIProvider(BaseAIProvider):
    """OpenAI provider using the openai v1.x SDK."""

    provider_name = "openai"

    def __init__(self, api_key: str, model: str = DEFAULT_CHAT_MODEL) -> None:
        self._api_key = api_key
        self._model_name = model
        self._embed_cache: dict[str, list[float]] = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_openai_messages(
        self, messages: List[AIMessage], system_prompt: Optional[str]
    ) -> list[dict]:
        """Convert our AIMessage list to the OpenAI message format."""
        result: list[dict] = []
        if system_prompt:
            result.append({"role": "system", "content": system_prompt})
        for msg in messages:
            if msg.role == "system":
                # Already handled above; skip duplicate system messages
                continue
            role = "assistant" if msg.role == "assistant" else msg.role
            result.append({"role": role, "content": msg.content})
        return result

    # ------------------------------------------------------------------
    # BaseAIProvider interface
    # ------------------------------------------------------------------

    async def chat(
        self,
        messages: List[AIMessage],
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> AIResponse:
        """Send a chat request to OpenAI and return a structured response."""
        import asyncio

        start = time.monotonic()

        try:
            from openai import AsyncOpenAI  # type: ignore

            client = AsyncOpenAI(api_key=self._api_key)
            openai_messages = self._build_openai_messages(messages, system_prompt)

            response = await client.chat.completions.create(
                model=self._model_name,
                messages=openai_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            content = response.choices[0].message.content or ""
            content = content.strip()
            elapsed_ms = int((time.monotonic() - start) * 1000)
            tokens = (
                response.usage.total_tokens if response.usage else None
            )

            return AIResponse(
                content=content,
                model=self._model_name,
                provider=self.provider_name,
                is_fallback=False,
                response_time_ms=elapsed_ms,
                tokens_used=tokens,
            )

        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.error("OpenAI chat error: %s", exc, exc_info=True)
            return AIResponse(
                content=(
                    "I'm having trouble connecting right now. "
                    "Please try again in a moment, or call us at +91 9309505388."
                ),
                model=self._model_name,
                provider=self.provider_name,
                is_fallback=True,
                response_time_ms=elapsed_ms,
            )

    async def embed(self, text: str) -> List[float]:
        """Return a 768-dim embedding vector using text-embedding-3-small."""
        # Cache based on hash
        cache_key = hashlib.md5(text.encode()).hexdigest()
        if cache_key in self._embed_cache:
            return self._embed_cache[cache_key]

        try:
            from openai import AsyncOpenAI  # type: ignore

            client = AsyncOpenAI(api_key=self._api_key)
            response = await client.embeddings.create(
                model=EMBED_MODEL,
                input=text,
                dimensions=EMBED_DIMENSIONS,
            )
            embedding = response.data[0].embedding
            self._embed_cache[cache_key] = embedding
            return embedding

        except Exception as exc:
            logger.error("OpenAI embed error: %s", exc, exc_info=True)
            return [0.0] * EMBED_DIM

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple texts in a single API call."""
        try:
            from openai import AsyncOpenAI  # type: ignore

            client = AsyncOpenAI(api_key=self._api_key)
            response = await client.embeddings.create(
                model=EMBED_MODEL,
                input=texts,
                dimensions=EMBED_DIMENSIONS,
            )
            return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]

        except Exception as exc:
            logger.error("OpenAI batch embed error: %s", exc, exc_info=True)
            return [[0.0] * EMBED_DIM for _ in texts]
