# security/permission_manager.py

"""
JARVIS OS - PERMISSION MANAGER
==============================

Central permission and safety layer for JarvisOS.

Responsibilities:
- Define action risk levels
- Allow safe actions
- Require confirmation for risky actions
- Block dangerous actions by default
- Manage user-granted permissions
- Track permission changes
- Provide confirmation messages
- Prevent unknown actions from being executed

IMPORTANT:
This module does NOT execute actions.

It only answers:
    "Is JarvisOS allowed to perform this action?"

Actual execution must happen in the actions/ modules.
"""

from __future__ import annotations

import copy
import json
import logging
import threading
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


logger = logging.getLogger(
    "JarvisOS.PermissionManager"
)


# ============================================================
# ENUMS
# ============================================================

class PermissionDecision(
    str,
    Enum,
):
    """Final permission decision."""

    ALLOW = "allow"

    CONFIRM = "confirm"

    DENY = "deny"

    UNKNOWN = "unknown"


class RiskLevel(
    str,
    Enum,
):
    """Risk classification."""

    LOW = "low"

    MEDIUM = "medium"

    HIGH = "high"

    CRITICAL = "critical"

    BLOCKED = "blocked"


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class PermissionRule:
    """Definition of one action permission."""

    action: str

    risk: RiskLevel

    requires_confirmation: bool = False

    default_allowed: bool = False

    description: str = ""

    permission_name: str = ""

    category: str = "general"


@dataclass
class PermissionRecord:
    """User-granted permission record."""

    permission: str

    granted: bool

    granted_at: str

    source: str = "user"

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )


@dataclass
class PermissionResult:
    """Result of a permission check/change."""

    decision: PermissionDecision

    action: str

    risk: RiskLevel

    allowed: bool

    requires_confirmation: bool

    message: str

    permission: str = ""

    reason: str = ""

    errors: list[str] = field(
        default_factory=list
    )

    warnings: list[str] = field(
        default_factory=list
    )

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self) -> Dict[str, Any]:

        data = asdict(self)

        data["decision"] = (
            self.decision.value
        )

        data["risk"] = (
            self.risk.value
        )

        return data


# ============================================================
# PERMISSION MANAGER
# ============================================================

class PermissionManager:
    """
    Central safety and permission manager.

    Typical usage:

        manager = PermissionManager()

        result = manager.check(
            "shutdown"
        )

        if result.allowed:
            ...
        elif result.requires_confirmation:
            ...
        else:
            ...
    """

    # ========================================================
    # DEFAULT ACTION RULES
    # ========================================================

    DEFAULT_RULES: Dict[
        str,
        PermissionRule,
    ] = {

        # ----------------------------------------------------
        # LOW RISK
        # ----------------------------------------------------

        "get_time": PermissionRule(
            action="get_time",
            risk=RiskLevel.LOW,
            default_allowed=True,
            description=(
                "Read the current time."
            ),
            category="information",
        ),

        "get_date": PermissionRule(
            action="get_date",
            risk=RiskLevel.LOW,
            default_allowed=True,
            description=(
                "Read the current date."
            ),
            category="information",
        ),

        "system_info": PermissionRule(
            action="system_info",
            risk=RiskLevel.LOW,
            default_allowed=True,
            description=(
                "Read system information."
            ),
            category="system",
        ),

        "list_processes": PermissionRule(
            action="list_processes",
            risk=RiskLevel.LOW,
            default_allowed=True,
            description=(
                "List running processes."
            ),
            category="system",
        ),

        "get_volume": PermissionRule(
            action="get_volume",
            risk=RiskLevel.LOW,
            default_allowed=True,
            description=(
                "Read system volume."
            ),
            category="system",
        ),

        "screenshot": PermissionRule(
            action="screenshot",
            risk=RiskLevel.MEDIUM,
            default_allowed=False,
            requires_confirmation=False,
            description=(
                "Capture the computer screen."
            ),
            permission_name="screen_access",
            category="privacy",
        ),

        "open_app": PermissionRule(
            action="open_app",
            risk=RiskLevel.LOW,
            default_allowed=True,
            description=(
                "Open a desktop application."
            ),
            category="computer",
        ),

        "open_url": PermissionRule(
            action="open_url",
            risk=RiskLevel.LOW,
            default_allowed=True,
            description=(
                "Open a web page."
            ),
            category="browser",
        ),

        "search_web": PermissionRule(
            action="search_web",
            risk=RiskLevel.LOW,
            default_allowed=True,
            description=(
                "Search the web."
            ),
            category="browser",
        ),

        "read_file": PermissionRule(
            action="read_file",
            risk=RiskLevel.MEDIUM,
            default_allowed=False,
            description=(
                "Read a local file."
            ),
            permission_name="file_read",
            category="files",
        ),

        "search_files": PermissionRule(
            action="search_files",
            risk=RiskLevel.MEDIUM,
            default_allowed=False,
            description=(
                "Search files on the computer."
            ),
            permission_name="file_read",
            category="files",
        ),

        "create_file": PermissionRule(
            action="create_file",
            risk=RiskLevel.MEDIUM,
            default_allowed=False,
            description=(
                "Create a local file."
            ),
            permission_name="file_write",
            category="files",
        ),

        "rename_file": PermissionRule(
            action="rename_file",
            risk=RiskLevel.MEDIUM,
            default_allowed=False,
            description=(
                "Rename a local file."
            ),
            permission_name="file_write",
            category="files",
        ),

        "copy_file": PermissionRule(
            action="copy_file",
            risk=RiskLevel.MEDIUM,
            default_allowed=False,
            description=(
                "Copy a local file."
            ),
            permission_name="file_write",
            category="files",
        ),

        "move_file": PermissionRule(
            action="move_file",
            risk=RiskLevel.MEDIUM,
            default_allowed=False,
            description=(
                "Move a local file."
            ),
            permission_name="file_write",
            category="files",
        ),

        # ----------------------------------------------------
        # MEDIUM RISK
        # ----------------------------------------------------

        "close_app": PermissionRule(
            action="close_app",
            risk=RiskLevel.MEDIUM,
            default_allowed=False,
            requires_confirmation=True,
            description=(
                "Close a running application."
            ),
            permission_name="app_control",
            category="computer",
        ),

        "keyboard_input": PermissionRule(
            action="keyboard_input",
            risk=RiskLevel.MEDIUM,
            default_allowed=False,
            description=(
                "Control keyboard input."
            ),
            permission_name="input_control",
            category="computer",
        ),

        "mouse_input": PermissionRule(
            action="mouse_input",
            risk=RiskLevel.MEDIUM,
            default_allowed=False,
            description=(
                "Control mouse input."
            ),
            permission_name="input_control",
            category="computer",
        ),

        "file_write": PermissionRule(
            action="file_write",
            risk=RiskLevel.MEDIUM,
            default_allowed=False,
            description=(
                "Write or modify local files."
            ),
            permission_name="file_write",
            category="files",
        ),

        "code_execution": PermissionRule(
            action="code_execution",
            risk=RiskLevel.HIGH,
            default_allowed=False,
            requires_confirmation=True,
            description=(
                "Execute generated or supplied code."
            ),
            permission_name="code_execution",
            category="coding",
        ),

        "plugin_execution": PermissionRule(
            action="plugin_execution",
            risk=RiskLevel.HIGH,
            default_allowed=False,
            requires_confirmation=True,
            description=(
                "Execute third-party plugin code."
            ),
            permission_name="plugin_execution",
            category="plugins",
        ),

        # ----------------------------------------------------
        # HIGH RISK
        # ----------------------------------------------------

        "delete_file": PermissionRule(
            action="delete_file",
            risk=RiskLevel.HIGH,
            default_allowed=False,
            requires_confirmation=True,
            description=(
                "Delete a local file."
            ),
            permission_name="file_delete",
            category="files",
        ),

        "delete_folder": PermissionRule(
            action="delete_folder",
            risk=RiskLevel.HIGH,
            default_allowed=False,
            requires_confirmation=True,
            description=(
                "Delete a local folder."
            ),
            permission_name="file_delete",
            category="files",
        ),

        "install_software": PermissionRule(
            action="install_software",
            risk=RiskLevel.HIGH,
            default_allowed=False,
            requires_confirmation=True,
            description=(
                "Install software on the computer."
            ),
            permission_name="software_install",
            category="system",
        ),

        "send_email": PermissionRule(
            action="send_email",
            risk=RiskLevel.HIGH,
            default_allowed=False,
            requires_confirmation=True,
            description=(
                "Send an email."
            ),
            permission_name="communication_send",
            category="communication",
        ),

        "send_whatsapp": PermissionRule(
            action="send_whatsapp",
            risk=RiskLevel.HIGH,
            default_allowed=False,
            requires_confirmation=True,
            description=(
                "Send a WhatsApp message."
            ),
            permission_name="communication_send",
            category="communication",
        ),

        "send_telegram": PermissionRule(
            action="send_telegram",
            risk=RiskLevel.HIGH,
            default_allowed=False,
            requires_confirmation=True,
            description=(
                "Send a Telegram message."
            ),
            permission_name="communication_send",
            category="communication",
        ),

        "transfer_file": PermissionRule(
            action="transfer_file",
            risk=RiskLevel.HIGH,
            default_allowed=False,
            requires_confirmation=True,
            description=(
                "Transfer files between devices."
            ),
            permission_name="file_transfer",
            category="mobile",
        ),

        "purchase": PermissionRule(
            action="purchase",
            risk=RiskLevel.CRITICAL,
            default_allowed=False,
            requires_confirmation=True,
            description=(
                "Make a purchase or financial transaction."
            ),
            permission_name="financial_action",
            category="financial",
        ),

        "payment": PermissionRule(
            action="payment",
            risk=RiskLevel.CRITICAL,
            default_allowed=False,
            requires_confirmation=True,
            description=(
                "Perform a payment."
            ),
            permission_name="financial_action",
            category="financial",
        ),

        # ----------------------------------------------------
        # CRITICAL / BLOCKED
        # ----------------------------------------------------

        "format_disk": PermissionRule(
            action="format_disk",
            risk=RiskLevel.BLOCKED,
            default_allowed=False,
            requires_confirmation=True,
            description=(
                "Format a disk."
            ),
            category="system",
        ),

        "system_reset": PermissionRule(
            action="system_reset",
            risk=RiskLevel.BLOCKED,
            default_allowed=False,
            requires_confirmation=True,
            description=(
                "Reset the operating system."
            ),
            category="system",
        ),

        "disable_security": PermissionRule(
            action="disable_security",
            risk=RiskLevel.BLOCKED,
            default_allowed=False,
            requires_confirmation=True,
            description=(
                "Disable operating-system security."
            ),
            category="security",
        ),

        "steal_credentials": PermissionRule(
            action="steal_credentials",
            risk=RiskLevel.BLOCKED,
            default_allowed=False,
            requires_confirmation=True,
            description=(
                "Attempt to obtain credentials."
            ),
            category="security",
        ),

        "shutdown": PermissionRule(
            action="shutdown",
            risk=RiskLevel.HIGH,
            default_allowed=False,
            requires_confirmation=True,
            description=(
                "Shut down Windows."
            ),
            permission_name="system_power",
            category="system",
        ),

        "restart": PermissionRule(
            action="restart",
            risk=RiskLevel.HIGH,
            default_allowed=False,
            requires_confirmation=True,
            description=(
                "Restart Windows."
            ),
            permission_name="system_power",
            category="system",
        ),

        "sleep": PermissionRule(
            action="sleep",
            risk=RiskLevel.MEDIUM,
            default_allowed=False,
            requires_confirmation=True,
            description=(
                "Put Windows into sleep mode."
            ),
            permission_name="system_power",
            category="system",
        ),

        "lock_windows": PermissionRule(
            action="lock_windows",
            risk=RiskLevel.LOW,
            default_allowed=True,
            description=(
                "Lock the Windows session."
            ),
            category="system",
        ),
    }

    # ========================================================
    # CONSTRUCTOR
    # ========================================================

    def __init__(
        self,
        storage_path: Optional[
            str | Path
        ] = None,
    ):

        if storage_path is None:

            self.storage_path = (
                Path(__file__).resolve().parent
                / "permissions.json"
            )

        else:

            self.storage_path = (
                Path(
                    storage_path
                )
                .expanduser()
                .resolve()
            )

        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._lock = (
            threading.RLock()
        )

        self.rules: Dict[
            str,
            PermissionRule,
        ] = copy.deepcopy(
            self.DEFAULT_RULES
        )

        self.grants: Dict[
            str,
            PermissionRecord,
        ] = {}

        self.history: list[
            Dict[str, Any]
        ] = []

        self.max_history = 200

        self._load()

    # ========================================================
    # TIME
    # ========================================================

    @staticmethod
    def _utc_now() -> str:

        from datetime import (
            datetime,
            timezone,
        )

        return (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

    # ========================================================
    # NORMALIZE ACTION
    # ========================================================

    @staticmethod
    def normalize_action(
        action: str,
    ) -> str:

        value = (
            action or ""
        ).strip().lower()

        aliases = {
            "open": "open_app",
            "launch_app": "open_app",
            "start_app": "open_app",

            "close": "close_app",
            "quit_app": "close_app",

            "delete": "delete_file",
            "remove_file": "delete_file",

            "remove_folder": "delete_folder",

            "run_code": "code_execution",
            "execute_code": "code_execution",

            "send_mail": "send_email",

            "whatsapp": "send_whatsapp",

            "telegram": "send_telegram",

            "restart_pc": "restart",
            "reboot": "restart",

            "shutdown_pc": "shutdown",

            "screen_capture": "screenshot",

            "web_search": "search_web",
        }

        return aliases.get(
            value,
            value,
        )

    # ========================================================
    # LOAD
    # ========================================================

    def _load(
        self,
    ) -> None:

        if not self.storage_path.exists():
            return

        try:

            with open(
                self.storage_path,
                "r",
                encoding="utf-8",
            ) as file:

                data = json.load(
                    file
                )

            if not isinstance(
                data,
                dict,
            ):

                return

            stored_grants = data.get(
                "grants",
                {},
            )

            if not isinstance(
                stored_grants,
                dict,
            ):

                return

            for permission, raw in (
                stored_grants.items()
            ):

                if not isinstance(
                    raw,
                    dict,
                ):

                    continue

                self.grants[
                    permission
                ] = PermissionRecord(
                    permission=(
                        str(
                            raw.get(
                                "permission",
                                permission,
                            )
                        )
                    ),
                    granted=bool(
                        raw.get(
                            "granted",
                            False,
                        )
                    ),
                    granted_at=str(
                        raw.get(
                            "granted_at",
                            "",
                        )
                    ),
                    source=str(
                        raw.get(
                            "source",
                            "user",
                        )
                    ),
                    metadata=dict(
                        raw.get(
                            "metadata",
                            {},
                        )
                    ),
                )

        except Exception as exc:

            logger.warning(
                "Could not load permission state: %s",
                exc,
            )

    # ========================================================
    # SAVE
    # ========================================================

    def _save(
        self,
    ) -> None:

        payload = {
            "version": 1,
            "updated_at": (
                self._utc_now()
            ),
            "grants": {
                permission: asdict(
                    record
                )
                for permission, record
                in self.grants.items()
            },
        }

        temporary = (
            self.storage_path.with_suffix(
                ".tmp"
            )
        )

        with open(
            temporary,
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                payload,
                file,
                indent=2,
                ensure_ascii=False,
            )

            file.write(
                "\n"
            )

        temporary.replace(
            self.storage_path
        )

    # ========================================================
    # RULE LOOKUP
    # ========================================================

    def get_rule(
        self,
        action: str,
    ) -> Optional[PermissionRule]:

        normalized = (
            self.normalize_action(
                action
            )
        )

        with self._lock:

            rule = self.rules.get(
                normalized
            )

            return (
                copy.deepcopy(rule)
                if rule
                else None
            )

    def get_risk_level(
        self,
        action: str,
    ) -> RiskLevel:

        rule = self.get_rule(
            action
        )

        if rule is None:

            return RiskLevel.HIGH

        return rule.risk

    # ========================================================
    # PERMISSION NAME
    # ========================================================

    def get_permission_name(
        self,
        action: str,
    ) -> str:

        rule = self.get_rule(
            action
        )

        if rule is None:

            return self.normalize_action(
                action
            )

        return (
            rule.permission_name
            or rule.action
        )

    # ========================================================
    # GRANT CHECK
    # ========================================================

    def has_permission(
        self,
        permission: str,
    ) -> bool:

        value = (
            permission or ""
        ).strip().lower()

        with self._lock:

            record = self.grants.get(
                value
            )

            return bool(
                record
                and record.granted
            )

    # ========================================================
    # GRANT
    # ========================================================

    def grant(
        self,
        permission: str,
        *,
        source: str = "user",
        metadata: Optional[
            Dict[str, Any]
        ] = None,
    ) -> PermissionResult:

        value = (
            permission or ""
        ).strip().lower()

        if not value:

            return PermissionResult(
                decision=(
                    PermissionDecision.DENY
                ),
                action="",
                risk=RiskLevel.HIGH,
                allowed=False,
                requires_confirmation=False,
                message=(
                    "Permission name cannot be empty."
                ),
                errors=[
                    "empty_permission"
                ],
            )

        with self._lock:

            record = PermissionRecord(
                permission=value,
                granted=True,
                granted_at=(
                    self._utc_now()
                ),
                source=source,
                metadata=(
                    copy.deepcopy(
                        metadata or {}
                    )
                ),
            )

            self.grants[
                value
            ] = record

            self._record_history(
                "grant",
                value,
                source,
            )

            self._save()

        return PermissionResult(
            decision=(
                PermissionDecision.ALLOW
            ),
            action="",
            risk=RiskLevel.LOW,
            allowed=True,
            requires_confirmation=False,
            message=(
                f"Permission '{value}' granted."
            ),
            permission=value,
        )

    # ========================================================
    # REVOKE
    # ========================================================

    def revoke(
        self,
        permission: str,
    ) -> PermissionResult:

        value = (
            permission or ""
        ).strip().lower()

        with self._lock:

            existed = (
                value in self.grants
            )

            if existed:

                self.grants[
                    value
                ].granted = False

                self._record_history(
                    "revoke",
                    value,
                    "user",
                )

                self._save()

        return PermissionResult(
            decision=(
                PermissionDecision.DENY
            ),
            action="",
            risk=RiskLevel.LOW,
            allowed=False,
            requires_confirmation=False,
            message=(
                f"Permission '{value}' "
                f"{'revoked' if existed else 'was not granted'}."
            ),
            permission=value,
        )

    # ========================================================
    # CHECK
    # ========================================================

    def check(
        self,
        action: str,
        *,
        user_confirmed: bool = False,
        temporary_permission: bool = False,
    ) -> PermissionResult:

        normalized = (
            self.normalize_action(
                action
            )
        )

        rule = self.get_rule(
            normalized
        )

        # Unknown actions are denied by default.
        if rule is None:

            return PermissionResult(
                decision=(
                    PermissionDecision.UNKNOWN
                ),
                action=normalized,
                risk=RiskLevel.HIGH,
                allowed=False,
                requires_confirmation=False,
                message=(
                    "Unknown action. "
                    "JarvisOS will not execute it "
                    "until an explicit permission rule exists."
                ),
                reason="unknown_action",
            )

        # Blocked actions can never be approved through
        # the normal confirmation mechanism.
        if rule.risk == RiskLevel.BLOCKED:

            return PermissionResult(
                decision=(
                    PermissionDecision.DENY
                ),
                action=normalized,
                risk=RiskLevel.BLOCKED,
                allowed=False,
                requires_confirmation=False,
                message=(
                    f"Action '{normalized}' is blocked "
                    "by the JarvisOS security policy."
                ),
                permission=(
                    rule.permission_name
                    or rule.action
                ),
                reason="blocked_action",
            )

        permission = (
            rule.permission_name
            or rule.action
        )

        granted = (
            self.has_permission(
                permission
            )
        )

        # Explicit temporary approval.
        if temporary_permission:

            granted = True

        # High/critical risk actions always require
        # explicit confirmation, even if a permission
        # exists.
        if rule.requires_confirmation:

            if user_confirmed:

                return PermissionResult(
                    decision=(
                        PermissionDecision.ALLOW
                    ),
                    action=normalized,
                    risk=rule.risk,
                    allowed=True,
                    requires_confirmation=False,
                    message=(
                        f"Action '{normalized}' "
                        "approved after confirmation."
                    ),
                    permission=permission,
                    reason="user_confirmed",
                )

            return PermissionResult(
                decision=(
                    PermissionDecision.CONFIRM
                ),
                action=normalized,
                risk=rule.risk,
                allowed=False,
                requires_confirmation=True,
                message=(
                    self.build_confirmation_message(
                        normalized
                    )
                ),
                permission=permission,
                reason="confirmation_required",
            )

        # Explicitly granted permission.
        if granted:

            return PermissionResult(
                decision=(
                    PermissionDecision.ALLOW
                ),
                action=normalized,
                risk=rule.risk,
                allowed=True,
                requires_confirmation=False,
                message=(
                    f"Action '{normalized}' is permitted."
                ),
                permission=permission,
                reason="permission_granted",
            )

        # Safe defaults.
        if rule.default_allowed:

            return PermissionResult(
                decision=(
                    PermissionDecision.ALLOW
                ),
                action=normalized,
                risk=rule.risk,
                allowed=True,
                requires_confirmation=False,
                message=(
                    f"Action '{normalized}' is allowed."
                ),
                permission=permission,
                reason="safe_default",
            )

        # Permission missing.
        return PermissionResult(
            decision=(
                PermissionDecision.DENY
            ),
            action=normalized,
            risk=rule.risk,
            allowed=False,
            requires_confirmation=False,
            message=(
                f"Permission '{permission}' "
                f"is required for '{normalized}'."
            ),
            permission=permission,
            reason="permission_missing",
        )

    # ========================================================
    # CONFIRMATION MESSAGE
    # ========================================================

    def build_confirmation_message(
        self,
        action: str,
    ) -> str:

        normalized = (
            self.normalize_action(
                action
            )
        )

        rule = self.get_rule(
            normalized
        )

        if rule is None:

            return (
                "This action requires permission."
            )

        descriptions = {
            "delete_file": (
                "delete a file"
            ),
            "delete_folder": (
                "delete a folder"
            ),
            "shutdown": (
                "shut down the computer"
            ),
            "restart": (
                "restart the computer"
            ),
            "sleep": (
                "put the computer to sleep"
            ),
            "send_email": (
                "send an email"
            ),
            "send_whatsapp": (
                "send a WhatsApp message"
            ),
            "send_telegram": (
                "send a Telegram message"
            ),
            "code_execution": (
                "execute code"
            ),
            "plugin_execution": (
                "execute plugin code"
            ),
            "install_software": (
                "install software"
            ),
            "transfer_file": (
                "transfer a file"
            ),
            "purchase": (
                "make a purchase"
            ),
            "payment": (
                "make a payment"
            ),
        }

        description = descriptions.get(
            normalized,
            rule.description
            or normalized,
        )

        return (
            f"This action will {description}. "
            "Do you want me to continue?"
        )

    # ========================================================
    # ACTION BATCH CHECK
    # ========================================================

    def check_many(
        self,
        actions: Iterable[str],
        *,
        user_confirmed: bool = False,
    ) -> list[PermissionResult]:

        return [
            self.check(
                action,
                user_confirmed=user_confirmed,
            )
            for action in actions
        ]

    def all_allowed(
        self,
        actions: Iterable[str],
    ) -> bool:

        results = self.check_many(
            actions
        )

        return all(
            result.allowed
            for result in results
        )

    # ========================================================
    # RULE MANAGEMENT
    # ========================================================

    def add_rule(
        self,
        action: str,
        risk: RiskLevel | str,
        *,
        requires_confirmation: bool = False,
        default_allowed: bool = False,
        description: str = "",
        permission_name: str = "",
        category: str = "custom",
    ) -> PermissionResult:

        normalized = (
            self.normalize_action(
                action
            )
        )

        try:

            risk_value = (
                risk
                if isinstance(
                    risk,
                    RiskLevel,
                )
                else RiskLevel(
                    str(risk).lower()
                )
            )

        except ValueError:

            return PermissionResult(
                decision=(
                    PermissionDecision.DENY
                ),
                action=normalized,
                risk=RiskLevel.HIGH,
                allowed=False,
                requires_confirmation=False,
                message=(
                    "Invalid risk level."
                ),
                errors=[
                    str(risk)
                ],
            )

        # Prevent accidentally creating a rule that
        # allows a blocked action.
        if (
            risk_value
            == RiskLevel.BLOCKED
        ):

            default_allowed = False
            requires_confirmation = True

        with self._lock:

            self.rules[
                normalized
            ] = PermissionRule(
                action=normalized,
                risk=risk_value,
                requires_confirmation=(
                    requires_confirmation
                ),
                default_allowed=(
                    default_allowed
                ),
                description=description,
                permission_name=(
                    permission_name
                    or normalized
                ),
                category=category,
            )

        return PermissionResult(
            decision=(
                PermissionDecision.ALLOW
            ),
            action=normalized,
            risk=risk_value,
            allowed=True,
            requires_confirmation=False,
            message=(
                f"Permission rule '{normalized}' added."
            ),
        )

    def remove_rule(
        self,
        action: str,
    ) -> PermissionResult:

        normalized = (
            self.normalize_action(
                action
            )
        )

        # Built-in security rules cannot be removed.
        if normalized in self.DEFAULT_RULES:

            return PermissionResult(
                decision=(
                    PermissionDecision.DENY
                ),
                action=normalized,
                risk=(
                    self.DEFAULT_RULES[
                        normalized
                    ].risk
                ),
                allowed=False,
                requires_confirmation=False,
                message=(
                    "Built-in security rules "
                    "cannot be removed."
                ),
                reason="protected_rule",
            )

        with self._lock:

            existed = (
                normalized
                in self.rules
            )

            self.rules.pop(
                normalized,
                None,
            )

        return PermissionResult(
            decision=(
                PermissionDecision.ALLOW
                if existed
                else PermissionDecision.DENY
            ),
            action=normalized,
            risk=RiskLevel.HIGH,
            allowed=existed,
            requires_confirmation=False,
            message=(
                "Custom permission rule removed."
                if existed
                else "Permission rule not found."
            ),
        )

    # ========================================================
    # LIST RULES
    # ========================================================

    def list_rules(
        self,
        category: Optional[str] = None,
    ) -> list[PermissionRule]:

        with self._lock:

            rules = list(
                self.rules.values()
            )

        if category:

            category = (
                category.strip().lower()
            )

            rules = [
                rule
                for rule in rules
                if rule.category.lower()
                == category
            ]

        return copy.deepcopy(
            rules
        )

    # ========================================================
    # GRANTED PERMISSIONS
    # ========================================================

    def list_grants(
        self,
    ) -> list[PermissionRecord]:

        with self._lock:

            return copy.deepcopy(
                list(
                    self.grants.values()
                )
            )

    # ========================================================
    # HISTORY
    # ========================================================

    def _record_history(
        self,
        operation: str,
        permission: str,
        source: str,
    ) -> None:

        self.history.append(
            {
                "operation": operation,
                "permission": permission,
                "source": source,
                "timestamp": (
                    self._utc_now()
                ),
            }
        )

        if (
            len(self.history)
            > self.max_history
        ):

            self.history = (
                self.history[
                    -self.max_history:
                ]
            )

    def get_history(
        self,
    ) -> list[Dict[str, Any]]:

        with self._lock:

            return copy.deepcopy(
                self.history
            )

    # ========================================================
    # RESET
    # ========================================================

    def reset(
        self,
        *,
        confirm: bool = False,
    ) -> PermissionResult:

        if not confirm:

            return PermissionResult(
                decision=(
                    PermissionDecision.CONFIRM
                ),
                action="reset_permissions",
                risk=RiskLevel.HIGH,
                allowed=False,
                requires_confirmation=True,
                message=(
                    "Resetting all permissions "
                    "requires confirmation."
                ),
            )

        with self._lock:

            self.grants.clear()

            self._record_history(
                "reset",
                "*",
                "user",
            )

            self._save()

        return PermissionResult(
            decision=(
                PermissionDecision.ALLOW
            ),
            action="reset_permissions",
            risk=RiskLevel.HIGH,
            allowed=True,
            requires_confirmation=False,
            message=(
                "All user-granted permissions "
                "have been revoked."
            ),
        )

    # ========================================================
    # STATUS
    # ========================================================

    def get_status(
        self,
    ) -> Dict[str, Any]:

        with self._lock:

            granted = [
                permission
                for permission, record
                in self.grants.items()
                if record.granted
            ]

            risk_counts = {
                level.value: 0
                for level in RiskLevel
            }

            for rule in self.rules.values():

                risk_counts[
                    rule.risk.value
                ] += 1

            return {
                "storage_path": str(
                    self.storage_path
                ),
                "rule_count": len(
                    self.rules
                ),
                "grant_count": len(
                    granted
                ),
                "granted_permissions": (
                    sorted(granted)
                ),
                "risk_counts": risk_counts,
                "history_count": len(
                    self.history
                ),
            }

    # ========================================================
    # CLOSE
    # ========================================================

    def close(
        self,
    ) -> None:

        with self._lock:

            self._save()

    def __enter__(
        self,
    ) -> "PermissionManager":

        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback_value,
    ) -> None:

        self.close()


# ============================================================
# SHARED INSTANCE
# ============================================================

_permission_manager: Optional[
    PermissionManager
] = None

_permission_manager_lock = (
    threading.Lock()
)


def get_permission_manager() -> PermissionManager:

    global _permission_manager

    with _permission_manager_lock:

        if _permission_manager is None:

            _permission_manager = (
                PermissionManager()
            )

        return _permission_manager


# ============================================================
# CONVENIENCE FUNCTIONS
# ============================================================

def check_permission(
    action: str,
    *,
    user_confirmed: bool = False,
) -> PermissionResult:

    return (
        get_permission_manager()
        .check(
            action,
            user_confirmed=user_confirmed,
        )
    )


def grant_permission(
    permission: str,
) -> PermissionResult:

    return (
        get_permission_manager()
        .grant(
            permission
        )
    )


def revoke_permission(
    permission: str,
) -> PermissionResult:

    return (
        get_permission_manager()
        .revoke(
            permission
        )
    )


def has_permission(
    permission: str,
) -> bool:

    return (
        get_permission_manager()
        .has_permission(
            permission
        )
    )


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

    print("=" * 60)
    print(
        "JARVIS OS - PERMISSION MANAGER TEST"
    )
    print("=" * 60)

    test_path = (
        Path(__file__).resolve().parent
        / "permissions.test.json"
    )

    manager = PermissionManager(
        storage_path=test_path
    )

    print("\nSafe action:")

    result = manager.check(
        "get_time"
    )

    print(
        json.dumps(
            result.to_dict(),
            indent=2,
        )
    )

    print("\nShutdown action:")

    result = manager.check(
        "shutdown"
    )

    print(
        json.dumps(
            result.to_dict(),
            indent=2,
        )
    )

    print("\nDelete action:")

    result = manager.check(
        "delete_file"
    )

    print(
        json.dumps(
            result.to_dict(),
            indent=2,
        )
    )

    print("\nBlocked action:")

    result = manager.check(
        "format_disk"
    )

    print(
        json.dumps(
            result.to_dict(),
            indent=2,
        )
    )

    print("\nConfirmed shutdown:")

    result = manager.check(
        "shutdown",
        user_confirmed=True,
    )

    print(
        json.dumps(
            result.to_dict(),
            indent=2,
        )
    )

    print("\nStatus:")

    print(
        json.dumps(
            manager.get_status(),
            indent=2,
        )
    )

    manager.close()

    try:

        if test_path.exists():

            test_path.unlink()

    except Exception:
        pass

    print(
        "\nPermission manager test completed."
)
