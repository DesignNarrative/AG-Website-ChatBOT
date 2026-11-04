"""
Gemini AI provider — uses Google Generative Language REST API via httpx.
Model selection:
  chat  → gemini-3.5-flash
  embed → gemini-embedding-001
"""
from __future__ import annotations

import hashlib
import logging
import time
from typing import List, Optional

import httpx
from app.ai.provider import AIMessage, AIResponse, BaseAIProvider

logger = logging.getLogger(__name__)

DEFAULT_CHAT_MODEL = "gemini-3.5-flash"
EMBED_MODEL = "gemini-embedding-001"
BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiProvider(BaseAIProvider):
    """Google Gemini provider using direct REST API for maximum reliability and speed."""

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
                "parts": [{"text": f"[SYSTEM INSTRUCTIONS]\n{system_prompt}\n[/SYSTEM INSTRUCTIONS]\nPlease acknowledge and follow these instructions."}]
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
        url = f"{BASE_URL}/{self._model_name}:generateContent?key={self._api_key}"

        contents = self._build_contents(messages, system_prompt)
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            }
        }

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.post(url, json=payload)

                if res.status_code != 200:
                    logger.error("gemini_api_error", status_code=res.status_code, body=res.text)
                    elapsed_ms = int((time.monotonic() - start) * 1000)
                    return AIResponse(
                        content=(
                            "Thank you for contacting Abhinav Group. "
                            "For immediate assistance, please connect with our sales team directly at +91 9890393838."
                        ),
                        model=self._model_name,
                        provider=self.provider_name,
                        is_fallback=True,
                        response_time_ms=elapsed_ms,
                    )

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
                    model=self._model_name,
                    provider=self.provider_name,
                    is_fallback=False,
                    response_time_ms=elapsed_ms,
                    tokens_used=tokens,
                )

        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.error("gemini_chat_exception", error=str(exc))
            return AIResponse(
                content=(
                    "Thank you for contacting Abhinav Group. "
                    "For immediate assistance with our projects, please call our sales office at +91 9890393838."
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
            logger.error("gemini_embed_exception", error=str(exc))

        return [0.0] * 768

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        results = []
        for t in texts:
            emb = await self.embed(t)
            results.append(emb)
        return results
