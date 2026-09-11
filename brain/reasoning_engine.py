"""
JarvisOS - Reasoning Engine

Provides the reasoning layer between task planning and decision making.

Flow:

User Request
     ↓
Command Processor
     ↓
Task Planner
     ↓
Reasoning Engine
     ↓
Decision Engine
     ↓
Action Modules

The ReasoningEngine does not directly execute system actions.
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
class ReasoningResult:
    """Result produced by the reasoning engine."""

    success: bool
    task: str
    conclusion: str
    reasoning_summary: str = ""
    next_action: Optional[str] = None
    confidence: float = 0.0
    requires_confirmation: bool = False
    alternatives: List[str] = field(
        default_factory=list
    )
    risks: List[str] = field(
        default_factory=list
    )
    metadata: Dict[str, Any] = field(
        default_factory=dict
    )


# ======================================================================
# REASONING ENGINE
# ======================================================================


class ReasoningEngine:
    """
    JarvisOS reasoning layer.

    Responsibilities:

    - Understand complex tasks
    - Evaluate available context
    - Analyze task plans
    - Identify risks
    - Determine the next logical action
    - Use AIRouter for advanced reasoning
    - Return structured reasoning results

    It intentionally does not perform PC actions.
    """

    DANGEROUS_ACTIONS = {
        "delete",
        "shutdown",
        "restart",
        "format",
        "uninstall",
        "send_email",
        "send_message",
        "transfer",
        "purchase",
        "payment",
        "system_reset",
    }

    def __init__(
        self,
        ai_router=None,
        memory_manager=None,
        prompt_manager=None,
        task_planner=None,
    ) -> None:

        self.ai_router = ai_router
        self.memory_manager = memory_manager
        self.prompt_manager = prompt_manager
        self.task_planner = task_planner

        self.reasoning_history: List[
            ReasoningResult
        ] = []

        self.max_history = 20

        self.last_result: Optional[
            ReasoningResult
        ] = None

        self._initialize_prompt_manager()

        logger.info(
            "ReasoningEngine initialized."
        )

    # ==================================================================
    # INITIALIZATION
    # ==================================================================

    def _initialize_prompt_manager(self) -> None:
        """Load PromptManager if one was not supplied."""

        if self.prompt_manager is not None:
            return

        try:

            from ai.prompt_manager import (
                PromptManager,
            )

            self.prompt_manager = (
                PromptManager()
            )

        except Exception as exc:

            logger.warning(
                "PromptManager unavailable: %s",
                exc,
            )

    # ==================================================================
    # MAIN REASONING
    # ==================================================================

    def reason(
        self,
        task: str,
        plan=None,
        context: Optional[str] = None,
        use_ai: bool = True,
    ) -> ReasoningResult:
        """
        Analyze a task and determine the next logical action.

        Args:
            task:
                Original user request.

            plan:
                Optional TaskPlan.

            context:
                Additional context.

            use_ai:
                Whether to use the configured AI provider.
        """

        task = self._clean_text(task)

        if not task:

            result = ReasoningResult(
                success=False,
                task="",
                conclusion="No task was provided.",
                confidence=0.0,
            )

            self._store_result(result)

            return result

        logger.info(
            "Reasoning about task: %s",
            task,
        )

        # --------------------------------------------------------------
        # Local safety analysis
        # --------------------------------------------------------------

        risks = self._detect_risks(
            task,
            plan,
        )

        requires_confirmation = (
            bool(risks)
            or self._requires_confirmation(
                task,
                plan,
            )
        )

        # --------------------------------------------------------------
        # AI reasoning
        # --------------------------------------------------------------

        if use_ai and self.ai_router is not None:

            result = self._reason_with_ai(
                task=task,
                plan=plan,
                context=context,
                risks=risks,
                requires_confirmation=(
                    requires_confirmation
                ),
            )

            if result is not None:

                self._store_result(result)

                return result

        # --------------------------------------------------------------
        # Local reasoning fallback
        # --------------------------------------------------------------

        result = self._reason_locally(
            task=task,
            plan=plan,
            risks=risks,
            requires_confirmation=(
                requires_confirmation
            ),
        )

        self._store_result(result)

        return result

    # ==================================================================
    # AI REASONING
    # ==================================================================

    def _reason_with_ai(
        self,
        task: str,
        plan=None,
        context: Optional[str] = None,
        risks: Optional[List[str]] = None,
        requires_confirmation: bool = False,
    ) -> Optional[ReasoningResult]:
        """Use the configured AI provider for advanced reasoning."""

        risks = risks or []

        system_prompt = """
You are the JarvisOS Reasoning Engine.

Analyze the user's task and determine the safest and most useful
next step.

Do not execute any action.

Return ONLY valid JSON in this format:

{
  "conclusion": "short conclusion",
  "reasoning_summary": "brief explanation",
  "next_action": "action_name or null",
  "confidence": 0.0,
  "requires_confirmation": false,
  "alternatives": [],
  "risks": []
}

Safety rules:

- Never execute actions.
- Never assume permission.
- File deletion requires confirmation.
- Shutdown/restart requires confirmation.
- Sending emails/messages requires confirmation.
- Financial actions require confirmation.
- If information is missing, say what is missing.
- Do not invent facts.
- Prefer reversible actions.
- Keep the reasoning summary concise.
"""

        user_prompt = (
            "TASK:\n"
            + task
        )

        if plan is not None:

            plan_data = self._plan_to_dict(
                plan
            )

            user_prompt += (
                "\n\nTASK PLAN:\n"
                + json.dumps(
                    plan_data,
                    ensure_ascii=False,
                    indent=2,
                )
            )

        if context:

            user_prompt += (
                "\n\nADDITIONAL CONTEXT:\n"
                + context
            )

        if risks:

            user_prompt += (
                "\n\nLOCALLY DETECTED RISKS:\n"
                + "\n".join(
                    f"- {risk}"
                    for risk in risks
                )
            )

        try:

            response = self.ai_router.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.2,
            )

            if hasattr(response, "text"):

                text = str(
                    response.text
                )

            else:

                text = str(response)

            data = self._parse_json(
                text
            )

            if not isinstance(
                data,
                dict,
            ):
                return None

            conclusion = str(
                data.get(
                    "conclusion",
                    "Task analyzed.",
                )
            )

            reasoning_summary = str(
                data.get(
                    "reasoning_summary",
                    "",
                )
            )

            next_action = data.get(
                "next_action"
            )

            if next_action is not None:

                next_action = str(
                    next_action
                ).strip()

                if not next_action:
                    next_action = None

            confidence = self._normalize_confidence(
                data.get(
                    "confidence",
                    0.70,
                )
            )

            ai_confirmation = bool(
                data.get(
                    "requires_confirmation",
                    False,
                )
            )

            alternatives = self._string_list(
                data.get(
                    "alternatives",
                    [],
                )
            )

            ai_risks = self._string_list(
                data.get(
                    "risks",
                    [],
                )
            )

            combined_risks = self._unique_strings(
                risks + ai_risks
            )

            final_confirmation = (
                requires_confirmation
                or ai_confirmation
                or self._action_is_dangerous(
                    next_action
                )
            )

            return ReasoningResult(
                success=True,
                task=task,
                conclusion=conclusion,
                reasoning_summary=(
                    reasoning_summary
                ),
                next_action=next_action,
                confidence=confidence,
                requires_confirmation=(
                    final_confirmation
                ),
                alternatives=alternatives,
                risks=combined_risks,
                metadata={
                    "source": "ai",
                },
            )

        except Exception as exc:

            logger.exception(
                "AI reasoning failed: %s",
                exc,
            )

            return None

    # ==================================================================
    # LOCAL REASONING
    # ==================================================================

    def _reason_locally(
        self,
        task: str,
        plan=None,
        risks: Optional[List[str]] = None,
        requires_confirmation: bool = False,
    ) -> ReasoningResult:
        """
        Perform safe local reasoning when AI is unavailable.
        """

        risks = risks or []

        if plan is not None:

            current_step = (
                self._get_current_step(
                    plan
                )
            )

            if current_step is not None:

                action = getattr(
                    current_step,
                    "action",
                    "general",
                )

                description = getattr(
                    current_step,
                    "description",
                    task,
                )

                confirmation = (
                    requires_confirmation
                    or bool(
                        getattr(
                            current_step,
                            "requires_confirmation",
                            False,
                        )
                    )
                    or self._action_is_dangerous(
                        action
                    )
                )

                return ReasoningResult(
                    success=True,
                    task=task,
                    conclusion=(
                        f"Next step: {description}"
                    ),
                    reasoning_summary=(
                        "The next pending step "
                        "from the task plan should "
                        "be processed."
                    ),
                    next_action=str(
                        action
                    ),
                    confidence=0.75,
                    requires_confirmation=(
                        confirmation
                    ),
                    risks=risks,
                    metadata={
                        "source": "local",
                    },
                )

        # --------------------------------------------------------------
        # Simple local intent detection
        # --------------------------------------------------------------

        intent, action = (
            self._infer_local_action(task)
        )

        if action is None:

            return ReasoningResult(
                success=True,
                task=task,
                conclusion=(
                    "The task requires "
                    "additional interpretation."
                ),
                reasoning_summary=(
                    "No specific local action "
                    "could be determined."
                ),
                next_action=None,
                confidence=0.40,
                requires_confirmation=(
                    requires_confirmation
                ),
                risks=risks,
                metadata={
                    "source": "local",
                    "intent": intent,
                },
            )

        confirmation = (
            requires_confirmation
            or self._action_is_dangerous(
                action
            )
        )

        return ReasoningResult(
            success=True,
            task=task,
            conclusion=(
                f"The likely action is {action}."
            ),
            reasoning_summary=(
                "The command matches a known "
                "JarvisOS action."
            ),
            next_action=action,
            confidence=0.70,
            requires_confirmation=confirmation,
            risks=risks,
            metadata={
                "source": "local",
                "intent": intent,
            },
        )

    # ==================================================================
    # RISK DETECTION
    # ==================================================================

    def _detect_risks(
        self,
        task: str,
        plan=None,
    ) -> List[str]:
        """Detect potentially risky operations."""

        risks: List[str] = []

        normalized = task.lower()

        risk_patterns = [
            (
                [
                    "delete",
                    "remove",
                    "erase",
                    "hatao",
                    "delete karo",
                ],
                "This task may delete data.",
            ),
            (
                [
                    "shutdown",
                    "shut down",
                    "turn off pc",
                    "pc band",
                    "computer band",
                ],
                "This task may shut down the computer.",
            ),
            (
                [
                    "restart",
                    "reboot",
                    "pc restart",
                ],
                "This task may restart the computer.",
            ),
            (
                [
                    "format",
                    "wipe disk",
                    "wipe drive",
                ],
                "This task may cause major data loss.",
            ),
            (
                [
                    "send email",
                    "email bhejo",
                    "send message",
                    "message bhejo",
                ],
                "This task may communicate externally.",
            ),
            (
                [
                    "pay",
                    "payment",
                    "purchase",
                    "buy",
                    "transfer money",
                ],
                "This task may involve a financial action.",
            ),
        ]

        for keywords, risk_text in risk_patterns:

            if any(
                keyword in normalized
                for keyword in keywords
            ):

                risks.append(
                    risk_text
                )

        # --------------------------------------------------------------
        # Check planned steps
        # --------------------------------------------------------------

        if plan is not None:

            steps = getattr(
                plan,
                "steps",
                [],
            )

            for step in steps:

                action = str(
                    getattr(
                        step,
                        "action",
                        "",
                    )
                ).lower()

                if self._action_is_dangerous(
                    action
                ):

                    risks.append(
                        f"Planned action "
                        f"'{action}' may be destructive "
                        f"or externally impactful."
                    )

        return self._unique_strings(
            risks
        )

    # ==================================================================
    # CONFIRMATION
    # ==================================================================

    def _requires_confirmation(
        self,
        task: str,
        plan=None,
    ) -> bool:
        """Determine whether confirmation is required."""

        normalized = task.lower()

        confirmation_words = [
            "delete",
            "remove",
            "erase",
            "format",
            "shutdown",
            "shut down",
            "restart",
            "reboot",
            "uninstall",
            "send",
            "transfer",
            "pay",
            "purchase",
            "wipe",
        ]

        if any(
            word in normalized
            for word in confirmation_words
        ):
            return True

        if plan is not None:

            if bool(
                getattr(
                    plan,
                    "requires_confirmation",
                    False,
                )
            ):
                return True

            for step in getattr(
                plan,
                "steps",
                [],
            ):

                if bool(
                    getattr(
                        step,
                        "requires_confirmation",
                        False,
                    )
                ):
                    return True

        return False

    # ==================================================================
    # ACTION CHECK
    # ==================================================================

    def _action_is_dangerous(
        self,
        action: Optional[str],
    ) -> bool:

        if not action:
            return False

        normalized = (
            str(action)
            .lower()
            .strip()
        )

        return (
            normalized
            in self.DANGEROUS_ACTIONS
        )

    # ==================================================================
    # LOCAL ACTION INFERENCE
    # ==================================================================

    def _infer_local_action(
        self,
        task: str,
    ) -> tuple[str, Optional[str]]:

        normalized = task.lower()

        if any(
            word in normalized
            for word in [
                "screenshot",
                "screen shot",
                "screen capture",
            ]
        ):
            return (
                "screenshot",
                "screenshot",
            )

        if any(
            word in normalized
            for word in [
                "shutdown",
                "shut down",
                "pc band",
                "computer band",
            ]
        ):
            return (
                "shutdown",
                "shutdown",
            )

        if any(
            word in normalized
            for word in [
                "restart",
                "reboot",
                "pc restart",
            ]
        ):
            return (
                "restart",
                "restart",
            )

        if any(
            word in normalized
            for word in [
                "delete",
                "remove",
                "erase",
                "file hatao",
            ]
        ):
            return (
                "delete",
                "delete",
            )

        if any(
            word in normalized
            for word in [
                "open chrome",
                "chrome kholo",
                "launch chrome",
            ]
        ):
            return (
                "open_app",
                "open_app",
            )

        if any(
            word in normalized
            for word in [
                "search",
                "google",
                "web search",
            ]
        ):
            return (
                "web_search",
                "web_search",
            )

        if any(
            word in normalized
            for word in [
                "write code",
                "generate code",
                "code likho",
                "program banao",
            ]
        ):
            return (
                "coding",
                "generate_code",
            )

        return (
            "general",
            None,
        )

    # ==================================================================
    # PLAN HELPERS
    # ==================================================================

    @staticmethod
    def _get_current_step(
        plan,
    ):

        current_index = getattr(
            plan,
            "current_step",
            0,
        )

        steps = getattr(
            plan,
            "steps",
            [],
        )

        if (
            current_index < 0
            or current_index >= len(steps)
        ):
            return None

        return steps[current_index]

    @staticmethod
    def _plan_to_dict(
        plan,
    ) -> Dict[str, Any]:

        if hasattr(
            plan,
            "to_dict",
        ):

            try:
                return plan.to_dict()
            except Exception:
                pass

        if isinstance(
            plan,
            dict,
        ):
            return plan

        return {
            "task": str(
                getattr(
                    plan,
                    "task",
                    "",
                )
            ),
            "goal": str(
                getattr(
                    plan,
                    "goal",
                    "",
                )
            ),
        }

    # ==================================================================
    # JSON
    # ==================================================================

    @staticmethod
    def _parse_json(
        text: str,
    ) -> Optional[Any]:

        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        match = re.search(
            r"```(?:json)?\s*(.*?)\s*```",
            text,
            re.DOTALL | re.IGNORECASE,
        )

        if match:

            try:
                return json.loads(
                    match.group(1)
                )
            except json.JSONDecodeError:
                pass

        start = text.find("{")
        end = text.rfind("}")

        if start >= 0 and end > start:

            try:
                return json.loads(
                    text[start : end + 1]
                )
            except json.JSONDecodeError:
                pass

        return None

    # ==================================================================
    # UTILITY
    # ==================================================================

    @staticmethod
    def _clean_text(
        text: str,
    ) -> str:

        if not text:
            return ""

        return re.sub(
            r"\s+",
            " ",
            str(text),
        ).strip()

    @staticmethod
    def _normalize_confidence(
        value: Any,
    ) -> float:

        try:

            confidence = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):

            confidence = 0.5

        return max(
            0.0,
            min(
                1.0,
                confidence,
            ),
        )

    @staticmethod
    def _string_list(
        value: Any,
    ) -> List[str]:

        if not isinstance(
            value,
            list,
        ):
            return []

        result = []

        for item in value:

            if item is None:
                continue

            text = str(
                item
            ).strip()

            if text:
                result.append(
                    text
                )

        return result

    @staticmethod
    def _unique_strings(
        values: List[str],
    ) -> List[str]:

        result = []
        seen = set()

        for value in values:

            normalized = (
                str(value)
                .strip()
                .lower()
            )

            if not normalized:
                continue

            if normalized in seen:
                continue

            seen.add(
                normalized
            )

            result.append(
                str(value).strip()
            )

        return result

    # ==================================================================
    # HISTORY
    # ==================================================================

    def _store_result(
        self,
        result: ReasoningResult,
    ) -> None:

        self.last_result = result

        self.reasoning_history.append(
            result
        )

        if (
            len(self.reasoning_history)
            > self.max_history
        ):

            self.reasoning_history = (
                self.reasoning_history[
                    -self.max_history:
                ]
            )

    def clear_history(self) -> None:
        """Clear reasoning history."""

        self.reasoning_history.clear()

        self.last_result = None

    # ==================================================================
    # STATUS
    # ==================================================================

    def get_status(self) -> Dict[str, Any]:
        """Return reasoning engine status."""

        return {
            "ai_available": (
                self.ai_router is not None
            ),
            "memory_available": (
                self.memory_manager is not None
            ),
            "prompt_manager_available": (
                self.prompt_manager is not None
            ),
            "task_planner_available": (
                self.task_planner is not None
            ),
            "history_count": len(
                self.reasoning_history
            ),
            "last_task": (
                self.last_result.task
                if self.last_result
                else None
            ),
            "last_confidence": (
                self.last_result.confidence
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
    print("JARVIS OS - REASONING ENGINE TEST")
    print("=" * 65)

    engine = ReasoningEngine()

    tests = [
        "Chrome kholo",
        "Mera screenshot lo",
        "Computer band karo",
        "File delete karo",
        "Python ka program banao",
        "Google par Python tutorial search karo",
    ]

    for task in tests:

        print()
        print("-" * 65)
        print("TASK:", task)

        result = engine.reason(
            task,
            use_ai=False,
        )

        print(
            "Conclusion:",
            result.conclusion,
        )

        print(
            "Next action:",
            result.next_action,
        )

        print(
            "Confidence:",
            result.confidence,
        )

        print(
            "Confirmation:",
            result.requires_confirmation,
        )

        if result.risks:

            print("Risks:")

            for risk in result.risks:

                print(
                    f"  - {risk}"
                )

    print()
    print("-" * 65)
    print("Engine status:")

    for key, value in (
        engine.get_status().items()
    ):

        print(
            f"  {key}: {value}"
        )

    print()
    print("=" * 65)
    print("TEST COMPLETE")
    print("=" * 65)
