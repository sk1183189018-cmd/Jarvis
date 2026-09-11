"""
JarvisOS - Task Planner

Creates structured execution plans from user requests.

Example:

User:
    "Chrome kholo aur YouTube par Python tutorial search karo"

Plan:
    1. Open Chrome
    2. Open YouTube
    3. Search for Python tutorial

This module creates plans.
It does NOT execute system actions directly.
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
class TaskStep:
    """One step inside an execution plan."""

    step_id: int
    description: str
    action: str = "general"
    target: Optional[str] = None
    parameters: Dict[str, Any] = field(
        default_factory=dict
    )
    requires_confirmation: bool = False
    completed: bool = False
    failed: bool = False


@dataclass
class TaskPlan:
    """Complete plan for a user request."""

    task: str
    goal: str
    steps: List[TaskStep] = field(
        default_factory=list
    )
    requires_confirmation: bool = False
    status: str = "pending"
    current_step: int = 0
    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert plan to a JSON-compatible dictionary."""

        return {
            "task": self.task,
            "goal": self.goal,
            "steps": [
                {
                    "step_id": step.step_id,
                    "description": step.description,
                    "action": step.action,
                    "target": step.target,
                    "parameters": step.parameters,
                    "requires_confirmation": (
                        step.requires_confirmation
                    ),
                    "completed": step.completed,
                    "failed": step.failed,
                }
                for step in self.steps
            ],
            "requires_confirmation": (
                self.requires_confirmation
            ),
            "status": self.status,
            "current_step": self.current_step,
            "metadata": self.metadata,
        }


# ======================================================================
# TASK PLANNER
# ======================================================================


class TaskPlanner:
    """
    Creates and manages JarvisOS task plans.

    AI can be used to create complex plans, while common simple
    commands can be planned locally.
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
        prompt_manager=None,
    ) -> None:

        self.ai_router = ai_router
        self.prompt_manager = prompt_manager

        self.current_plan: Optional[
            TaskPlan
        ] = None

        self.plan_history: List[TaskPlan] = []

        self.max_history = 20

        self._initialize_prompt_manager()

        logger.info(
            "TaskPlanner initialized."
        )

    # ==================================================================
    # INITIALIZATION
    # ==================================================================

    def _initialize_prompt_manager(self) -> None:
        """Load PromptManager if required."""

        if self.prompt_manager is not None:
            return

        try:

            from ai.prompt_manager import (
                PromptManager,
            )

            self.prompt_manager = PromptManager()

        except Exception as exc:

            logger.warning(
                "PromptManager unavailable: %s",
                exc,
            )

    # ==================================================================
    # CREATE PLAN
    # ==================================================================

    def create_plan(
        self,
        task: str,
        context: Optional[str] = None,
        use_ai: bool = True,
    ) -> TaskPlan:
        """
        Create a plan for a task.

        Args:
            task:
                User's complete request.

            context:
                Additional context.

            use_ai:
                Use AI for complex planning when available.
        """

        task = self._clean_task(task)

        if not task:

            plan = TaskPlan(
                task="",
                goal="No task provided.",
                status="invalid",
            )

            self.current_plan = plan

            return plan

        # --------------------------------------------------------------
        # Try local planning first for common commands.
        # --------------------------------------------------------------

        local_plan = (
            self._create_local_plan(task)
        )

        if local_plan is not None:

            self._finalize_plan(local_plan)

            return local_plan

        # --------------------------------------------------------------
        # AI planning for complex tasks.
        # --------------------------------------------------------------

        if use_ai and self.ai_router is not None:

            ai_plan = self._create_ai_plan(
                task,
                context,
            )

            if ai_plan is not None:

                self._finalize_plan(ai_plan)

                return ai_plan

        # --------------------------------------------------------------
        # Safe generic fallback.
        # --------------------------------------------------------------

        fallback = TaskPlan(
            task=task,
            goal=task,
            steps=[
                TaskStep(
                    step_id=1,
                    description=task,
                    action="general",
                    requires_confirmation=False,
                )
            ],
        )

        self._finalize_plan(fallback)

        return fallback

    # ==================================================================
    # LOCAL PLAN
    # ==================================================================

    def _create_local_plan(
        self,
        task: str,
    ) -> Optional[TaskPlan]:
        """
        Create plans for common desktop commands without AI.
        """

        normalized = task.lower()

        # --------------------------------------------------------------
        # Open application
        # --------------------------------------------------------------

        if self._contains_any(
            normalized,
            [
                "open ",
                "launch ",
                "start ",
                " kholo",
                " kholo",
            ],
        ):

            target = self._extract_after_keyword(
                task,
                [
                    "open ",
                    "launch ",
                    "start ",
                ],
            )

            if target:

                return TaskPlan(
                    task=task,
                    goal=f"Open {target}",
                    steps=[
                        TaskStep(
                            step_id=1,
                            description=(
                                f"Open application or "
                                f"program: {target}"
                            ),
                            action="open_app",
                            target=target,
                        )
                    ],
                )

        # --------------------------------------------------------------
        # Screenshot
        # --------------------------------------------------------------

        if self._contains_any(
            normalized,
            [
                "screenshot",
                "screen shot",
                "capture screen",
                "screen capture",
            ],
        ):

            return TaskPlan(
                task=task,
                goal="Capture the computer screen",
                steps=[
                    TaskStep(
                        step_id=1,
                        description=(
                            "Capture the current screen"
                        ),
                        action="screenshot",
                    )
                ],
            )

        # --------------------------------------------------------------
        # Shutdown
        # --------------------------------------------------------------

        if self._contains_any(
            normalized,
            [
                "shutdown",
                "shut down",
                "turn off pc",
                "turn off computer",
                "computer band karo",
                "pc band karo",
            ],
        ):

            return TaskPlan(
                task=task,
                goal="Shut down the computer",
                steps=[
                    TaskStep(
                        step_id=1,
                        description=(
                            "Shut down the computer"
                        ),
                        action="shutdown",
                        requires_confirmation=True,
                    )
                ],
                requires_confirmation=True,
            )

        # --------------------------------------------------------------
        # Restart
        # --------------------------------------------------------------

        if self._contains_any(
            normalized,
            [
                "restart",
                "reboot",
                "pc restart karo",
                "computer restart karo",
            ],
        ):

            return TaskPlan(
                task=task,
                goal="Restart the computer",
                steps=[
                    TaskStep(
                        step_id=1,
                        description=(
                            "Restart the computer"
                        ),
                        action="restart",
                        requires_confirmation=True,
                    )
                ],
                requires_confirmation=True,
            )

        # --------------------------------------------------------------
        # Delete
        # --------------------------------------------------------------

        if self._contains_any(
            normalized,
            [
                "delete file",
                "delete folder",
                "remove file",
                "remove folder",
                "file delete",
                "folder delete",
                "file hatao",
                "folder hatao",
            ],
        ):

            return TaskPlan(
                task=task,
                goal="Delete the requested item",
                steps=[
                    TaskStep(
                        step_id=1,
                        description=(
                            "Identify the item to delete"
                        ),
                        action="find_file",
                    ),
                    TaskStep(
                        step_id=2,
                        description=(
                            "Ask user for confirmation"
                        ),
                        action="confirmation",
                        requires_confirmation=True,
                    ),
                    TaskStep(
                        step_id=3,
                        description=(
                            "Delete the confirmed item"
                        ),
                        action="delete",
                        requires_confirmation=True,
                    ),
                ],
                requires_confirmation=True,
            )

        # --------------------------------------------------------------
        # Web search
        # --------------------------------------------------------------

        if self._contains_any(
            normalized,
            [
                "search web",
                "search online",
                "google ",
                "internet par search",
                "online search",
            ],
        ):

            query = self._extract_search_query(
                task
            )

            return TaskPlan(
                task=task,
                goal=(
                    f"Search the web for {query}"
                    if query
                    else "Search the web"
                ),
                steps=[
                    TaskStep(
                        step_id=1,
                        description=(
                            "Search the web"
                            + (
                                f" for {query}"
                                if query
                                else ""
                            )
                        ),
                        action="web_search",
                        target=query,
                    )
                ],
            )

        return None

    # ==================================================================
    # AI PLAN
    # ==================================================================

    def _create_ai_plan(
        self,
        task: str,
        context: Optional[str],
    ) -> Optional[TaskPlan]:
        """
        Ask the configured AI provider to create a structured plan.
        """

        system_prompt = """
You are the JarvisOS Task Planning Engine.

Break a user's request into clear, executable steps.

Return ONLY valid JSON.

Required structure:

{
  "goal": "short goal",
  "steps": [
    {
      "description": "what should happen",
      "action": "action_name",
      "target": "optional target",
      "parameters": {},
      "requires_confirmation": false
    }
  ],
  "requires_confirmation": false
}

Rules:

1. Never execute actions yourself.
2. Destructive actions require confirmation.
3. Deleting files requires confirmation.
4. Shutdown/restart require confirmation.
5. Sending messages or emails requires confirmation.
6. Financial actions require confirmation.
7. Keep steps ordered.
8. Do not invent unavailable information.
9. Use simple action names.
"""

        user_prompt = task

        if context:
            user_prompt += (
                "\n\nAdditional context:\n"
                + context
            )

        try:

            result = self.ai_router.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.2,
            )

            if hasattr(result, "text"):
                response = str(result.text)

            else:
                response = str(result)

            data = self._parse_json(
                response
            )

            if not isinstance(data, dict):
                return None

            return self._plan_from_dict(
                task,
                data,
            )

        except Exception as exc:

            logger.exception(
                "AI task planning failed: %s",
                exc,
            )

            return None

    # ==================================================================
    # PLAN FROM DICTIONARY
    # ==================================================================

    def _plan_from_dict(
        self,
        task: str,
        data: Dict[str, Any],
    ) -> Optional[TaskPlan]:
        """Convert AI JSON into TaskPlan."""

        goal = str(
            data.get(
                "goal",
                task,
            )
        )

        raw_steps = data.get(
            "steps",
            [],
        )

        if not isinstance(
            raw_steps,
            list,
        ):
            return None

        steps: List[TaskStep] = []

        for index, raw_step in enumerate(
            raw_steps,
            start=1,
        ):

            if not isinstance(
                raw_step,
                dict,
            ):
                continue

            description = str(
                raw_step.get(
                    "description",
                    f"Step {index}",
                )
            )

            action = str(
                raw_step.get(
                    "action",
                    "general",
                )
            ).lower().strip()

            target = raw_step.get(
                "target"
            )

            parameters = raw_step.get(
                "parameters",
                {},
            )

            if not isinstance(
                parameters,
                dict,
            ):
                parameters = {}

            confirmation = bool(
                raw_step.get(
                    "requires_confirmation",
                    False,
                )
            )

            if action in self.DANGEROUS_ACTIONS:
                confirmation = True

            steps.append(
                TaskStep(
                    step_id=index,
                    description=description,
                    action=action,
                    target=(
                        str(target)
                        if target is not None
                        else None
                    ),
                    parameters=parameters,
                    requires_confirmation=(
                        confirmation
                    ),
                )
            )

        if not steps:
            return None

        requires_confirmation = bool(
            data.get(
                "requires_confirmation",
                False,
            )
        )

        if any(
            step.requires_confirmation
            for step in steps
        ):
            requires_confirmation = True

        return TaskPlan(
            task=task,
            goal=goal,
            steps=steps,
            requires_confirmation=(
                requires_confirmation
            ),
        )

    # ==================================================================
    # JSON PARSER
    # ==================================================================

    @staticmethod
    def _parse_json(
        text: str,
    ) -> Optional[Any]:
        """Extract JSON from normal text or a markdown block."""

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
    # PLAN FINALIZATION
    # ==================================================================

    def _finalize_plan(
        self,
        plan: TaskPlan,
    ) -> None:
        """Finalize, validate and store a plan."""

        self._validate_plan(plan)

        plan.metadata[
            "step_count"
        ] = len(plan.steps)

        plan.metadata[
            "created_at"
        ] = __import__(
            "datetime"
        ).datetime.now().isoformat()

        self.current_plan = plan

        self.plan_history.append(
            plan
        )

        if len(self.plan_history) > self.max_history:

            self.plan_history = (
                self.plan_history[
                    -self.max_history:
                ]
            )

        logger.info(
            "Task plan created: %s (%d steps)",
            plan.goal,
            len(plan.steps),
        )

    # ==================================================================
    # VALIDATION
    # ==================================================================

    def _validate_plan(
        self,
        plan: TaskPlan,
    ) -> None:
        """Validate plan safety."""

        for step in plan.steps:

            if step.action in self.DANGEROUS_ACTIONS:

                step.requires_confirmation = True

                plan.requires_confirmation = True

        if not plan.steps:

            plan.status = "empty"

        else:

            plan.status = "pending"

    # ==================================================================
    # STEP MANAGEMENT
    # ==================================================================

    def get_current_step(
        self,
    ) -> Optional[TaskStep]:
        """Return the current step."""

        if self.current_plan is None:
            return None

        if (
            self.current_plan.current_step
            >= len(
                self.current_plan.steps
            )
        ):
            return None

        return self.current_plan.steps[
            self.current_plan.current_step
        ]

    def mark_step_completed(
        self,
        step_id: int,
    ) -> bool:
        """Mark a step as completed."""

        if self.current_plan is None:
            return False

        for step in self.current_plan.steps:

            if step.step_id == step_id:

                step.completed = True
                step.failed = False

                self.current_plan.current_step = (
                    self._next_pending_index()
                )

                if all(
                    s.completed
                    for s in self.current_plan.steps
                ):
                    self.current_plan.status = (
                        "completed"
                    )

                return True

        return False

    def mark_step_failed(
        self,
        step_id: int,
    ) -> bool:
        """Mark a step as failed."""

        if self.current_plan is None:
            return False

        for step in self.current_plan.steps:

            if step.step_id == step_id:

                step.failed = True
                self.current_plan.status = (
                    "failed"
                )

                return True

        return False

    def _next_pending_index(self) -> int:
        """Find the next incomplete step index."""

        if self.current_plan is None:
            return 0

        for index, step in enumerate(
            self.current_plan.steps
        ):

            if not step.completed:
                return index

        return len(
            self.current_plan.steps
        )

    # ==================================================================
    # CANCEL
    # ==================================================================

    def cancel_plan(self) -> bool:
        """Cancel the current plan."""

        if self.current_plan is None:
            return False

        self.current_plan.status = (
            "cancelled"
        )

        logger.info(
            "Current task plan cancelled."
        )

        return True

    # ==================================================================
    # RESET
    # ==================================================================

    def clear_plan(self) -> None:
        """Clear current task plan."""

        self.current_plan = None

    # ==================================================================
    # HELPERS
    # ==================================================================

    @staticmethod
    def _clean_task(
        task: str,
    ) -> str:

        if not task:
            return ""

        task = str(task)

        task = re.sub(
            r"\s+",
            " ",
            task,
        )

        return task.strip()

    @staticmethod
    def _contains_any(
        text: str,
        keywords: List[str],
    ) -> bool:

        return any(
            keyword in text
            for keyword in keywords
        )

    @staticmethod
    def _extract_after_keyword(
        text: str,
        keywords: List[str],
    ) -> Optional[str]:

        normalized = text.lower()

        for keyword in keywords:

            index = normalized.find(
                keyword.lower()
            )

            if index >= 0:

                value = text[
                    index + len(keyword) :
                ].strip()

                if value:
                    return value

        return None

    @staticmethod
    def _extract_search_query(
        text: str,
    ) -> str:

        patterns = [
            r"search\s+(?:for\s+)?(.+)",
            r"google\s+(.+)",
            r"search\s+online\s+(?:for\s+)?(.+)",
            r"internet\s+par\s+search\s+(.+)",
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                text,
                re.IGNORECASE,
            )

            if match:

                return match.group(1).strip()

        return ""

    # ==================================================================
    # EXPORT
    # ==================================================================

    def export_current_plan(
        self,
    ) -> Optional[str]:
        """Export current plan as formatted JSON."""

        if self.current_plan is None:
            return None

        return json.dumps(
            self.current_plan.to_dict(),
            ensure_ascii=False,
            indent=2,
        )

    # ==================================================================
    # STATUS
    # ==================================================================

    def get_status(self) -> Dict[str, Any]:
        """Return planner status."""

        current = self.current_plan

        return {
            "has_current_plan": (
                current is not None
            ),
            "current_status": (
                current.status
                if current
                else None
            ),
            "current_goal": (
                current.goal
                if current
                else None
            ),
            "current_step": (
                current.current_step
                if current
                else None
            ),
            "step_count": (
                len(current.steps)
                if current
                else 0
            ),
            "requires_confirmation": (
                current.requires_confirmation
                if current
                else False
            ),
            "history_count": len(
                self.plan_history
            ),
            "ai_available": (
                self.ai_router is not None
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
    print("JARVIS OS - TASK PLANNER TEST")
    print("=" * 65)

    planner = TaskPlanner()

    tests = [
        "Chrome kholo",
        "Mera screenshot lo",
        "Computer band karo",
        "Python tutorial search karo",
        "File delete karo",
    ]

    for command in tests:

        print()
        print("-" * 65)
        print("TASK:", command)

        plan = planner.create_plan(
            command,
            use_ai=False,
        )

        print("GOAL:", plan.goal)
        print(
            "CONFIRMATION:",
            plan.requires_confirmation,
        )

        for step in plan.steps:

            print(
                f"  {step.step_id}. "
                f"{step.description}"
            )

            print(
                f"     Action: {step.action}"
            )

            print(
                f"     Confirmation: "
                f"{step.requires_confirmation}"
            )

    print()
    print("-" * 65)
    print("Planner status:")

    for key, value in (
        planner.get_status().items()
    ):

        print(
            f"  {key}: {value}"
        )

    print()
    print("=" * 65)
    print("TEST COMPLETE")
    print("=" * 65)
