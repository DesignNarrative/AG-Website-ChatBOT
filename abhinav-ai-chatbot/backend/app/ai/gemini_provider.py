"""
Gemini AI provider — uses google-generativeai SDK.

Model selection:
  chat  → gemini-1.5-flash   (fast, cheap, good for chat)
  embed → models/text-embedding-004  (768-dim, best for semantic search)

Environment variables required:
  GEMINI_API_KEY   — from Google AI Studio (aistudio.google.com)
  GEMINI_MODEL     — optional override (default: gemini-1.5-flash)
"""
from __future__ import annotations

import hashlib
import logging
import time
from typing import List, Optional

from app.ai.provider import AIMessage, AIResponse, BaseAIProvider

logger = logging.getLogger(__name__)

EMBED_DIM = 768
DEFAULT_CHAT_MODEL = "gemini-1.5-flash"
EMBED_MODEL = "models/text-embedding-004"


class GeminiProvider(BaseAIProvider):
    """Google Gemini provider using the google-generativeai SDK."""

    provider_name = "gemini"

    def __init__(self, api_key: str, model: str = DEFAULT_CHAT_MODEL) -> None:
        self._api_key = api_key
        self._model_name = model
        self._client = None  # lazy-init; imported inside methods to avoid import at module load
        self._embed_cache: dict[str, list[float]] = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_client(self):
        """Lazy-load and configure the genai client."""
        if self._client is None:
            try:
                import google.generativeai as genai  # type: ignore
                genai.configure(api_key=self._api_key)
                self._client = genai.GenerativeModel(self._model_name)
            except ImportError:
                raise RuntimeError(
                    "google-generativeai is not installed. "
                    "Run: pip install google-generativeai"
                )
        return self._client

    def _build_gemini_history(
        self, messages: List[AIMessage]
    ) -> tuple[str | None, list[dict]]:
        """
        Splits message list into:
          - system_prompt (first message if role == 'system')
          - history list of {'role': 'user'|'model', 'parts': [text]}
        Gemini uses 'model' instead of 'assistant' for the bot role.
        """
        system_prompt: Optional[str] = None
        history: list[dict] = []

        for msg in messages:
            if msg.role == "system":
                system_prompt = msg.content
            elif msg.role == "user":
                history.append({"role": "user", "parts": [msg.content]})
            elif msg.role == "assistant":
                history.append({"role": "model", "parts": [msg.content]})

        return system_prompt, history

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
        """Send a chat request to Gemini and return a structured response."""
        import asyncio

        start = time.monotonic()

        try:
            import google.generativeai as genai  # type: ignore
            from google.generativeai.types import HarmBlockThreshold, HarmCategory  # type: ignore

            genai.configure(api_key=self._api_key)

            # Merge system prompt into message list
            full_messages: List[AIMessage] = []
            sp = system_prompt or ""
            # Prepend system prompt as a user→model pair (Gemini doesn't have native system role)
            if sp:
                full_messages.append(AIMessage(role="user", content=f"[SYSTEM INSTRUCTIONS]\n{sp}\n[/SYSTEM INSTRUCTIONS]\n\nAcknowledge the instructions and say you are ready."))
                full_messages.append(AIMessage(role="assistant", content="Understood. I am ready to assist with Abhinav Group property enquiries."))
            full_messages.extend(messages)

            _, history = self._build_gemini_history(full_messages)

            # Generation config
            generation_config = genai.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                candidate_count=1,
            )

            # Safety settings — reduce over-refusal for property questions
            safety_settings = {
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            }

            model = genai.GenerativeModel(
                self._model_name,
                generation_config=generation_config,
                safety_settings=safety_settings,
            )

            # Build chat and send last user message
            if len(history) > 1:
                chat_session = model.start_chat(history=history[:-1])
                last_content = history[-1]["parts"][0]
                # Run in executor so we don't block the event loop
                response = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: chat_session.send_message(last_content)
                )
            else:
                last_content = history[0]["parts"][0] if history else "Hello"
                response = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: model.generate_content(last_content)
                )

            content = response.text.strip() if response.text else ""
            elapsed_ms = int((time.monotonic() - start) * 1000)

            return AIResponse(
                content=content,
                model=self._model_name,
                provider=self.provider_name,
                is_fallback=False,
                response_time_ms=elapsed_ms,
                tokens_used=None,  # Gemini SDK doesn't always expose token counts
            )

        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.error("Gemini chat error: %s", exc, exc_info=True)
            return AIResponse(
                content=(
                    "I'm having trouble connecting to my AI service right now. "
                    "Please try again in a moment, or call us at +91 9890393838."
                ),
                model=self._model_name,
                provider=self.provider_name,
                is_fallback=True,
                response_time_ms=elapsed_ms,
            )

    async def embed(self, text: str) -> List[float]:
        """Return a 768-dim embedding vector for text using text-embedding-004."""
        import asyncio

        # Cache based on hash
        cache_key = hashlib.md5(text.encode()).hexdigest()
        if cache_key in self._embed_cache:
            return self._embed_cache[cache_key]

        try:
            import google.generativeai as genai  # type: ignore

            genai.configure(api_key=self._api_key)

            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: genai.embed_content(
                    model=EMBED_MODEL,
                    content=text,
                    task_type="RETRIEVAL_DOCUMENT",
                )
            )
            embedding = result["embedding"]  # list of 768 floats
            self._embed_cache[cache_key] = embedding
            return embedding

        except Exception as exc:
            logger.error("Gemini embed error: %s", exc, exc_info=True)
            # Return zero vector on failure so the system degrades gracefully
            return [0.0] * EMBED_DIM

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple texts. Calls embed() for each (Gemini SDK batch is limited)."""
        results = []
        for text in texts:
            embedding = await self.embed(text)
            results.append(embedding)
        return results
