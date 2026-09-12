"""
JarvisOS - Mouse Control
========================

Real Windows mouse controller using PyAutoGUI.

Features:
- Get mouse position
- Move mouse
- Click
- Double click
- Right click
- Middle click
- Mouse down / up
- Drag
- Scroll
- Move to screen edge
- Screen size
- Position checking
- Safe error handling

IMPORTANT:
This module performs real mouse actions.
Higher-level JarvisOS security/decision layers should decide
whether an action is allowed before executing sensitive actions.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional, Tuple

try:
    import pyautogui
except ImportError:
    pyautogui = None


logger = logging.getLogger("JarvisOS.MouseControl")


@dataclass
class MousePosition:
    """Represents a mouse cursor position."""

    x: int
    y: int

    def to_tuple(self) -> Tuple[int, int]:
        return self.x, self.y

    def to_dict(self) -> dict:
        return {
            "x": self.x,
            "y": self.y,
        }


@dataclass
class MouseResult:
    """Result returned by mouse operations."""

    success: bool
    action: str
    message: str = ""
    error: Optional[str] = None
    position: Optional[MousePosition] = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "action": self.action,
            "message": self.message,
            "error": self.error,
            "position": (
                self.position.to_dict()
                if self.position
                else None
            ),
        }


class MouseControl:
    """
    Real mouse controller for JarvisOS.

    Example:

        mouse = MouseControl()

        mouse.move_to(500, 300)
        mouse.click()
        mouse.right_click()
        mouse.scroll(-5)
    """

    BUTTONS = {
        "left": "left",
        "right": "right",
        "middle": "middle",
    }

    def __init__(
        self,
        move_duration: float = 0.2,
        action_delay: float = 0.05,
        fail_safe: bool = True,
    ):
        self.move_duration = max(
            0.0,
            float(move_duration),
        )

        self.action_delay = max(
            0.0,
            float(action_delay),
        )

        self.fail_safe = bool(fail_safe)

        self._available = pyautogui is not None

        if self._available:
            try:
                pyautogui.PAUSE = self.action_delay
                pyautogui.FAILSAFE = self.fail_safe
            except Exception as exc:
                logger.warning(
                    "Could not configure PyAutoGUI: %s",
                    exc,
                )

        logger.info(
            "MouseControl initialized. available=%s",
            self._available,
        )

    # =========================================================
    # STATUS
    # =========================================================

    def is_available(self) -> bool:
        """Return True if PyAutoGUI is available."""

        return self._available

    def get_status(self) -> dict:
        """Return mouse controller status."""

        status = {
            "available": self._available,
            "move_duration": self.move_duration,
            "action_delay": self.action_delay,
            "fail_safe": self.fail_safe,
        }

        if self._available:
            try:
                position = self.get_position()

                if position is not None:
                    status["position"] = position.to_dict()
            except Exception:
                status["position"] = None

        return status

    def _check_available(self) -> Optional[MouseResult]:
        """Check whether mouse control is available."""

        if not self._available:
            return MouseResult(
                success=False,
                action="availability_check",
                error=(
                    "PyAutoGUI is not installed. "
                    "Install it with: pip install pyautogui"
                ),
            )

        return None

    # =========================================================
    # POSITION
    # =========================================================

    def get_position(self) -> Optional[MousePosition]:
        """Return the current mouse position."""

        if not self._available:
            return None

        try:
            point = pyautogui.position()

            return MousePosition(
                x=int(point.x),
                y=int(point.y),
            )

        except Exception as exc:
            logger.exception(
                "Could not get mouse position: %s",
                exc,
            )
            return None

    def position_result(self) -> MouseResult:
        """Return current mouse position as a MouseResult."""

        unavailable = self._check_available()

        if unavailable:
            unavailable.action = "get_position"
            return unavailable

        try:
            position = self.get_position()

            if position is None:
                return MouseResult(
                    success=False,
                    action="get_position",
                    error="Could not determine mouse position.",
                )

            return MouseResult(
                success=True,
                action="get_position",
                message=(
                    f"Mouse position: "
                    f"({position.x}, {position.y})"
                ),
                position=position,
            )

        except Exception as exc:
            logger.exception(
                "Position lookup failed."
            )

            return MouseResult(
                success=False,
                action="get_position",
                error=str(exc),
            )

    # =========================================================
    # SCREEN
    # =========================================================

    def get_screen_size(self) -> Optional[Tuple[int, int]]:
        """Return screen width and height."""

        if not self._available:
            return None

        try:
            width, height = pyautogui.size()

            return int(width), int(height)

        except Exception as exc:
            logger.exception(
                "Could not get screen size: %s",
                exc,
            )
            return None

    def get_screen_size_result(self) -> MouseResult:
        """Return screen size as a MouseResult."""

        unavailable = self._check_available()

        if unavailable:
            unavailable.action = "get_screen_size"
            return unavailable

        try:
            size = self.get_screen_size()

            if size is None:
                return MouseResult(
                    success=False,
                    action="get_screen_size",
                    error="Could not determine screen size.",
                )

            width, height = size

            return MouseResult(
                success=True,
                action="get_screen_size",
                message=(
                    f"Screen size: {width}x{height}"
                ),
            )

        except Exception as exc:
            logger.exception(
                "Screen size lookup failed."
            )

            return MouseResult(
                success=False,
                action="get_screen_size",
                error=str(exc),
            )

    # =========================================================
    # MOVE
    # =========================================================

    def move_to(
        self,
        x: int,
        y: int,
        duration: Optional[float] = None,
    ) -> MouseResult:
        """
        Move mouse to an absolute screen position.

        Example:
            mouse.move_to(500, 300)
        """

        unavailable = self._check_available()

        if unavailable:
            unavailable.action = "move_to"
            return unavailable

        try:
            x = int(x)
            y = int(y)

            actual_duration = (
                self.move_duration
                if duration is None
                else max(0.0, float(duration))
            )

            pyautogui.moveTo(
                x,
                y,
                duration=actual_duration,
            )

            position = MousePosition(x, y)

            return MouseResult(
                success=True,
                action="move_to",
                message=(
                    f"Mouse moved to ({x}, {y})."
                ),
                position=position,
            )

        except Exception as exc:
            logger.exception(
                "Mouse move failed."
            )

            return MouseResult(
                success=False,
                action="move_to",
                error=str(exc),
            )

    def move_relative(
        self,
        x: int,
        y: int,
        duration: Optional[float] = None,
    ) -> MouseResult:
        """
        Move mouse relative to current position.

        Example:
            mouse.move_relative(100, 50)
        """

        unavailable = self._check_available()

        if unavailable:
            unavailable.action = "move_relative"
            return unavailable

        try:
            x = int(x)
            y = int(y)

            actual_duration = (
                self.move_duration
                if duration is None
                else max(0.0, float(duration))
            )

            pyautogui.moveRel(
                x,
                y,
                duration=actual_duration,
            )

            position = self.get_position()

            return MouseResult(
                success=True,
                action="move_relative",
                message=(
                    f"Mouse moved by ({x}, {y})."
                ),
                position=position,
            )

        except Exception as exc:
            logger.exception(
                "Relative mouse move failed."
            )

            return MouseResult(
                success=False,
                action="move_relative",
                error=str(exc),
            )

    # =========================================================
    # CLICK
    # =========================================================

    def click(
        self,
        x: Optional[int] = None,
        y: Optional[int] = None,
        button: str = "left",
        clicks: int = 1,
        interval: float = 0.1,
    ) -> MouseResult:
        """
        Click the mouse.

        If x/y are provided, the cursor moves there first.

        Examples:
            mouse.click()
            mouse.click(500, 300)
            mouse.click(button="right")
        """

        unavailable = self._check_available()

        if unavailable:
            unavailable.action = "click"
            return unavailable

        try:
            button = str(button).strip().lower()

            if button not in self.BUTTONS:
                raise ValueError(
                    "button must be left, right or middle."
                )

            clicks = int(clicks)

            if clicks < 1:
                raise ValueError(
                    "clicks must be at least 1."
                )

            if x is not None or y is not None:
                if x is None or y is None:
                    raise ValueError(
                        "Both x and y must be provided together."
                    )

                x = int(x)
                y = int(y)

                pyautogui.moveTo(
                    x,
                    y,
                    duration=self.move_duration,
                )

            pyautogui.click(
                button=button,
                clicks=clicks,
                interval=max(0.0, float(interval)),
            )

            position = self.get_position()

            return MouseResult(
                success=True,
                action="click",
                message=(
                    f"{button} click completed "
                    f"({clicks} click(s))."
                ),
                position=position,
            )

        except Exception as exc:
            logger.exception(
                "Mouse click failed."
            )

            return MouseResult(
                success=False,
                action="click",
                error=str(exc),
            )

    def left_click(
        self,
        x: Optional[int] = None,
        y: Optional[int] = None,
    ) -> MouseResult:
        """Perform a left click."""

        return self.click(
            x=x,
            y=y,
            button="left",
        )

    def right_click(
        self,
        x: Optional[int] = None,
        y: Optional[int] = None,
    ) -> MouseResult:
        """Perform a right click."""

        return self.click(
            x=x,
            y=y,
            button="right",
        )

    def middle_click(
        self,
        x: Optional[int] = None,
        y: Optional[int] = None,
    ) -> MouseResult:
        """Perform a middle click."""

        return self.click(
            x=x,
            y=y,
            button="middle",
        )

    def double_click(
        self,
        x: Optional[int] = None,
        y: Optional[int] = None,
    ) -> MouseResult:
        """Perform a double left click."""

        return self.click(
            x=x,
            y=y,
            button="left",
            clicks=2,
            interval=0.1,
        )

    # =========================================================
    # MOUSE BUTTON HOLD
    # =========================================================

    def button_down(
        self,
        button: str = "left",
    ) -> MouseResult:
        """Hold a mouse button down."""

        unavailable = self._check_available()

        if unavailable:
            unavailable.action = "button_down"
            return unavailable

        try:
            button = str(button).strip().lower()

            if button not in self.BUTTONS:
                raise ValueError(
                    "button must be left, right or middle."
                )

            pyautogui.mouseDown(button=button)

            return MouseResult(
                success=True,
                action="button_down",
                message=(
                    f"{button} mouse button pressed down."
                ),
                position=self.get_position(),
            )

        except Exception as exc:
            logger.exception(
                "Mouse button down failed."
            )

            return MouseResult(
                success=False,
                action="button_down",
                error=str(exc),
            )

    def button_up(
        self,
        button: str = "left",
    ) -> MouseResult:
        """Release a mouse button."""

        unavailable = self._check_available()

        if unavailable:
            unavailable.action = "button_up"
            return unavailable

        try:
            button = str(button).strip().lower()

            if button not in self.BUTTONS:
                raise ValueError(
                    "button must be left, right or middle."
                )

            pyautogui.mouseUp(button=button)

            return MouseResult(
                success=True,
                action="button_up",
                message=(
                    f"{button} mouse button released."
                ),
                position=self.get_position(),
            )

        except Exception as exc:
            logger.exception(
                "Mouse button up failed."
            )

            return MouseResult(
                success=False,
                action="button_up",
                error=str(exc),
            )

    # =========================================================
    # DRAG
    # =========================================================

    def drag_to(
        self,
        x: int,
        y: int,
        duration: Optional[float] = None,
        button: str = "left",
    ) -> MouseResult:
        """
        Drag from current mouse position to x/y.

        Example:
            mouse.drag_to(800, 500)
        """

        unavailable = self._check_available()

        if unavailable:
            unavailable.action = "drag_to"
            return unavailable

        try:
            button = str(button).strip().lower()

            if button not in self.BUTTONS:
                raise ValueError(
                    "button must be left, right or middle."
                )

            x = int(x)
            y = int(y)

            actual_duration = (
                self.move_duration
                if duration is None
                else max(0.0, float(duration))
            )

            pyautogui.dragTo(
                x,
                y,
                duration=actual_duration,
                button=button,
            )

            position = MousePosition(x, y)

            return MouseResult(
                success=True,
                action="drag_to",
                message=(
                    f"Mouse dragged to ({x}, {y})."
                ),
                position=position,
            )

        except Exception as exc:
            logger.exception(
                "Mouse drag failed."
            )

            return MouseResult(
                success=False,
                action="drag_to",
                error=str(exc),
            )

    def drag_relative(
        self,
        x: int,
        y: int,
        duration: Optional[float] = None,
        button: str = "left",
    ) -> MouseResult:
        """Drag relative to current mouse position."""

        unavailable = self._check_available()

        if unavailable:
            unavailable.action = "drag_relative"
            return unavailable

        try:
            button = str(button).strip().lower()

            if button not in self.BUTTONS:
                raise ValueError(
                    "button must be left, right or middle."
                )

            actual_duration = (
                self.move_duration
                if duration is None
                else max(0.0, float(duration))
            )

            pyautogui.dragRel(
                int(x),
                int(y),
                duration=actual_duration,
                button=button,
            )

            return MouseResult(
                success=True,
                action="drag_relative",
                message=(
                    f"Mouse dragged by ({x}, {y})."
                ),
                position=self.get_position(),
            )

        except Exception as exc:
            logger.exception(
                "Relative mouse drag failed."
            )

            return MouseResult(
                success=False,
                action="drag_relative",
                error=str(exc),
            )

    # =========================================================
    # SCROLL
    # =========================================================

    def scroll(
        self,
        amount: int,
        x: Optional[int] = None,
        y: Optional[int] = None,
    ) -> MouseResult:
        """
        Scroll the mouse wheel.

        Positive amount = scroll up.
        Negative amount = scroll down.

        Example:
            mouse.scroll(5)
            mouse.scroll(-5)
        """

        unavailable = self._check_available()

        if unavailable:
            unavailable.action = "scroll"
            return unavailable

        try:
            amount = int(amount)

            if x is not None or y is not None:
                if x is None or y is None:
                    raise ValueError(
                        "Both x and y must be provided together."
                    )

                pyautogui.moveTo(
                    int(x),
                    int(y),
                    duration=self.move_duration,
                )

            pyautogui.scroll(amount)

            return MouseResult(
                success=True,
                action="scroll",
                message=(
                    f"Scrolled {amount} step(s)."
                ),
                position=self.get_position(),
            )

        except Exception as exc:
            logger.exception(
                "Mouse scroll failed."
            )

            return MouseResult(
                success=False,
                action="scroll",
                error=str(exc),
            )

    def scroll_up(self, amount: int = 5) -> MouseResult:
        """Scroll upward."""

        amount = abs(int(amount))

        return self.scroll(amount)

    def scroll_down(self, amount: int = 5) -> MouseResult:
        """Scroll downward."""

        amount = -abs(int(amount))

        return self.scroll(amount)

    # =========================================================
    # MOVE TO SCREEN EDGES
    # =========================================================

    def move_to_center(
        self,
        duration: Optional[float] = None,
    ) -> MouseResult:
        """Move mouse to the center of the primary screen."""

        unavailable = self._check_available()

        if unavailable:
            unavailable.action = "move_to_center"
            return unavailable

        try:
            size = self.get_screen_size()

            if size is None:
                return MouseResult(
                    success=False,
                    action="move_to_center",
                    error="Could not determine screen size.",
                )

            width, height = size

            return self.move_to(
                width // 2,
                height // 2,
                duration=duration,
            )

        except Exception as exc:
            logger.exception(
                "Could not move mouse to center."
            )

            return MouseResult(
                success=False,
                action="move_to_center",
                error=str(exc),
            )

    def move_to_top_left(self) -> MouseResult:
        """Move mouse to the top-left corner."""

        return self.move_to(0, 0)

    def move_to_top_right(self) -> MouseResult:
        """Move mouse to the top-right corner."""

        size = self.get_screen_size()

        if size is None:
            return MouseResult(
                success=False,
                action="move_to_top_right",
                error="Could not determine screen size.",
            )

        width, _ = size

        return self.move_to(
            width - 1,
            0,
        )

    def move_to_bottom_left(self) -> MouseResult:
        """Move mouse to the bottom-left corner."""

        size = self.get_screen_size()

        if size is None:
            return MouseResult(
                success=False,
                action="move_to_bottom_left",
                error="Could not determine screen size.",
            )

        _, height = size

        return self.move_to(
            0,
            height - 1,
        )

    def move_to_bottom_right(self) -> MouseResult:
        """Move mouse to the bottom-right corner."""

        size = self.get_screen_size()

        if size is None:
            return MouseResult(
                success=False,
                action="move_to_bottom_right",
                error="Could not determine screen size.",
            )

        width, height = size

        return self.move_to(
            width - 1,
            height - 1,
        )

    # =========================================================
    # SAFE TEST
    # =========================================================

    def test(self) -> MouseResult:
        """
        Non-invasive mouse controller test.

        It only reads the cursor position and screen size.
        It does NOT click or move the mouse.
        """

        unavailable = self._check_available()

        if unavailable:
            unavailable.action = "test"
            return unavailable

        try:
            position = self.get_position()
            size = self.get_screen_size()

            if position is None:
                raise RuntimeError(
                    "Could not read mouse position."
                )

            if size is None:
                raise RuntimeError(
                    "Could not read screen size."
                )

            width, height = size

            return MouseResult(
                success=True,
                action="test",
                message=(
                    f"Mouse control ready. "
                    f"Position=({position.x}, {position.y}), "
                    f"Screen={width}x{height}."
                ),
                position=position,
            )

        except Exception as exc:
            logger.exception(
                "Mouse test failed."
            )

            return MouseResult(
                success=False,
                action="test",
                error=str(exc),
            )

    # =========================================================
    # CLOSE
    # =========================================================

    def close(self) -> None:
        """Release controller resources."""

        logger.info("MouseControl closed.")

    def __enter__(self) -> "MouseControl":
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        self.close()


# =============================================================
# SHARED CONTROLLER
# =============================================================

_mouse_controller: Optional[MouseControl] = None


def get_mouse_controller() -> MouseControl:
    """Return the shared MouseControl instance."""

    global _mouse_controller

    if _mouse_controller is None:
        _mouse_controller = MouseControl()

    return _mouse_controller


# =============================================================
# CONVENIENCE FUNCTIONS
# =============================================================

def move_to(
    x: int,
    y: int,
) -> MouseResult:
    """Move mouse to an absolute position."""

    return get_mouse_controller().move_to(x, y)


def click(
    x: Optional[int] = None,
    y: Optional[int] = None,
    button: str = "left",
) -> MouseResult:
    """Click the mouse."""

    return get_mouse_controller().click(
        x=x,
        y=y,
        button=button,
    )


def double_click(
    x: Optional[int] = None,
    y: Optional[int] = None,
) -> MouseResult:
    """Double-click."""

    return get_mouse_controller().double_click(
        x=x,
        y=y,
    )


def right_click(
    x: Optional[int] = None,
    y: Optional[int] = None,
) -> MouseResult:
    """Right-click."""

    return get_mouse_controller().right_click(
        x=x,
        y=y,
    )


def scroll(amount: int) -> MouseResult:
    """Scroll mouse wheel."""

    return get_mouse_controller().scroll(amount)


def get_position() -> Optional[MousePosition]:
    """Get current mouse position."""

    return get_mouse_controller().get_position()


# =============================================================
# DIRECT TEST
# =============================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    print("=" * 60)
    print("JarvisOS Mouse Control Test")
    print("=" * 60)

    mouse = MouseControl()

    print("\nStatus:")
    print(mouse.get_status())

    print("\nRunning safe test...")

    result = mouse.test()

    print(result.to_dict())

    print("\nNo automatic mouse movement or clicking performed.")
    print("Mouse control module is ready.")
