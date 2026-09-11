"""
JarvisOS - Decision Engine

Final decision layer between reasoning and action execution.

Flow:

User Command
     ↓
Command Processor
     ↓
Task Planner
     ↓
Reasoning Engine
     ↓
Decision Engine
     ↓
Action Module

Decision types:

    ALLOW   -> Action may proceed
    CONFIRM -> User confirmation is required
    DENY    -> Action must not proceed
    WAIT    -> More information is required

This module DOES NOT execute actions.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ======================================================================
# DECISION TYPES
# ======================================================================


class DecisionType(str, Enum):
    """Possible decisions made by JarvisOS."""

    ALLOW = "allow"
    CONFIRM = "confirm"
    DENY = "deny"
    WAIT = "wait"


# ======================================================================
# DATA CLASSES
# ======================================================================


@dataclass
class Decision:
    """Final decision for an action."""

    decision: DecisionType
    action: Optional[str] = None
    reason: str = ""
    message: str = ""
    confidence: float = 0.0
    requires_confirmation: bool = False
    risks: List[str] = field(
        default_factory=list
    )
    missing_information: List[str] = field(
        default_factory=list
    )
    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    @property
    def allowed(self) -> bool:
        """Return True only when action is allowed."""

        return (
            self.decision
            == DecisionType.ALLOW
        )

    @property
    def blocked(self) -> bool:
        """Return True when action is denied."""

        return (
            self.decision
            == DecisionType.DENY
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert decision to dictionary."""

        return {
            "decision": self.decision.value,
            "action": self.action,
            "reason": self.reason,
            "message": self.message,
            "confidence": self.confidence,
            "requires_confirmation": (
                self.requires_confirmation
            ),
            "risks": self.risks,
            "missing_information": (
                self.missing_information
            ),
            "metadata": self.metadata,
        }


# ======================================================================
# DECISION ENGINE
# ======================================================================


class DecisionEngine:
    """
    Controls whether a planned action may proceed.

    The engine follows a conservative safety policy:

    LOW RISK
        Usually allowed.

    MEDIUM RISK
        May require additional information.

    HIGH RISK
        Requires explicit user confirmation.

    BLOCKED
        Never allowed automatically.

    The engine is intentionally separate from action modules.
    """

    HIGH_RISK_ACTIONS = {
        "delete",
        "delete_file",
        "delete_folder",
        "format",
        "wipe",
        "shutdown",
        "restart",
        "uninstall",
        "system_reset",
        "send_email",
        "send_message",
        "sms",
        "payment",
        "purchase",
        "transfer",
    }

    MEDIUM_RISK_ACTIONS = {
        "move_file",
        "rename_file",
        "rename_folder",
        "copy_file",
        "download",
        "upload",
        "install",
        "open_url",
        "browser_control",
        "keyboard_control",
        "mouse_control",
    }

    LOW_RISK_ACTIONS = {
        "open_app",
        "close_app",
        "screenshot",
        "system_info",
        "volume",
        "volume_up",
        "volume_down",
        "mute",
        "unmute",
        "web_search",
        "search",
        "read_file",
        "find_file",
        "find_folder",
        "get_time",
        "get_weather",
        "general",
        "generate_code",
        "coding",
    }

    BLOCKED_ACTIONS = {
        "disable_security",
        "disable_antivirus",
        "bypass_security",
        "steal_password",
        "credential_theft",
        "keylogger",
        "malware",
        "ransomware",
        "credential_dump",
    }

    def __init__(
        self,
        permission_manager=None,
        security_manager=None,
    ) -> None:

        self.permission_manager = (
            permission_manager
        )

        self.security_manager = (
            security_manager
        )

        self.last_decision: Optional[
            Decision
        ] = None

        self.decision_history: List[
            Decision
        ] = []

        self.max_history = 50

        logger.info(
            "DecisionEngine initialized."
        )

    # ==================================================================
    # MAIN DECISION
    # ==================================================================

    def decide(
        self,
        action: Optional[str],
        task: str = "",
        reasoning_result=None,
        plan_step=None,
        user_confirmed: bool = False,
        permissions: Optional[Dict[str, Any]] = None,
    ) -> Decision:
        """
        Make the final decision for an action.

        Args:
            action:
                Action that may be executed.

            task:
                Original user task.

            reasoning_result:
                Optional ReasoningResult.

            plan_step:
                Optional TaskStep.

            user_confirmed:
                Explicit confirmation from user.

            permissions:
                Optional permission configuration.
        """

        normalized_action = (
            self._normalize_action(action)
        )

        task = str(
            task or ""
        ).strip()

        # --------------------------------------------------------------
        # Missing action
        # --------------------------------------------------------------

        if not normalized_action:

            return self._store_and_return(
                Decision(
                    decision=DecisionType.WAIT,
                    action=None,
                    reason=(
                        "No executable action "
                        "was identified."
                    ),
                    message=(
                        "I need to know what action "
                        "should be performed."
                    ),
                    confidence=0.0,
                    metadata={
                        "stage": "decision"
                    },
                )
            )

        # --------------------------------------------------------------
        # Explicitly blocked action
        # --------------------------------------------------------------

        if self._is_blocked_action(
            normalized_action
        ):

            return self._store_and_return(
                Decision(
                    decision=DecisionType.DENY,
                    action=normalized_action,
                    reason=(
                        "This action is blocked "
                        "by JarvisOS safety policy."
                    ),
                    message=(
                        "I can't perform this action."
                    ),
                    confidence=1.0,
                    metadata={
                        "stage": "security",
                        "risk_level": "blocked",
                    },
                )
            )

        # --------------------------------------------------------------
        # Missing information
        # --------------------------------------------------------------

        missing = (
            self._find_missing_information(
                normalized_action,
                task,
                plan_step,
            )
        )

        if missing:

            return self._store_and_return(
                Decision(
                    decision=DecisionType.WAIT,
                    action=normalized_action,
                    reason=(
                        "Required information "
                        "is missing."
                    ),
                    message=(
                        "I need more information "
                        "before I can continue."
                    ),
                    confidence=0.90,
                    missing_information=missing,
                    metadata={
                        "stage": "validation"
                    },
                )
            )

        # --------------------------------------------------------------
        # Determine risk
        # --------------------------------------------------------------

        risk_level = self.get_risk_level(
            normalized_action
        )

        # --------------------------------------------------------------
        # Determine risks from reasoning
        # --------------------------------------------------------------

        risks = self._get_reasoning_risks(
            reasoning_result
        )

        # --------------------------------------------------------------
        # Check explicit confirmation
        # --------------------------------------------------------------

        confirmation_required = (
            risk_level == "high"
            or self._reasoning_requires_confirmation(
                reasoning_result
            )
            or self._plan_requires_confirmation(
                plan_step
            )
        )

        # --------------------------------------------------------------
        # Permission check
        # --------------------------------------------------------------

        permission_result = (
            self._check_permission(
                normalized_action,
                permissions,
            )
        )

        if permission_result is False:

            return self._store_and_return(
                Decision(
                    decision=DecisionType.DENY,
                    action=normalized_action,
                    reason=(
                        "Permission for this "
                        "action has not been granted."
                    ),
                    message=(
                        "Permission is required "
                        "before I can perform this action."
                    ),
                    confidence=1.0,
                    risks=risks,
                    metadata={
                        "risk_level": risk_level,
                        "permission": False,
                    },
                )
            )

        # --------------------------------------------------------------
        # High-risk action
        # --------------------------------------------------------------

        if confirmation_required:

            if user_confirmed:

                return self._store_and_return(
                    Decision(
                        decision=DecisionType.ALLOW,
                        action=normalized_action,
                        reason=(
                            "Required user confirmation "
                            "has been received."
                        ),
                        message=(
                            "Confirmed. The action "
                            "may proceed."
                        ),
                        confidence=0.95,
                        requires_confirmation=True,
                        risks=risks,
                        metadata={
                            "risk_level": risk_level,
                            "user_confirmed": True,
                        },
                    )
                )

            return self._store_and_return(
                Decision(
                    decision=DecisionType.CONFIRM,
                    action=normalized_action,
                    reason=(
                        "Explicit user confirmation "
                        "is required."
                    ),
                    message=(
                        self._confirmation_message(
                            normalized_action,
                            task,
                        )
                    ),
                    confidence=0.95,
                    requires_confirmation=True,
                    risks=risks,
                    metadata={
                        "risk_level": risk_level,
                        "user_confirmed": False,
                    },
                )
            )

        # --------------------------------------------------------------
        # Low / medium risk
        # --------------------------------------------------------------

        if risk_level == "medium":

            # If security manager explicitly requires confirmation.
            security_confirmation = (
                self._security_requires_confirmation(
                    normalized_action
                )
            )

            if security_confirmation:

                return self._store_and_return(
                    Decision(
                        decision=DecisionType.CONFIRM,
                        action=normalized_action,
                        reason=(
                            "Security policy requires "
                            "confirmation."
                        ),
                        message=(
                            self._confirmation_message(
                                normalized_action,
                                task,
                            )
                        ),
                        confidence=0.90,
                        requires_confirmation=True,
                        risks=risks,
                        metadata={
                            "risk_level": "medium"
                        },
                    )
                )

        # --------------------------------------------------------------
        # Allow
        # --------------------------------------------------------------

        return self._store_and_return(
            Decision(
                decision=DecisionType.ALLOW,
                action=normalized_action,
                reason=(
                    "Action passed JarvisOS "
                    "safety checks."
                ),
                message=(
                    "The action is allowed."
                ),
                confidence=0.90,
                requires_confirmation=False,
                risks=risks,
                metadata={
                    "risk_level": risk_level,
                    "user_confirmed": user_confirmed,
                },
            )
        )

    # ==================================================================
    # RISK LEVEL
    # ==================================================================

    def get_risk_level(
        self,
        action: Optional[str],
    ) -> str:
        """
        Return action risk level.

        Returns:
            low / medium / high / blocked
        """

        normalized = (
            self._normalize_action(action)
        )

        if not normalized:
            return "medium"

        if normalized in self.BLOCKED_ACTIONS:
            return "blocked"

        if normalized in self.HIGH_RISK_ACTIONS:
            return "high"

        if normalized in self.MEDIUM_RISK_ACTIONS:
            return "medium"

        if normalized in self.LOW_RISK_ACTIONS:
            return "low"

        # Unknown actions are treated conservatively.
        return "medium"

    # ==================================================================
    # BLOCK CHECK
    # ==================================================================

    def _is_blocked_action(
        self,
        action: str,
    ) -> bool:

        if action in self.BLOCKED_ACTIONS:
            return True

        blocked_patterns = [
            "keylogger",
            "credential_theft",
            "password_steal",
            "malware",
            "ransomware",
            "disable_antivirus",
            "bypass_security",
        ]

        return any(
            pattern in action
            for pattern in blocked_patterns
        )

    # ==================================================================
    # MISSING INFORMATION
    # ==================================================================

    def _find_missing_information(
        self,
        action: str,
        task: str,
        plan_step=None,
    ) -> List[str]:

        missing: List[str] = []

        target = None

        if plan_step is not None:

            target = getattr(
                plan_step,
                "target",
                None,
            )

            parameters = getattr(
                plan_step,
                "parameters",
                {},
            )

        else:

            parameters = {}

        # --------------------------------------------------------------
        # App actions
        # --------------------------------------------------------------

        if action in {
            "open_app",
            "close_app",
        }:

            if not target:

                target = (
                    self._extract_app_target(
                        task
                    )
                )

            if not target:

                missing.append(
                    "application name"
                )

        # --------------------------------------------------------------
        # File actions
        # --------------------------------------------------------------

        if action in {
            "delete",
            "delete_file",
            "delete_folder",
            "move_file",
            "rename_file",
            "copy_file",
            "read_file",
        }:

            if not target:

                target = (
                    parameters.get(
                        "path"
                    )
                    if isinstance(
                        parameters,
                        dict,
                    )
                    else None
                )

            if not target:

                missing.append(
                    "file or folder path"
                )

        # --------------------------------------------------------------
        # Web search
        # --------------------------------------------------------------

        if action in {
            "web_search",
            "search",
        }:

            query = None

            if isinstance(
                parameters,
                dict,
            ):
                query = parameters.get(
                    "query"
                )

            if not query:

                query = (
                    self._extract_search_query(
                        task
                    )
                )

            if not query:

                missing.append(
                    "search query"
                )

        return missing

    # ==================================================================
    # PERMISSION
    # ==================================================================

    def _check_permission(
        self,
        action: str,
        permissions: Optional[
            Dict[str, Any]
        ],
    ) -> Optional[bool]:
        """
        Check permission configuration.

        Returns:
            True  -> explicitly allowed
            False -> explicitly denied
            None  -> no external decision
        """

        if permissions is not None:

            if isinstance(
                permissions,
                dict,
            ):

                # Direct action permission.
                if action in permissions:

                    value = permissions[
                        action
                    ]

                    if isinstance(
                        value,
                        bool,
                    ):
                        return value

                # Category permission.
                risk = self.get_risk_level(
                    action
                )

                category_key = (
                    f"{risk}_risk"
                )

                if category_key in permissions:

                    value = permissions[
                        category_key
                    ]

                    if isinstance(
                        value,
                        bool,
                    ):
                        return value

        # --------------------------------------------------------------
        # Optional permission manager
        # --------------------------------------------------------------

        if self.permission_manager is not None:

            method_names = [
                "is_allowed",
                "check_permission",
                "has_permission",
            ]

            for name in method_names:

                method = getattr(
                    self.permission_manager,
                    name,
                    None,
                )

                if not callable(method):
                    continue

                try:

                    result = method(
                        action
                    )

                    if isinstance(
                        result,
                        bool,
                    ):
                        return result

                except TypeError:

                    try:

                        result = method(
                            permission=action
                        )

                        if isinstance(
                            result,
                            bool,
                        ):
                            return result

                    except Exception:
                        pass

                except Exception as exc:

                    logger.debug(
                        "Permission check failed: %s",
                        exc,
                    )

        return None

    # ==================================================================
    # SECURITY MANAGER
    # ==================================================================

    def _security_requires_confirmation(
        self,
        action: str,
    ) -> bool:

        if self.security_manager is None:
            return False

        methods = [
            "requires_confirmation",
            "needs_confirmation",
            "is_high_risk",
        ]

        for name in methods:

            method = getattr(
                self.security_manager,
                name,
                None,
            )

            if not callable(method):
                continue

            try:

                result = method(
                    action
                )

                if isinstance(
                    result,
                    bool,
                ):
                    return result

            except Exception:
                continue

        return False

    # ==================================================================
    # REASONING CHECKS
    # ==================================================================

    @staticmethod
    def _reasoning_requires_confirmation(
        reasoning_result,
    ) -> bool:

        if reasoning_result is None:
            return False

        return bool(
            getattr(
                reasoning_result,
                "requires_confirmation",
                False,
            )
        )

    @staticmethod
    def _plan_requires_confirmation(
        plan_step,
    ) -> bool:

        if plan_step is None:
            return False

        return bool(
            getattr(
                plan_step,
                "requires_confirmation",
                False,
            )
        )

    @staticmethod
    def _get_reasoning_risks(
        reasoning_result,
    ) -> List[str]:

        if reasoning_result is None:
            return []

        risks = getattr(
            reasoning_result,
            "risks",
            [],
        )

        if not isinstance(
            risks,
            list,
        ):
            return []

        return [
            str(risk)
            for risk in risks
            if str(risk).strip()
        ]

    # ==================================================================
    # CONFIRMATION MESSAGE
    # ==================================================================

    @staticmethod
    def _confirmation_message(
        action: str,
        task: str,
    ) -> str:

        messages = {
            "delete": (
                "This may delete data. "
                "Do you want me to continue?"
            ),
            "delete_file": (
                "This will delete a file. "
                "Do you want me to continue?"
            ),
            "delete_folder": (
                "This will delete a folder "
                "and possibly its contents. "
                "Do you want me to continue?"
            ),
            "shutdown": (
                "This will shut down the computer. "
                "Do you want me to continue?"
            ),
            "restart": (
                "This will restart the computer. "
                "Do you want me to continue?"
            ),
            "format": (
                "Formatting can permanently erase data. "
                "Do you want to continue?"
            ),
            "uninstall": (
                "This will uninstall software. "
                "Do you want me to continue?"
            ),
            "send_email": (
                "This will send an email externally. "
                "Do you want me to continue?"
            ),
            "send_message": (
                "This will send a message externally. "
                "Do you want me to continue?"
            ),
            "payment": (
                "This may perform a financial action. "
                "Do you want me to continue?"
            ),
            "purchase": (
                "This may make a purchase. "
                "Do you want me to continue?"
            ),
        }

        return messages.get(
            action,
            (
                f"The action '{action}' "
                "requires your confirmation. "
                "Do you want me to continue?"
            ),
        )

    # ==================================================================
    # ACTION NORMALIZATION
    # ==================================================================

    @staticmethod
    def _normalize_action(
        action: Optional[str],
    ) -> str:

        if action is None:
            return ""

        value = str(
            action
        ).strip().lower()

        value = re.sub(
            r"\s+",
            "_",
            value,
        )

        return value

    # ==================================================================
    # TEXT HELPERS
    # ==================================================================

    @staticmethod
    def _extract_app_target(
        task: str,
    ) -> Optional[str]:

        patterns = [
            r"(?:open|launch|start)\s+(.+)",
            r"(.+)\s+kholo",
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                task,
                re.IGNORECASE,
            )

            if match:

                value = (
                    match.group(1)
                    .strip()
                )

                if value:
                    return value

        return None

    @staticmethod
    def _extract_search_query(
        task: str,
    ) -> Optional[str]:

        patterns = [
            r"search\s+(?:for\s+)?(.+)",
            r"google\s+(.+)",
            r"search online\s+(.+)",
            r"search karo\s+(.+)",
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                task,
                re.IGNORECASE,
            )

            if match:

                value = (
                    match.group(1)
                    .strip()
                )

                if value:
                    return value

        return None

    # ==================================================================
    # HISTORY
    # ==================================================================

    def _store_and_return(
        self,
        decision: Decision,
    ) -> Decision:

        self.last_decision = decision

        self.decision_history.append(
            decision
        )

        if (
            len(self.decision_history)
            > self.max_history
        ):

            self.decision_history = (
                self.decision_history[
                    -self.max_history:
                ]
            )

        logger.info(
            "Decision: %s | Action: %s",
            decision.decision.value,
            decision.action,
        )

        return decision

    def clear_history(self) -> None:
        """Clear decision history."""

        self.decision_history.clear()
        self.last_decision = None

    # ==================================================================
    # STATUS
    # ==================================================================

    def get_status(self) -> Dict[str, Any]:
        """Return decision engine status."""

        last = self.last_decision

        return {
            "permission_manager": (
                self.permission_manager
                is not None
            ),
            "security_manager": (
                self.security_manager
                is not None
            ),
            "history_count": len(
                self.decision_history
            ),
            "last_decision": (
                last.decision.value
                if last
                else None
            ),
            "last_action": (
                last.action
                if last
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
    print("=" * 70)
    print("JARVIS OS - DECISION ENGINE TEST")
    print("=" * 70)

    engine = DecisionEngine()

    tests = [
        ("open_app", "Chrome kholo", False),
        ("screenshot", "Screenshot lo", False),
        ("web_search", "Python search karo", False),
        ("delete_file", "test.txt delete karo", False),
        ("delete_file", "test.txt delete karo", True),
        ("shutdown", "Computer band karo", False),
        ("shutdown", "Computer band karo", True),
        ("restart", "PC restart karo", False),
        ("disable_security", "Security disable karo", True),
    ]

    for action, task, confirmed in tests:

        print()
        print("-" * 70)

        print(
            "Action:",
            action,
        )

        print(
            "Task:",
            task,
        )

        print(
            "User confirmed:",
            confirmed,
        )

        print(
            "Risk:",
            engine.get_risk_level(
                action
            ),
        )

        decision = engine.decide(
            action=action,
            task=task,
            user_confirmed=confirmed,
        )

        print(
            "Decision:",
            decision.decision.value,
        )

        print(
            "Reason:",
            decision.reason,
        )

        print(
            "Allowed:",
            decision.allowed,
        )

        print(
            "Blocked:",
            decision.blocked,
        )

    print()
    print("-" * 70)
    print("Engine status:")

    for key, value in (
        engine.get_status().items()
    ):

        print(
            f"  {key}: {value}"
        )

    print()
    print("=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)
