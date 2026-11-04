"""
Gemini AI provider — uses Google Generative Language REST API via httpx.
Model selection with automatic quota fallback:
  primary   → gemini-3.5-flash-lite
  fallback  → gemini-flash-lite-latest, gemini-3.5-flash
  embed     → gemini-embedding-001
"""
from __future__ import annotations

import hashlib
import logging
import time
from typing import List, Optional

import httpx
from app.ai.provider import AIMessage, AIResponse, BaseAIProvider

logger = logging.getLogger(__name__)

DEFAULT_CHAT_MODEL = "gemini-3.5-flash-lite"
CANDIDATE_CHAT_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-3.5-flash",
]
EMBED_MODEL = "gemini-embedding-001"
BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiProvider(BaseAIProvider):
    """Google Gemini provider using direct REST API with automatic multi-model fallback."""

    provider_name = "gemini"

    def __init__(self, api_key: str, model: str = DEFAULT_CHAT_MODEL) -> None:
        self._api_key = api_key
        self._model_name = model or DEFAULT_CHAT_MODEL
        self._embed_cache: dict[str, list[float]] = {}

    def _build_contents(self, messages: List[AIMessage], system_prompt: Optional[str] = None):
        contents = []

        if system_prompt:
            contents.append({
                "role": "user",
                "parts": [{
                    "text": (
                        f"[SYSTEM INSTRUCTIONS]\n{system_prompt}\n[/SYSTEM INSTRUCTIONS]\n"
                        "Please acknowledge and strictly follow these property sales guidelines."
                    )
                }]
            })
            contents.append({
                "role": "model",
                "parts": [{"text": "Understood. I will act strictly according to the Abhinav Group property sales instructions."}]
            })

        for msg in messages:
            role = "user" if msg.role in ("user", "system") else "model"
            contents.append({
                "role": role,
                "parts": [{"text": msg.content}]
            })

        return contents

    async def chat(
        self,
        messages: List[AIMessage],
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> AIResponse:
        start = time.monotonic()
        contents = self._build_contents(messages, system_prompt)
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            }
        }

        # Candidate models to try in sequence if one hits rate limits (429) or high traffic (503)
        models_to_try = [self._model_name] + [m for m in CANDIDATE_CHAT_MODELS if m != self._model_name]

        last_error = ""
        for model in models_to_try:
            url = f"{BASE_URL}/{model}:generateContent?key={self._api_key}"
            try:
                async with httpx.AsyncClient(timeout=35.0) as client:
                    res = await client.post(url, json=payload)

                    if res.status_code == 200:
                        data = res.json()
                        content = ""
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts:
                                content = parts[0].get("text", "").strip()

                        elapsed_ms = int((time.monotonic() - start) * 1000)
                        usage = data.get("usageMetadata", {})
                        tokens = usage.get("totalTokenCount")

                        return AIResponse(
                            content=content,
                            model=model,
                            provider=self.provider_name,
                            is_fallback=False,
                            response_time_ms=elapsed_ms,
                            tokens_used=tokens,
                        )

                    # If 429 or 503, log warning and try the next candidate model
                    if res.status_code in (429, 503, 404):
                        logger.warning("Gemini model %s returned status %s; trying next model...", model, res.status_code)
                        last_error = f"HTTP {res.status_code}: {res.text[:200]}"
                        continue

                    # Other non-200 error
                    logger.error("Gemini API error on %s: %s %s", model, res.status_code, res.text[:200])
                    last_error = f"HTTP {res.status_code}"
                    break

            except Exception as exc:
                logger.warning("Gemini exception on %s: %s; trying next model...", model, str(exc))
                last_error = str(exc)
                continue

        # If all candidates failed, return standard polite sales escalation
        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.error("All Gemini candidate models failed. Last error: %s", last_error)
        return AIResponse(
            content=(
                "Thank you for contacting Abhinav Group. "
                "For immediate assistance with our projects, please call our sales team directly at +91 9890393838 "
                "or email sales@abhinavinfra.com."
            ),
            model=self._model_name,
            provider=self.provider_name,
            is_fallback=True,
            response_time_ms=elapsed_ms,
        )

    async def embed(self, text: str) -> List[float]:
        cache_key = hashlib.md5(text.encode()).hexdigest()
        if cache_key in self._embed_cache:
            return self._embed_cache[cache_key]

        url = f"{BASE_URL}/{EMBED_MODEL}:embedContent?key={self._api_key}"
        payload = {"content": {"parts": [{"text": text}]}}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    values = res.json().get("embedding", {}).get("values", [])
                    if values:
                        self._embed_cache[cache_key] = values
                        return values
        except Exception as exc:
            logger.error("Gemini embed exception: %s", str(exc))

        return [0.0] * 768

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        results = []
        for t in texts:
            emb = await self.embed(t)
            results.append(emb)
        return results
