"""
JARVIS OS - OpenAI Provider

This module provides the OpenAI implementation used by
ai_router.py.

Environment variables:

    OPENAI_API_KEY
    OPENAI_MODEL

Example:

    OPENAI_API_KEY=your_api_key
    OPENAI_MODEL=gpt-5.6-luna
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional


logger = logging.getLogger("JarvisOS.OpenAI")


class OpenAIProvider:
    """
    OpenAI provider for JARVIS OS.

    Uses the official OpenAI Python SDK.

    The provider intentionally exposes a small common interface:

        is_available()
        generate()
    """

    DEFAULT_MODEL = "gpt-5.6-luna"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:

        self.api_key = (
            api_key
            or os.getenv("OPENAI_API_KEY", "")
        ).strip()

        self.model = (
            model
            or os.getenv(
                "OPENAI_MODEL",
                self.DEFAULT_MODEL,
            )
        ).strip()

        self.client = None

        self._initialize_client()

    # ========================================================
    # CLIENT INITIALIZATION
    # ========================================================

    def _initialize_client(self) -> None:
        """
        Initialize the OpenAI client.

        The application can start without an API key.
        The actual AI request will only work after a key
        has been configured.
        """

        if not self.api_key:
            logger.warning(
                "OPENAI_API_KEY is not configured."
            )
            return

        try:
            from openai import OpenAI

            self.client = OpenAI(
                api_key=self.api_key
            )

            logger.info(
                "OpenAI client initialized."
            )

        except ImportError:
            logger.error(
                "OpenAI package is not installed."
            )

            self.client = None

        except Exception as exc:
            logger.exception(
                "Failed to initialize OpenAI client: %s",
                exc,
            )

            self.client = None

    # ========================================================
    # AVAILABILITY
    # ========================================================

    def is_available(self) -> bool:
        """
        Return True when the OpenAI provider is configured
        and the client is ready.
        """

        return (
            bool(self.api_key)
            and self.client is not None
        )

    # ========================================================
    # MODEL
    # ========================================================

    def get_model(self) -> str:
        """Return the currently configured model."""

        return self.model

    def set_model(self, model: str) -> None:
        """Change the OpenAI model."""

        model = model.strip()

        if not model:
            raise ValueError(
                "OpenAI model name cannot be empty."
            )

        self.model = model

        logger.info(
            "OpenAI model changed to: %s",
            model,
        )

    # ========================================================
    # GENERATE
    # ========================================================

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        conversation: Optional[
            List[Dict[str, str]]
        ] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
    ) -> str:
        """
        Generate a response using OpenAI.

        Parameters
        ----------
        prompt:
            Current user message.

        system_prompt:
            Optional system instruction.

        conversation:
            Previous messages.

            Expected format:

                [
                    {
                        "role": "user",
                        "content": "Hello"
                    },
                    {
                        "role": "assistant",
                        "content": "Hi!"
                    }
                ]

        temperature:
            Controls randomness where supported.

        max_tokens:
            Maximum output length when supported.

        model:
            Optional per-request model override.

        Returns
        -------
        str
            Generated text.
        """

        if not isinstance(prompt, str):
            raise TypeError(
                "prompt must be a string."
            )

        prompt = prompt.strip()

        if not prompt:
            raise ValueError(
                "prompt cannot be empty."
            )

        if not self.is_available():
            raise RuntimeError(
                "OpenAI provider is not available. "
                "Set OPENAI_API_KEY in the .env file."
            )

        selected_model = (
            model or self.model
        ).strip()

        if not selected_model:
            raise RuntimeError(
                "No OpenAI model has been configured."
            )

        # Build the request input.
        input_messages = self._build_messages(
            prompt=prompt,
            system_prompt=system_prompt,
            conversation=conversation,
        )

        request: Dict[str, Any] = {
            "model": selected_model,
            "input": input_messages,
        }

        # ----------------------------------------------------
        # Optional output limit
        # ----------------------------------------------------

        if max_tokens is not None:

            if max_tokens <= 0:
                raise ValueError(
                    "max_tokens must be greater than 0."
                )

            request[
                "max_output_tokens"
            ] = max_tokens

        # ----------------------------------------------------
        # Temperature
        # ----------------------------------------------------
        #
        # Some newer reasoning models may not expose all
        # sampling parameters in the same way. Therefore
        # temperature is only sent when explicitly useful.
        #
        # ----------------------------------------------------

        if temperature is not None:

            if not 0 <= temperature <= 2:
                raise ValueError(
                    "temperature must be between 0 and 2."
                )

            request[
                "temperature"
            ] = temperature

        # ----------------------------------------------------
        # API request
        # ----------------------------------------------------

        try:

            logger.info(
                "Sending request to OpenAI model '%s'.",
                selected_model,
            )

            response = self.client.responses.create(
                **request
            )

            text = self._extract_text(
                response
            )

            if not text:
                raise RuntimeError(
                    "OpenAI returned an empty response."
                )

            logger.info(
                "OpenAI response received successfully."
            )

            return text

        except Exception as exc:

            logger.exception(
                "OpenAI request failed: %s",
                exc,
            )

            raise RuntimeError(
                f"OpenAI request failed: {exc}"
            ) from exc

    # ========================================================
    # BUILD MESSAGES
    # ========================================================

    @staticmethod
    def _build_messages(
        prompt: str,
        system_prompt: Optional[str],
        conversation: Optional[
            List[Dict[str, str]]
        ],
    ) -> List[Dict[str, str]]:
        """
        Build the Responses API input message list.
        """

        messages: List[
            Dict[str, str]
        ] = []

        # ----------------------------------------------------
        # System instruction
        # ----------------------------------------------------

        if system_prompt:

            system_prompt = (
                system_prompt.strip()
            )

            if system_prompt:

                messages.append(
                    {
                        "role": "system",
                        "content": system_prompt,
                    }
                )

        # ----------------------------------------------------
        # Previous conversation
        # ----------------------------------------------------

        if conversation:

            for message in conversation:

                if not isinstance(
                    message,
                    dict,
                ):
                    continue

                role = str(
                    message.get(
                        "role",
                        ""
                    )
                ).strip().lower()

                content = str(
                    message.get(
                        "content",
                        ""
                    )
                ).strip()

                if not content:
                    continue

                # Only normal conversation roles are accepted.
                if role not in {
                    "user",
                    "assistant",
                    "system",
                }:
                    continue

                messages.append(
                    {
                        "role": role,
                        "content": content,
                    }
                )

        # ----------------------------------------------------
        # Current user message
        # ----------------------------------------------------

        messages.append(
            {
                "role": "user",
                "content": prompt,
            }
        )

        return messages

    # ========================================================
    # EXTRACT RESPONSE TEXT
    # ========================================================

    @staticmethod
    def _extract_text(
        response: Any,
    ) -> str:
        """
        Extract generated text from an OpenAI response.

        The official SDK exposes output_text for convenient
        text extraction. A fallback parser is also included
        so the provider is more tolerant of response shapes.
        """

        # ----------------------------------------------------
        # Preferred SDK property
        # ----------------------------------------------------

        output_text = getattr(
            response,
            "output_text",
            None,
        )

        if isinstance(
            output_text,
            str,
        ):

            return output_text.strip()

        # ----------------------------------------------------
        # Dictionary-style fallback
        # ----------------------------------------------------

        if isinstance(
            response,
            dict,
        ):

            output_text = response.get(
                "output_text"
            )

            if isinstance(
                output_text,
                str,
            ):

                return output_text.strip()

        # ----------------------------------------------------
        # Generic output parser
        # ----------------------------------------------------

        output = getattr(
            response,
            "output",
            None,
        )

        if output is None:

            if isinstance(
                response,
                dict,
            ):

                output = response.get(
                    "output"
                )

        if not output:
            return ""

        parts: List[str] = []

        try:

            for item in output:

                # Object form
                content = getattr(
                    item,
                    "content",
                    None,
                )

                # Dictionary form
                if content is None and isinstance(
                    item,
                    dict,
                ):

                    content = item.get(
                        "content"
                    )

                if not content:
                    continue

                for content_item in content:

                    text = getattr(
                        content_item,
                        "text",
                        None,
                    )

                    if text is None and isinstance(
                        content_item,
                        dict,
                    ):

                        text = content_item.get(
                            "text"
                        )

                    if isinstance(
                        text,
                        str,
                    ):

                        parts.append(
                            text
                        )

        except TypeError:
            return ""

        return "\n".join(
            part.strip()
            for part in parts
            if part.strip()
        ).strip()

    # ========================================================
    # SIMPLE CHAT
    # ========================================================

    def chat(
        self,
        message: str,
        conversation: Optional[
            List[Dict[str, str]]
        ] = None,
    ) -> str:
        """
        Simplified chat interface.
        """

        return self.generate(
            prompt=message,
            conversation=conversation,
        )

    # ========================================================
    # PROVIDER INFORMATION
    # ========================================================

    def get_status(self) -> Dict[str, Any]:
        """Return provider status without exposing the API key."""

        return {
            "provider": "openai",
            "available": self.is_available(),
            "model": self.model,
            "api_key_configured": bool(
                self.api_key
            ),
        }


# ============================================================
# DIRECT TEST
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

    provider = OpenAIProvider()

    print()
    print("=" * 50)
    print("JARVIS OS - OpenAI Provider")
    print("=" * 50)

    status = provider.get_status()

    print(
        f"Provider: {status['provider']}"
    )

    print(
        f"Model: {status['model']}"
    )

    print(
        f"API key configured: "
        f"{status['api_key_configured']}"
    )

    print(
        f"Available: "
        f"{status['available']}"
    )

    print("=" * 50)

    if provider.is_available():

        try:

            answer = provider.chat(
                "Say hello to JARVIS OS in one short sentence."
            )

            print()
            print("OpenAI:")
            print(answer)

        except Exception as exc:

            print()
            print(
                f"Test request failed: {exc}"
            )

    else:

        print()
        print(
            "OpenAI is not configured."
        )

        print(
            "Add OPENAI_API_KEY to .env "
            "before testing the provider."
          )
