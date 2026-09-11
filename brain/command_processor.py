"""
JarvisOS - Command Processor

Converts user commands into structured AI responses.

Flow:

User Voice/Text
      ↓
CommandProcessor
      ↓
PromptManager
      ↓
AIRouter
      ↓
AI Provider
      ↓
Response
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ======================================================================
# DATA CLASSES
# ======================================================================


@dataclass
class CommandResult:
    """Result returned after processing a command."""

    success: bool
    user_input: str
    response: str
    intent: str = "general"
    action: Optional[str] = None
    requires_confirmation: bool = False
    confidence: float = 0.0
    provider: str = ""
    model: str = ""
    metadata: Dict[str, Any] = field(
        default_factory=dict
    )


# ======================================================================
# COMMAND PROCESSOR
# ======================================================================


class CommandProcessor:
    """
    Main command-processing layer of JarvisOS.

    Responsibilities:

    - Clean user input
    - Detect basic command intent
    - Retrieve relevant memory
    - Build AI context
    - Send request to AIRouter
    - Parse structured AI output
    - Decide whether an action may require confirmation

    Actual PC actions should be performed by the action modules.
    This class does not directly shut down, delete files, etc.
    """

    DANGEROUS_INTENTS = {
        "shutdown",
        "restart",
        "delete",
        "format",
        "uninstall",
        "system_reset",
        "send_message",
        "send_email",
        "financial",
    }

    CONFIRMATION_KEYWORDS = {
        "delete",
        "remove",
        "format",
        "shutdown",
        "restart",
        "uninstall",
        "erase",
        "wipe",
        "send",
        "transfer",
        "pay",
        "purchase",
    }

    def __init__(
        self,
        ai_router=None,
        memory_manager=None,
        prompt_manager=None,
    ) -> None:

        self.ai_router = ai_router
        self.memory_manager = memory_manager
        self.prompt_manager = prompt_manager

        self.conversation: List[Dict[str, str]] = []

        self.max_conversation_messages = 20

        self.last_result: Optional[
            CommandResult
        ] = None

        self._initialize_prompt_manager()

        logger.info(
            "CommandProcessor initialized."
        )

    # ==================================================================
    # INITIALIZATION
    # ==================================================================

    def _initialize_prompt_manager(self) -> None:
        """Create PromptManager when one wasn't injected."""

        if self.prompt_manager is not None:
            return

        try:

            from ai.prompt_manager import (
                PromptManager,
            )

            self.prompt_manager = PromptManager()

        except Exception as exc:

            logger.warning(
                "PromptManager could not be loaded: %s",
                exc,
            )

            self.prompt_manager = None

    # ==================================================================
    # MAIN PROCESS METHOD
    # ==================================================================

    def process(
        self,
        user_input: str,
        language: str = "auto",
        use_memory: bool = True,
        execute_actions: bool = False,
    ) -> CommandResult:
        """
        Process one user command.

        Args:
            user_input:
                User's voice/text command.

            language:
                auto / english / hindi / hinglish.

            use_memory:
                Whether relevant memory should be included.

            execute_actions:
                Reserved for future action execution.
                Dangerous actions should still be confirmed.

        Returns:
            CommandResult
        """

        cleaned = self.clean_input(user_input)

        if not cleaned:

            result = CommandResult(
                success=False,
                user_input=user_input or "",
                response=(
                    "I didn't hear a command. "
                    "Please try again."
                ),
                intent="empty",
            )

            self.last_result = result

            return result

        logger.info(
            "Processing command: %s",
            cleaned,
        )

        intent = self.detect_intent(cleaned)

        requires_confirmation = (
            self.requires_confirmation(
                cleaned,
                intent,
            )
        )

        memory_context = ""

        if use_memory:
            memory_context = (
                self._get_memory_context(
                    cleaned
                )
            )

        try:

            response = self._generate_response(
                cleaned,
                language=language,
                intent=intent,
                memory_context=memory_context,
            )

            parsed = self._parse_ai_response(
                response
            )

            final_text = parsed.get(
                "response",
                response,
            )

            action = parsed.get(
                "action"
            )

            if parsed.get("intent"):
                intent = str(
                    parsed["intent"]
                )

            if parsed.get(
                "requires_confirmation"
            ) is True:

                requires_confirmation = True

            result = CommandResult(
                success=True,
                user_input=cleaned,
                response=final_text.strip(),
                intent=intent,
                action=action,
                requires_confirmation=(
                    requires_confirmation
                ),
                confidence=self._calculate_confidence(
                    cleaned,
                    intent,
                ),
                provider=(
                    parsed.get(
                        "provider",
                        "",
                    )
                ),
                model=(
                    parsed.get(
                        "model",
                        "",
                    )
                ),
                metadata={
                    "memory_used": bool(
                        memory_context
                    ),
                    "execute_actions": (
                        execute_actions
                    ),
                    "parsed_ai_response": parsed,
                },
            )

            self._add_to_conversation(
                cleaned,
                result.response,
            )

            self._save_conversation_memory(
                cleaned,
                result.response,
            )

            self.last_result = result

            logger.info(
                "Command processed successfully. "
                "Intent=%s Confirmation=%s",
                result.intent,
                result.requires_confirmation,
            )

            return result

        except Exception as exc:

            logger.exception(
                "Command processing failed."
            )

            result = CommandResult(
                success=False,
                user_input=cleaned,
                response=(
                    "Sorry, I couldn't process "
                    "that command right now."
                ),
                intent=intent,
                requires_confirmation=(
                    requires_confirmation
                ),
                metadata={
                    "error": str(exc)
                },
            )

            self.last_result = result

            return result

    # ==================================================================
    # INPUT CLEANING
    # ==================================================================

    @staticmethod
    def clean_input(
        text: str,
    ) -> str:
        """
        Clean speech-recognition output.

        Keeps normal punctuation but removes excessive whitespace.
        """

        if not text:
            return ""

        text = str(text)

        text = text.replace(
            "\x00",
            "",
        )

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        return text.strip()

    # ==================================================================
    # INTENT DETECTION
    # ==================================================================

    def detect_intent(
        self,
        text: str,
    ) -> str:
        """
        Detect common command intents.

        This is a lightweight local classifier.
        The AI remains responsible for complex interpretation.
        """

        normalized = text.lower().strip()

        rules = [
            (
                "shutdown",
                [
                    "shutdown computer",
                    "shut down computer",
                    "shutdown pc",
                    "shut down pc",
                    "turn off computer",
                    "turn off pc",
                    "pc band karo",
                    "computer band karo",
                    "system band karo",
                ],
            ),
            (
                "restart",
                [
                    "restart computer",
                    "restart pc",
                    "reboot computer",
                    "reboot pc",
                    "computer restart karo",
                    "pc restart karo",
                ],
            ),
            (
                "delete",
                [
                    "delete file",
                    "delete folder",
                    "remove file",
                    "remove folder",
                    "file delete karo",
                    "folder delete karo",
                    "file hatao",
                    "folder hatao",
                ],
            ),
            (
                "open_app",
                [
                    "open app",
                    "open application",
                    "launch app",
                    "start app",
                    "app kholo",
                    "application kholo",
                ],
            ),
            (
                "close_app",
                [
                    "close app",
                    "close application",
                    "exit app",
                    "app band karo",
                    "application band karo",
                ],
            ),
            (
                "open_website",
                [
                    "open website",
                    "open site",
                    "website kholo",
                    "site kholo",
                ],
            ),
            (
                "search_web",
                [
                    "search web",
                    "search online",
                    "google this",
                    "internet par search",
                    "online search",
                ],
            ),
            (
                "screenshot",
                [
                    "take screenshot",
                    "capture screen",
                    "screen shot",
                    "screenshot lo",
                    "screen ka photo",
                ],
            ),
            (
                "volume",
                [
                    "increase volume",
                    "decrease volume",
                    "volume up",
                    "volume down",
                    "mute",
                    "unmute",
                    "volume badhao",
                    "volume kam karo",
                ],
            ),
            (
                "file_search",
                [
                    "find file",
                    "search file",
                    "find folder",
                    "file dhundo",
                    "folder dhundo",
                ],
            ),
            (
                "coding",
                [
                    "write code",
                    "generate code",
                    "create code",
                    "program banao",
                    "code likho",
                    "python code",
                    "javascript code",
                    "website banao",
                    "app banao",
                ],
            ),
            (
                "weather",
                [
                    "weather",
                    "mausam",
                    "temperature",
                    "temperature kya hai",
                ],
            ),
            (
                "time",
                [
                    "what time",
                    "current time",
                    "time kya hai",
                    "kitne baje",
                ],
            ),
        ]

        for intent, keywords in rules:

            for keyword in keywords:

                if keyword in normalized:
                    return intent

        return "general"

    # ==================================================================
    # CONFIRMATION
    # ==================================================================

    def requires_confirmation(
        self,
        text: str,
        intent: Optional[str] = None,
    ) -> bool:
        """
        Determine whether a command should require confirmation.

        Destructive or externally impactful actions require confirmation.
        """

        if intent in self.DANGEROUS_INTENTS:
            return True

        normalized = text.lower()

        for keyword in self.CONFIRMATION_KEYWORDS:

            if keyword in normalized:
                return True

        return False

    # ==================================================================
    # AI GENERATION
    # ==================================================================

    def _generate_response(
        self,
        user_input: str,
        language: str,
        intent: str,
        memory_context: str,
    ) -> str:
        """Generate the assistant response through AIRouter."""

        if self.ai_router is None:

            return self._local_fallback(
                user_input,
                intent,
            )

        system_prompt = None

        if self.prompt_manager is not None:

            try:

                system_prompt = (
                    self.prompt_manager
                    .build_system_prompt(
                        language=language,
                        memory=memory_context,
                        current_task=intent,
                    )
                )

            except Exception as exc:

                logger.warning(
                    "Unable to build system prompt: %s",
                    exc,
                )

        user_prompt = user_input

        if self.prompt_manager is not None:

            try:

                user_prompt = (
                    self.prompt_manager
                    .build_user_prompt(
                        user_input,
                        language=language,
                        current_task=intent,
                        memory=memory_context,
                    )
                )

            except Exception:
                user_prompt = user_input

        result = self.ai_router.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            conversation=self.conversation,
            temperature=0.7,
        )

        if hasattr(result, "text"):
            return str(result.text)

        if isinstance(result, str):
            return result

        return str(result)

    # ==================================================================
    # MEMORY
    # ==================================================================

    def _get_memory_context(
        self,
        query: str,
    ) -> str:
        """
        Retrieve relevant memory.

        Supports different MemoryManager implementations without
        forcing a single internal API.
        """

        if self.memory_manager is None:
            return ""

        methods = [
            "search",
            "search_memory",
            "retrieve",
            "get_relevant_memories",
        ]

        for method_name in methods:

            method = getattr(
                self.memory_manager,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:

                result = method(query)

                return self._format_memory_result(
                    result
                )

            except TypeError:

                try:

                    result = method(
                        query=query
                    )

                    return self._format_memory_result(
                        result
                    )

                except Exception:
                    continue

            except Exception as exc:

                logger.debug(
                    "Memory search failed: %s",
                    exc,
                )

                continue

        return ""

    @staticmethod
    def _format_memory_result(
        result: Any,
    ) -> str:
        """Convert different memory result formats into text."""

        if result is None:
            return ""

        if isinstance(result, str):
            return result.strip()

        if isinstance(result, dict):

            try:
                return json.dumps(
                    result,
                    ensure_ascii=False,
                    indent=2,
                )
            except Exception:
                return str(result)

        if isinstance(result, (list, tuple)):

            parts = []

            for item in result:

                if isinstance(item, str):
                    parts.append(item)

                elif isinstance(item, dict):

                    text = (
                        item.get("text")
                        or item.get("content")
                        or item.get("memory")
                    )

                    if text:
                        parts.append(
                            str(text)
                        )
                    else:
                        parts.append(
                            str(item)
                        )

                else:
                    parts.append(str(item))

            return "\n".join(parts).strip()

        return str(result)

    # ==================================================================
    # AI RESPONSE PARSING
    # ==================================================================

    def _parse_ai_response(
        self,
        response: str,
    ) -> Dict[str, Any]:
        """
        Parse structured JSON if the AI returned it.

        Normal conversational responses remain plain text.
        """

        if not response:
            return {
                "response": ""
            }

        text = response.strip()

        # --------------------------------------------------------------
        # Direct JSON
        # --------------------------------------------------------------

        try:

            parsed = json.loads(text)

            if isinstance(parsed, dict):
                return parsed

        except json.JSONDecodeError:
            pass

        # --------------------------------------------------------------
        # JSON inside markdown code block
        # --------------------------------------------------------------

        match = re.search(
            r"```(?:json)?\s*(\{.*?\})\s*```",
            text,
            re.DOTALL | re.IGNORECASE,
        )

        if match:

            try:

                parsed = json.loads(
                    match.group(1)
                )

                if isinstance(parsed, dict):

                    return parsed

            except json.JSONDecodeError:
                pass

        return {
            "response": text
        }

    # ==================================================================
    # CONFIDENCE
    # ==================================================================

    def _calculate_confidence(
        self,
        text: str,
        intent: str,
    ) -> float:
        """
        Calculate a simple local confidence score.

        This is not an AI confidence score.
        It is only an estimate for local intent matching.
        """

        if intent == "general":
            return 0.40

        normalized = text.lower()

        if intent in self.DANGEROUS_INTENTS:
            return 0.85

        keyword_map = {
            "open_app": [
                "open",
                "launch",
                "start",
                "khol",
            ],
            "close_app": [
                "close",
                "exit",
                "band",
            ],
            "coding": [
                "code",
                "program",
                "website",
                "app",
            ],
            "screenshot": [
                "screenshot",
                "screen",
            ],
            "search_web": [
                "search",
                "google",
                "internet",
            ],
        }

        keywords = keyword_map.get(
            intent,
            [],
        )

        matches = sum(
            1
            for keyword in keywords
            if keyword in normalized
        )

        if matches >= 2:
            return 0.95

        if matches == 1:
            return 0.80

        return 0.60

    # ==================================================================
    # CONVERSATION
    # ==================================================================

    def _add_to_conversation(
        self,
        user_input: str,
        response: str,
    ) -> None:
        """Add a conversation turn to short-term context."""

        self.conversation.append(
            {
                "role": "user",
                "content": user_input,
            }
        )

        self.conversation.append(
            {
                "role": "assistant",
                "content": response,
            }
        )

        max_messages = (
            self.max_conversation_messages
        )

        if len(self.conversation) > max_messages:

            self.conversation = (
                self.conversation[
                    -max_messages:
                ]
            )

    def clear_conversation(self) -> None:
        """Clear current conversation context."""

        self.conversation.clear()

        logger.info(
            "Command conversation cleared."
        )

    def get_conversation(
        self,
    ) -> List[Dict[str, str]]:
        """Return a copy of conversation history."""

        return list(
            self.conversation
        )

    # ==================================================================
    # MEMORY SAVE
    # ==================================================================

    def _save_conversation_memory(
        self,
        user_input: str,
        response: str,
    ) -> None:
        """
        Save conversation if MemoryManager supports it.

        Failures here do not break the command.
        """

        if self.memory_manager is None:
            return

        methods = [
            "add_memory",
            "save_memory",
            "remember",
            "store",
        ]

        content = (
            f"User: {user_input}\n"
            f"JarvisOS: {response}"
        )

        for method_name in methods:

            method = getattr(
                self.memory_manager,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:

                method(content)

                return

            except TypeError:

                try:

                    method(
                        content=content
                    )

                    return

                except Exception:
                    continue

            except Exception as exc:

                logger.debug(
                    "Memory save failed: %s",
                    exc,
                )

                return

    # ==================================================================
    # LOCAL FALLBACK
    # ==================================================================

    def _local_fallback(
        self,
        user_input: str,
        intent: str,
    ) -> str:
        """
        Basic offline response when no AI provider is available.

        This is intentionally limited. Complex reasoning still requires
        an AI provider.
        """

        responses = {
            "time": (
                "I can check the current time "
                "when the system service is connected."
            ),
            "weather": (
                "I need web access to check "
                "the current weather."
            ),
            "screenshot": (
                "The screenshot action is ready "
                "to be handled by the desktop action system."
            ),
            "open_app": (
                "I understood that you want "
                "to open an application."
            ),
            "close_app": (
                "I understood that you want "
                "to close an application."
            ),
            "coding": (
                "I understood that you want "
                "help with coding."
            ),
        }

        return responses.get(
            intent,
            (
                "I understood your command, "
                "but an AI provider is not currently "
                "available for a complete response."
            ),
        )

    # ==================================================================
    # STATUS
    # ==================================================================

    def get_status(self) -> dict:
        """Return command processor status."""

        provider_status = None

        if self.ai_router is not None:

            try:

                provider_status = (
                    self.ai_router.status()
                )

            except Exception:
                provider_status = None

        return {
            "conversation_messages": len(
                self.conversation
            ),
            "max_conversation_messages": (
                self.max_conversation_messages
            ),
            "ai_router_available": (
                self.ai_router is not None
            ),
            "memory_manager_available": (
                self.memory_manager is not None
            ),
            "prompt_manager_available": (
                self.prompt_manager is not None
            ),
            "provider_status": provider_status,
            "last_command": (
                self.last_result.user_input
                if self.last_result
                else None
            ),
            "last_intent": (
                self.last_result.intent
                if self.last_result
                else None
            ),
        }


# ======================================================================
# DIRECT TEST
# ======================================================================


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

    print()
    print("=" * 65)
    print("JARVIS OS - COMMAND PROCESSOR TEST")
    print("=" * 65)

    processor = CommandProcessor()

    test_commands = [
        "Chrome kholo",
        "Mera screenshot lo",
        "Computer band karo",
        "Python ka program banao",
        "Google par search karo",
        "Mujhe help chahiye",
    ]

    for command in test_commands:

        print()
        print("-" * 65)
        print(
            "Command:",
            command,
        )

        intent = processor.detect_intent(
            command
        )

        confirmation = (
            processor.requires_confirmation(
                command,
                intent,
            )
        )

        print(
            "Intent:",
            intent,
        )

        print(
            "Confirmation required:",
            confirmation,
        )

    print()
    print("-" * 65)
    print("Processor status:")

    for key, value in processor.get_status().items():

        print(
            f"  {key}: {value}"
        )

    print()
    print("=" * 65)
    print("TEST COMPLETE")
    print("=" * 65)
