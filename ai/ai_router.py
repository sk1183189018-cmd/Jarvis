"""
JARVIS OS - AI Router

Provides a single interface for multiple AI providers.

Supported providers:
- OpenAI
- Google Gemini
- Anthropic Claude

The router can:
- Select a provider
- Use a configured default provider
- Fall back to another provider when possible
- Keep provider-specific code outside the brain
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


logger = logging.getLogger("JarvisOS.AIRouter")


@dataclass
class AIResponse:
    """Standard response returned by every AI provider."""

    text: str
    provider: str
    model: str = ""
    raw: Any = None


class AIRouter:
    """
    Routes AI requests to the selected AI provider.

    Environment variables:

        AI_PROVIDER=openai

    Supported values:

        openai
        gemini
        claude
        auto
    """

    SUPPORTED_PROVIDERS = {
        "openai",
        "gemini",
        "claude",
        "auto",
    }

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:

        self.provider_name = (
            provider
            or os.getenv("AI_PROVIDER", "auto")
        ).strip().lower()

        self.model = model or os.getenv("AI_MODEL", "")

        self.providers: Dict[str, Any] = {}

        self._load_providers()

    # ========================================================
    # PROVIDER LOADING
    # ========================================================

    def _load_providers(self) -> None:
        """Load available provider implementations."""

        # OpenAI
        try:
            from ai.openai_provider import OpenAIProvider

            self.providers["openai"] = OpenAIProvider()

            logger.info("OpenAI provider loaded.")

        except Exception as exc:
            logger.warning(
                "OpenAI provider unavailable: %s",
                exc,
            )

        # Gemini
        try:
            from ai.gemini_provider import GeminiProvider

            self.providers["gemini"] = GeminiProvider()

            logger.info("Gemini provider loaded.")

        except Exception as exc:
            logger.warning(
                "Gemini provider unavailable: %s",
                exc,
            )

        # Claude
        try:
            from ai.claude_provider import ClaudeProvider

            self.providers["claude"] = ClaudeProvider()

            logger.info("Claude provider loaded.")

        except Exception as exc:
            logger.warning(
                "Claude provider unavailable: %s",
                exc,
            )

    # ========================================================
    # PROVIDER SELECTION
    # ========================================================

    def available_providers(self) -> List[str]:
        """Return currently loaded providers."""

        return list(self.providers.keys())

    def is_provider_available(self, provider: str) -> bool:
        """Check whether a provider is available."""

        return provider.lower() in self.providers

    def set_provider(self, provider: str) -> None:
        """
        Change the active AI provider.

        Example:

            router.set_provider("gemini")
        """

        provider = provider.strip().lower()

        if provider not in self.SUPPORTED_PROVIDERS:
            raise ValueError(
                f"Unsupported AI provider: {provider}. "
                f"Supported providers: "
                f"{', '.join(sorted(self.SUPPORTED_PROVIDERS))}"
            )

        self.provider_name = provider

        logger.info(
            "AI provider changed to %s.",
            provider,
        )

    # ========================================================
    # AUTO SELECTION
    # ========================================================

    def _get_auto_provider(self) -> Optional[str]:
        """
        Select the first usable provider.

        Priority:

            OpenAI
            Gemini
            Claude
        """

        priority = [
            "openai",
            "gemini",
            "claude",
        ]

        for name in priority:

            provider = self.providers.get(name)

            if provider is None:
                continue

            try:
                if provider.is_available():
                    return name

            except Exception as exc:
                logger.warning(
                    "Could not check %s provider: %s",
                    name,
                    exc,
                )

        return None

    # ========================================================
    # ACTIVE PROVIDER
    # ========================================================

    def _get_active_provider(self) -> tuple[str, Any]:
        """Return active provider name and provider object."""

        if self.provider_name == "auto":

            selected = self._get_auto_provider()

            if selected is None:
                raise RuntimeError(
                    "No AI provider is currently available. "
                    "Configure an API key in .env."
                )

            return selected, self.providers[selected]

        provider = self.providers.get(self.provider_name)

        if provider is None:
            raise RuntimeError(
                f"AI provider '{self.provider_name}' "
                f"is not available."
            )

        try:
            if not provider.is_available():
                raise RuntimeError(
                    f"AI provider '{self.provider_name}' "
                    f"is not configured."
                )

        except AttributeError:
            # Providers without is_available() are still usable.
            pass

        return self.provider_name, provider

    # ========================================================
    # GENERATE
    # ========================================================

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        conversation: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> AIResponse:
        """
        Generate an AI response.

        Parameters:

            prompt:
                User's current request.

            system_prompt:
                Optional system instruction.

            conversation:
                Previous conversation messages.

            temperature:
                Controls response randomness.

            max_tokens:
                Maximum output length when supported.
        """

        if not isinstance(prompt, str):
            raise TypeError("prompt must be a string.")

        prompt = prompt.strip()

        if not prompt:
            raise ValueError("prompt cannot be empty.")

        provider_name, provider = self._get_active_provider()

        logger.info(
            "Sending request to AI provider: %s",
            provider_name,
        )

        try:

            result = provider.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                conversation=conversation,
                temperature=temperature,
                max_tokens=max_tokens,
                model=self.model or None,
            )

            return self._normalize_response(
                result=result,
                provider_name=provider_name,
            )

        except Exception as exc:

            logger.exception(
                "AI provider '%s' failed.",
                provider_name,
            )

            # Auto mode can attempt another provider.
            if self.provider_name == "auto":

                return self._fallback_generate(
                    failed_provider=provider_name,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    conversation=conversation,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

            raise RuntimeError(
                f"AI request failed using "
                f"{provider_name}: {exc}"
            ) from exc

    # ========================================================
    # FALLBACK
    # ========================================================

    def _fallback_generate(
        self,
        failed_provider: str,
        prompt: str,
        system_prompt: Optional[str],
        conversation: Optional[List[Dict[str, str]]],
        temperature: float,
        max_tokens: Optional[int],
    ) -> AIResponse:
        """Try another available provider."""

        logger.warning(
            "Attempting AI fallback after %s failure.",
            failed_provider,
        )

        priority = [
            "openai",
            "gemini",
            "claude",
        ]

        errors: List[str] = []

        for name in priority:

            if name == failed_provider:
                continue

            provider = self.providers.get(name)

            if provider is None:
                continue

            try:

                if hasattr(provider, "is_available"):
                    if not provider.is_available():
                        continue

                result = provider.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    conversation=conversation,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    model=self.model or None,
                )

                logger.info(
                    "Fallback provider '%s' succeeded.",
                    name,
                )

                return self._normalize_response(
                    result=result,
                    provider_name=name,
                )

            except Exception as exc:

                errors.append(
                    f"{name}: {exc}"
                )

                logger.warning(
                    "Fallback provider '%s' failed: %s",
                    name,
                    exc,
                )

        details = "; ".join(errors)

        raise RuntimeError(
            "All configured AI providers failed."
            + (f" Details: {details}" if details else "")
        )

    # ========================================================
    # NORMALIZATION
    # ========================================================

    @staticmethod
    def _normalize_response(
        result: Any,
        provider_name: str,
    ) -> AIResponse:
        """
        Convert provider-specific responses into AIResponse.
        """

        if isinstance(result, AIResponse):
            return result

        if isinstance(result, str):

            return AIResponse(
                text=result.strip(),
                provider=provider_name,
            )

        if isinstance(result, dict):

            text = (
                result.get("text")
                or result.get("content")
                or result.get("response")
                or ""
            )

            model = result.get(
                "model",
                "",
            )

            return AIResponse(
                text=str(text).strip(),
                provider=provider_name,
                model=str(model),
                raw=result,
            )

        # Provider may return an object.
        text = getattr(
            result,
            "text",
            None,
        )

        if text is None:

            text = getattr(
                result,
                "content",
                None,
            )

        if text is None:
            text = str(result)

        model = getattr(
            result,
            "model",
            "",
        )

        return AIResponse(
            text=str(text).strip(),
            provider=provider_name,
            model=str(model),
            raw=result,
        )

    # ========================================================
    # SIMPLE CHAT
    # ========================================================

    def chat(
        self,
        message: str,
        conversation: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """
        Simple chat interface.

        Returns only the generated text.
        """

        response = self.generate(
            prompt=message,
            conversation=conversation,
        )

        return response.text

    # ========================================================
    # STATUS
    # ========================================================

    def status(self) -> Dict[str, Any]:
        """Return AI system status."""

        available = {}

        for name, provider in self.providers.items():

            try:

                if hasattr(provider, "is_available"):
                    available[name] = bool(
                        provider.is_available()
                    )
                else:
                    available[name] = True

            except Exception:
                available[name] = False

        return {
            "selected_provider": self.provider_name,
            "model": self.model,
            "loaded_providers": list(
                self.providers.keys()
            ),
            "available_providers": [
                name
                for name, value in available.items()
                if value
            ],
            "providers": available,
        }


# ============================================================
# TEST / DIRECT EXECUTION
# ============================================================

if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s | "
            "%(levelname)s | "
            "%(name)s | "
            "%(message)s"
        ),
    )

    router = AIRouter()

    print("\nJARVIS OS - AI Router")
    print("-" * 40)

    status = router.status()

    print(
        f"Selected provider: "
        f"{status['selected_provider']}"
    )

    print(
        f"Loaded providers: "
        f"{', '.join(status['loaded_providers']) or 'None'}"
    )

    print(
        f"Available providers: "
        f"{', '.join(status['available_providers']) or 'None'}"
          )
