"""
JarvisOS - Gemini AI Provider

This module provides Google Gemini integration for JarvisOS.

Environment variables:
    GEMINI_API_KEY   -> Google Gemini API key
    GEMINI_MODEL     -> Optional Gemini model name

Example:
    GEMINI_API_KEY=your_api_key_here
    GEMINI_MODEL=gemini-3.8-flash

The provider follows the interface expected by ai_router.py:

    is_available()
    generate()
    chat()
    get_model()
    set_model()
    get_status()
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class GeminiProvider:
    """
    Google Gemini provider for JarvisOS.

    Uses the current Google GenAI Python SDK:

        from google import genai

    The provider is intentionally kept independent from AIRouter so that
    JarvisOS can switch between OpenAI, Gemini and Claude.
    """

    DEFAULT_MODEL = "gemini-3.8-flash"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        """
        Initialize Gemini provider.

        Args:
            api_key:
                Gemini API key. If not supplied, GEMINI_API_KEY is used.

            model:
                Gemini model name. If not supplied, GEMINI_MODEL is used.
        """

        self.api_key = (
            api_key
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
        )

        self.model = (
            model
            or os.getenv("GEMINI_MODEL")
            or self.DEFAULT_MODEL
        )

        self.client: Any = None
        self._initialized = False
        self.last_error: Optional[str] = None

        self._initialize()

    # ------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------

    def _initialize(self) -> None:
        """
        Initialize the Google GenAI client.

        The import is performed here instead of at module level so that
        JarvisOS can still start when the Gemini package is not installed.
        """

        if not self.api_key:
            logger.info(
                "Gemini provider disabled: GEMINI_API_KEY is not configured."
            )
            return

        try:
            from google import genai

            self.client = genai.Client(api_key=self.api_key)

            self._initialized = True
            self.last_error = None

            logger.info(
                "Gemini provider initialized successfully. Model: %s",
                self.model,
            )

        except ImportError:
            self.last_error = (
                "Google GenAI SDK is not installed. "
                "Install it with: pip install google-genai"
            )

            logger.warning(self.last_error)

        except Exception as exc:
            self.last_error = str(exc)

            logger.exception(
                "Failed to initialize Gemini provider: %s",
                exc,
            )

    # ------------------------------------------------------------------
    # AVAILABILITY
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """
        Return True when Gemini is configured and initialized.
        """

        return bool(
            self.api_key
            and self.client is not None
            and self._initialized
        )

    # ------------------------------------------------------------------
    # MODEL
    # ------------------------------------------------------------------

    def get_model(self) -> str:
        """Return the currently selected Gemini model."""

        return self.model

    def set_model(self, model: str) -> None:
        """
        Change the Gemini model.

        Args:
            model: Gemini model name.
        """

        if not model or not model.strip():
            raise ValueError("Gemini model name cannot be empty.")

        self.model = model.strip()

        logger.info(
            "Gemini model changed to: %s",
            self.model,
        )

    # ------------------------------------------------------------------
    # MESSAGE BUILDING
    # ------------------------------------------------------------------

    def _build_contents(
        self,
        prompt: str,
        conversation: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """
        Convert JarvisOS conversation history into a single Gemini prompt.

        Gemini's API supports structured conversation contents, but for the
        provider abstraction used by JarvisOS we create a clean text
        representation. This keeps the AIRouter interface identical across
        providers.

        Args:
            prompt:
                Current user message.

            conversation:
                Previous messages.

        Returns:
            Combined text prompt.
        """

        parts: List[str] = []

        if conversation:
            for message in conversation:
                if not isinstance(message, dict):
                    continue

                role = str(
                    message.get("role", "user")
                ).strip().lower()

                content = message.get("content")

                if content is None:
                    content = message.get("text", "")

                if isinstance(content, list):
                    content = self._flatten_content(content)

                content = str(content).strip()

                if not content:
                    continue

                if role in {"assistant", "model"}:
                    label = "JarvisOS"
                elif role == "system":
                    label = "System"
                else:
                    label = "User"

                parts.append(f"{label}: {content}")

        if prompt and prompt.strip():
            parts.append(f"User: {prompt.strip()}")

        return "\n\n".join(parts)

    @staticmethod
    def _flatten_content(content: List[Any]) -> str:
        """
        Convert list-based message content into text.
        """

        result: List[str] = []

        for item in content:
            if isinstance(item, str):
                result.append(item)
                continue

            if isinstance(item, dict):
                text = item.get("text")

                if text is not None:
                    result.append(str(text))

        return "\n".join(result)

    # ------------------------------------------------------------------
    # GENERATION
    # ------------------------------------------------------------------

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        conversation: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
    ) -> str:
        """
        Generate a response using Gemini.

        Args:
            prompt:
                User's current request.

            system_prompt:
                Optional system instruction for JarvisOS.

            conversation:
                Optional conversation history.

            temperature:
                Generation temperature.

            max_tokens:
                Maximum output token count.

            model:
                Optional model override.

        Returns:
            Generated text.

        Raises:
            RuntimeError:
                If Gemini is not available or generation fails.
        """

        if not self.is_available():
            raise RuntimeError(
                self.last_error
                or "Gemini provider is not available."
            )

        if not prompt or not prompt.strip():
            raise ValueError("Gemini prompt cannot be empty.")

        selected_model = (
            model.strip()
            if model and model.strip()
            else self.model
        )

        contents = self._build_contents(
            prompt=prompt,
            conversation=conversation,
        )

        config_kwargs: Dict[str, Any] = {
            "temperature": temperature,
        }

        if system_prompt and system_prompt.strip():
            config_kwargs["system_instruction"] = system_prompt.strip()

        if max_tokens is not None:
            if max_tokens <= 0:
                raise ValueError(
                    "max_tokens must be greater than zero."
                )

            config_kwargs["max_output_tokens"] = max_tokens

        try:
            from google.genai import types

            config = types.GenerateContentConfig(
                **config_kwargs
            )

            response = self.client.models.generate_content(
                model=selected_model,
                contents=contents,
                config=config,
            )

            text = self._extract_text(response)

            if not text:
                raise RuntimeError(
                    "Gemini returned an empty response."
                )

            self.last_error = None

            logger.debug(
                "Gemini response generated successfully using %s.",
                selected_model,
            )

            return text

        except Exception as exc:
            self.last_error = str(exc)

            logger.exception(
                "Gemini generation failed: %s",
                exc,
            )

            raise RuntimeError(
                f"Gemini generation failed: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # RESPONSE EXTRACTION
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_text(response: Any) -> str:
        """
        Extract text from a Gemini response.

        Handles the standard response.text property and provides
        additional fallbacks for SDK response variations.
        """

        if response is None:
            return ""

        # Standard Google GenAI SDK response.
        try:
            text = getattr(response, "text", None)

            if text:
                return str(text).strip()
        except Exception:
            pass

        # Try candidates -> content -> parts -> text.
        try:
            candidates = getattr(response, "candidates", None)

            if candidates:
                collected: List[str] = []

                for candidate in candidates:
                    content = getattr(
                        candidate,
                        "content",
                        None,
                    )

                    if content is None:
                        continue

                    parts = getattr(
                        content,
                        "parts",
                        None,
                    )

                    if not parts:
                        continue

                    for part in parts:
                        text = getattr(
                            part,
                            "text",
                            None,
                        )

                        if text:
                            collected.append(str(text))

                if collected:
                    return "\n".join(collected).strip()

        except Exception:
            pass

        # Dictionary fallback.
        if isinstance(response, dict):
            text = response.get("text")

            if text:
                return str(text).strip()

            candidates = response.get("candidates", [])

            if isinstance(candidates, list):
                collected = []

                for candidate in candidates:
                    if not isinstance(candidate, dict):
                        continue

                    content = candidate.get(
                        "content",
                        {},
                    )

                    if not isinstance(content, dict):
                        continue

                    parts = content.get(
                        "parts",
                        [],
                    )

                    if not isinstance(parts, list):
                        continue

                    for part in parts:
                        if isinstance(part, dict):
                            text = part.get("text")

                            if text:
                                collected.append(
                                    str(text)
                                )

                if collected:
                    return "\n".join(
                        collected
                    ).strip()

        return ""

    # ------------------------------------------------------------------
    # CHAT
    # ------------------------------------------------------------------

    def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        conversation: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Convenience wrapper around generate().
        """

        return self.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            conversation=conversation,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    # ------------------------------------------------------------------
    # STATUS
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """
        Return provider status information.

        API keys are never returned.
        """

        return {
            "provider": "gemini",
            "available": self.is_available(),
            "initialized": self._initialized,
            "model": self.model,
            "api_key_configured": bool(self.api_key),
            "last_error": self.last_error,
        }

    # ------------------------------------------------------------------
    # TEST
    # ------------------------------------------------------------------

    def test_connection(self) -> Dict[str, Any]:
        """
        Test the Gemini connection with a very small request.

        Returns:
            Dictionary containing success/error information.
        """

        if not self.is_available():
            return {
                "success": False,
                "provider": "gemini",
                "error": (
                    self.last_error
                    or "Gemini provider is not configured."
                ),
            }

        try:
            response = self.generate(
                prompt="Reply with exactly: JARVIS OK",
                temperature=0.0,
                max_tokens=20,
            )

            return {
                "success": True,
                "provider": "gemini",
                "model": self.model,
                "response": response,
            }

        except Exception as exc:
            return {
                "success": False,
                "provider": "gemini",
                "model": self.model,
                "error": str(exc),
            }


# ======================================================================
# DIRECT TEST
# ======================================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    provider = GeminiProvider()

    print("\n" + "=" * 60)
    print("JARVIS OS - GEMINI PROVIDER TEST")
    print("=" * 60)

    status = provider.get_status()

    print(f"Provider: {status['provider']}")
    print(f"Model: {status['model']}")
    print(f"API Key configured: {status['api_key_configured']}")
    print(f"Available: {status['available']}")

    if provider.is_available():
        result = provider.test_connection()

        print("\nConnection test:")
        print(result)
    else:
        print(
            "\nGemini is not configured."
            "\nSet GEMINI_API_KEY in your .env file."
      )
