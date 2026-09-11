"""
JarvisOS - Claude AI Provider

Provides Anthropic Claude integration for JarvisOS.

Environment variables:
    ANTHROPIC_API_KEY
    CLAUDE_MODEL

Expected interface for AIRouter:
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


class ClaudeProvider:
    """
    Anthropic Claude provider for JarvisOS.
    """

    # Current Claude model.
    # Can always be overridden with CLAUDE_MODEL.
    DEFAULT_MODEL = "claude-sonnet-5"

    DEFAULT_MAX_TOKENS = 4096

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        """
        Initialize Claude provider.

        Args:
            api_key:
                Anthropic API key. If omitted, ANTHROPIC_API_KEY
                is read from the environment.

            model:
                Claude model name. If omitted, CLAUDE_MODEL
                is read from the environment.
        """

        self.api_key = (
            api_key
            or os.getenv("ANTHROPIC_API_KEY")
        )

        self.model = (
            model
            or os.getenv("CLAUDE_MODEL")
            or self.DEFAULT_MODEL
        )

        self.client: Any = None
        self._initialized = False
        self.last_error: Optional[str] = None

        self._initialize()

    # ================================================================
    # INITIALIZATION
    # ================================================================

    def _initialize(self) -> None:
        """
        Initialize the official Anthropic Python client.
        """

        if not self.api_key:
            self.last_error = (
                "ANTHROPIC_API_KEY is not configured."
            )

            logger.info(
                "Claude provider disabled: API key not configured."
            )

            return

        try:
            from anthropic import Anthropic

            self.client = Anthropic(
                api_key=self.api_key
            )

            self._initialized = True
            self.last_error = None

            logger.info(
                "Claude provider initialized successfully. "
                "Model: %s",
                self.model,
            )

        except ImportError:
            self.last_error = (
                "Anthropic SDK is not installed. "
                "Install it with: pip install anthropic"
            )

            logger.warning(self.last_error)

        except Exception as exc:
            self.last_error = str(exc)

            logger.exception(
                "Failed to initialize Claude provider: %s",
                exc,
            )

    # ================================================================
    # AVAILABILITY
    # ================================================================

    def is_available(self) -> bool:
        """
        Check whether Claude is configured and ready.
        """

        return bool(
            self.api_key
            and self.client is not None
            and self._initialized
        )

    # ================================================================
    # MODEL
    # ================================================================

    def get_model(self) -> str:
        """
        Return current Claude model.
        """

        return self.model

    def set_model(self, model: str) -> None:
        """
        Change Claude model.
        """

        if not model or not model.strip():
            raise ValueError(
                "Claude model name cannot be empty."
            )

        self.model = model.strip()

        logger.info(
            "Claude model changed to: %s",
            self.model,
        )

    # ================================================================
    # CONVERSATION
    # ================================================================

    def _build_messages(
        self,
        prompt: str,
        conversation: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Convert JarvisOS conversation history into
        Anthropic Messages API format.

        Claude expects user/assistant messages.
        System instructions are handled separately.
        """

        messages: List[Dict[str, Any]] = []

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
                    content = self._flatten_content(
                        content
                    )

                content = str(content).strip()

                if not content:
                    continue

                # Claude Messages API uses:
                # user / assistant
                if role == "assistant":
                    claude_role = "assistant"
                elif role == "user":
                    claude_role = "user"
                else:
                    # System messages are not placed in
                    # messages. They are handled by
                    # system_prompt in generate().
                    continue

                messages.append(
                    {
                        "role": claude_role,
                        "content": content,
                    }
                )

        # Add current user request.
        if prompt and prompt.strip():
            messages.append(
                {
                    "role": "user",
                    "content": prompt.strip(),
                }
            )

        return self._normalize_messages(
            messages
        )

    @staticmethod
    def _flatten_content(
        content: List[Any],
    ) -> str:
        """
        Flatten list-based content into plain text.
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

    @staticmethod
    def _normalize_messages(
        messages: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Normalize consecutive messages with the same role.

        This prevents malformed conversation history
        from producing unnecessary API errors.
        """

        normalized: List[Dict[str, Any]] = []

        for message in messages:
            if not normalized:
                normalized.append(message)
                continue

            previous = normalized[-1]

            if previous["role"] == message["role"]:
                previous_content = str(
                    previous.get("content", "")
                )

                current_content = str(
                    message.get("content", "")
                )

                previous["content"] = (
                    previous_content
                    + "\n\n"
                    + current_content
                )

            else:
                normalized.append(message)

        return normalized

    # ================================================================
    # GENERATION
    # ================================================================

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
        Generate a response using Claude.

        Args:
            prompt:
                Current user request.

            system_prompt:
                Optional system instruction.

            conversation:
                Previous conversation messages.

            temperature:
                Kept in the common provider interface for
                AIRouter compatibility.

                It is intentionally NOT sent to Claude because
                current Claude models may reject this parameter.

            max_tokens:
                Maximum response tokens.

            model:
                Optional model override.

        Returns:
            Claude response text.
        """

        if not self.is_available():
            raise RuntimeError(
                self.last_error
                or "Claude provider is not available."
            )

        if not prompt or not prompt.strip():
            raise ValueError(
                "Claude prompt cannot be empty."
            )

        selected_model = (
            model.strip()
            if model and model.strip()
            else self.model
        )

        output_tokens = (
            max_tokens
            if max_tokens is not None
            else self.DEFAULT_MAX_TOKENS
        )

        if output_tokens <= 0:
            raise ValueError(
                "max_tokens must be greater than zero."
            )

        messages = self._build_messages(
            prompt=prompt,
            conversation=conversation,
        )

        request: Dict[str, Any] = {
            "model": selected_model,
            "max_tokens": output_tokens,
            "messages": messages,
        }

        # Anthropic handles system instructions as a
        # separate top-level parameter.
        if system_prompt and system_prompt.strip():
            request["system"] = system_prompt.strip()

        try:
            response = self.client.messages.create(
                **request
            )

            text = self._extract_text(
                response
            )

            if not text:
                raise RuntimeError(
                    "Claude returned an empty response."
                )

            self.last_error = None

            logger.debug(
                "Claude response generated successfully "
                "using model %s.",
                selected_model,
            )

            return text

        except Exception as exc:
            self.last_error = str(exc)

            logger.exception(
                "Claude generation failed: %s",
                exc,
            )

            raise RuntimeError(
                f"Claude generation failed: {exc}"
            ) from exc

    # ================================================================
    # RESPONSE EXTRACTION
    # ================================================================

    @staticmethod
    def _extract_text(
        response: Any,
    ) -> str:
        """
        Extract text from an Anthropic Message response.
        """

        if response is None:
            return ""

        collected: List[str] = []

        # Standard Anthropic response:
        #
        # response.content
        #
        # [
        #   TextBlock(text="...")
        # ]
        try:
            content = getattr(
                response,
                "content",
                None,
            )

            if content:
                for block in content:
                    block_type = getattr(
                        block,
                        "type",
                        None,
                    )

                    if block_type == "text":
                        text = getattr(
                            block,
                            "text",
                            None,
                        )

                        if text:
                            collected.append(
                                str(text)
                            )

        except Exception:
            pass

        if collected:
            return "\n".join(
                collected
            ).strip()

        # Some SDK versions / test mocks may return
        # a dictionary instead of an SDK object.
        if isinstance(response, dict):
            content = response.get(
                "content",
                [],
            )

            if isinstance(content, list):
                for block in content:
                    if not isinstance(
                        block,
                        dict,
                    ):
                        continue

                    if block.get("type") == "text":
                        text = block.get("text")

                        if text:
                            collected.append(
                                str(text)
                            )

        return "\n".join(
            collected
        ).strip()

    # ================================================================
    # CHAT
    # ================================================================

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

    # ================================================================
    # STATUS
    # ================================================================

    def get_status(self) -> Dict[str, Any]:
        """
        Return safe provider status.

        API key itself is never returned.
        """

        return {
            "provider": "claude",
            "available": self.is_available(),
            "initialized": self._initialized,
            "model": self.model,
            "api_key_configured": bool(
                self.api_key
            ),
            "last_error": self.last_error,
        }

    # ================================================================
    # CONNECTION TEST
    # ================================================================

    def test_connection(self) -> Dict[str, Any]:
        """
        Test the Claude API connection.
        """

        if not self.is_available():
            return {
                "success": False,
                "provider": "claude",
                "error": (
                    self.last_error
                    or "Claude provider is not configured."
                ),
            }

        try:
            response = self.generate(
                prompt="Reply with exactly: JARVIS OK",
                max_tokens=20,
            )

            return {
                "success": True,
                "provider": "claude",
                "model": self.model,
                "response": response,
            }

        except Exception as exc:
            return {
                "success": False,
                "provider": "claude",
                "model": self.model,
                "error": str(exc),
            }


# ====================================================================
# DIRECT TEST
# ====================================================================

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

    provider = ClaudeProvider()

    print("\n" + "=" * 60)
    print("JARVIS OS - CLAUDE PROVIDER TEST")
    print("=" * 60)

    status = provider.get_status()

    print(
        f"Provider: {status['provider']}"
    )
    print(
        f"Model: {status['model']}"
    )
    print(
        f"API Key configured: "
        f"{status['api_key_configured']}"
    )
    print(
        f"Available: {status['available']}"
    )

    if provider.is_available():
        result = provider.test_connection()

        print("\nConnection test:")
        print(result)
    else:
        print(
            "\nClaude is not configured."
            "\nSet ANTHROPIC_API_KEY in your .env file."
          )
