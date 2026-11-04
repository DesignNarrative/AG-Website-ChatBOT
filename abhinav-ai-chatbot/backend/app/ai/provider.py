"""
Abhinav Group AI Chatbot — AI Provider Interface
Abstraction layer that supports Gemini, OpenAI, and Mock providers.
Switching providers only requires changing AI_PROVIDER in .env.
"""
from __future__ import annotations

import abc
import time
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class AIMessage:
    role: str  # "user" | "assistant" | "system"
    content: str


@dataclass
class AIResponse:
    content: str
    model: str
    response_time_ms: int
    is_fallback: bool = False
    provider: str = "unknown"
    tokens_used: Optional[int] = None


class BaseAIProvider(abc.ABC):
    """Abstract base class for all AI providers."""

    @abc.abstractmethod
    async def chat(
        self,
        messages: List[AIMessage],
        system_prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.1,
    ) -> AIResponse:
        """Send a conversation to the AI and get a response."""
        ...

    @abc.abstractmethod
    async def embed(self, text: str) -> List[float]:
        """Generate a vector embedding for a text string."""
        ...

    @abc.abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate vector embeddings for multiple texts."""
        ...

    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        """Return the name of this provider for logging."""
        ...


class MockAIProvider(BaseAIProvider):
    """
    Mock AI provider for development and testing.
    Returns deterministic responses without calling any external API.
    Used when AI_PROVIDER=mock in .env.
    """

    MOCK_EMBEDDING_DIM = 768  # Matches Google text-embedding-004

    # Canned responses for common property chatbot intents
    _RESPONSES = {
        "greeting": (
            "Hello! Welcome to Abhinav Group. I'm your property assistant. "
            "How can I help you today?\n\n"
            "You can ask me about:\n"
            "• Our residential projects (Samsara, Pebbles Greenfield, The Curve)\n"
            "• Commercial spaces (Aeromall)\n"
            "• Project configurations, locations, and amenities\n"
            "• General real estate questions"
        ),
        "greeting_hi": (
            "नमस्ते! अभिनव ग्रुप में आपका स्वागत है। मैं आपका प्रॉपर्टी असिस्टेंट हूं। "
            "आज मैं आपकी कैसे मदद कर सकता हूं?\n\n"
            "आप मुझसे पूछ सकते हैं:\n"
            "• हमारे आवासीय प्रोजेक्ट्स के बारे में\n"
            "• प्रोजेक्ट की कॉन्फ़िगरेशन और कीमतें\n"
            "• सामान्य रियल एस्टेट जानकारी"
        ),
        "projects_list": (
            "Abhinav Group currently has these active projects:\n\n"
            "**Residential:**\n"
            "1. 🏠 **Samsara** — Mukund Nagar, Pune | 3 BHK luxury residences\n"
            "2. 🏠 **Pebbles Greenfield** — Tathawade/Wakad, Pune | 2 & 3 BHK\n"
            "3. 🏠 **The Curve** — Virar West, Mumbai | 2 & 3 BHK\n\n"
            "**Commercial:**\n"
            "4. 🏢 **Aeromall** — Airport Road, Lohegaon, Pune\n\n"
            "Which project would you like to know more about?"
        ),
        "out_of_scope": (
            "I'm here specifically to help with Abhinav Group's property enquiries. "
            "I can answer questions about our projects, configurations, locations, amenities, "
            "and general real estate topics.\n\n"
            "For other matters, please contact us at:\n"
            "📞 +91 9890393838\n"
            "🌐 abhinavgroup.co.in"
        ),
        "fallback": (
            "I'm sorry, I'm having trouble understanding that right now. "
            "Could you rephrase your question?\n\n"
            "Or you can speak to our sales team directly:\n"
            "📞 +91 9890393838\n"
            "Available Monday to Saturday, 10 AM to 7 PM"
        ),
        "ai_unavailable": (
            "Our AI assistant is temporarily unavailable. "
            "Please contact our sales team directly:\n"
            "📞 +91 9890393838\n"
            "📧 sales@abhinavinfra.com\n\n"
            "We apologise for the inconvenience."
        ),
    }

    async def chat(
        self,
        messages: List[AIMessage],
        system_prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.1,
    ) -> AIResponse:
        start = time.monotonic()
        last_user_msg = ""
        for m in reversed(messages):
            if m.role == "user":
                last_user_msg = m.content.lower()
                break

        # Simple keyword routing for mock responses
        if any(w in last_user_msg for w in ["hello", "hi", "namaste", "hey", "start"]):
            if any(w in last_user_msg for w in ["नमस्ते", "हैलो", "नमस्कार"]):
                content = self._RESPONSES["greeting_hi"]
            else:
                content = self._RESPONSES["greeting"]
        elif any(w in last_user_msg for w in ["project", "property", "flat", "home", "apartment",
                                               "प्रोजेक्ट", "फ्लैट", "घर"]):
            content = self._RESPONSES["projects_list"]
        elif any(w in last_user_msg for w in ["career", "job", "vendor", "supplier", "contractor"]):
            content = self._RESPONSES["out_of_scope"]
        else:
            content = (
                "[MOCK AI RESPONSE] This is a mock response. "
                f"Your message was: '{last_user_msg[:100]}'. "
                "Replace AI_PROVIDER=mock with gemini or openai in .env to get real AI responses."
            )

        elapsed_ms = int((time.monotonic() - start) * 1000) + 50  # simulate network
        return AIResponse(
            content=content,
            model="mock-v1",
            tokens_used=len(content.split()),
            response_time_ms=elapsed_ms,
            is_fallback=False,
            provider="mock",
        )

    async def embed(self, text: str) -> List[float]:
        """Return a deterministic mock embedding (all zeros — not suitable for real search)."""
        import hashlib
        # Create a deterministic but fake embedding based on text hash
        h = int(hashlib.sha256(text.encode()).hexdigest(), 16)
        dim = self.MOCK_EMBEDDING_DIM
        return [(((h >> i) & 0xFF) / 255.0 - 0.5) for i in range(dim)]

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [await self.embed(t) for t in texts]

    @property
    def provider_name(self) -> str:
        return "mock"


def get_ai_provider() -> BaseAIProvider:
    """
    Factory: returns the configured AI provider based on AI_PROVIDER env var.

    Supported values:
      mock   — no API key required; deterministic canned responses (default)
      gemini — requires GEMINI_API_KEY; uses gemini-1.5-flash + text-embedding-004
      openai — requires OPENAI_API_KEY; uses gpt-4o-mini + text-embedding-3-small

    Falls back to mock automatically if the provider fails to initialise.
    """
    from app.core.config import get_settings
    s = get_settings()
    provider = s.ai_provider

    if provider == "gemini":
        api_key = getattr(s, "gemini_api_key", None)
        if not api_key:
            import structlog
            structlog.get_logger().warning(
                "gemini_key_missing_falling_back_to_mock",
                hint="Set GEMINI_API_KEY in .env",
            )
            return MockAIProvider()
        try:
            from app.ai.gemini_provider import GeminiProvider
            model = getattr(s, "gemini_chat_model", "gemini-3.5-flash")
            return GeminiProvider(api_key=api_key, model=model)
        except Exception as exc:
            import structlog
            structlog.get_logger().warning("gemini_init_error", error=str(exc))
            return MockAIProvider()

    elif provider == "openai":
        api_key = getattr(s, "openai_api_key", None)
        if not api_key:
            import structlog
            structlog.get_logger().warning(
                "openai_key_missing_falling_back_to_mock",
                hint="Set OPENAI_API_KEY in .env",
            )
            return MockAIProvider()
        try:
            from app.ai.openai_provider import OpenAIProvider
            model = getattr(s, "openai_chat_model", "gpt-4o-mini")
            return OpenAIProvider(api_key=api_key, model=model)
        except Exception as exc:
            import structlog
            structlog.get_logger().warning("openai_init_error", error=str(exc))
            return MockAIProvider()

    # Default / "mock"
    return MockAIProvider()
