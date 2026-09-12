"""
JarvisOS - Keyboard Control
===========================

Controls the Windows keyboard using PyAutoGUI.

Features:
- Type text
- Press individual keys
- Press multiple keys
- Hotkeys / shortcuts
- Copy / paste
- Select all
- Undo / redo
- Enter / Escape / Tab
- Backspace / delete
- Clear text
- Keyboard status
- Safe error handling

IMPORTANT:
This module performs real keyboard actions.
The higher-level DecisionEngine / PermissionManager should decide
whether an action is allowed before calling dangerous operations.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

try:
    import pyautogui
except ImportError:
    pyautogui = None


logger = logging.getLogger("JarvisOS.KeyboardControl")


@dataclass
class KeyboardResult:
    """Result returned by keyboard operations."""

    success: bool
    action: str
    message: str = ""
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "action": self.action,
            "message": self.message,
            "error": self.error,
        }


class KeyboardControl:
    """
    Real keyboard controller for JarvisOS.

    Example:

        keyboard = KeyboardControl()

        keyboard.type_text("Hello")
        keyboard.press("enter")
        keyboard.hotkey("ctrl", "c")
        keyboard.hotkey("ctrl", "v")
    """

    # Common keys accepted by PyAutoGUI.
    COMMON_KEYS = {
        "a",
        "b",
        "c",
        "d",
        "e",
        "f",
        "g",
        "h",
        "i",
        "j",
        "k",
        "l",
        "m",
        "n",
        "o",
        "p",
        "q",
        "r",
        "s",
        "t",
        "u",
        "v",
        "w",
        "x",
        "y",
        "z",
        "0",
        "1",
        "2",
        "3",
        "4",
        "5",
        "6",
        "7",
        "8",
        "9",
        "enter",
        "return",
        "esc",
        "escape",
        "tab",
        "space",
        "backspace",
        "delete",
        "insert",
        "home",
        "end",
        "pageup",
        "pagedown",
        "up",
        "down",
        "left",
        "right",
        "shift",
        "ctrl",
        "control",
        "alt",
        "win",
        "command",
        "capslock",
        "numlock",
        "scrolllock",
        "printscreen",
        "pause",
        "menu",
        "decimal",
        "add",
        "subtract",
        "multiply",
        "divide",
        "separator",
        "f1",
        "f2",
        "f3",
        "f4",
        "f5",
        "f6",
        "f7",
        "f8",
        "f9",
        "f10",
        "f11",
        "f12",
        "f13",
        "f14",
        "f15",
        "f16",
        "f17",
        "f18",
        "f19",
        "f20",
        "f21",
        "f22",
        "f23",
        "f24",
    }

    KEY_ALIASES = {
        "return": "enter",
        "escape": "esc",
        "control": "ctrl",
        "windows": "win",
        "super": "win",
        "cmd": "command",
        "spacebar": "space",
        "back": "backspace",
        "del": "delete",
        "pgup": "pageup",
        "pgdn": "pagedown",
    }

    def __init__(
        self,
        typing_interval: float = 0.01,
        action_delay: float = 0.05,
        fail_safe: bool = True,
    ):
        self.typing_interval = max(0.0, float(typing_interval))
        self.action_delay = max(0.0, float(action_delay))
        self.fail_safe = bool(fail_safe)

        self._available = pyautogui is not None

        if self._available:
            try:
                pyautogui.PAUSE = self.action_delay
                pyautogui.FAILSAFE = self.fail_safe
            except Exception as exc:
                logger.warning("Could not configure PyAutoGUI: %s", exc)

        logger.info(
            "KeyboardControl initialized. available=%s",
            self._available,
        )

    # =========================================================
    # BASIC STATUS
    # =========================================================

    def is_available(self) -> bool:
        """Return True when PyAutoGUI is installed and usable."""

        return self._available

    def get_status(self) -> dict:
        """Return keyboard controller status."""

        return {
            "available": self._available,
            "typing_interval": self.typing_interval,
            "action_delay": self.action_delay,
            "fail_safe": self.fail_safe,
        }

    def _check_available(self) -> Optional[KeyboardResult]:
        """Return an error result when keyboard control is unavailable."""

        if not self._available:
            return KeyboardResult(
                success=False,
                action="availability_check",
                message="Keyboard control is unavailable.",
                error=(
                    "PyAutoGUI is not installed. "
                    "Install it with: pip install pyautogui"
                ),
            )

        return None

    @staticmethod
    def _normalize_key(key: str) -> str:
        """Normalize common keyboard aliases."""

        normalized = str(key).strip().lower()

        return KeyboardControl.KEY_ALIASES.get(
            normalized,
            normalized,
        )

    def _validate_key(self, key: str) -> str:
        """Validate and normalize a keyboard key."""

        normalized = self._normalize_key(key)

        if normalized not in self.COMMON_KEYS:
            raise ValueError(
                f"Unsupported keyboard key: {key!r}"
            )

        return normalized

    # =========================================================
    # TYPE TEXT
    # =========================================================

    def type_text(
        self,
        text: str,
        interval: Optional[float] = None,
    ) -> KeyboardResult:
        """
        Type text using the keyboard.

        Example:
            keyboard.type_text("Hello Jarvis")
        """

        unavailable = self._check_available()

        if unavailable:
            unavailable.action = "type_text"
            return unavailable

        if text is None:
            return KeyboardResult(
                success=False,
                action="type_text",
                error="Text cannot be None.",
            )

        text = str(text)

        try:
            actual_interval = (
                self.typing_interval
                if interval is None
                else max(0.0, float(interval))
            )

            pyautogui.write(
                text,
                interval=actual_interval,
            )

            return KeyboardResult(
                success=True,
                action="type_text",
                message=f"Typed {len(text)} characters.",
            )

        except Exception as exc:
            logger.exception("Keyboard typing failed.")

            return KeyboardResult(
                success=False,
                action="type_text",
                error=str(exc),
            )

    def write(self, text: str) -> KeyboardResult:
        """Alias for type_text()."""

        return self.type_text(text)

    # =========================================================
    # PRESS KEY
    # =========================================================

    def press(
        self,
        key: str,
        presses: int = 1,
        interval: Optional[float] = None,
    ) -> KeyboardResult:
        """
        Press a keyboard key one or more times.

        Examples:
            keyboard.press("enter")
            keyboard.press("f5")
            keyboard.press("backspace", presses=5)
        """

        unavailable = self._check_available()

        if unavailable:
            unavailable.action = "press"
            return unavailable

        try:
            normalized = self._validate_key(key)

            presses = int(presses)

            if presses < 1:
                raise ValueError("presses must be at least 1.")

            actual_interval = (
                self.action_delay
                if interval is None
                else max(0.0, float(interval))
            )

            pyautogui.press(
                normalized,
                presses=presses,
                interval=actual_interval,
            )

            return KeyboardResult(
                success=True,
                action="press",
                message=(
                    f"Pressed '{normalized}' "
                    f"{presses} time(s)."
                ),
            )

        except Exception as exc:
            logger.exception("Key press failed.")

            return KeyboardResult(
                success=False,
                action="press",
                error=str(exc),
            )

    # =========================================================
    # MULTIPLE KEYS
    # =========================================================

    def press_keys(
        self,
        keys: Sequence[str],
    ) -> KeyboardResult:
        """
        Press multiple keys sequentially.

        Example:
            keyboard.press_keys(["a", "b", "c"])
        """

        unavailable = self._check_available()

        if unavailable:
            unavailable.action = "press_keys"
            return unavailable

        if not keys:
            return KeyboardResult(
                success=False,
                action="press_keys",
                error="No keys were provided.",
            )

        try:
            normalized_keys = [
                self._validate_key(key)
                for key in keys
            ]

            for key in normalized_keys:
                pyautogui.press(key)

            return KeyboardResult(
                success=True,
                action="press_keys",
                message=(
                    f"Pressed {len(normalized_keys)} key(s)."
                ),
            )

        except Exception as exc:
            logger.exception("Multiple key press failed.")

            return KeyboardResult(
                success=False,
                action="press_keys",
                error=str(exc),
            )

    # =========================================================
    # HOTKEY
    # =========================================================

    def hotkey(
        self,
        *keys: str,
    ) -> KeyboardResult:
        """
        Press a keyboard shortcut.

        Examples:
            Ctrl+C:
                keyboard.hotkey("ctrl", "c")

            Ctrl+V:
                keyboard.hotkey("ctrl", "v")

            Alt+F4:
                keyboard.hotkey("alt", "f4")

            Windows+D:
                keyboard.hotkey("win", "d")
        """

        unavailable = self._check_available()

        if unavailable:
            unavailable.action = "hotkey"
            return unavailable

        if not keys:
            return KeyboardResult(
                success=False,
                action="hotkey",
                error="No hotkey keys were provided.",
            )

        try:
            normalized_keys = [
                self._validate_key(key)
                for key in keys
            ]

            pyautogui.hotkey(*normalized_keys)

            return KeyboardResult(
                success=True,
                action="hotkey",
                message=(
                    "Pressed shortcut: "
                    + "+".join(normalized_keys)
                ),
            )

        except Exception as exc:
            logger.exception("Hotkey failed.")

            return KeyboardResult(
                success=False,
                action="hotkey",
                error=str(exc),
            )

    # =========================================================
    # KEY DOWN / KEY UP
    # =========================================================

    def key_down(self, key: str) -> KeyboardResult:
        """Hold a keyboard key down."""

        unavailable = self._check_available()

        if unavailable:
            unavailable.action = "key_down"
            return unavailable

        try:
            normalized = self._validate_key(key)

            pyautogui.keyDown(normalized)

            return KeyboardResult(
                success=True,
                action="key_down",
                message=f"Key down: {normalized}",
            )

        except Exception as exc:
            logger.exception("key_down failed.")

            return KeyboardResult(
                success=False,
                action="key_down",
                error=str(exc),
            )

    def key_up(self, key: str) -> KeyboardResult:
        """Release a keyboard key."""

        unavailable = self._check_available()

        if unavailable:
            unavailable.action = "key_up"
            return unavailable

        try:
            normalized = self._validate_key(key)

            pyautogui.keyUp(normalized)

            return KeyboardResult(
                success=True,
                action="key_up",
                message=f"Key up: {normalized}",
            )

        except Exception as exc:
            logger.exception("key_up failed.")

            return KeyboardResult(
                success=False,
                action="key_up",
                error=str(exc),
            )

    # =========================================================
    # COMMON SHORTCUTS
    # =========================================================

    def copy(self) -> KeyboardResult:
        """Ctrl+C."""

        return self.hotkey("ctrl", "c")

    def paste(self) -> KeyboardResult:
        """Ctrl+V."""

        return self.hotkey("ctrl", "v")

    def cut(self) -> KeyboardResult:
        """Ctrl+X."""

        return self.hotkey("ctrl", "x")

    def select_all(self) -> KeyboardResult:
        """Ctrl+A."""

        return self.hotkey("ctrl", "a")

    def undo(self) -> KeyboardResult:
        """Ctrl+Z."""

        return self.hotkey("ctrl", "z")

    def redo(self) -> KeyboardResult:
        """Ctrl+Y."""

        return self.hotkey("ctrl", "y")

    def save(self) -> KeyboardResult:
        """Ctrl+S."""

        return self.hotkey("ctrl", "s")

    def open_file(self) -> KeyboardResult:
        """Ctrl+O."""

        return self.hotkey("ctrl", "o")

    def find(self) -> KeyboardResult:
        """Ctrl+F."""

        return self.hotkey("ctrl", "f")

    def refresh(self) -> KeyboardResult:
        """F5 refresh."""

        return self.press("f5")

    # =========================================================
    # NAVIGATION
    # =========================================================

    def enter(self) -> KeyboardResult:
        return self.press("enter")

    def escape(self) -> KeyboardResult:
        return self.press("esc")

    def tab(self) -> KeyboardResult:
        return self.press("tab")

    def space(self) -> KeyboardResult:
        return self.press("space")

    def backspace(self, presses: int = 1) -> KeyboardResult:
        return self.press(
            "backspace",
            presses=presses,
        )

    def delete(self, presses: int = 1) -> KeyboardResult:
        return self.press(
            "delete",
            presses=presses,
        )

    def arrow_up(self, presses: int = 1) -> KeyboardResult:
        return self.press("up", presses=presses)

    def arrow_down(self, presses: int = 1) -> KeyboardResult:
        return self.press("down", presses=presses)

    def arrow_left(self, presses: int = 1) -> KeyboardResult:
        return self.press("left", presses=presses)

    def arrow_right(self, presses: int = 1) -> KeyboardResult:
        return self.press("right", presses=presses)

    def home(self) -> KeyboardResult:
        return self.press("home")

    def end(self) -> KeyboardResult:
        return self.press("end")

    # =========================================================
    # CLEAR TEXT
    # =========================================================

    def clear_current_field(
        self,
        use_delete: bool = True,
    ) -> KeyboardResult:
        """
        Select all text in the active field and delete it.

        This acts on whatever UI field currently has keyboard focus.
        """

        unavailable = self._check_available()

        if unavailable:
            unavailable.action = "clear_current_field"
            return unavailable

        try:
            result = self.select_all()

            if not result.success:
                return result

            if use_delete:
                result = self.delete()
            else:
                result = self.press("backspace")

            if result.success:
                result.action = "clear_current_field"
                result.message = "Current keyboard field cleared."

            return result

        except Exception as exc:
            logger.exception("Could not clear current field.")

            return KeyboardResult(
                success=False,
                action="clear_current_field",
                error=str(exc),
            )

    # =========================================================
    # KEYBOARD SEQUENCES
    # =========================================================

    def execute_sequence(
        self,
        sequence: Iterable[dict],
        delay: Optional[float] = None,
    ) -> KeyboardResult:
        """
        Execute a sequence of keyboard operations.

        Example:

            keyboard.execute_sequence([
                {"action": "type", "text": "Hello"},
                {"action": "press", "key": "enter"},
                {"action": "hotkey", "keys": ["ctrl", "s"]},
            ])
        """

        unavailable = self._check_available()

        if unavailable:
            unavailable.action = "execute_sequence"
            return unavailable

        try:
            actual_delay = (
                self.action_delay
                if delay is None
                else max(0.0, float(delay))
            )

            for item in sequence:
                if not isinstance(item, dict):
                    raise ValueError(
                        "Each sequence item must be a dictionary."
                    )

                action = str(
                    item.get("action", "")
                ).strip().lower()

                if action == "type":
                    result = self.type_text(
                        item.get("text", "")
                    )

                elif action == "press":
                    result = self.press(
                        item.get("key", ""),
                        presses=item.get("presses", 1),
                    )

                elif action == "hotkey":
                    keys = item.get("keys", [])

                    if not isinstance(keys, (list, tuple)):
                        raise ValueError(
                            "'keys' must be a list or tuple."
                        )

                    result = self.hotkey(*keys)

                elif action == "wait":
                    seconds = max(
                        0.0,
                        float(item.get("seconds", 0)),
                    )

                    time.sleep(seconds)

                    result = KeyboardResult(
                        success=True,
                        action="wait",
                        message=f"Waited {seconds:.2f} seconds.",
                    )

                else:
                    raise ValueError(
                        f"Unknown keyboard sequence action: {action}"
                    )

                if not result.success:
                    return KeyboardResult(
                        success=False,
                        action="execute_sequence",
                        error=(
                            f"Sequence failed at "
                            f"action '{action}': "
                            f"{result.error}"
                        ),
                    )

                if actual_delay > 0:
                    time.sleep(actual_delay)

            return KeyboardResult(
                success=True,
                action="execute_sequence",
                message="Keyboard sequence completed.",
            )

        except Exception as exc:
            logger.exception("Keyboard sequence failed.")

            return KeyboardResult(
                success=False,
                action="execute_sequence",
                error=str(exc),
            )

    # =========================================================
    # SPECIAL WINDOWS SHORTCUTS
    # =========================================================

    def show_desktop(self) -> KeyboardResult:
        """Windows+D."""

        return self.hotkey("win", "d")

    def lock_windows(self) -> KeyboardResult:
        """
        Lock Windows using Win+L.

        This changes the user's system state and should normally
        be protected by JarvisOS's decision/permission layer.
        """

        return self.hotkey("win", "l")

    def open_task_manager(self) -> KeyboardResult:
        """Open Windows Task Manager."""

        return self.hotkey(
            "ctrl",
            "shift",
            "esc",
        )

    def switch_window(self) -> KeyboardResult:
        """Alt+Tab."""

        return self.hotkey("alt", "tab")

    def close_active_window(self) -> KeyboardResult:
        """
        Close the active application/window.

        This should normally require confirmation at the
        higher-level decision layer when used by JarvisOS.
        """

        return self.hotkey("alt", "f4")

    # =========================================================
    # TEST
    # =========================================================

    def test(self) -> KeyboardResult:
        """
        Basic availability test.

        Does not type anything or press any key.
        """

        if not self._available:
            return KeyboardResult(
                success=False,
                action="test",
                error="PyAutoGUI is not available.",
            )

        try:
            # Access PyAutoGUI position API as a non-invasive test.
            pyautogui.position()

            return KeyboardResult(
                success=True,
                action="test",
                message="Keyboard control is ready.",
            )

        except Exception as exc:
            logger.exception("Keyboard test failed.")

            return KeyboardResult(
                success=False,
                action="test",
                error=str(exc),
            )


# =============================================================
# SHARED CONTROLLER
# =============================================================

_keyboard_controller: Optional[KeyboardControl] = None


def get_keyboard_controller() -> KeyboardControl:
    """Return the shared KeyboardControl instance."""

    global _keyboard_controller

    if _keyboard_controller is None:
        _keyboard_controller = KeyboardControl()

    return _keyboard_controller


# =============================================================
# CONVENIENCE FUNCTIONS
# =============================================================

def type_text(text: str) -> KeyboardResult:
    """Type text using the shared keyboard controller."""

    return get_keyboard_controller().type_text(text)


def press(key: str, presses: int = 1) -> KeyboardResult:
    """Press a key using the shared keyboard controller."""

    return get_keyboard_controller().press(
        key,
        presses=presses,
    )


def hotkey(*keys: str) -> KeyboardResult:
    """Press a keyboard shortcut."""

    return get_keyboard_controller().hotkey(*keys)


def copy() -> KeyboardResult:
    """Copy selected content."""

    return get_keyboard_controller().copy()


def paste() -> KeyboardResult:
    """Paste clipboard content."""

    return get_keyboard_controller().paste()


def select_all() -> KeyboardResult:
    """Select all content."""

    return get_keyboard_controller().select_all()


# =============================================================
# DIRECT TEST
# =============================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    print("=" * 60)
    print("JarvisOS Keyboard Control Test")
    print("=" * 60)

    keyboard = KeyboardControl()

    print("\nStatus:")
    print(keyboard.get_status())

    print("\nTesting availability...")

    result = keyboard.test()

    print(result.to_dict())

    print("\nNo automatic typing will be performed.")
    print("Keyboard control module is ready.")
