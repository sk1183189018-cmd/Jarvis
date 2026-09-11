"""
JarvisOS - Prompt Manager

Centralized prompt management for the JarvisOS AI system.

Responsibilities:
    - Build the main JarvisOS system prompt
    - Add user preferences
    - Add memory context
    - Add current task context
    - Add tool/action rules
    - Build prompts for different AI tasks
    - Keep AI behavior consistent across providers
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ======================================================================
# DATA CLASSES
# ======================================================================


@dataclass
class PromptContext:
    """
    Context used to build an AI prompt.
    """

    user_name: Optional[str] = None
    language: str = "auto"
    memory: List[str] = field(default_factory=list)
    current_task: Optional[str] = None
    current_app: Optional[str] = None
    system_info: Dict[str, Any] = field(default_factory=dict)
    permissions: Dict[str, Any] = field(default_factory=dict)
    extra_context: List[str] = field(default_factory=list)


# ======================================================================
# PROMPT MANAGER
# ======================================================================


class PromptManager:
    """
    Central prompt manager for JarvisOS.

    The manager does not call any AI API itself.

    It only prepares high-quality prompts that can be passed to:
        OpenAI
        Gemini
        Claude
        Local AI models
    """

    VERSION = "1.0.0"

    DEFAULT_ASSISTANT_NAME = "JarvisOS"

    # ------------------------------------------------------------------
    # MAIN SYSTEM PROMPT
    # ------------------------------------------------------------------

    BASE_SYSTEM_PROMPT = """
You are JarvisOS, an advanced personal AI assistant running on a
Windows computer.

Your job is to help the user understand information, solve problems,
write and debug code, manage files, control supported computer
functions, research information, and complete tasks safely.

GENERAL BEHAVIOR:

1. Be helpful, accurate, practical, and concise.
2. Understand natural language rather than requiring exact commands.
3. Understand English, Hindi, and Hinglish.
4. Reply in the user's preferred language when possible.
5. If the user speaks Hinglish, natural Hinglish is acceptable.
6. Do not invent facts, actions, files, results, or tool execution.
7. Never claim that an action was completed unless the corresponding
   tool/action actually reports success.
8. If information is missing, ask only for information that is actually
   necessary.
9. For simple requests, give a simple answer.
10. For complex tasks, break the task into clear steps.
11. Avoid unnecessary repetition.

VOICE-FIRST BEHAVIOR:

JarvisOS is designed primarily for voice interaction.

Voice responses should:
    - sound natural when spoken aloud,
    - avoid unnecessary long paragraphs,
    - clearly state what is being done,
    - avoid excessive formatting,
    - avoid reading raw code unless specifically requested.

When a task is completed, provide a short spoken confirmation.

COMPUTER ACTION SAFETY:

JarvisOS may have access to computer-control tools.

Never perform dangerous or destructive actions without appropriate
permission or confirmation.

Examples of actions that normally require confirmation:

    - permanent file deletion,
    - deleting folders,
    - formatting drives,
    - shutdown,
    - restart,
    - factory reset,
    - changing important security settings,
    - sending sensitive information,
    - executing unknown or dangerous commands,
    - installing potentially unsafe software.

Before a high-risk action:
    1. Explain what will happen.
    2. Ask for confirmation.
    3. Perform the action only after confirmation.

Do not bypass operating-system security or user permissions.

FILE SAFETY:

Do not permanently delete important files without confirmation.

Before moving, replacing, overwriting, or deleting an important file,
verify the target path and intended operation.

CODING BEHAVIOR:

When helping with programming:

    - understand the requested language and framework,
    - provide real executable code,
    - avoid fake APIs,
    - avoid placeholder implementations unless explicitly requested,
    - explain important errors,
    - preserve existing project structure when possible,
    - avoid overwriting existing files without permission.

When generating a complete file, provide the complete file rather than
only a fragment when the user asks for full code.

RESEARCH BEHAVIOR:

When external information is available through tools, use the
appropriate research/search tool.

Do not pretend that you searched the internet when you did not.

MEMORY BEHAVIOR:

Use available memory only when relevant to the current task.

Do not expose private memory unnecessarily.

Do not invent memories.

If memory is disabled or unavailable, continue normally without it.

PRIVACY:

Treat user data, files, conversations, credentials, API keys, and
private information as sensitive.

Never reveal API keys or secrets in responses.

Do not place secrets into generated source code.

Use environment variables or secure storage for credentials.

TOOL EXECUTION:

If tools are available, use the appropriate tool rather than merely
describing an action that could actually be performed.

After a tool reports success, summarize the result clearly.

If a tool reports failure, honestly explain the failure and, when
possible, provide a safe next step.

IDENTITY:

Assistant name: JarvisOS.

Do not claim to be a human.

Do not claim to have physical abilities.

Do not claim to have accessed a computer, file, camera, microphone,
or website unless the relevant capability was actually used.

RESPONSE STYLE:

Prefer:
    - clear language,
    - short useful answers,
    - actionable instructions,
    - natural conversation.

Avoid:
    - unnecessary disclaimers,
    - repetitive introductions,
    - fake confidence,
    - fabricated results,
    - unnecessary technical jargon.
""".strip()

    # ------------------------------------------------------------------
    # LANGUAGE INSTRUCTIONS
    # ------------------------------------------------------------------

    LANGUAGE_INSTRUCTIONS = {
        "auto": """
Detect the user's language automatically.

If the user writes Hindi, respond in Hindi.
If the user writes English, respond in English.
If the user writes Hinglish, respond naturally in Hinglish.
""".strip(),

        "hindi": """
Respond primarily in Hindi.
Use English technical terms when they are clearer or commonly used.
""".strip(),

        "english": """
Respond primarily in English.
Keep technical explanations clear and practical.
""".strip(),

        "hinglish": """
Respond naturally in Hinglish.
Keep technical terms such as Python, API, file, folder, browser,
database, code, and settings in English when appropriate.
""".strip(),
    }

    # ------------------------------------------------------------------
    # TASK PROMPTS
    # ------------------------------------------------------------------

    TASK_INSTRUCTIONS = {
        "general": """
Handle the user's request as a general personal-assistant task.
Understand the intent first and provide the most useful response.
""".strip(),

        "coding": """
Act as a professional software development assistant.

For coding tasks:
    - identify the requested language,
    - understand the existing architecture,
    - produce real code,
    - keep code maintainable,
    - explain important implementation decisions,
    - identify dependencies when required.
""".strip(),

        "debugging": """
Act as a debugging specialist.

Analyze:
    1. the reported error,
    2. the likely root cause,
    3. the affected component,
    4. the safest fix.

Prefer fixing the actual root cause instead of hiding the error.
""".strip(),

        "research": """
Act as a research assistant.

Separate known facts from assumptions.
When web/research tools are available, use them for current or
time-sensitive information.
""".strip(),

        "computer_control": """
Act as a Windows computer-control assistant.

Understand the requested operation and select the appropriate computer
tool.

Before destructive or high-risk operations, require confirmation.
""".strip(),

        "file_management": """
Act as a safe file-management assistant.

Verify paths and intended operations.

Reading, searching, creating, and organizing files may be low-risk.
Permanent deletion, overwriting important files, or destructive
operations require appropriate confirmation.
""".strip(),

        "planning": """
Act as a task-planning assistant.

Convert the user's goal into:
    - objective,
    - required steps,
    - dependencies,
    - possible risks,
    - final result.

Do not perform actions merely because they appeared in a plan unless
the user actually requested execution.
""".strip(),
    }

    # ------------------------------------------------------------------
    # CONSTRUCTOR
    # ------------------------------------------------------------------

    def __init__(
        self,
        assistant_name: str = DEFAULT_ASSISTANT_NAME,
        language: str = "auto",
    ) -> None:
        """
        Initialize PromptManager.
        """

        self.assistant_name = (
            assistant_name.strip()
            if assistant_name
            else self.DEFAULT_ASSISTANT_NAME
        )

        self.language = self._normalize_language(
            language
        )

        self.custom_instructions: List[str] = []

        logger.debug(
            "PromptManager initialized. Language=%s",
            self.language,
        )

    # ==================================================================
    # LANGUAGE
    # ==================================================================

    @staticmethod
    def _normalize_language(language: str) -> str:
        """
        Normalize language setting.
        """

        if not language:
            return "auto"

        language = language.strip().lower()

        aliases = {
            "hi": "hindi",
            "en": "english",
            "hinglish": "hinglish",
            "mix": "hinglish",
            "mixed": "hinglish",
            "automatic": "auto",
        }

        language = aliases.get(
            language,
            language,
        )

        if language not in {
            "auto",
            "hindi",
            "english",
            "hinglish",
        }:
            logger.warning(
                "Unknown language '%s'. Using auto.",
                language,
            )
            return "auto"

        return language

    def set_language(self, language: str) -> None:
        """
        Change the default response language.
        """

        self.language = self._normalize_language(
            language
        )

    def get_language(self) -> str:
        """
        Return current language.
        """

        return self.language

    # ==================================================================
    # CUSTOM INSTRUCTIONS
    # ==================================================================

    def add_instruction(
        self,
        instruction: str,
    ) -> None:
        """
        Add a custom instruction.

        Duplicate instructions are ignored.
        """

        if not instruction or not instruction.strip():
            return

        instruction = instruction.strip()

        if instruction not in self.custom_instructions:
            self.custom_instructions.append(
                instruction
            )

    def remove_instruction(
        self,
        instruction: str,
    ) -> bool:
        """
        Remove a custom instruction.

        Returns:
            True if removed.
        """

        try:
            self.custom_instructions.remove(
                instruction
            )
            return True
        except ValueError:
            return False

    def clear_instructions(self) -> None:
        """
        Remove all custom instructions.
        """

        self.custom_instructions.clear()

    # ==================================================================
    # CONTEXT HELPERS
    # ==================================================================

    @staticmethod
    def _format_memory(
        memory: List[str],
    ) -> str:
        """
        Format memory information safely.
        """

        if not memory:
            return ""

        lines = []

        for item in memory:
            if item is None:
                continue

            text = str(item).strip()

            if text:
                lines.append(
                    f"- {text}"
                )

        if not lines:
            return ""

        return (
            "RELEVANT USER MEMORY:\n"
            + "\n".join(lines)
        )

    @staticmethod
    def _format_system_info(
        system_info: Dict[str, Any],
    ) -> str:
        """
        Format system information.
        """

        if not system_info:
            return ""

        lines = []

        for key, value in system_info.items():
            if value is None:
                continue

            key_text = str(key).replace(
                "_",
                " ",
            ).title()

            lines.append(
                f"- {key_text}: {value}"
            )

        if not lines:
            return ""

        return (
            "CURRENT SYSTEM INFORMATION:\n"
            + "\n".join(lines)
        )

    @staticmethod
    def _format_permissions(
        permissions: Dict[str, Any],
    ) -> str:
        """
        Format permission information.
        """

        if not permissions:
            return ""

        lines = []

        for key, value in permissions.items():
            key_text = str(key).replace(
                "_",
                " ",
            ).title()

            lines.append(
                f"- {key_text}: {value}"
            )

        if not lines:
            return ""

        return (
            "CURRENT PERMISSIONS:\n"
            + "\n".join(lines)
        )

    # ==================================================================
    # BUILD SYSTEM PROMPT
    # ==================================================================

    def build_system_prompt(
        self,
        context: Optional[PromptContext] = None,
        task_type: str = "general",
    ) -> str:
        """
        Build the complete system prompt.

        Args:
            context:
                Optional runtime context.

            task_type:
                general, coding, debugging, research,
                computer_control, file_management, planning.

        Returns:
            Complete system prompt.
        """

        if context is None:
            context = PromptContext(
                language=self.language
            )

        language = self._normalize_language(
            context.language or self.language
        )

        sections: List[str] = [
            self.BASE_SYSTEM_PROMPT
        ]

        # --------------------------------------------------------------
        # ASSISTANT NAME
        # --------------------------------------------------------------

        sections.append(
            f"ASSISTANT CONFIGURATION:\n"
            f"- Assistant name: {self.assistant_name}"
        )

        # --------------------------------------------------------------
        # USER NAME
        # --------------------------------------------------------------

        if context.user_name:
            sections.append(
                "USER INFORMATION:\n"
                f"- User name: {context.user_name}"
            )

        # --------------------------------------------------------------
        # LANGUAGE
        # --------------------------------------------------------------

        language_instruction = (
            self.LANGUAGE_INSTRUCTIONS.get(
                language,
                self.LANGUAGE_INSTRUCTIONS["auto"],
            )
        )

        sections.append(
            "LANGUAGE:\n"
            + language_instruction
        )

        # --------------------------------------------------------------
        # TASK
        # --------------------------------------------------------------

        task_type = (
            task_type.strip().lower()
            if task_type
            else "general"
        )

        task_instruction = (
            self.TASK_INSTRUCTIONS.get(
                task_type,
                self.TASK_INSTRUCTIONS["general"],
            )
        )

        sections.append(
            f"TASK MODE: {task_type}\n"
            + task_instruction
        )

        # --------------------------------------------------------------
        # CURRENT TASK
        # --------------------------------------------------------------

        if context.current_task:
            sections.append(
                "CURRENT TASK:\n"
                + context.current_task.strip()
            )

        # --------------------------------------------------------------
        # CURRENT APP
        # --------------------------------------------------------------

        if context.current_app:
            sections.append(
                "CURRENT APPLICATION:\n"
                f"{context.current_app.strip()}"
            )

        # --------------------------------------------------------------
        # MEMORY
        # --------------------------------------------------------------

        memory_text = self._format_memory(
            context.memory
        )

        if memory_text:
            sections.append(memory_text)

        # --------------------------------------------------------------
        # SYSTEM INFORMATION
        # --------------------------------------------------------------

        system_info_text = (
            self._format_system_info(
                context.system_info
            )
        )

        if system_info_text:
            sections.append(
                system_info_text
            )

        # --------------------------------------------------------------
        # PERMISSIONS
        # --------------------------------------------------------------

        permissions_text = (
            self._format_permissions(
                context.permissions
            )
        )

        if permissions_text:
            sections.append(
                permissions_text
            )

        # --------------------------------------------------------------
        # EXTRA CONTEXT
        # --------------------------------------------------------------

        if context.extra_context:
            extra_lines = []

            for item in context.extra_context:
                if item is None:
                    continue

                text = str(item).strip()

                if text:
                    extra_lines.append(
                        f"- {text}"
                    )

            if extra_lines:
                sections.append(
                    "ADDITIONAL CONTEXT:\n"
                    + "\n".join(extra_lines)
                )

        # --------------------------------------------------------------
        # CUSTOM INSTRUCTIONS
        # --------------------------------------------------------------

        if self.custom_instructions:
            custom_lines = [
                f"- {item}"
                for item in self.custom_instructions
                if item.strip()
            ]

            if custom_lines:
                sections.append(
                    "CUSTOM USER INSTRUCTIONS:\n"
                    + "\n".join(custom_lines)
                )

        return "\n\n".join(
            section.strip()
            for section in sections
            if section and section.strip()
        )

    # ==================================================================
    # BUILD USER PROMPT
    # ==================================================================

    def build_user_prompt(
        self,
        user_message: str,
        context: Optional[PromptContext] = None,
    ) -> str:
        """
        Build the user-facing prompt.

        Usually the raw user message is enough, but this method allows
        additional task context to be included when necessary.
        """

        if not user_message or not user_message.strip():
            raise ValueError(
                "User message cannot be empty."
            )

        parts: List[str] = []

        if context and context.current_task:
            parts.append(
                "Task context:\n"
                + context.current_task.strip()
            )

        parts.append(
            "User request:\n"
            + user_message.strip()
        )

        return "\n\n".join(parts)

    # ==================================================================
    # SPECIALIZED PROMPTS
    # ==================================================================

    def build_coding_prompt(
        self,
        request: str,
        language: Optional[str] = None,
        framework: Optional[str] = None,
        project_context: Optional[str] = None,
    ) -> str:
        """
        Build a coding-specific prompt.
        """

        if not request or not request.strip():
            raise ValueError(
                "Coding request cannot be empty."
            )

        parts = [
            "You are working as the JarvisOS software development "
            "assistant.",
            "",
            "CODING REQUEST:",
            request.strip(),
        ]

        if language:
            parts.extend(
                [
                    "",
                    f"PROGRAMMING LANGUAGE: {language.strip()}",
                ]
            )

        if framework:
            parts.extend(
                [
                    "",
                    f"FRAMEWORK / TECHNOLOGY: {framework.strip()}",
                ]
            )

        if project_context:
            parts.extend(
                [
                    "",
                    "PROJECT CONTEXT:",
                    project_context.strip(),
                ]
            )

        parts.extend(
            [
                "",
                "REQUIREMENTS:",
                "- Produce real working code.",
                "- Do not invent library APIs.",
                "- Preserve existing architecture when possible.",
                "- Include required imports.",
                "- Mention required dependencies.",
                "- Explain important changes briefly.",
            ]
        )

        return "\n".join(parts)

    def build_debugging_prompt(
        self,
        error: str,
        code: Optional[str] = None,
        environment: Optional[str] = None,
    ) -> str:
        """
        Build a debugging prompt.
        """

        if not error or not error.strip():
            raise ValueError(
                "Error message cannot be empty."
            )

        parts = [
            "You are debugging a JarvisOS-related software problem.",
            "",
            "ERROR:",
            error.strip(),
        ]

        if environment:
            parts.extend(
                [
                    "",
                    "ENVIRONMENT:",
                    environment.strip(),
                ]
            )

        if code:
            parts.extend(
                [
                    "",
                    "CODE:",
                    "```",
                    code,
                    "```",
                ]
            )

        parts.extend(
            [
                "",
                "ANALYSIS REQUIRED:",
                "1. Identify the likely root cause.",
                "2. Explain why it happens.",
                "3. Provide the exact fix.",
                "4. Mention any dependency or configuration changes.",
                "5. Do not hide the error with a fake workaround.",
            ]
        )

        return "\n".join(parts)

    def build_research_prompt(
        self,
        question: str,
        scope: Optional[str] = None,
    ) -> str:
        """
        Build a research prompt.
        """

        if not question or not question.strip():
            raise ValueError(
                "Research question cannot be empty."
            )

        parts = [
            "You are the JarvisOS research assistant.",
            "",
            "RESEARCH QUESTION:",
            question.strip(),
        ]

        if scope:
            parts.extend(
                [
                    "",
                    "RESEARCH SCOPE:",
                    scope.strip(),
                ]
            )

        parts.extend(
            [
                "",
                "RESEARCH RULES:",
                "- Distinguish facts from assumptions.",
                "- Prefer authoritative sources.",
                "- For current information, verify freshness.",
                "- Do not fabricate sources or results.",
                "- Clearly identify uncertainty.",
            ]
        )

        return "\n".join(parts)

    def build_action_prompt(
        self,
        request: str,
        available_actions: Optional[List[str]] = None,
        risk_level: str = "low",
    ) -> str:
        """
        Build a computer-action planning prompt.
        """

        if not request or not request.strip():
            raise ValueError(
                "Action request cannot be empty."
            )

        parts = [
            "You are JarvisOS's computer action planner.",
            "",
            "USER REQUEST:",
            request.strip(),
            "",
            f"RISK LEVEL: {risk_level.upper()}",
        ]

        if available_actions:
            parts.extend(
                [
                    "",
                    "AVAILABLE ACTIONS:",
                    *[
                        f"- {action}"
                        for action in available_actions
                        if action
                    ],
                ]
            )

        parts.extend(
            [
                "",
                "RULES:",
                "- Select only actions needed for the request.",
                "- Never invent unavailable tools.",
                "- Do not perform destructive actions without confirmation.",
                "- Respect user permissions.",
                "- If confirmation is required, clearly identify what "
                "will happen before execution.",
            ]
        )

        return "\n".join(parts)

    # ==================================================================
    # COMPLETE PROMPT
    # ==================================================================

    def build_complete_prompt(
        self,
        user_message: str,
        context: Optional[PromptContext] = None,
        task_type: str = "general",
    ) -> Dict[str, str]:
        """
        Build both system and user prompts.

        Returns:
            {
                "system_prompt": "...",
                "user_prompt": "..."
            }
        """

        system_prompt = self.build_system_prompt(
            context=context,
            task_type=task_type,
        )

        user_prompt = self.build_user_prompt(
            user_message=user_message,
            context=context,
        )

        return {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
        }

    # ==================================================================
    # SERIALIZATION / DEBUGGING
    # ==================================================================

    def get_config(self) -> Dict[str, Any]:
        """
        Return prompt-manager configuration.

        Does not contain secrets.
        """

        return {
            "version": self.VERSION,
            "assistant_name": self.assistant_name,
            "language": self.language,
            "custom_instruction_count": len(
                self.custom_instructions
            ),
        }

    def preview(
        self,
        user_message: str,
        task_type: str = "general",
        context: Optional[PromptContext] = None,
    ) -> str:
        """
        Create a readable prompt preview for debugging.
        """

        prompts = self.build_complete_prompt(
            user_message=user_message,
            context=context,
            task_type=task_type,
        )

        return (
            "================ SYSTEM PROMPT ================\n"
            + prompts["system_prompt"]
            + "\n\n"
            "================ USER PROMPT ==================\n"
            + prompts["user_prompt"]
            + "\n"
        )


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

    manager = PromptManager(
        assistant_name="JarvisOS",
        language="hinglish",
    )

    manager.add_instruction(
        "Prefer practical step-by-step explanations."
    )

    context = PromptContext(
        user_name="User",
        language="hinglish",
        memory=[
            "User prefers practical explanations.",
            "User is building JarvisOS.",
        ],
        current_task=(
            "Build the AI provider layer for JarvisOS."
        ),
        current_app="VS Code",
        system_info={
            "os": "Windows",
            "architecture": "64-bit",
        },
        permissions={
            "file_delete": "confirmation_required",
            "shutdown": "confirmation_required",
        },
        extra_context=[
            "The AI provider can be OpenAI, Gemini, or Claude."
        ],
    )

    print("\n" + "=" * 70)
    print("JARVIS OS - PROMPT MANAGER TEST")
    print("=" * 70)

    print(
        manager.preview(
            user_message=(
                "Mujhe AI provider system ka next module banana hai."
            ),
            task_type="coding",
            context=context,
        )
    )

    print("\nConfiguration:")
    print(manager.get_config())
